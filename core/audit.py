"""Append-only audit receipt for mail-triage actions.

The product's headline guarantee is that a protected sender (lawyer, bank,
government, your own account) is NEVER archived or moved out of the inbox. A
guarantee you cannot *see* is one you have to take on faith. This module turns the
protected-sender gate from "trust me" into "here is the receipt": every action the
engine applies is appended as one JSON line, every protected sender the gate held
is recorded with disposition ``protected_held``, and after a run :meth:`summary`
reports the counts.

Crucially, the audit is an INDEPENDENT observer of the gate — and "independent"
here is load-bearing, so it is worth being precise about *what* is independent:

  1. The provider records each disposition from the **actual operations it
     executed** (did ``archive()`` succeed? was ``INBOX`` really removed? did a
     folder ``apply_label`` move run?), NOT from the post-gate ``LabelAction``
     fields the gate just mutated in place. So a regression where the gate fails
     to neutralize a protected message — but the provider still carries the
     archive/move out — is observed as it really happened.
  2. :meth:`record` re-derives "is this sender protected?" by re-running the
     canonical :func:`core.rules.is_protected_sender` on the RAW sender, instead
     of trusting the ``protected`` flag the gate passed in. So even a gate that
     stops *recognizing* a protected sender (and therefore reports
     ``protected=False``) is still caught here, because the audit recognizes it
     anyway and sees it left the inbox.

If a sender the audit independently judges protected is observed leaving the inbox,
that is a contradiction the gate is supposed to make impossible —
:meth:`assert_no_violations` raises :class:`AuditInvariantError` so a regression
fails loudly instead of silently eating someone's legal mail.

The audit shares exactly ONE thing with the gate: the canonical *definition* of
"protected" (``is_protected_sender``). That sharing is correct — a second,
divergent definition would itself be the bug — and it is unit-tested at the rules
layer. What the audit does NOT share is the gate's say-so about any individual
message: it re-checks the sender and observes the real outcome. That is the
difference between "two components agreeing" and "one component reading its own
output," and it is the difference this module exists to provide.

PII: receipt lines contain real sender addresses, so the default file path lives
under ``audit/`` which is gitignored. Pass ``redact=True`` to store domain-only
lines (no local-part) for a receipt you can share or commit.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)


# --- Disposition vocabulary -------------------------------------------------
# What the engine ACTUALLY did with a message, recorded after the operation ran.
PROTECTED_HELD = "protected_held"   # protected sender; out-of-inbox ops neutralized
ARCHIVED = "archived"               # removed from inbox (Gmail INBOX-removal / archive)
MOVED = "moved"                     # folder provider: moved out of inbox to a folder
LABELED = "labeled"                 # label/category added, stayed in inbox
KEPT = "kept"                       # no action that leaves the inbox

# Dispositions that mean "left the inbox". A protected message must never land here.
OUT_OF_INBOX = frozenset({ARCHIVED, MOVED})


class AuditInvariantError(AssertionError):
    """Raised when the audit trail proves a protected sender left the inbox.

    This should be unreachable: the gate neutralizes out-of-inbox operations for
    protected senders before any action is applied. If it fires, the gate has
    regressed and the run must be treated as untrustworthy.
    """


def _domain_of(sender: str) -> str:
    """Best-effort sender domain, decoded through the same resolver the gate uses.

    Imported lazily so ``core.audit`` has no import-time dependency on the heavier
    rules module (keeps the audit log usable in isolation / in tests).
    """
    try:
        from core.rules import normalize_sender
        _disp, _addr, domain = normalize_sender(sender or "")
        return domain or ""
    except Exception:
        # Never let receipt-keeping raise into the apply path. Guard against a
        # non-str sender (int/bytes/None) so even the fallback cannot raise.
        s = sender if isinstance(sender, str) else ""
        return s.rpartition("@")[2].strip().strip(">").lower()


def _independently_protected(sender: str) -> bool:
    """Re-derive protected status from the RAW sender, independent of the gate.

    The audit does not simply trust the ``protected`` flag the caller passed: it
    re-runs the canonical ``is_protected_sender`` on the original sender. This is
    what lets the cross-check catch a gate that stopped *recognizing* a protected
    sender (and therefore reported ``protected=False``) — the audit recognizes it
    anyway, and if it is observed leaving the inbox, that is a violation.

    Shares only the canonical DEFINITION of "protected" with the gate (correct —
    that definition is unit-tested at the rules layer), never the gate's per-message
    decision. Swallows import/parse errors (returns False) so receipt-keeping never
    raises into the apply path; the gate upstream remains the real enforcement and
    the audit declines to assert a protection it cannot compute.
    """
    try:
        from core.rules import is_protected_sender
        return bool(is_protected_sender(sender))
    except Exception:
        return False


class AuditLog:
    """Accumulates per-action dispositions and (optionally) appends them to JSONL.

    Memory-only when ``path`` is None — useful for a dry-run preview digest where
    you want the counts without writing a file. When ``path`` is set, each
    :meth:`record` call appends one JSON line and the parent directory is created
    on first write.
    """

    def __init__(
        self,
        path: Optional[str] = None,
        provider: Optional[str] = None,
        redact: bool = False,
        dry_run: bool = False,
    ):
        self.path = path
        self.provider = provider
        self.redact = redact
        self.dry_run = dry_run
        self.counts: Counter = Counter()
        self.violations: List[str] = []
        self._total = 0
        self._dir_ready = False
        # Set if a file write fails: the log degrades to in-memory only (counts,
        # violations, and assert_no_violations keep working) rather than raising
        # into the apply path. The CLI surfaces this so the run is not silently
        # left without a persisted receipt.
        self.write_error: Optional[str] = None
        self._write_disabled = False

    # -- recording ----------------------------------------------------------
    def record(
        self,
        *,
        message_id: str,
        sender: str,
        protected: bool,
        archived: bool = False,
        moved: bool = False,
        labels_added: Optional[Sequence[str]] = None,
    ) -> str:
        """Record one message's ACTUAL disposition; returns the disposition string.

        ``archived``/``moved`` must reflect what the provider *actually did* (a
        succeeded out-of-inbox operation), not the pre-execution intent — callers
        record after applying, so a failed API call does not over-report a move.

        ``protected`` is the gate's view, but it is not trusted on its own: the
        audit independently re-derives protection from ``sender`` (see
        :func:`_independently_protected`) and treats the message as protected if
        EITHER source says so. If a protected sender is observed leaving the inbox,
        that is recorded as a violation (the gate failed) AND still surfaced as
        ``protected_held`` so the breach is visible rather than hidden.
        """
        labels_added = list(labels_added or [])

        # Independent re-derivation: union of the gate's flag and the audit's own
        # check on the raw sender. Catches both a gate that forgot to neutralize
        # (protected=True, but archived/moved observed) and a gate that stopped
        # recognizing the sender (protected=False, yet the sender IS protected).
        is_protected = bool(protected) or _independently_protected(sender)
        left_inbox = bool(archived) or bool(moved)

        if is_protected:
            disposition = PROTECTED_HELD
            if left_inbox:
                self.violations.append(message_id)
        elif archived:
            disposition = ARCHIVED
        elif moved:
            disposition = MOVED
        elif labels_added:
            disposition = LABELED
        else:
            disposition = KEPT

        self.counts[disposition] += 1
        self._total += 1

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "message_id": message_id,
            "disposition": disposition,
            "protected": bool(is_protected),
            "archived": bool(archived),
            "moved": bool(moved),
            "labels_added": labels_added,
            "domain": _domain_of(sender),
            "dry_run": bool(self.dry_run),
        }
        if not self.redact:
            entry["sender"] = sender

        self._append(entry)
        return disposition

    def _append(self, entry: dict) -> None:
        if not self.path or self._write_disabled:
            return
        try:
            if not self._dir_ready:
                parent = os.path.dirname(os.path.abspath(self.path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                self._dir_ready = True
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            # Receipt-keeping must NEVER raise into the apply path (it runs after
            # the mail op, so a raise here would abort the run mid-batch). Degrade
            # to in-memory only: counts / violations / assert_no_violations still
            # work, so the safety invariant is still checked — we just cannot
            # persist the file. Disable further writes and surface the error once.
            self._write_disabled = True
            self.write_error = str(e)
            logger.warning(
                "audit receipt write to %s failed (%s); continuing in-memory only "
                "— the invariant is still checked but no file is persisted",
                self.path, e,
            )

    # -- reporting ----------------------------------------------------------
    def summary(self) -> dict:
        """Return disposition counts plus the invariant-violation list."""
        return {
            "total": self._total,
            "protected_held": self.counts.get(PROTECTED_HELD, 0),
            "archived": self.counts.get(ARCHIVED, 0),
            "moved": self.counts.get(MOVED, 0),
            "labeled": self.counts.get(LABELED, 0),
            "kept": self.counts.get(KEPT, 0),
            "violations": list(self.violations),
        }

    def assert_no_violations(self) -> None:
        """Fail loudly if the trail proves a protected sender left the inbox."""
        if self.violations:
            raise AuditInvariantError(
                "protected-sender gate VIOLATION — these protected message(s) were "
                f"archived/moved out of inbox: {self.violations}"
            )

    def receipt_line(self) -> str:
        """One-line human receipt, e.g. for a CLI tail or a log statement."""
        s = self.summary()
        verb = "would" if self.dry_run else "did"
        out = (
            f"Triage receipt: {s['total']} message(s) — "
            f"{s['protected_held']} protected held in inbox, "
            f"{s['archived'] + s['moved']} {verb} leave inbox, "
            f"{s['labeled']} labeled-in-inbox, {s['kept']} kept."
        )
        if s["violations"]:
            out += f"  ⚠ GATE VIOLATION on {len(s['violations'])} protected message(s)!"
        return out
