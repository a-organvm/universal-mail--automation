#!/usr/bin/env python3
"""gmail_imap_sweep.py — archive Gmail noise by REMOVING the INBOX label over raw IMAP.

WHY this exists: Apple Mail cannot archive a Gmail *label* store. A "move to All Mail"
is a no-op on the INBOX label (every message is already in All Mail), so Gmail re-asserts
INBOX on the next sync — VERIFIED 2026-06-22: after Apple Mail reported archived=18, the
threads still carried INBOX on Google's servers. Raw IMAP CAN archive: the Gmail
X-GM-LABELS extension lets us drop the ``\\Inbox`` label, a TRUE archive that sticks
(providers/imap.py::archive -> remove_label(uid, "\\Inbox"), success only on a server OK).

This reuses the EXACT SAME classifier as inbox_sweep.py (core.rules + decide), so the
fail-closed protected-sender gate and the local allowlist
(config/protected_senders.local.txt: lemonsqueezy/santander/accessgrantedsystems/givingdata)
hold identically — the dry-run classification already verified on the Apple-Mail path
carries over unchanged.

Reversible: archive drops ONLY the INBOX label; every thread stays in All Mail, and the
JSON receipt records uid/sender/subject of everything touched = the exact undo manifest.
Fires are flagged (a status bit). NEVER deletes, NEVER sends. Dry-run by default; --apply
executes.

Auth (keyless after one setup): IMAP_USER + a Gmail APP PASSWORD via IMAP_PASS or a
1Password item (OP_ACCOUNT/OP_ITEM/OP_FIELD). An app password is required — OAuth/Apple-
Mail tokens cannot do a raw IMAP LOGIN.
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.imap import IMAPProvider          # noqa: E402
from core.rules import categorize_with_tier, is_protected_sender  # noqa: E402
from inbox_sweep import decide                    # noqa: E402  (same verified classifier)


def classify(provider, mailbox, limit):
    """List the mailbox and classify each message with the shared rules engine."""
    res = provider.list_messages(query="ALL", limit=limit, mailbox=mailbox)
    rows = []
    for m in res.messages:
        d = provider.get_message_details(m.id)
        if d is None:
            continue
        sender, subject = d.sender or "", d.subject or ""
        protected = is_protected_sender(sender)
        cat = categorize_with_tier(sender, subject)
        rows.append({
            "uid": m.id, "sender": sender, "subject": subject,
            "label": cat.label, "tier": cat.tier, "protected": protected,
            "is_starred": d.is_starred,
            "action": decide(sender, subject, cat.tier, protected),
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Gmail IMAP sweep — archive noise by dropping the INBOX label (dry run by default).")
    ap.add_argument("--user", default=os.getenv("IMAP_USER", "padavano.anthony@gmail.com"))
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--mailbox", default="INBOX")
    ap.add_argument("--apply", action="store_true",
                    help="actually flag/archive (default: dry run, no changes)")
    ap.add_argument("--receipt", default=None, help="path to write the JSON receipt / undo manifest")
    args = ap.parse_args(argv)

    provider = IMAPProvider(user=args.user, use_gmail_extensions=True)
    provider.connect()
    try:
        rows = classify(provider, args.mailbox, args.limit)
        acts = Counter(r["action"] for r in rows)
        print(f"=== {args.user}  {args.mailbox}  — {len(rows)} messages ===")
        print(f"  FIRE(flag)={acts['fire']}   KEEP(leave)={acts['keep']}   "
              f"ARCHIVE(drop INBOX)={acts['archive']}")
        for r in [x for x in rows if x["action"] == "archive"][:25]:
            print(f"    archive  {r['sender'][:30]:30} | {r['subject'][:46]}")

        result = {"user": args.user, "mailbox": args.mailbox, "total": len(rows),
                  "mode": "apply" if args.apply else "dry_run", "rows": rows}
        if args.apply:
            flagged = archived = ferr = aerr = 0
            for r in rows:
                if r["action"] == "fire" and not r["is_starred"]:
                    if provider.star(r["uid"]):
                        flagged += 1
                    else:
                        ferr += 1
                elif r["action"] == "archive":
                    if provider.archive(r["uid"]):
                        archived += 1
                        r["archived"] = True
                    else:
                        aerr += 1
                        r["archived"] = False
            result.update(flagged=flagged, archived=archived,
                          flag_errors=ferr, archive_errors=aerr)
            print(f"  APPLIED: flagged={flagged}  archived={archived}  "
                  f"(errors: flag={ferr} archive={aerr})")
        else:
            print("  DRY RUN — no changes. Re-run with --apply to execute.")

        receipt = args.receipt or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "audit",
            f"imap_sweep-{args.user.replace('@', '_at_')}.json")
        os.makedirs(os.path.dirname(receipt), exist_ok=True)
        with open(receipt, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"  receipt → {receipt}")
        return 0
    finally:
        provider.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
