"""Tests for the Stripe billing router (api/billing.py).

The webhook tests exercise the real signature path (bad signature -> 400) and the
event-handling logic (via a monkeypatched construct_event) without any live keys.
"""

import stripe
from fastapi.testclient import TestClient

from api import billing
from api.app import app
from api.store import get_store

client = TestClient(app)


def test_plans_public_no_creds():
    r = client.get("/v1/billing/plans")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["plans"]}
    assert {"free", "pro", "business"} <= ids
    assert r.json()["credit_packs"]


def test_checkout_free_plan_rejected():
    r = client.post("/v1/billing/checkout", json={"plan": "free"})
    assert r.status_code == 400


def test_checkout_unconfigured_is_503(monkeypatch):
    # Pro plan exists but no STRIPE_PRICE_PRO -> billing not configured -> 503.
    monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)
    r = client.post("/v1/billing/checkout", json={"plan": "pro"})
    assert r.status_code == 503


def test_webhook_no_secret_is_503(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = client.post("/v1/billing/webhook", content=b"{}",
                    headers={"stripe-signature": "x"})
    assert r.status_code == 503


def test_webhook_bad_signature_is_400(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    # Real construct_event with a bogus signature must reject (never grant).
    r = client.post("/v1/billing/webhook", content=b'{"id":"evt_1"}',
                    headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert r.status_code == 400


def test_webhook_subscription_event_grants_and_dedups(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")

    store = get_store()
    acct = store.create_account(plan="free")

    event = {
        "id": "evt_sub_1",
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "active",
            "metadata": {"account_id": acct["id"]},
            "current_period_end": 1893456000,
            "items": {"data": [{"price": {"id": "price_pro_test"}}]},
        }},
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event",
                        lambda payload, sig, _whsec: event)

    r = client.post("/v1/billing/webhook", content=b"{}",
                    headers={"stripe-signature": "ok"})
    assert r.status_code == 200 and r.json() == {"received": True}
    got = store.get_account(acct["id"])
    assert got["plan"] == "pro"
    assert got["status"] == "active"
    assert got["stripe_customer_id"] == "cus_1"

    # A redelivery of the same event id is acknowledged but not re-applied.
    r2 = client.post("/v1/billing/webhook", content=b"{}",
                     headers={"stripe-signature": "ok"})
    assert r2.json().get("duplicate") is True


def test_handle_subscription_canceled_drops_to_free():
    store = get_store()
    acct = store.create_account(plan="pro", status="active")
    store.link_customer(acct["id"], "cus_cancel")
    billing._handle_event("customer.subscription.deleted", {
        "id": "sub_2", "customer": "cus_cancel", "status": "canceled",
        "metadata": {"account_id": acct["id"]},
    })
    got = store.get_account(acct["id"])
    assert got["plan"] == "free"
    assert got["status"] == "canceled"


def test_handle_invoice_payment_failed_marks_past_due():
    store = get_store()
    acct = store.create_account(plan="pro", status="active")
    store.link_customer(acct["id"], "cus_pd")
    billing._handle_event("invoice.payment_failed", {"customer": "cus_pd"})
    assert store.get_account(acct["id"])["status"] == "past_due"
