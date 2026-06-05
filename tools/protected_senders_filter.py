#!/usr/bin/env python3
"""Canonical shell-facing wrapper around the protected-sender gate.

The macOS Mail.app AppleScript movers (archive_old_inbox.applescript,
route_bulk_senders.applescript) run OUTSIDE the Python engine, so historically
they bypassed the protected-sender gate entirely and could move a protected
sender's mail (legal / bank / government) out of the inbox — the exact data-loss
the gate exists to prevent (review G16).

Rather than duplicate the gate logic in AppleScript (a second implementation that
would drift), those scripts shell out to THIS wrapper, which delegates to the one
canonical gate: ``core.rules.is_protected_sender``. Single source of truth.

Usage
-----
    # Single sender — prints exactly "PROTECTED" or "OK" (for per-message checks):
    python3 tools/protected_senders_filter.py --one "Jane Doe <jane@irs.gov>"

    # Batch — read From-header strings on stdin (one per line), echo back ONLY the
    # protected ones, verbatim and in order (for set-membership in the caller):
    python3 tools/protected_senders_filter.py < senders.txt

Exit status is non-zero only on an internal/import failure, so a caller can treat
a failed invocation as "gate unavailable" and FAIL CLOSED (do not move the mail).
``is_protected_sender`` itself already fails closed on empty/unparseable input.
"""
import os
import sys

# Make the repo importable regardless of the caller's working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rules import is_protected_sender


def main(argv):
    if len(argv) >= 2 and argv[1] == "--one":
        sender = argv[2] if len(argv) > 2 else ""
        print("PROTECTED" if is_protected_sender(sender) else "OK")
        return 0

    # Batch mode: echo protected senders verbatim so the caller can do exact
    # set membership without re-parsing.
    for line in sys.stdin:
        sender = line.rstrip("\n")
        if is_protected_sender(sender):
            print(sender)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
