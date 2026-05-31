"""Tests for the Agentic Commerce Protocol surface (acp/)."""

import uuid

from fastapi.testclient import TestClient

from acp import API_VERSION, payment
from api.app import app
from api.store import get_store

client = TestClient(app)


def _headers(idempotent=True, version=API_VERSION, auth="Bearer testkey"):
    h = {"API-Version": version}
    if auth:
        h["Authorization"] = auth
    if idempotent:
        h["Idempotency-Key"] = str(uuid.uuid4())
    return h


class _OKPay(payment.PaymentClient):
    configured = True

    def charge(self, *, amount, currency, token, idempotency_key):
        return payment.ChargeResult(ok=True, payment_id="pi_test_123")


# -- gate -------------------------------------------------------------------
def test_gate_wrong_api_version():
    r = client.post("/acp/checkout_sessions", json={"items": []},
                    headers=_headers(version="1999-01-01"))
    assert r.status_code == 400
    assert r.json()["code"] == "unsupported_api_version"


def test_gate_missing_auth():
    r = client.post("/acp/checkout_sessions", json={"items": []},
                    headers=_headers(auth=None))
    assert r.status_code == 401


def test_gate_missing_idempotency_key():
    r = client.post("/acp/checkout_sessions", json={"items": []},
                    headers=_headers(idempotent=False))
    assert r.status_code == 400
    assert r.json()["param"] == "Idempotency-Key"


# -- create / shape ---------------------------------------------------------
def test_create_valid_pack_ready_for_payment():
    r = client.post("/acp/checkout_sessions",
                    json={"items": [{"id": "pack_100", "quantity": 1}]},
                    headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready_for_payment"
    assert body["line_items"][0]["total"] == 100
    assert body["fulfillment_options"]  # digital option returned, not omitted
    assert {link["type"] for link in body["links"]} == {"terms_of_use",
                                                         "privacy_policy"}


def test_create_invalid_item_not_ready():
    r = client.post("/acp/checkout_sessions",
                    json={"items": [{"id": "no_such_pack"}]}, headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "not_ready_for_payment"
    assert r.json()["messages"][0]["code"] == "invalid_items"


# -- idempotency ------------------------------------------------------------
def test_idempotent_replay_returns_same_session():
    h = _headers()
    payload = {"items": [{"id": "pack_100"}]}
    r1 = client.post("/acp/checkout_sessions", json=payload, headers=h)
    r2 = client.post("/acp/checkout_sessions", json=payload, headers=h)
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.headers.get("Idempotent-Replayed") == "true"


def test_idempotency_conflict_same_key_different_body():
    h = _headers()
    client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                headers=h)
    r = client.post("/acp/checkout_sessions",
                    json={"items": [{"id": "pack_1000"}]}, headers=h)
    assert r.status_code == 422
    assert r.json()["code"] == "idempotency_conflict"


# -- retrieve ---------------------------------------------------------------
def test_get_session_and_404():
    r = client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                    headers=_headers())
    sid = r.json()["id"]
    got = client.get(f"/acp/checkout_sessions/{sid}", headers=_headers(idempotent=False))
    assert got.status_code == 200 and got.json()["id"] == sid
    missing = client.get("/acp/checkout_sessions/acp_cs_nope",
                         headers=_headers(idempotent=False))
    assert missing.status_code == 404


# -- complete ---------------------------------------------------------------
def test_complete_without_payment_configured_is_402():
    # Default (no STRIPE key) -> NullPaymentClient refuses -> session stays ready.
    payment.set_payment_client(None)
    sid = client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                      headers=_headers()).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_x"}}, headers=_headers())
    assert r.status_code == 402
    assert r.json()["messages"][0]["code"] == "payment_failed"


def test_complete_success_credits_and_emits_signed_order_receipt():
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100", "quantity": 2}]},
                      headers=_headers()).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_ok"}}, headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    order = body["order"]
    assert order["checkout_session_id"] == sid
    assert order["permalink_url"].endswith(f"/v1/audit/{order['id']}")

    # 2 x pack_100 = 200 runs credited to the buyer (keyed by api_key 'testkey').
    acct = get_store().get_account_by_api_key("testkey")
    assert acct["run_credits"] == 200

    # The order receipt is a real, retrievable signed receipt.
    rec = client.get(order["permalink_url"].split(str(client.base_url).rstrip("/"))[-1])
    assert rec.status_code == 200
    assert rec.json()["signed_body"]["summary"]["runs_credited"] == 200


def test_complete_is_idempotent_no_double_credit():
    # Completing the same session twice (even with a fresh Idempotency-Key) must
    # not re-charge or double-credit — the session-status guard + fulfill_once.
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                      headers=_headers()).json()["id"]
    r1 = client.post(f"/acp/checkout_sessions/{sid}/complete",
                     json={"payment_data": {"token": "spt_ok"}}, headers=_headers())
    assert r1.json()["status"] == "completed"
    r2 = client.post(f"/acp/checkout_sessions/{sid}/complete",
                     json={"payment_data": {"token": "spt_ok"}}, headers=_headers())
    assert r2.json()["status"] == "completed"
    assert get_store().get_account_by_api_key("testkey")["run_credits"] == 100


def test_cancel_then_cannot_cancel_completed():
    # Cancel a fresh session.
    sid = client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                      headers=_headers()).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/cancel", json={}, headers=_headers())
    assert r.status_code == 200 and r.json()["status"] == "canceled"

    # Complete a different session, then cancel must fail.
    payment.set_payment_client(_OKPay())
    sid2 = client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                       headers=_headers()).json()["id"]
    client.post(f"/acp/checkout_sessions/{sid2}/complete",
                json={"payment_data": {"token": "spt_ok"}}, headers=_headers())
    r2 = client.post(f"/acp/checkout_sessions/{sid2}/cancel", json={},
                     headers=_headers())
    assert r2.status_code == 400
