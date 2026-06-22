#!/usr/bin/env python3
"""
inbox_sweep.py — Phase-0 inbox triage for Apple Mail (all accounts, no cloud creds).

Why: the claude.ai Gmail MCP connector is read-only and the Gmail-API path needs `op`
(not signed in). Apple Mail holds every account authenticated and is AppleScript-
drivable, so it's the cheapest working apply lane. Reuses the vetted classifier +
protected-sender gate from core.rules and the MailAppProvider primitives.

The coarse Eisenhower tier alone over-flags (treats every Apple receipt / GitHub
usage notice / FICO update as a "fire"). So on top of the tier we apply an
ACTION-vs-NOISE refinement so only genuine action items + real humans + gov/legal
stay surfaced; receipts / marketing / usage-FYI are archived even from big-brand
domains. Three outcomes:

    FIRE    -> flag + keep in inbox (+ goes to the obligations ledger)   [surfaced]
    KEEP    -> leave in inbox untouched (protected, ambiguous)           [safe]
    ARCHIVE -> mark read + move to <noise mailbox>                       [noise out]

DRY RUN by default. --apply to act. Nothing deleted; noise → one reversible mailbox.
Fail-open: a single message error never aborts the sweep. Writes a JSON receipt.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.mailapp import MailAppProvider  # noqa: E402
from core.rules import categorize_with_tier, is_protected_sender  # noqa: E402

NOISE_MAILBOX_DEFAULT = "AI-Triaged"

# A genuine, consequential action is required.
ACTION_SIGNALS = re.compile(r"""(?ix)
    default | garnish | wage | unsuccessful | declined | past\s*due | overdue |
    suspend | paused | (problem\s*billing) | (billing\s*problem) | underpayment |
    outstanding | (action\s*required) | (immediate\s*action) | fraud | unauthorized |
    unrecognized | (confirm\s*you) | (did\s*you\s*make) | (verify\s*(your|it|these)) |
    (fsa\s*id) | (was\s*changed) | (prevent\s*wage) | (take\s*action) | (final\s*reminder) |
    (last\s*chance\s*to\s*stay) | constituent | mediat | docusign | (deletion\s*notice) |
    expiring | (expire\s*soon) | disconnected | (security\s*alert) | suspicious | locked |
    (past[-\s]*due) | reinstate | (resign) | compliant | consent\s*form | zoom\s*link
""")

# Receipts / marketing / usage-FYI — archive even from protected big brands (reversible).
NOISE_SIGNALS = re.compile(r"""(?ix)
    receipt | (your\s*order) | ordered | (order\s*\#) | delivered | shipped | tracking |
    (out\s*for\s*delivery) | (review\s*your) | (how\s*was) | (rate\s*your) | feedback |
    survey | fico | loyalty | (\d+%\s*off) | (off\s*your) | \bsale\b | \bdeal\b | newsletter |
    digest | changelog | webinar | (offer\s*inside) | (\$\d+\s*off) | testflight |
    (data\s*is\s*ready) | takeout | (used\s*\d+%) | (scheduled\s*tasks) | (back\s*in\s*stock) |
    (new\s*groups) | celebrate | \bgifts?\b | introducing | (early\s*bird) | promotion |
    (week(ly)?\s*(performance|financial)) | (monthly\s*(account\s*)?statement) | (dive\s*deeper)
""")

ROLE_LOCALPARTS = ("noreply", "no-reply", "donotreply", "do-not-reply", "notification",
                   "notifications", "alert", "alerts", "support", "info", "hello", "team",
                   "deals", "news", "marketing", "auto", "mailer", "updates", "account",
                   "billing", "service", "services", "member", "reply", "sales", "contact",
                   "admin", "shop", "express", "store", "order", "payments", "securityalert")

# Brand/dept/ESP tokens — if any appear in the FULL address (local+domain) the sender
# is a role mailbox, not a person (e.g. dxl@reviews.dxl.com, questfeedback@…, invoice+…).
ROLE_TOKENS = ROLE_LOCALPARTS + (
    "reviews", "feedback", "survey", "invoice", "statement", "medallia", "mystore",
    "satisfaction", "notify", "campaign", "questfeedback", "customersat", "mailchimp")

IMPORTANT_DOMAINS = ("studentaid.gov", ".gov", "legalzoom.com", "docusign", "irs.gov",
                     "ssa.gov", "court", "nysenate", "nysenate.gov")


def _addr(sender):
    return (sender.split("<")[-1].rstrip(">").strip().lower()
            if "<" in sender else sender.strip().lower())


def looks_human(sender):
    addr = _addr(sender)
    if any(k in addr for k in ROLE_TOKENS):
        return False
    name = sender.split("<")[0].strip().strip('"')
    parts = [p for p in re.split(r"\s+", name) if p]
    brandish = any(b in name.lower() for b in
                   ("via", "inc", "llc", "bank", "card", "health", "pharmacy",
                    "deals", "store", "cinema", "finance", "co.", "labs", "group",
                    "diagnostics", "edison", "platform", "pbc", "big +"))
    return (len(parts) >= 2 and not name.isupper() and "@" not in name and not brandish)


def important_sender(sender):
    addr = _addr(sender)
    return any(d in addr for d in IMPORTANT_DOMAINS)


def decide(sender, subject, tier, protected):
    """Return 'fire' | 'keep' | 'archive'."""
    text = f"{subject}"
    if ACTION_SIGNALS.search(text) or looks_human(sender) or important_sender(sender):
        return "fire"
    if protected:
        return "keep"          # HARD fail-closed never-archive gate: a protected sender is
                               # NEVER archived, even if its subject trips a noise word. (The
                               # fire check above still lets a genuine action surface first.)
                               # Must precede NOISE_SIGNALS — else the gate is fail-OPEN.
    if NOISE_SIGNALS.search(text):
        return "archive"
    if tier <= 2:
        return "keep"
    return "archive"


def classify_inbox(provider, inbox_name, limit):
    rows, page_token, fetched = [], None, 0
    while fetched < limit:
        res = provider.list_messages(query="", limit=min(limit - fetched, 50),
                                     page_token=page_token, mailbox=inbox_name)
        if not res.messages:
            break
        for m in res.messages:
            sender, subject = m.sender or "", m.subject or ""
            protected = is_protected_sender(sender)
            cat = categorize_with_tier(sender, subject)
            rows.append({
                "id": m.id, "sender": sender, "subject": subject,
                "is_read": m.is_read, "is_flagged": m.is_starred,
                "label": cat.label, "tier": cat.tier, "protected": protected,
                "action": decide(sender, subject, cat.tier, protected),
            })
        fetched += len(res.messages)
        page_token = res.next_page_token
        if not page_token:
            break
    return rows


def report(account, inbox_name, rows):
    acts = Counter(r["action"] for r in rows)
    print(f"\n=== {account}  (mailbox: {inbox_name})  — {len(rows)} messages ===")
    print(f"  plan : FIRE(flag+keep)={acts['fire']}   KEEP(leave)={acts['keep']}   "
          f"ARCHIVE→noise={acts['archive']}")
    fires = [r for r in rows if r["action"] == "fire"]
    print(f"\n  --- FIRES → flag + keep in inbox + ledger ({len(fires)}) ---")
    for r in fires:
        print(f"    [{r['label'][:18]:18}] {r['sender'][:34]:34}  {r['subject'][:50]}")
    keep = [r for r in rows if r["action"] == "keep"]
    if keep:
        print(f"\n  --- KEEP (left in inbox, unflagged) ({len(keep)}) ---")
        for r in keep[:15]:
            print(f"    [{r['label'][:14]:14}] {r['sender'][:30]:30} {r['subject'][:42]}")
        if len(keep) > 15:
            print(f"    … +{len(keep) - 15} more")
    noise = [r for r in rows if r["action"] == "archive"]
    print(f"\n  --- ARCHIVE → '{NOISE_MAILBOX_DEFAULT}' ({len(noise)}), sample ---")
    for r in noise[:20]:
        print(f"    [{r['label'][:14]:14}] {r['sender'][:28]:28} {r['subject'][:40]}")
    if len(noise) > 20:
        print(f"    … +{len(noise) - 20} more")


def _osa(script, timeout=900):
    r = subprocess.run(["osascript", "-e", script], capture_output=True,
                       text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _account_is_gmail(account):
    """Gmail accounts expose an 'All Mail' archive mailbox; folder stores don't."""
    _, out, _ = _osa(f'''tell application "Mail"
      set acc to account "{account}"
      repeat with mb in (every mailbox of acc)
        if name of mb is "All Mail" then return "yes"
      end repeat
      return "no"
    end tell''', timeout=120)
    return out.strip() == "yes"


GMAIL_BATCH = 10          # archive this many per sync cycle
GMAIL_SETTLE = 20         # seconds to let each batch commit server-side


def _flag_fires(account, inbox, fire_ids):
    """Flag fires in one pass. Flagging is a status bit, not a label-move, so Gmail
    respects it immediately and reliably (no revert)."""
    if not fire_ids:
        return 0, 0
    flist = "{" + ", ".join(fire_ids) + "}"
    _, out, _ = _osa(f'''tell application "Mail"
      set mb to mailbox "{inbox}" of account "{account}"
      set fc to 0
      set ec to 0
      repeat with anId in {flist}
        try
          set flagged status of (first message of mb whose id is (anId as integer)) to true
          set fc to fc + 1
        on error
          set ec to ec + 1
        end try
      end repeat
      return (fc as string) & "," & (ec as string)
    end tell''', timeout=300)
    try:
        fc, ec = (int(x) for x in out.split(","))
    except ValueError:
        fc, ec = 0, 0
    return fc, ec


def _archive_folder(account, inbox, arch_ids, noise_mailbox):
    """Folder store (iCloud/IMAP): a single move out of INBOX archives. Sticks."""
    if not arch_ids:
        return 0, 0
    _osa(f'''tell application "Mail"
      try
        set mb to mailbox "{noise_mailbox}" of account "{account}"
      on error
        make new mailbox at end of mailboxes of account "{account}" with properties {{name:"{noise_mailbox}"}}
      end try
    end tell''', timeout=60)
    alist = "{" + ", ".join(arch_ids) + "}"
    _, out, _ = _osa(f'''tell application "Mail"
      set mb to mailbox "{inbox}" of account "{account}"
      set noiseMb to mailbox "{noise_mailbox}" of account "{account}"
      set mc to 0
      set ec to 0
      repeat with anId in {alist}
        try
          set m to (first message of mb whose id is (anId as integer))
          set read status of m to true
          move m to noiseMb
          set mc to mc + 1
        on error
          set ec to ec + 1
        end try
      end repeat
      return (mc as string) & "," & (ec as string)
    end tell''', timeout=900)
    try:
        mc, ec = (int(x) for x in out.split(","))
    except ValueError:
        mc, ec = 0, 0
    return mc, ec


def _archive_gmail(account, inbox, arch_ids):
    """Gmail: mailboxes are LABELS, not folders. A bulk move to a noise mailbox/All Mail
    is optimistically applied locally then REVERTED on the next server sync (the INBOX
    label re-asserts). The reliable gesture is to archive DIRECTLY to 'All Mail' (Gmail's
    archive = drop the INBOX label) in SMALL batches, calling `synchronize` and settling
    after each so every batch commits server-side before the next. Proven to stick where
    the bulk move did not. Reversible: archived mail lives in All Mail and the JSON receipt
    is the exact undo manifest (sender/subject/id of everything moved)."""
    want = {int(i) for i in arch_ids}
    if not want:
        return 0, 0
    script = f'''tell application "Mail"
      set acc to account "{account}"
      set amBox to missing value
      repeat with b in (every mailbox of acc)
        if name of b is "All Mail" then
          set amBox to b
          exit repeat
        end if
      end repeat
      if amBox is missing value then return "0,0"
      set inb to mailbox "{inbox}" of account "{account}"
      set targetIds to {{{", ".join(str(i) for i in want)}}}
      set mc to 0
      set ec to 0
      set iter to 0
      repeat
        set iter to iter + 1
        if iter > 40 then exit repeat
        set inboxIds to (id of every message of inb)
        set todo to {{}}
        repeat with t in targetIds
          if inboxIds contains (t as integer) then set end of todo to (t as integer)
        end repeat
        if (count of todo) is 0 then exit repeat
        set n to 0
        repeat with aid in todo
          if n ≥ {GMAIL_BATCH} then exit repeat
          try
            move (first message of inb whose id is (aid as integer)) to amBox
            set n to n + 1
            set mc to mc + 1
          on error
            set ec to ec + 1
          end try
        end repeat
        synchronize with acc
        delay {GMAIL_SETTLE}
      end repeat
      return (mc as string) & "," & (ec as string)
    end tell'''
    # Generous timeout: up to ~40 sync cycles of GMAIL_SETTLE seconds each.
    _, out, _ = _osa(script, timeout=max(900, 40 * (GMAIL_SETTLE + 5)))
    try:
        mc, ec = (int(x) for x in out.split(","))
    except ValueError:
        mc, ec = 0, 0
    return mc, ec


def apply(account, inbox, rows, noise_mailbox, flag_only_gmail=False):
    """Flag the fires (surface obligations) and archive the noise out of the inbox,
    reversibly. Branches by store type: Gmail (label store) archives directly to All
    Mail in synced small batches that actually stick; iCloud/IMAP (folder store) use a
    single move to the reversible noise mailbox. Fires are flagged in place either way.

    flag_only_gmail: for the autonomic heartbeat — skip the heavy/futile Gmail bulk-archive
    loop (Gmail archive is currently gated on a write door, L-MCP/L-OAUTH/L-IMAP-APP-PW) but
    STILL flag the Gmail fires (reliable status bit) and STILL archive folder stores
    (iCloud/Outlook, reliable). Keeps the beat bounded and fast without ever dead-stopping."""
    fire_ids = [str(r["id"]) for r in rows if r["action"] == "fire" and not r["is_flagged"]]
    arch_ids = [str(r["id"]) for r in rows if r["action"] == "archive"]
    is_gmail = _account_is_gmail(account)

    fc, fe = _flag_fires(account, inbox, fire_ids)
    if is_gmail:
        mc, me = (0, 0) if flag_only_gmail else _archive_gmail(account, inbox, arch_ids)
    else:
        mc, me = _archive_folder(account, inbox, arch_ids, noise_mailbox)

    return {"flag_requested": len(fire_ids), "archive_requested": len(arch_ids),
            "is_gmail": is_gmail, "flag_only_gmail": flag_only_gmail,
            "flagged": fc, "archived": mc, "errors": fe + me,
            "applescript": f"flagged={fc} archived={mc} err={fe + me}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase-0 Apple Mail inbox sweep (dry run by default).")
    ap.add_argument("--account", required=True)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--apply", action="store_true", help="actually flag/move (default: dry run)")
    ap.add_argument("--flag-only-gmail", action="store_true",
                    help="autonomic mode: flag Gmail fires + archive folder stores, but skip the "
                         "heavy/futile Gmail bulk-archive loop (gated on a write door)")
    ap.add_argument("--noise-mailbox", default=NOISE_MAILBOX_DEFAULT)
    ap.add_argument("--receipt", default=None, help="path to write JSON receipt of all decisions")
    args = ap.parse_args(argv)

    provider = MailAppProvider(account=args.account)
    provider.connect()
    inbox = pick_inbox_name(provider)
    rows = classify_inbox(provider, inbox, args.limit)
    report(args.account, inbox, rows)

    result = {"account": args.account, "inbox": inbox, "total": len(rows),
              "mode": "apply" if args.apply else "dry_run"}
    if args.apply:
        n = sum(1 for r in rows if r["action"] == "archive")
        mode = "flag-only-gmail" if args.flag_only_gmail else "full"
        print(f"\n  APPLYING [{mode}] (flag fires; move {n} noise → '{args.noise_mailbox}')…")
        result.update(apply(args.account, inbox, rows, args.noise_mailbox,
                            flag_only_gmail=args.flag_only_gmail))
        print(f"  done: {result}")
    else:
        print("\n  DRY RUN — no changes. Re-run with --apply to execute.")

    receipt = args.receipt or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "audit",
        f"inbox_sweep-{args.account.replace('@', '_at_')}.json")
    os.makedirs(os.path.dirname(receipt), exist_ok=True)
    with open(receipt, "w") as f:
        json.dump({"result": result, "rows": rows}, f, indent=2)
    print(f"  receipt → {receipt}")
    return 0


def pick_inbox_name(provider):
    try:
        boxes = provider.get_mailboxes()
    except Exception:
        boxes = []
    for cand in ("INBOX", "Inbox"):
        if cand in boxes:
            return cand
    for b in boxes:
        if "inbox" in b.lower():
            return b
    return "INBOX"


if __name__ == "__main__":
    raise SystemExit(main())
