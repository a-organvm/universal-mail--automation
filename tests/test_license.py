"""Tests for HMAC license validation and CLI tier gates."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import sys
from datetime import datetime, timezone

import pytest

import cli
from cli import enforce_cli_license
from core.license import (
    DEFAULT_PRODUCT_ID,
    FREE_DAILY_MESSAGE_CAP,
    FREE_LICENSE,
    LicenseError,
    load_license_from_env,
    make_license_key,
    validate_license_key,
)

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def test_validate_generated_pro_license():
    key = make_license_key(
        email="Buyer@Example.test",
        tier="pro",
        expiry="2099-01-01",
        secret="test-secret",
    )

    license = validate_license_key(key, "test-secret", now=NOW)

    assert license.product_id == DEFAULT_PRODUCT_ID
    assert license.email == "buyer@example.test"
    assert license.tier == "pro"
    assert license.allowed_providers is None
    assert license.daily_message_cap is None


def test_validate_pipe_delimited_hex_signature():
    payload = f"{DEFAULT_PRODUCT_ID}|buyer@example.test|free|2099-01-01"
    signature = hmac.new(
        b"test-secret", payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    license = validate_license_key(f"{payload}|{signature}", "test-secret", now=NOW)

    assert license.tier == "free"
    assert license.allowed_providers == {"gmail"}
    assert license.daily_message_cap == FREE_DAILY_MESSAGE_CAP


def test_validate_plus_delimited_signature():
    payload = f"{DEFAULT_PRODUCT_ID}+buyer@example.test+free+2099-01-01"
    signature = hmac.new(
        b"test-secret", payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    license = validate_license_key(f"{payload}+{signature}", "test-secret", now=NOW)

    assert license.tier == "free"


def test_rejects_bad_signature():
    key = make_license_key(
        email="buyer@example.test",
        tier="pro",
        expiry="2099-01-01",
        secret="test-secret",
    )

    with pytest.raises(LicenseError, match="signature"):
        validate_license_key(key, "wrong-secret", now=NOW)


def test_rejects_expired_license():
    key = make_license_key(
        email="buyer@example.test",
        tier="pro",
        expiry="2020-01-01",
        secret="test-secret",
    )

    with pytest.raises(LicenseError, match="expired"):
        validate_license_key(key, "test-secret", now=NOW)


def test_load_license_without_key_defaults_to_free():
    license = load_license_from_env({}, now=NOW)

    assert license == FREE_LICENSE


def test_free_cli_gate_rejects_non_gmail_provider():
    args = argparse.Namespace(provider="outlook", limit=10)

    with pytest.raises(LicenseError, match="requires a pro license"):
        enforce_cli_license(args, FREE_LICENSE)


def test_free_cli_gate_caps_message_limit():
    args = argparse.Namespace(provider="gmail", limit=250)

    enforce_cli_license(args, FREE_LICENSE)

    assert args.limit == FREE_DAILY_MESSAGE_CAP


def test_main_applies_free_limit_before_command(monkeypatch):
    seen = {}

    def fake_label(args):
        seen["limit"] = args.limit
        return 0

    monkeypatch.setattr(cli, "cmd_label", fake_label)
    monkeypatch.setattr(cli, "load_license_from_env", lambda: FREE_LICENSE)
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "label", "--provider", "gmail", "--limit", "250", "--dry-run"],
    )

    assert cli.main() == 0
    assert seen["limit"] == FREE_DAILY_MESSAGE_CAP


def test_main_rejects_free_non_gmail_before_command(monkeypatch):
    called = False

    def fake_health(_args):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(cli, "cmd_health", fake_health)
    monkeypatch.setattr(cli, "load_license_from_env", lambda: FREE_LICENSE)
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "health", "--provider", "outlook"],
    )

    assert cli.main() == 2
    assert called is False
