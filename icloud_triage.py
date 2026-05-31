#!/usr/bin/env python3
"""
iCloud (and generic IMAP) inbox triage — label-by-category + ARCHIVE (move to
Archive), with the canonical fail-closed protected-sender gate from core.rules.

Unlike Gmail (label removal) or imap_rules.py (label/COPY only), iCloud archive
is a real folder MOVE: INBOX -> Archive. A protected sender is NEVER moved.

Auth: reads ICLOUD_IMAP_HOST/USER/PASS (falls back to bare IMAP_HOST/USER/PASS),
sourced from ~/.config/op/mail_automation.env.op.sh in the user's op-unlocked shell.

DRY RUN by default (no changes). Pass --apply to actually MOVE archivable noise.
Safety policy for archive eligibility (all must hold):
  - sender is NOT protected (core.rules.is_protected_sender -> False), AND
  - category is a positively-identified non-keep label (should_keep_in_inbox False), AND
  - category is NOT the 'Misc/Other' catch-all (uncategorized stays in inbox).
"""
import argparse
import email
import imaplib
import os
import ssl
import sys
from collections import defaultdict
from email.header import decode_header

# Make core.* importable regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.rules import (  # noqa: E402
    categorize_from_strings,
    is_protected_sender,
    normalize_sender,
    should_keep_in_inbox,
)

CATCH_ALL = "Misc/Other"


def decode_str(s: str) -> str:
    parts = []
    for text, enc in decode_header(s or ""):
        if isinstance(text, bytes):
            parts.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            parts.append(text)
    return " ".join(parts)


def connect(host: str, user: str, password: str) -> imaplib.IMAP4_SSL:  # allow-secret (param name, no literal)
    imap = imaplib.IMAP4_SSL(host, ssl_context=ssl.create_default_context())
    imap.login(user, password)
    return imap


def fetch_from_subject(imap: imaplib.IMAP4_SSL, uid: str):
    res, data = imap.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
    if res != "OK" or not data or data[0] is None:
        return "", ""
    msg = email.message_from_bytes(data[0][1])
    return decode_str(msg.get("From", "")), decode_str(msg.get("Subject", ""))


def archive_uid(imap: imaplib.IMAP4_SSL, uid: str, archive_mailbox: str) -> bool:
    """Move a message INBOX -> archive_mailbox. Prefer UID MOVE (RFC 6851);
    fall back to COPY + \\Deleted + EXPUNGE if MOVE is unsupported."""
    try:
        res, _ = imap.uid("MOVE", uid, f'"{archive_mailbox}"')
        if res == "OK":
            return True
    except imaplib.IMAP4.error:
        pass
    res, _ = imap.uid("COPY", uid, f'"{archive_mailbox}"')
    if res != "OK":
        return False
    imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
    imap.expunge()
    return True


def main():
    ap = argparse.ArgumentParser(description="iCloud/IMAP triage with protected gate + archive.")
    ap.add_argument("--mailbox", default="INBOX", help="source mailbox (default INBOX)")
    ap.add_argument("--archive-mailbox", default="Archive", help="archive destination (default Archive)")
    ap.add_argument("--query", default="ALL", help="IMAP SEARCH criteria (default ALL)")
    ap.add_argument("--limit", type=int, default=500, help="max most-recent messages to scan")
    ap.add_argument("--apply", action="store_true", help="actually MOVE archivable noise (default: dry run)")
    ap.add_argument("--sample", type=int, default=4, help="sample senders to show per bucket in dry run")
    args = ap.parse_args()

    host = os.getenv("ICLOUD_IMAP_HOST") or os.getenv("IMAP_HOST") or "imap.mail.me.com"
    user = os.getenv("ICLOUD_IMAP_USER") or os.getenv("IMAP_USER")
    password = os.getenv("ICLOUD_IMAP_PASS") or os.getenv("IMAP_PASS")  # allow-secret (env read, no literal)
    if not user or not password:
        sys.exit("ICLOUD_IMAP_USER and ICLOUD_IMAP_PASS must be set (source the op env file).")

    print("=" * 64)
    print("MODE:", "APPLY (will MOVE to Archive)" if args.apply else "DRY RUN (no changes)")
    print(f"Account: {user}  Host: {host}  Archive mailbox: {args.archive_mailbox!r}")
    print("=" * 64)

    imap = connect(host, user, password)
    try:
        imap.select(args.mailbox)
        res, data = imap.uid("search", None, args.query)
        if res != "OK":
            sys.exit(f"IMAP search failed: {args.query}")
        uids = data[0].split()
        total = len(uids)
        if not uids:
            print("Inbox empty / no matches.")
            return
        uids = uids[max(0, len(uids) - args.limit):]  # most recent N
        print(f"INBOX total={total}; scanning most-recent {len(uids)}\n")

        protected, uncategorized, keep_inbox = [], [], []
        archivable = []  # (uid, label, sender)
        by_label_samples = defaultdict(list)
        protected_samples = []

        for raw in uids:
            uid = raw.decode()
            frm, subj = fetch_from_subject(imap, uid)
            if is_protected_sender(frm):           # HARD GATE — fail closed
                protected.append(uid)
                if len(protected_samples) < args.sample:
                    protected_samples.append(frm)
                continue
            # Categorize off the DECODED real domain so a Hide-My-Email relay
            # sender is labeled by its true origin, not the iCloud carrier.
            _disp, _addr, real_domain = normalize_sender(frm)
            label = categorize_from_strings(real_domain or frm, subj)
            if label == CATCH_ALL:                 # uncertain -> keep, never auto-archive
                uncategorized.append(uid)
            elif should_keep_in_inbox(label):      # tier 1/2 / keep labels
                keep_inbox.append(uid)
            else:
                archivable.append((uid, label, frm))
                if len(by_label_samples[label]) < args.sample:
                    by_label_samples[label].append(frm)

        print("--- Disposition (dry run) ---")
        print(f"  PROTECTED (never touched) : {len(protected)}")
        for s in protected_samples:
            print(f"      keep: {s[:70]}")
        print(f"  KEEP-IN-INBOX (tier 1/2)  : {len(keep_inbox)}")
        print(f"  UNCATEGORIZED (kept)      : {len(uncategorized)}  [Misc/Other — review, not auto-archived]")
        print(f"  ARCHIVABLE noise          : {len(archivable)}")
        for label in sorted(by_label_samples):
            n = sum(1 for _, lb, _ in archivable if lb == label)
            print(f"      {label:24s}: {n}")
            for s in by_label_samples[label]:
                print(f"          {s[:66]}")

        if not args.apply:
            print(f"\nDRY RUN complete. Would archive {len(archivable)} of {len(uids)} scanned. No changes made.")
            print("Re-run with --apply to MOVE the archivable noise to Archive (protected/uncategorized stay).")
            return

        print(f"\n--- APPLYING: moving {len(archivable)} -> {args.archive_mailbox!r} ---")
        moved, failed = 0, 0
        for uid, label, _frm in archivable:
            if archive_uid(imap, uid, args.archive_mailbox):
                moved += 1
            else:
                failed += 1
        print(f"DONE. Moved {moved}, failed {failed}. Protected untouched: {len(protected)}.")
    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
