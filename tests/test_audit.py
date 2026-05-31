"""Tests for the triage audit receipt (core/audit.py) and its chokepoint wiring.

The audit log is an INDEPENDENT observer of the protected-sender gate. These tests
prove three things:
  1. It records the correct post-gate disposition for each message.
  2. It writes a parseable append-only JSONL (and redacts to domain-only on request).
  3. It detects — and refuses to stay silent about — a gate violation, i.e. a
     protected sender recorded as archived/moved. That path should be unreachable
     through the real chokepoint; the test injects it directly to prove the alarm
     works, then proves the real chokepoint never trips it.
"""

import json

import pytest

from core.audit import (
    AuditLog,
    AuditInvariantError,
    PROTECTED_HELD,
    ARCHIVED,
    MOVED,
    LABELED,
    KEPT,
    _domain_of,
    _independently_protected,
)
from core.models import LabelAction, EmailMessage
from providers.base import EmailProvider, ProviderCapabilities, ListMessagesResult

PROTECTED = "Lawyer <a@example-lawfirm.com>"   # shipped in EXAMPLE_PROTECTED_SENDERS
NORMAL = "Sale <promo@some-shop.example>"


# --- minimal recording providers (self-contained; mirror base semantics) ----
class _Recording(EmailProvider):
    """Label provider (Gmail-like): additive labels, archive removes from inbox."""
    name = "rec"
    capabilities = ProviderCapabilities.TRUE_LABELS | ProviderCapabilities.ARCHIVE
    LABEL_IS_MOVE = False

    def __init__(self):
        self.archived = []
        self.labeled = []     # (message_id, label) for each apply_label call
        self.removed = []     # (message_id, label) for each remove_label call

    def connect(self): pass
    def disconnect(self): pass
    def list_messages(self, query=None, limit=None, page_token=None): return None
    def get_message_details(self, message_id): return None
    def apply_label(self, message_id, label):
        self.labeled.append((message_id, label))
        return True
    def remove_label(self, message_id, label):
        self.removed.append((message_id, label))
        return True
    def ensure_label_exists(self, label): return label
    def archive(self, message_id):
        self.archived.append(message_id)
        return True


class _RecordingFolder(_Recording):
    """Folder MOVE provider (Outlook/Mail.app-like): apply_label IS a move."""
    name = "rec-folder"
    capabilities = ProviderCapabilities.FOLDERS | ProviderCapabilities.ARCHIVE
    LABEL_IS_MOVE = True


class _RecordingImapLike(_Recording):
    """Folder provider with ADDITIVE labels (IMAP +X-GM-LABELS / COPY): apply_label
    leaves the message in the inbox; departure is via remove_label(INBOX)/archive()."""
    name = "rec-imap"
    capabilities = (
        ProviderCapabilities.FOLDERS
        | ProviderCapabilities.TRUE_LABELS
        | ProviderCapabilities.ARCHIVE
    )
    LABEL_IS_MOVE = False


class _BrokenGateLabel(_Recording):
    """A label provider whose protected gate REGRESSED: _drop_if_protected no longer
    recognizes or neutralizes anything (returns False, leaves the action intact).
    The audit must still catch a protected breach through the REAL apply path."""
    name = "broken"

    def _drop_if_protected(self, action):
        return False


class _BrokenGateFolder(_RecordingFolder):
    name = "broken-folder"

    def _drop_if_protected(self, action):
        return False


class _FailingArchive(_Recording):
    """archive() raises — simulates a transient API error mid-apply."""
    name = "fail-archive"

    def archive(self, message_id):
        raise RuntimeError("503 — archive did NOT happen")


# --- disposition logic -------------------------------------------------------
class TestDispositions:
    def test_counts_each_disposition(self):
        log = AuditLog()  # memory-only
        log.record(message_id="p", sender=PROTECTED, protected=True, labels_added=["Finance/Banking"])
        log.record(message_id="a", sender=NORMAL, protected=False, archived=True)
        log.record(message_id="m", sender=NORMAL, protected=False, moved=True)
        log.record(message_id="l", sender=NORMAL, protected=False, labels_added=["Marketing"])
        log.record(message_id="k", sender=NORMAL, protected=False)
        s = log.summary()
        assert s == {
            "total": 5, "protected_held": 1, "archived": 1,
            "moved": 1, "labeled": 1, "kept": 1, "violations": [],
        }

    def test_protected_always_held_even_with_labels(self):
        log = AuditLog()
        # A protected sender that gets a label (Gmail additive case) is still HELD,
        # not labeled-and-gone — protection dominates the disposition.
        d = log.record(message_id="p", sender=PROTECTED, protected=True, labels_added=["X"])
        assert d == PROTECTED_HELD
        assert log.summary()["protected_held"] == 1

    def test_disposition_return_values(self):
        log = AuditLog()
        assert log.record(message_id="1", sender=NORMAL, protected=False, archived=True) == ARCHIVED
        assert log.record(message_id="2", sender=NORMAL, protected=False, moved=True) == MOVED
        assert log.record(message_id="3", sender=NORMAL, protected=False, labels_added=["Y"]) == LABELED
        assert log.record(message_id="4", sender=NORMAL, protected=False) == KEPT


# --- the invariant alarm -----------------------------------------------------
class TestInvariant:
    def test_violation_recorded_when_protected_leaves_inbox(self):
        log = AuditLog()
        # Inject the impossible: a protected sender marked archived. The gate should
        # never produce this; the audit must still NOT hide it.
        d = log.record(message_id="boom", sender=PROTECTED, protected=True, archived=True)
        assert d == PROTECTED_HELD          # disposition still names it protected
        assert log.summary()["violations"] == ["boom"]
        with pytest.raises(AuditInvariantError):
            log.assert_no_violations()

    def test_clean_run_has_no_violations(self):
        log = AuditLog()
        log.record(message_id="p", sender=PROTECTED, protected=True)
        log.record(message_id="a", sender=NORMAL, protected=False, archived=True)
        assert log.summary()["violations"] == []
        log.assert_no_violations()  # does not raise


# --- file output -------------------------------------------------------------
class TestJsonl:
    def test_appends_parseable_lines_with_sender(self, tmp_path):
        path = str(tmp_path / "r.jsonl")
        log = AuditLog(path=path, provider="gmail")
        log.record(message_id="a", sender=NORMAL, protected=False, archived=True, labels_added=["Marketing"])
        log.record(message_id="p", sender=PROTECTED, protected=True, labels_added=["Finance/Banking"])
        lines = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        assert len(lines) == 2
        assert lines[0]["sender"] == NORMAL
        assert lines[0]["disposition"] == ARCHIVED
        assert lines[0]["domain"] == "some-shop.example"
        assert lines[1]["disposition"] == PROTECTED_HELD
        assert lines[1]["domain"] == "example-lawfirm.com"
        assert lines[1]["protected"] is True

    def test_redact_stores_domain_not_sender(self, tmp_path):
        path = str(tmp_path / "r.jsonl")
        log = AuditLog(path=path, provider="gmail", redact=True)
        log.record(message_id="a", sender=NORMAL, protected=False, archived=True)
        line = json.loads(open(path, encoding="utf-8").read().strip())
        assert "sender" not in line          # local-part never written
        assert line["domain"] == "some-shop.example"

    def test_memory_only_writes_no_file(self, tmp_path):
        missing = tmp_path / "nope.jsonl"
        log = AuditLog(path=None)
        log.record(message_id="a", sender=NORMAL, protected=False, archived=True)
        assert not missing.exists()
        assert log.summary()["archived"] == 1


# --- chokepoint integration --------------------------------------------------
class TestChokepointIntegration:
    def test_base_label_provider_records_held_and_archived(self, tmp_path):
        path = str(tmp_path / "r.jsonl")
        log = AuditLog(path=path, provider="rec")
        p = _Recording()
        p.apply_actions([
            LabelAction(message_id="prot", sender=PROTECTED, archive=True,
                        remove_labels=["INBOX"], add_labels=["Finance/Banking"]),
            LabelAction(message_id="noise", sender=NORMAL, archive=True,
                        remove_labels=["INBOX"], add_labels=["Marketing"]),
        ], audit=log)
        s = log.summary()
        assert s["protected_held"] == 1
        assert s["archived"] == 1
        assert s["violations"] == []        # gate held — audit agrees
        assert "prot" not in p.archived      # and the protected message was not archived

    def test_folder_provider_records_protected_held_not_moved(self, tmp_path):
        path = str(tmp_path / "r.jsonl")
        log = AuditLog(path=path, provider="rec-folder")
        p = _RecordingFolder()
        p.apply_actions([
            LabelAction(message_id="prot", sender=PROTECTED,
                        add_labels=["Archive"], remove_labels=["INBOX"]),
            LabelAction(message_id="noise", sender=NORMAL,
                        add_labels=["Archive"], remove_labels=["INBOX"]),
        ], audit=log)
        s = log.summary()
        assert s["protected_held"] == 1
        assert s["moved"] == 1               # noise: label-as-move on a folder provider
        assert s["violations"] == []
        # On a move-on-label provider the gate must suppress the label entirely for
        # the protected sender (the apply_label would itself move it out of inbox).
        assert ("prot", "Archive") not in p.labeled
        assert ("noise", "Archive") in p.labeled

    def test_imap_additive_label_recorded_labeled_not_moved(self):
        # IMAP +X-GM-LABELS / standard COPY leaves the message in the inbox, so an
        # additive label with no INBOX-removal is LABELED — matching the Gmail API
        # provider for the byte-identical action (regression guard for the old
        # capability-proxy that mislabeled this as MOVED).
        log = AuditLog()
        p = _RecordingImapLike()
        p.apply_actions(
            [LabelAction(message_id="n", sender=NORMAL, add_labels=["Finance/Banking"])],
            audit=log,
        )
        s = log.summary()
        assert s["labeled"] == 1
        assert s["moved"] == 0
        assert ("n", "Finance/Banking") in p.labeled

    def test_imap_archive_is_recorded_moved(self):
        # IMAP's out-of-inbox departure is via archive()/INBOX-removal, which IS a move.
        log = AuditLog()
        p = _RecordingImapLike()
        p.apply_actions(
            [LabelAction(message_id="n", sender=NORMAL, archive=True)],
            audit=log,
        )
        assert log.summary()["moved"] == 1

    def test_failed_archive_is_not_recorded_as_archived(self, tmp_path):
        # Finding #2: the receipt must reflect what ACTUALLY happened. archive() is
        # the only inbox-departure mechanism here and it raises, so the message
        # stayed in the inbox — it must be LABELED (the label applied first), never
        # ARCHIVED.
        log = AuditLog(path=str(tmp_path / "r.jsonl"), provider="fail-archive")
        p = _FailingArchive()
        result = p.apply_actions(
            [LabelAction(message_id="n", sender=NORMAL, archive=True,
                         add_labels=["Marketing"])],
            audit=log,
        )
        s = log.summary()
        assert result.error_count == 1       # the apply genuinely failed
        assert s["archived"] == 0            # ...so nothing is reported archived
        assert s["labeled"] == 1             # the label that DID apply is recorded
        assert "n" not in p.archived

    def test_gmail_override_records_via_audit(self, tmp_path, monkeypatch):
        pytest.importorskip("googleapiclient")
        import providers.gmail as gmod
        monkeypatch.setattr(gmod.time, "sleep", lambda *_a, **_k: None)

        class _Exec:
            def execute(self): return {}

        class _Messages:
            def batchModify(self, userId, body): return _Exec()

        class _Users:
            def messages(self): return _Messages()

        class _Service:
            def users(self): return _Users()

        gp = gmod.GmailProvider(service=_Service())
        gp.ensure_label_exists = lambda label: label
        gp._execute_with_backoff = lambda fn, _desc: fn()

        path = str(tmp_path / "r.jsonl")
        log = AuditLog(path=path, provider="gmail")
        gp.apply_actions([
            LabelAction(message_id="prot", sender=PROTECTED, archive=True, add_labels=["Finance/Banking"]),
            LabelAction(message_id="noise", sender=NORMAL, archive=True, add_labels=["Marketing"]),
        ], audit=log)
        s = log.summary()
        assert s["protected_held"] == 1
        assert s["archived"] == 1
        assert s["moved"] == 0               # Gmail labels are additive, never moves
        assert s["violations"] == []


class _FakeLister(_Recording):
    """A label provider that returns two messages (one protected, one noise)."""
    name = "fake"

    def __init__(self):
        super().__init__()
        self.msgs = {
            "p": EmailMessage(id="p", sender=PROTECTED, subject="case update"),
            "n": EmailMessage(id="n", sender=NORMAL, subject="50% off newsletter unsubscribe"),
        }

    def list_messages(self, query="", limit=100, page_token=None):
        if page_token:
            return ListMessagesResult(messages=[], next_page_token=None)
        return ListMessagesResult(messages=list(self.msgs.values()), next_page_token=None)

    def get_message_details(self, mid):
        return self.msgs.get(mid)

    def batch_get_details(self, ids):
        return {i: self.msgs[i] for i in ids if i in self.msgs}


class TestRunLabelerReceipt:
    """The CLI decision layer drops protected senders BEFORE the chokepoint, so the
    receipt must record the hold there too — otherwise protected_held undercounts."""

    def test_decision_layer_protected_hold_is_recorded(self, tmp_path):
        from cli import run_labeler
        path = str(tmp_path / "r.jsonl")
        log = AuditLog(path=path, provider="fake")
        p = _FakeLister()
        with p:
            run_labeler(p, query="all", limit=10, dry_run=False,
                        remove_label=None, state_file=None, audit=log)
        s = log.summary()
        assert s["protected_held"] == 1       # held at the decision layer, still counted
        assert s["archived"] == 1             # noise archived at the chokepoint
        assert s["violations"] == []
        assert "p" not in p.archived          # protected lawyer never archived


# --- the cross-check is REAL: a regressed gate is caught through the apply path --
class TestGateRegressionCaught:
    """The decisive test the audit exists for: drive a BROKEN gate through the real
    apply_actions and confirm the independent observer catches the breach. Without
    this, "independent cross-check" is just a claim. The break here is total — the
    gate neither recognizes nor neutralizes the protected sender — yet the audit
    re-derives protection from the raw sender and observes the actual operation."""

    def test_regressed_label_gate_is_caught_at_chokepoint(self, tmp_path):
        log = AuditLog(path=str(tmp_path / "r.jsonl"), provider="broken")
        p = _BrokenGateLabel()
        p.apply_actions([
            LabelAction(message_id="prot", sender=PROTECTED, archive=True,
                        remove_labels=["INBOX"]),
        ], audit=log)
        s = log.summary()
        assert "prot" in p.archived           # the broken gate DID let mail leave inbox
        assert s["violations"] == ["prot"]    # ...and the audit caught it regardless
        with pytest.raises(AuditInvariantError):
            log.assert_no_violations()

    def test_regressed_folder_gate_is_caught_at_chokepoint(self, tmp_path):
        log = AuditLog(path=str(tmp_path / "r.jsonl"), provider="broken-folder")
        p = _BrokenGateFolder()
        p.apply_actions([
            LabelAction(message_id="prot", sender=PROTECTED,
                        add_labels=["Archive"], remove_labels=["INBOX"]),
        ], audit=log)
        s = log.summary()
        assert ("prot", "Archive") in p.labeled   # broken gate let the move-label run
        assert s["violations"] == ["prot"]
        with pytest.raises(AuditInvariantError):
            log.assert_no_violations()


# --- record-level independence + fail-closed parity with the gate --------------
class TestIndependence:
    def test_independent_check_catches_detection_regression(self):
        # Gate reported NOT protected (protected=False), but the sender IS protected
        # and left the inbox. The audit re-derives protection and flags the breach.
        log = AuditLog()
        d = log.record(message_id="x", sender=PROTECTED, protected=False, archived=True)
        assert d == PROTECTED_HELD
        assert log.summary()["violations"] == ["x"]

    def test_independent_helper_matches_gate_definition(self):
        assert _independently_protected(PROTECTED) is True
        assert _independently_protected(NORMAL) is False
        assert _independently_protected("") is True       # blank fails closed, like the gate
        assert _independently_protected(12345) is False   # non-str swallowed, never raises

    def test_non_protected_archive_is_not_a_violation(self):
        log = AuditLog()
        log.record(message_id="a", sender=NORMAL, protected=False, archived=True)
        assert log.summary()["violations"] == []


# --- receipt-keeping never raises into the apply path (findings #4, #5) --------
class TestRobustness:
    def test_append_failure_degrades_to_memory_and_still_checks_invariant(self, tmp_path):
        blocked = tmp_path / "d"
        blocked.mkdir()                       # path is a DIR -> open(..., "a") raises
        log = AuditLog(path=str(blocked), provider="rec")
        d = log.record(message_id="boom", sender=PROTECTED, protected=True, archived=True)
        assert d == PROTECTED_HELD            # record() did NOT raise
        assert log.write_error is not None    # the write failure is surfaced, not hidden
        assert log.summary()["violations"] == ["boom"]   # in-memory invariant still works
        with pytest.raises(AuditInvariantError):
            log.assert_no_violations()

    def test_apply_with_unwritable_audit_does_not_raise_or_breach(self, tmp_path):
        blocked = tmp_path / "d"
        blocked.mkdir()
        log = AuditLog(path=str(blocked), provider="rec")
        p = _Recording()
        result = p.apply_actions([
            LabelAction(message_id="prot", sender=PROTECTED, archive=True,
                        remove_labels=["INBOX"]),
            LabelAction(message_id="noise", sender=NORMAL, archive=True,
                        remove_labels=["INBOX"]),
        ], audit=log)
        assert result.error_count == 0        # the run completed despite unwritable audit
        assert "prot" not in p.archived       # gate still held
        assert log.write_error is not None    # degraded to in-memory
        assert log.summary()["archived"] == 1 # counts still work in memory

    def test_domain_of_non_str_does_not_raise(self):
        assert _domain_of(12345) == ""
        assert _domain_of(b"a@b.com") == ""
        assert _domain_of(None) == ""
        assert _domain_of("Sale <promo@some-shop.example>") == "some-shop.example"
