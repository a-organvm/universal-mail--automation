"""Tests for account API-key issuance and verification endpoints."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from api.auth import ISSUER_TOKEN_ENV
from api.app import app
from api.store import get_store

client = TestClient(app)


def test_issue_api_key_requires_configured_issuer(monkeypatch):
    monkeypatch.delenv(ISSUER_TOKEN_ENV, raising=False)

    r = client.post(
        "/v1/auth/api-keys",
        json={"email": "buyer@example.test"},
        headers={"X-UMA-Issuer-Token": "issuer-token"},
    )

    assert r.status_code == 503


def test_issue_api_key_rejects_missing_or_invalid_issuer(monkeypatch):
    monkeypatch.setenv(ISSUER_TOKEN_ENV, "issuer-token")

    missing = client.post("/v1/auth/api-keys", json={"email": "buyer@example.test"})
    wrong = client.post(
        "/v1/auth/api-keys",
        json={"email": "buyer@example.test"},
        headers={"X-UMA-Issuer-Token": "wrong-token"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_issue_api_key_returns_generated_key_and_verify_omits_key(monkeypatch):
    monkeypatch.setenv(ISSUER_TOKEN_ENV, "issuer-token")

    issued = client.post(
        "/v1/auth/api-keys",
        json={"email": "buyer@example.test", "plan": "pro", "run_credits": 3},
        headers={"X-UMA-Issuer-Token": "issuer-token"},
    )

    assert issued.status_code == 200
    body = issued.json()
    assert body["account_id"].startswith("acct_")
    assert body["api_key"].startswith("uma_")
    assert body["email"] == "buyer@example.test"
    assert body["plan"] == "pro"
    assert body["run_credits"] == 3

    account = get_store().get_account(body["account_id"])
    assert account["api_key"] == body["api_key"]

    verified = client.get(
        "/v1/auth/verify",
        headers={"Authorization": f"Bearer {body['api_key']}"},
    )

    assert verified.status_code == 200
    verified_body = verified.json()
    assert verified_body["authenticated"] is True
    assert verified_body["account_id"] == body["account_id"]
    assert verified_body["plan"] == "pro"
    assert verified_body["entitlements"]["providers"] == "all"
    assert "api_key" not in verified_body


def test_issue_api_key_rejects_unknown_plan(monkeypatch):
    monkeypatch.setenv(ISSUER_TOKEN_ENV, "issuer-token")

    r = client.post(
        "/v1/auth/api-keys",
        json={"plan": "enterprise-plus"},
        headers={"X-UMA-Issuer-Token": "issuer-token"},
    )

    assert r.status_code == 400


def test_verify_rejects_missing_and_unknown_bearer():
    missing = client.get("/v1/auth/verify")
    unknown = client.get(
        "/v1/auth/verify",
        headers={"Authorization": "Bearer uma_unknown"},
    )

    assert missing.status_code == 401
    assert unknown.status_code == 401
