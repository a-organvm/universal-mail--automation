"""Focused coverage for the CLI control path and decision-layer orchestration."""

from types import SimpleNamespace
from typing import Any, List

import pytest

from core.models import EmailMessage, ProcessingResult
from core.audit import AuditLog
from providers.base import ListMessagesResult, ProviderCapabilities

import cli


def _cat_result(label: str = "Shopping", tier: int = 4, is_vip: bool = False):
    return SimpleNamespace(
        label=label,
        tier=tier,
        time_sensitive=False,
        tier_config=None,
        is_vip=is_vip,
        vip_note="",
    )


class _CaptureAudit:
    def __init__(self):
        self.calls: List[dict[str, Any]] = []

    def record(self, **kwargs):
        self.calls.append(kwargs)


class _CaptureProvider:
    name = "fake"
    capabilities = ProviderCapabilities.TRUE_LABELS | ProviderCapabilities.ARCHIVE
    LABEL_IS_MOVE = False

    def __init__(self, messages: List[EmailMessage], next_page_token=None):
        self.messages = {msg.id: msg for msg in messages}
        self.next_page_token = next_page_token
        self.apply_actions_calls = 0
        self.raise_if_apply = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None

    def connect(self):
        return None

    def disconnect(self):
        return None

    def list_messages(self, query="", limit=100, page_token=None):
        return ListMessagesResult(
            messages=list(self.messages.values()),
            next_page_token=self.next_page_token,
        )

    def get_message_details(self, message_id):
        return self.messages[message_id]

    def apply_actions(self, actions, audit=None):
        self.apply_actions_calls += 1
        if self.raise_if_apply:
            raise AssertionError("provider apply_actions should not be called in this path")
        return ProcessingResult(processed_count=len(actions), success_count=len(actions))

    def ensure_label_exists(self, label):
        return label


class _NoMessageProvider(_CaptureProvider):
    def list_messages(self, query="", limit=100, page_token=None):
        return ListMessagesResult(messages=[], next_page_token=None)


def test_make_audit_returns_none_for_dry_run():
    args = SimpleNamespace(
        provider="gmail",
        dry_run=True,
        no_audit=False,
        audit_file=None,
        redact_audit=False,
    )

    assert cli._make_audit(args, kind="triage") is None


def test_make_audit_builds_default_audit_path():
    args = SimpleNamespace(
        provider="gmail",
        dry_run=False,
        no_audit=False,
        audit_file=None,
        redact_audit=False,
    )
    audit = cli._make_audit(args, kind="triage")

    assert audit is not None
    assert audit.path == "audit/gmail-triage.jsonl"


def test_make_audit_no_audit_flag():
    args = SimpleNamespace(
        provider="gmail",
        dry_run=False,
        no_audit=True,
        audit_file=None,
        redact_audit=False,
    )
    assert cli._make_audit(args, kind="triage") is None


def test_record_dry_run_intent_marks_archive_and_move(monkeypatch):
    folder_provider = SimpleNamespace(
        capabilities=ProviderCapabilities.FOLDERS,
        LABEL_IS_MOVE=False,
    )
    label_provider = SimpleNamespace(
        capabilities=ProviderCapabilities.NONE,
        LABEL_IS_MOVE=False,
    )
    audit = _CaptureAudit()

    monkeypatch.setattr(cli, "is_protected_sender", lambda sender: sender == "protected@example")

    action = cli.LabelAction(message_id="m1", sender="normal@example", archive=True)
    action.add_labels.append("Shopping")
    action.remove_labels.append("INBOX")

    cli._record_dry_run_intent(folder_provider, [action], audit)
    assert audit.calls[-1] == {
        "message_id": "m1",
        "sender": "normal@example",
        "protected": False,
        "archived": False,
        "moved": True,
        "labels_added": ["Shopping"],
    }

    cli._record_dry_run_intent(label_provider, [action], audit)
    assert audit.calls[-1] == {
        "message_id": "m1",
        "sender": "normal@example",
        "protected": False,
        "archived": True,
        "moved": False,
        "labels_added": ["Shopping"],
    }


def test_record_dry_run_intent_protected_sender_skips_move(monkeypatch):
    folder_provider = SimpleNamespace(
        capabilities=ProviderCapabilities.FOLDERS,
        LABEL_IS_MOVE=True,
    )
    audit = _CaptureAudit()

    monkeypatch.setattr(cli, "is_protected_sender", lambda sender: sender == "protected@example")
    action = cli.LabelAction(message_id="m2", sender="protected@example")
    action.add_labels.append("Shopping")
    action.target_folder = "Action/Critical"

    cli._record_dry_run_intent(folder_provider, [action], audit)
    assert audit.calls[-1]["archived"] is False
    assert audit.calls[-1]["moved"] is False
    assert audit.calls[-1]["labels_added"] == []


def test_run_labeler_dry_run_records_intent(monkeypatch):
    monkeypatch.setattr(cli, "categorize_with_tier", lambda *_args, **_kwargs: _cat_result("Shopping", tier=4))
    monkeypatch.setattr(cli, "is_protected_sender", lambda sender: False)
    monkeypatch.setattr(cli, "is_vip_sender", lambda sender: False)
    monkeypatch.setattr(cli, "should_star", lambda label: False)
    monkeypatch.setattr(cli, "should_keep_in_inbox", lambda label: False)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    provider = _CaptureProvider([
        EmailMessage(id="msg-1", sender="friend@example.org", subject="Hello world"),
    ])
    provider.raise_if_apply = True
    audit = _CaptureAudit()

    result = cli.run_labeler(
        provider=provider,
        query="all",
        limit=5,
        dry_run=True,
        remove_label="Misc/Other",
        state_file=None,
        audit=audit,
    )

    assert result.processed_count == 1
    assert result.success_count == 1
    assert provider.apply_actions_calls == 0
    assert audit.calls[0]["archived"] is True
    assert audit.calls[0]["labels_added"] == ["Shopping"]


def test_run_labeler_applies_and_updates_state(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "categorize_with_tier", lambda *_args, **_kwargs: _cat_result("Shopping", tier=2))
    monkeypatch.setattr(cli, "is_protected_sender", lambda sender: sender == "protected@example.com")
    monkeypatch.setattr(cli, "is_vip_sender", lambda sender: False)
    monkeypatch.setattr(cli, "should_star", lambda label: False)
    monkeypatch.setattr(cli, "should_keep_in_inbox", lambda label: True)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    provider = _CaptureProvider([
        EmailMessage(id="m1", sender="normal@org.net", subject="A note"),
    ])
    state_path = str(tmp_path / "state.json")

    result = cli.run_labeler(
        provider=provider,
        query="all",
        limit=5,
        dry_run=False,
        remove_label=None,
        state_file=state_path,
    )

    assert result.processed_count == 1
    assert result.success_count == 1
    assert provider.apply_actions_calls == 1

    stored = tmp_path.joinpath("state.json").read_text()
    assert '"Shopping": 1' in stored


def test_run_labeler_skips_protected_sender_and_records_hold(monkeypatch):
    monkeypatch.setattr(cli, "categorize_with_tier", lambda *_args, **_kwargs: _cat_result("Shopping", tier=4))
    monkeypatch.setattr(cli, "is_protected_sender", lambda sender: sender == "protected@law")
    monkeypatch.setattr(cli, "is_vip_sender", lambda sender: False)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    provider = _CaptureProvider([
        EmailMessage(id="m1", sender="protected@law", subject="Privileged"),
    ])
    audit = AuditLog(path=None, provider="fake")

    result = cli.run_labeler(
        provider=provider,
        query="all",
        limit=5,
        dry_run=False,
        remove_label=None,
        state_file=None,
        audit=audit,
    )

    assert result.processed_count == 0
    assert result.success_count == 0
    assert audit.summary()["protected_held"] == 1
    assert provider.apply_actions_calls == 0


def test_run_labeler_no_messages_returns_clean_result():
    provider = _NoMessageProvider([])
    result = cli.run_labeler(
        provider=provider,
        query="all",
        limit=5,
        dry_run=False,
        remove_label=None,
        state_file=None,
    )

    assert result == ProcessingResult()


def test_cmd_label_returns_violation_code_when_audit_violates(monkeypatch):
    class _Args:
        provider = "gmail"
        host = user = password = account = None
        gmail_extensions = False
        query = "all"
        limit = 10
        dry_run = False
        remove_label = None
        state_file = None
        tier_routing = False
        vip_only = False
        no_audit = False
        audit_file = None
        redact_audit = False

    class _FakeProvider:
        name = "gmail"
        capabilities = ProviderCapabilities.NONE

        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): return None

    called = []

    monkeypatch.setattr(cli, "load_config", lambda: {})
    monkeypatch.setattr(cli, "apply_vip_senders_from_config", lambda _cfg: None)
    monkeypatch.setattr(cli, "get_provider", lambda *args, **kwargs: _FakeProvider())
    monkeypatch.setattr(cli, "run_labeler", lambda *args, **kwargs: ProcessingResult(error_count=1))
    monkeypatch.setattr(cli, "_make_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "_report_audit", lambda audit: called.append("reported") or True)

    assert cli.cmd_label(_Args()) == 2
    assert called == ["reported"]
