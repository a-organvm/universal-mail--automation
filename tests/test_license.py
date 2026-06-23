"""Tests for HMAC license validation and CLI tier gates."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import sys
from datetime import datetime, timezone

import pytest

import cli
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


