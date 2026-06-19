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


class _Session:
    id = "cs_test_123"
    url = "https://stripe.example/session"


class _CheckoutSessions:
    def __init__(self):
        self.params = None

    def create(self, *, params):
        self.params = params
        return _Session()


class _PortalSessions:
    def __init__(self):
        self.params = None

    def create(self, *, params):
        self.params = params
        return _Session()


class _Client:
    def __init__(self):
        self.checkout_sessions = _CheckoutSessions()
        self.portal_sessions = _PortalSessions()

        class _Checkout:
            sessions = self.checkout_sessions

        class _BillingPortal:
            sessions = self.portal_sessions

        class _V1:
            checkout = _Checkout()
            billing_portal = _BillingPortal()

        self.v1 = _V1()


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


def test_checkout_existing_account_requires_bearer(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")
    store = get_store()
    acct = store.create_account(plan="free")

    r = client.post(
        "/v1/billing/checkout",
        json={"plan": "pro", "account_id": acct["id"]},
    )

    assert r.status_code == 401


def test_checkout_existing_account_requires_matching_bearer(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")
    store = get_store()
    target = store.create_account(plan="free")
    other = store.create_account(plan="free")

    r = client.post(
        "/v1/billing/checkout",
        json={"plan": "pro", "account_id": target["id"]},
        headers={"Authorization": f"Bearer {other['api_key']}"},
    )

    assert r.status_code == 403


def test_checkout_authenticated_account_reuses_existing_account(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")
    fake = _Client()
    monkeypatch.setattr(billing, "_client", lambda: fake)
    acct = get_store().create_account(plan="free")

    r = client.post(
        "/v1/billing/checkout",
        json={"plan": "pro", "account_id": acct["id"]},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 200
    assert r.json()["account_id"] == acct["id"]
    assert "account_api_key" not in r.json()
    assert fake.checkout_sessions.params["client_reference_id"] == acct["id"]


def test_checkout_new_account_returns_generated_key(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")
    fake = _Client()
    monkeypatch.setattr(billing, "_client", lambda: fake)

    r = client.post(
        "/v1/billing/checkout",
        json={"plan": "pro", "email": "buyer@example.test"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["account_id"].startswith("acct_")
    assert body["account_api_key"].startswith("uma_")
    account = get_store().get_account(body["account_id"])
    assert account["api_key"] == body["account_api_key"]
    assert fake.checkout_sessions.params["client_reference_id"] == body["account_id"]


def test_portal_requires_bearer_even_with_customer_id(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")

    r = client.post(
        "/v1/billing/portal",
        json={"customer_id": "cus_known"},
    )

    assert r.status_code == 401


def test_portal_rejects_customer_mismatch(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    store = get_store()
    acct = store.create_account(plan="pro")
    store.link_customer(acct["id"], "cus_owned")

    r = client.post(
        "/v1/billing/portal",
        json={"customer_id": "cus_other"},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 403


def test_portal_opens_for_authorized_account_customer(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    fake = _Client()
    monkeypatch.setattr(billing, "_client", lambda: fake)
    store = get_store()
    acct = store.create_account(plan="pro")
    store.link_customer(acct["id"], "cus_owned")

    r = client.post(
        "/v1/billing/portal",
        json={"account_id": acct["id"]},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 200
    assert r.json()["url"] == _Session.url
    assert fake.portal_sessions.params["customer"] == "cus_owned"


def test_usage_requires_bearer():
    assert client.get("/v1/billing/usage").status_code == 401


def test_usage_reports_consumption_and_headroom():
    from api import metering

    store = get_store()
    acct = store.create_account(plan="free")  # cap 50, gmail only
    period = metering.current_period_key()
    # Consume three live runs this period.
    for _ in range(3):
        store.reserve_live_run(acct["id"], period, 50)

    r = client.get(
        "/v1/billing/usage",
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["plan"] == "free"
    assert body["period"] == period
    assert body["live_runs_used"] == 3
    assert body["monthly_run_cap"] == 50
    assert body["monthly_runs_remaining"] == 47
    assert body["runs_remaining"] == 47
    assert body["unlimited"] is False
    assert body["near_limit"] is False
    assert body["at_limit"] is False
    assert "upgrade" not in body


def test_usage_credits_extend_total_headroom():
    store = get_store()
    acct = store.create_account(plan="free", run_credits=10)
    r = client.get(
        "/v1/billing/usage",
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )
    body = r.json()
    assert body["run_credits"] == 10
    assert body["monthly_runs_remaining"] == 50
    assert body["runs_remaining"] == 60  # monthly allowance + prepaid credits


def test_usage_near_limit_nudges_to_next_paid_plan():
    from api import metering

    store = get_store()
    acct = store.create_account(plan="free")
    period = metering.current_period_key()
    for _ in range(45):  # 45/50 == 90% -> past the 80% nudge threshold
        store.reserve_live_run(acct["id"], period, 50)

    body = client.get(
        "/v1/billing/usage",
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    ).json()
    assert body["near_limit"] is True
    assert body["at_limit"] is False
    assert body["upgrade"]["id"] == "pro"


def test_usage_at_limit_is_flagged():
    from api import metering

    store = get_store()
    acct = store.create_account(plan="free")
    period = metering.current_period_key()
    for _ in range(50):  # cap fully consumed, no credits
        store.reserve_live_run(acct["id"], period, 50)

    body = client.get(
        "/v1/billing/usage",
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    ).json()
    assert body["at_limit"] is True
    assert body["monthly_runs_remaining"] == 0
    assert body["runs_remaining"] == 0
    assert body["upgrade"]["id"] == "pro"


def test_usage_unlimited_plan_has_no_cap_and_no_upgrade():
    store = get_store()
    acct = store.create_account(plan="business", status="active")
    body = client.get(
        "/v1/billing/usage",
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    ).json()
    assert body["plan"] == "business"
    assert body["unlimited"] is True
    assert body["monthly_run_cap"] is None
    assert body["monthly_runs_remaining"] is None
    assert body["runs_remaining"] is None
    assert body["near_limit"] is False
    assert body["at_limit"] is False
    assert "upgrade" not in body


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


def test_webhook_handler_failure_not_marked_and_redelivery_grants(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")

    store = get_store()
    acct = store.create_account(plan="free")

    event = {
        "id": "evt_retry_1",
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_retry",
            "customer": "cus_retry",
            "status": "active",
            "metadata": {"account_id": acct["id"]},
            "items": {"data": [{"price": {"id": "price_pro_test"}}]},
        }},
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event",
                        lambda payload, sig, _whsec: event)

    original = billing._handle_event
    calls = {"n": 0}

    def flaky_handle(event_type, obj):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient grant failure")
        return original(event_type, obj)

    monkeypatch.setattr(billing, "_handle_event", flaky_handle)

    r = client.post("/v1/billing/webhook", content=b"{}",
                    headers={"stripe-signature": "ok"})
    assert r.status_code == 500
    assert store.is_event_processed("evt_retry_1") is False
    assert store.get_account(acct["id"])["plan"] == "free"

    r2 = client.post("/v1/billing/webhook", content=b"{}",
                     headers={"stripe-signature": "ok"})
    assert r2.status_code == 200
    assert store.is_event_processed("evt_retry_1") is True
    assert store.get_account(acct["id"])["plan"] == "pro"


def test_checkout_session_completed_sets_plan_from_metadata():
    store = get_store()
    acct = store.create_account(plan="free", status="active")

    billing._handle_event("checkout.session.completed", {
        "client_reference_id": acct["id"],
        "customer": "cus_checkout",
        "subscription": "sub_checkout",
        "metadata": {"plan": "pro"},
    })

    got = store.get_account(acct["id"])
    assert got["plan"] == "pro"
    assert got["status"] == "active"
    assert got["stripe_customer_id"] == "cus_checkout"


def test_resolve_account_prefers_existing_customer_mapping():
    store = get_store()
    mapped = store.create_account(plan="pro")
    store.link_customer(mapped["id"], "cus_conflict")
    stale_meta = store.create_account(plan="free")

    resolved = billing._resolve_account(stale_meta["id"], "cus_conflict")

    assert resolved == mapped["id"]


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
