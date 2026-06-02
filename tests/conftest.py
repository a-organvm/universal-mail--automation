"""Shared test fixtures for mail automation tests."""

import os
import json
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

# Ensure we're in the project root so core imports work
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import EmailMessage, LabelAction, ProcessingResult
from core.state import StateManager
from core.rules import VIP_SENDERS

from api import store as _store_mod


@pytest.fixture(autouse=True)
def isolated_commerce_store(tmp_path, monkeypatch):
    """Give every test a fresh, throwaway SQLite store (never the real data/app.db)
    and reset injected singletons (store + ACP payment client) so commerce tests
    don't bleed state into each other."""
    monkeypatch.setenv("MAIL_DB_PATH", str(tmp_path / "test_app.db"))
    _store_mod.set_store(None)
    try:
        from acp import payment as _payment_mod
        _payment_mod.set_payment_client(None)
    except Exception:
        _payment_mod = None
    yield
    _store_mod.set_store(None)
    if _payment_mod is not None:
        _payment_mod.set_payment_client(None)


@pytest.fixture
def sample_email():
    """A basic EmailMessage for testing."""
    return EmailMessage(
        id="msg001",
        sender="notifications@github.com",
        subject="[repo] New pull request #42",
        date=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def finance_email():
    """An email from a financial institution."""
    return EmailMessage(
        id="msg002",
        sender="alerts@chase.com",
        subject="Your statement is ready",
        date=datetime(2026, 1, 14, 8, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def marketing_email():
    """A marketing/newsletter email."""
    return EmailMessage(
        id="msg003",
        sender="deals@store.com",
        subject="Special offer: 50% discount today only!",
        date=datetime(2026, 1, 13, 12, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def security_email():
    """A security alert email."""
    return EmailMessage(
        id="msg004",
        sender="noreply@1password.com",
        subject="New device login detected",
        date=datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
    )


@pytest.fixture
def tmp_state_file(tmp_path):
    """Provide a temporary file path for state persistence."""
    return str(tmp_path / "test_state.json")


@pytest.fixture
def state_manager(tmp_state_file):
    """A fresh StateManager using a temp file."""
    return StateManager(tmp_state_file)


@pytest.fixture
def populated_state(tmp_path):
    """A StateManager with pre-populated state."""
    path = str(tmp_path / "populated_state.json")
    data = {
        "next_page_token": "TOKEN123",
        "total_processed": 42,
        "history": {"Dev/GitHub": 10, "Finance/Banking": 5, "Misc/Other": 27},
        "last_run": "2026-01-15T10:00:00",
        "provider": "gmail",
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return StateManager(path)


@pytest.fixture(autouse=True)
def clean_vip_senders():
    """Ensure VIP_SENDERS is clean before/after each test."""
    original = dict(VIP_SENDERS)
    VIP_SENDERS.clear()
    VIP_SENDERS.update(original)
    yield
    VIP_SENDERS.clear()
    VIP_SENDERS.update(original)


@pytest.fixture
def tmp_yaml_config(tmp_path):
    """Create a temporary YAML config file."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""\
default_provider: outlook
log_level: DEBUG
batch_size: 50
throttle_seconds: 0.5

gmail:
  enabled: true
  default_query: "label:INBOX"
  state_file: "custom_gmail_state.json"

imap:
  host: imap.custom.com
  port: 143
  use_gmail_extensions: true

outlook:
  enabled: true
  client_id: "test-client-id-123"

vip_senders:
  "boss@company.com":
    pattern: "boss@company\\\\.com"
    tier: 1
    star: true
    note: "The Boss"
""")
    return config_path
