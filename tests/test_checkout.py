"""Tests for the license-issued webhook receiver (platform/checkout.py).

The receiver is loaded by file path rather than ``import platform.checkout`` so
the test never binds the local ``platform`` package over Python's stdlib
``platform`` module for the rest of the process.

Coverage: constant-time signature verification, atomic 0600 license write, and
the fail-closed route contract (503 unconfigured, 400 unverified/unparseable with
nothing written, 200 + persisted license on a verified body).
"""

import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_HERE = Path(__file__).resolve().parent
_MODULE_PATH = _HERE.parent / "platform" / "checkout.py"

_spec = importlib.util.spec_from_file_location("platform_checkout", _MODULE_PATH)
checkout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checkout)

SECRET = "s3cr3t-shared"
BODY = json.dumps({"license_key": "ABC-123", "plan": "pro", "seats": 3}).encode()
GOOD_SIG = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()


# -- pure helpers -----------------------------------------------------------
def test_verify_signature_accepts_matching_hmac():
    assert checkout.verify_signature(SECRET, BODY, GOOD_SIG) is True


@pytest.mark.parametrize(
    "secret,body,sig",
    [
        (SECRET, BODY, None),                # missing
        (SECRET, BODY, "deadbeef"),          # wrong digest
        (SECRET, BODY + b"x", GOOD_SIG),     # tampered body
        ("wrong-secret", BODY, GOOD_SIG),    # wrong key
    ],
)
def test_verify_signature_rejects(secret, body, sig):
    assert checkout.verify_signature(secret, body, sig) is False


def test_write_license_is_atomic_and_owner_only(tmp_path):
    target = tmp_path / "nested" / "license.json"
    written = checkout.write_license({"license_key": "ABC-123"}, target)
    assert written == target
    assert json.loads(target.read_text())["license_key"] == "ABC-123"
    assert oct(target.stat().st_mode & 0o777) == "0o600"


# -- route contract ---------------------------------------------------------
@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Redirect the default license path into a temp HOME.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        checkout, "DEFAULT_LICENSE_PATH", tmp_path / ".config/mail_automation/license.json"
    )
    monkeypatch.delenv(checkout.SECRET_ENV, raising=False)
    app = FastAPI()
    app.include_router(checkout.router)
    return TestClient(app, raise_server_exceptions=True)


def _post(client, body=BODY, sig=GOOD_SIG, header="x-signature-256", prefix="sha256="):
    headers = {}
    if sig is not None:
        headers[header] = f"{prefix}{sig}"
    return client.post("/webhook/license-issued", content=body, headers=headers)


def test_unconfigured_returns_503_and_writes_nothing(client, monkeypatch, tmp_path):
    r = _post(client)
    assert r.status_code == 503
    assert not checkout.DEFAULT_LICENSE_PATH.exists()


def test_bad_signature_returns_400_and_writes_nothing(client, monkeypatch):
    monkeypatch.setenv(checkout.SECRET_ENV, SECRET)
    r = _post(client, sig="deadbeef")
    assert r.status_code == 400
    assert not checkout.DEFAULT_LICENSE_PATH.exists()


def test_missing_signature_returns_400(client, monkeypatch):
    monkeypatch.setenv(checkout.SECRET_ENV, SECRET)
    r = _post(client, sig=None)
    assert r.status_code == 400


def test_verified_but_unparseable_returns_400(client, monkeypatch):
    monkeypatch.setenv(checkout.SECRET_ENV, SECRET)
    bad = b"not json"
    sig = hmac.new(SECRET.encode(), bad, hashlib.sha256).hexdigest()
    r = _post(client, body=bad, sig=sig)
    assert r.status_code == 400
    assert not checkout.DEFAULT_LICENSE_PATH.exists()


def test_verified_payload_must_be_object(client, monkeypatch):
    monkeypatch.setenv(checkout.SECRET_ENV, SECRET)
    arr = b"[1, 2, 3]"
    sig = hmac.new(SECRET.encode(), arr, hashlib.sha256).hexdigest()
    r = _post(client, body=arr, sig=sig)
    assert r.status_code == 400


def test_verified_body_persists_license_and_returns_200(client, monkeypatch):
    monkeypatch.setenv(checkout.SECRET_ENV, SECRET)
    r = _post(client)
    assert r.status_code == 200
    assert r.json() == {"received": True}
    saved = json.loads(checkout.DEFAULT_LICENSE_PATH.read_text())
    assert saved["plan"] == "pro" and saved["seats"] == 3
    assert oct(checkout.DEFAULT_LICENSE_PATH.stat().st_mode & 0o777) == "0o600"


def test_alias_header_and_bare_hex_accepted(client, monkeypatch):
    monkeypatch.setenv(checkout.SECRET_ENV, SECRET)
    r = _post(client, header="x-license-signature", prefix="")
    assert r.status_code == 200
    assert checkout.DEFAULT_LICENSE_PATH.exists()
