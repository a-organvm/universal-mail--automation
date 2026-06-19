"""Tests for providers.mailapp.MailAppProvider.

Mail.app is driven entirely through AppleScript run via ``_run_applescript``.
Every test stubs that single seam, so the parsing, pagination, folder-move
semantics, mailbox caching, and error handling are exercised with no osascript
subprocess and no macOS dependency.
"""

from datetime import datetime

from core.models import LabelAction
from providers.mailapp import MailAppProvider


class _Script:
    """Stub for MailAppProvider._run_applescript.

    Records every script string and returns a canned result, or raises a
    pre-seeded error to simulate an AppleScript failure.
    """

    def __init__(self, result="ok", error=None):
        self.scripts = []
        self.result = result
        self.error = error
        self.calls = 0

    def __call__(self, script):
        self.calls += 1
        self.scripts.append(script)
        if self.error is not None:
            raise self.error
        if callable(self.result):
            return self.result(script)
        return self.result

    @property
    def last(self):
        return self.scripts[-1]

    @property
    def joined(self):
        return "\n".join(self.scripts)


def _provider(result="ok", error=None, account=None):
    p = MailAppProvider(account=account)
    p._run_applescript = _Script(result=result, error=error)
    return p


# --------------------------------------------------------------------------- #
# Existing regression (kept): star with due_date flows through base apply_actions
# --------------------------------------------------------------------------- #
def test_mailapp_star_accepts_due_date_from_base_apply_actions():
    provider = MailAppProvider()
    scripts = []
    provider._run_applescript = lambda script: scripts.append(script) or "ok"

    result = provider.apply_actions([
        LabelAction(
            message_id="123",
            sender="promo@some-shop.example",
            star=True,
            due_date=datetime(2026, 6, 1),
        )
    ])

    assert result.error_count == 0
    assert result.success_count == 1
    assert scripts and "flagged status" in scripts[0]


class TestListMessages:
    OUTPUT = (
        "42\tboss@co.com\tHello\ttrue\tfalse\n"
        "7\tdeals@store.com\tSale\tfalse\ttrue\n"
        "---TOTAL:50"
    )

    def test_parses_messages_and_flags(self):
        p = _provider(result=self.OUTPUT)
        res = p.list_messages(limit=10)
        assert [m.id for m in res.messages] == ["42", "7"]
        first, second = res.messages
        assert first.sender == "boss@co.com"
        assert first.subject == "Hello"
        assert first.is_read is True
        assert first.is_starred is False
        assert second.is_read is False
        assert second.is_starred is True
        assert res.total_estimate == 50

    def test_pagination_token_when_more_remain(self):
        p = _provider(result=self.OUTPUT)
        res = p.list_messages(limit=10)
        # 0 + 10 < 50 -> another page
        assert res.next_page_token == "10"

    def test_no_pagination_token_on_last_page(self):
        p = _provider(result=self.OUTPUT)
        res = p.list_messages(limit=100)
        # 0 + 100 >= 50 -> done
        assert res.next_page_token is None

    def test_page_token_offset_is_honored(self):
        p = _provider(result=self.OUTPUT)
        res = p.list_messages(limit=10, page_token="20")
        # 20 + 10 < 50 -> next is "30"
        assert res.next_page_token == "30"

    def test_account_filter_injected_into_script(self):
        p = _provider(result=self.OUTPUT, account="iCloud")
        p.list_messages()
        assert 'of account "iCloud"' in p._run_applescript.last

    def test_applescript_failure_returns_empty_result(self):
        p = _provider(error=RuntimeError("Mail not running"))
        res = p.list_messages()
        assert res.messages == []
        assert res.next_page_token is None


class TestGetMessageDetails:
    def test_parses_details_and_mailbox_label(self):
        p = _provider(result="boss@co.com\tHello\ttrue\tfalse\tINBOX")
        msg = p.get_message_details("42")
        assert msg.id == "42"
        assert msg.sender == "boss@co.com"
        assert msg.is_read is True
        assert msg.is_starred is False
        assert msg.labels == {"INBOX"}

    def test_truncated_output_returns_none(self):
        p = _provider(result="too\tfew\tparts")
        assert p.get_message_details("42") is None

    def test_failure_returns_none(self):
        p = _provider(error=RuntimeError("no such message"))
        assert p.get_message_details("42") is None


class TestApplyLabelMove:
    def test_move_runs_and_succeeds(self):
        p = _provider(result="ok")
        p._created_mailboxes.add("Work")  # skip the ensure round-trip
        assert p.apply_label("42", "Work") is True
        assert "move targetMsg to targetMailbox" in p._run_applescript.last
        assert 'mailbox "Work"' in p._run_applescript.last

    def test_move_failure_returns_false(self):
        p = _provider(error=RuntimeError("mailbox missing"))
        assert p.apply_label("42", "Work") is False

    def test_account_filter_in_move(self):
        p = _provider(result="ok", account="iCloud")
        p._created_mailboxes.add("Work")
        p.apply_label("42", "Work")
        assert 'of account "iCloud"' in p._run_applescript.last


class TestRemoveLabel:
    def test_remove_label_is_unsupported_noop(self):
        p = _provider()
        assert p.remove_label("42", "Work") is False
        # No AppleScript should be run for an unsupported op.
        assert p._run_applescript.calls == 0


class TestArchive:
    def test_archive_moves_to_archive_mailbox(self):
        p = _provider(result="ok")
        p._created_mailboxes.add("Archive")
        assert p.archive("42") is True
        assert 'mailbox "Archive"' in p._run_applescript.joined


class TestStarUnstar:
    def test_star_sets_flag_true(self):
        p = _provider(result="ok")
        assert p.star("42") is True
        assert "set flagged status of targetMsg to true" in p._run_applescript.last

    def test_star_failure_returns_false(self):
        p = _provider(error=RuntimeError("denied"))
        assert p.star("42") is False

    def test_unstar_sets_flag_false(self):
        p = _provider(result="ok")
        assert p.unstar("42") is True
        assert "set flagged status of targetMsg to false" in p._run_applescript.last


class TestMarkReadUnread:
    def test_mark_read(self):
        p = _provider(result="ok")
        assert p.mark_read("42") is True
        assert "set read status of targetMsg to true" in p._run_applescript.last

    def test_mark_unread(self):
        p = _provider(result="ok")
        assert p.mark_unread("42") is True
        assert "set read status of targetMsg to false" in p._run_applescript.last

    def test_mark_read_failure_returns_false(self):
        p = _provider(error=RuntimeError("denied"))
        assert p.mark_read("42") is False


class TestEnsureLabelExists:
    def test_created_mailbox_is_cached(self):
        p = _provider(result="created")
        assert p.ensure_label_exists("Work") == "Work"
        assert "Work" in p._created_mailboxes
        # Second call short-circuits — no further AppleScript.
        assert p.ensure_label_exists("Work") == "Work"
        assert p._run_applescript.calls == 1

    def test_existing_mailbox_is_cached(self):
        p = _provider(result="exists")
        p.ensure_label_exists("Finance")
        assert "Finance" in p._created_mailboxes

    def test_failure_does_not_cache(self):
        p = _provider(error=RuntimeError("permission denied"))
        assert p.ensure_label_exists("Work") == "Work"
        assert "Work" not in p._created_mailboxes


class TestAccountsAndMailboxes:
    def test_get_accounts_parses_linefeed_list(self):
        p = _provider(result="iCloud\nGmail\n")
        assert p.get_accounts() == ["iCloud", "Gmail"]

    def test_get_accounts_failure_returns_empty(self):
        p = _provider(error=RuntimeError("no Mail"))
        assert p.get_accounts() == []

    def test_get_mailboxes_parses_list(self):
        p = _provider(result="INBOX\nArchive\nWork/Dev")
        assert p.get_mailboxes() == ["INBOX", "Archive", "Work/Dev"]

    def test_get_mailboxes_failure_returns_empty(self):
        p = _provider(error=RuntimeError("no Mail"))
        assert p.get_mailboxes() == []


class TestCapabilities:
    def test_declares_folder_move_semantics(self):
        # Mail.app's apply_label IS an out-of-inbox move; the audit/gate rely on this.
        assert MailAppProvider.LABEL_IS_MOVE is True
