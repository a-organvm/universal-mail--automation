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


# Characters that cannot legally appear in an RFC 3501 quoted-string: a
# quoted-string is built from QUOTED-CHAR, which excludes CR, LF and NUL
# entirely (RFC 3501 §4.3 / §9). Passing them through would let a CR/LF in a
# mailbox name split the command stream and inject a forged IMAP command, so a
# name carrying them is not safely encodable and we reject it (fail closed).
_IMAP_FORBIDDEN = frozenset(chr(c) for c in range(0x20)) | frozenset("\x7f")


def imap_quote(name: str) -> str:
    """Wrap a mailbox name as an RFC 3501 quoted-string, backslash-escaping the
    two characters special inside one (``\\`` and ``"``) and REJECTING control
    characters. Without escaping, a name containing a quote breaks the command;
    without rejecting CR/LF, attacker- or config-controlled text could inject
    extra IMAP arguments (review U799/U800). A quoted-string cannot represent
    CR/LF/NUL at all, so we raise rather than emit an injectable string."""
    bad = sorted({c for c in name if c in _IMAP_FORBIDDEN})
    if bad:
        raise ValueError(
            "mailbox name contains control character(s) that cannot be safely "
            f"encoded as an IMAP quoted-string: {[hex(ord(c)) for c in bad]}")
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _supports(imap: imaplib.IMAP4_SSL, capability: str) -> bool:
    """True iff the server advertised ``capability``. imaplib populates
    ``.capabilities`` (a tuple of upper-case names) at connect/login; fall back
    to an explicit CAPABILITY query if that attribute is unavailable. Matching
    is exact-token (not substring) so e.g. ``UIDPLUS`` never misfires on a bare
    ``UID`` token, nor ``MOVE`` on ``X-REMOVE``."""
    want = capability.upper().encode()
    caps = getattr(imap, "capabilities", None)
    if caps:
        return want in {str(c).upper().encode() for c in caps}
    try:
        res, data = imap.capability()
    except Exception:
        return False
    if res != "OK" or not data:
        return False
    tokens = {t.upper() for x in data if isinstance(x, (bytes, bytearray))
              for t in x.split()}
    return want in tokens


def archive_uid(imap: imaplib.IMAP4_SSL, uid: str, archive_mailbox: str) -> str:
    """Move ONE message INBOX -> archive_mailbox, returning an outcome string:

      "moved"              - the message is in Archive and gone from the source
                             (atomic UID MOVE, or COPY + scoped UID EXPUNGE).
      "copied_not_removed" - an archive copy exists but the original could not be
                             SAFELY removed; it is left flagged \\Deleted in place
                             (a recoverable duplicate), NOT expunged.
      "failed"             - nothing changed; the original is untouched.

    CRITICAL (review U006): this function NEVER issues a mailbox-wide EXPUNGE.
    A bare ``imap.expunge()`` removes EVERY \\Deleted-flagged message in the
    mailbox (RFC 3501 semantics), so the old COPY + STORE + expunge() fallback
    could permanently destroy unrelated mail the user (or another tool) had
    flagged. We only ever delete scoped to THIS uid via UID EXPUNGE (RFC 4315 /
    UIDPLUS); if the server advertises neither MOVE nor UIDPLUS we decline to
    delete and report "copied_not_removed" rather than risk data loss."""
    dest = imap_quote(archive_mailbox)

    # Preferred: atomic, server-side UID MOVE (RFC 6851). When the server
    # supports MOVE we trust its result and never fall through to COPY — a
    # non-OK MOVE that fell through would leave the original AND create a copy
    # (duplicate), review U801.
    if _supports(imap, "MOVE"):
        try:
            res, _ = imap.uid("MOVE", uid, dest)
        except imaplib.IMAP4.error:
            res = "NO"
        return "moved" if res == "OK" else "failed"

    # Fallback path: COPY, then flag the original \\Deleted, then scoped expunge.
    try:
        res, _ = imap.uid("COPY", uid, dest)
    except imaplib.IMAP4.error:
        res = "NO"
    if res != "OK":
        return "failed"  # nothing copied; original untouched

    # The archive copy now exists. Flag the original for deletion, checking the
    # result (review U358/U359) — an unchecked STORE could leave us reporting
    # success while the message stays put.
    try:
        sres, _ = imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
    except imaplib.IMAP4.error:
        sres = "NO"
    if sres != "OK":
        return "copied_not_removed"  # copy made; couldn't flag original -> dup

    # Remove ONLY this message. UID EXPUNGE (RFC 4315) is scoped to the given
    # UID set; the bare EXPUNGE we refuse to call would be mailbox-wide.
    if _supports(imap, "UIDPLUS"):
        try:
            eres, _ = imap.uid("EXPUNGE", uid)
        except imaplib.IMAP4.error:
            eres = "NO"
        return "moved" if eres == "OK" else "copied_not_removed"

    # No UIDPLUS: there is no way to expunge a single message without a
    # mailbox-wide EXPUNGE, so we decline. The original stays flagged \\Deleted
    # (a duplicate the user can reconcile), which is strictly safer than
    # destroying every other \\Deleted message in the mailbox.
    return "copied_not_removed"


def main():
    ap = argparse.ArgumentParser(description="iCloud/IMAP triage with protected gate + archive.")
    ap.add_argument("--mailbox", default="INBOX", help="source mailbox (default INBOX)")
    ap.add_argument("--archive-mailbox", default="Archive", help="archive destination (default Archive)")
    ap.add_argument("--query", default="ALL", help="IMAP SEARCH criteria (default ALL)")
    ap.add_argument("--limit", type=int, default=500, help="max most-recent messages to scan")
    ap.add_argument("--apply", action="store_true", help="actually MOVE archivable noise (default: dry run)")
    ap.add_argument("--sample", type=int, default=4, help="sample senders to show per bucket in dry run")
    args = ap.parse_args()

    # Fail closed on an un-encodable archive mailbox name BEFORE touching the
    # server, rather than raising mid-loop after some messages have moved.
    try:
        imap_quote(args.archive_mailbox)
        imap_quote(args.mailbox)
    except ValueError as exc:
        sys.exit(f"Invalid mailbox name: {exc}")

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
        moved, copied_not_removed, failed = 0, 0, 0
        for uid, label, _frm in archivable:
            outcome = archive_uid(imap, uid, args.archive_mailbox)
            if outcome == "moved":
                moved += 1
            elif outcome == "copied_not_removed":
                copied_not_removed += 1
            else:
                failed += 1
        print(f"DONE. Moved {moved}, copied-not-removed {copied_not_removed}, "
              f"failed {failed}. Protected untouched: {len(protected)}.")
        if copied_not_removed:
            print(f"  NOTE: {copied_not_removed} message(s) were COPIED to "
                  f"{args.archive_mailbox!r} but left flagged \\Deleted in the source")
            print("        because the server advertises neither MOVE nor UIDPLUS. They are")
            print("        NOT auto-expunged — a mailbox-wide EXPUNGE would delete unrelated")
            print("        \\Deleted mail. Expunge the source manually if you want them gone.")
    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
