import pytest
from unittest.mock import MagicMock, patch
import sys

from core.models import LabelAction
from core.audit import AuditLog
from providers.base import EmailProvider, ProviderCapabilities
import cli
from cli import _record_dry_run_intent, get_provider

def test_record_dry_run_intent_no_folders():
    mock_provider = MagicMock(spec=EmailProvider)
    mock_provider.capabilities = ProviderCapabilities.CATEGORIES
    mock_provider.LABEL_IS_MOVE = False

    audit_log = MagicMock(spec=AuditLog)
    action = LabelAction(
        message_id="msg1",
        sender="foo@example.com",
        add_labels={"IMPORTANT"},
        remove_labels={"INBOX"},
        archive=True
    )
    
    with patch("cli.is_protected_sender", return_value=False):
        _record_dry_run_intent(mock_provider, [action], audit_log)
    
    audit_log.record.assert_called_once_with(
        message_id="msg1",
        sender="foo@example.com",
        protected=False,
        archived=True,
        moved=False,
        labels_added=["IMPORTANT"]
    )

def test_record_dry_run_intent_protected_sender():
    mock_provider = MagicMock(spec=EmailProvider)
    mock_provider.capabilities = ProviderCapabilities.CATEGORIES
    mock_provider.LABEL_IS_MOVE = True

    audit_log = MagicMock(spec=AuditLog)
    action = LabelAction(
        message_id="msg2",
        sender="protected@example.com",
        add_labels={"URGENT"},
        remove_labels={"INBOX"},
        archive=True
    )
    
    with patch("cli.is_protected_sender", return_value=True):
        _record_dry_run_intent(mock_provider, [action], audit_log)
    
    audit_log.record.assert_called_once_with(
        message_id="msg2",
        sender="protected@example.com",
        protected=True,
        archived=False,
        moved=False,
        labels_added=[]
    )

def test_get_provider_invalid():
    with pytest.raises(ValueError, match="Unknown provider: invalid"):
        get_provider("invalid")

@patch("providers.gmail.GmailProvider")
def test_get_provider_gmail(mock_gmail):
    provider = get_provider("gmail")
    assert provider == mock_gmail.return_value

@patch("providers.imap.IMAPProvider")
def test_get_provider_imap(mock_imap):
    provider = get_provider("imap", host="imap.test", user="testuser", password="pwd")
    mock_imap.assert_called_once_with(
        host="imap.test", user="testuser", password="pwd", use_gmail_extensions=False
    )
    assert provider == mock_imap.return_value

@patch("providers.mailapp.MailAppProvider")
def test_get_provider_mailapp(mock_mailapp):
    provider = get_provider("mailapp", account="testaccount")
    mock_mailapp.assert_called_once_with(account="testaccount")
    assert provider == mock_mailapp.return_value

@patch("providers.outlook.OutlookProvider")
def test_get_provider_outlook(mock_outlook):
    provider = get_provider("outlook")
    assert provider == mock_outlook.return_value

def test_main_no_args():
    with patch("sys.argv", ["cli.py"]):
        assert cli.main() == 1

@patch("cli.cmd_label")
def test_main_label_command(mock_cmd_label):
    mock_cmd_label.return_value = 0
    with patch("sys.argv", ["cli.py", "label", "--provider", "gmail"]):
        assert cli.main() == 0
    mock_cmd_label.assert_called_once()
    
@patch("cli.cmd_health")
def test_main_health_command(mock_cmd_health):
    mock_cmd_health.return_value = 0
    with patch("sys.argv", ["cli.py", "health", "--provider", "outlook"]):
        assert cli.main() == 0
    mock_cmd_health.assert_called_once()
    
@patch("cli.cmd_pending")
def test_main_pending_command(mock_cmd_pending):
    mock_cmd_pending.return_value = 0
    with patch("sys.argv", ["cli.py", "pending", "--provider", "imap", "--host", "imap.gmail.com"]):
        assert cli.main() == 0
    mock_cmd_pending.assert_called_once()
