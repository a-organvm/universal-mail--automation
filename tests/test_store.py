"""Tests for the durable identity + ledger store (api/store.py)."""

from api.store import Store


def _store():
    # In-memory store: one connection, isolated per test.
    return Store(":memory:")


def test_account_create_and_lookup():
    s = _store()
    acct = s.create_account(email="a@example.com", plan="free")
    assert acct["id"].startswith("acct_")
    assert acct["api_key"].startswith("uma_")
    assert s.get_account(acct["id"])["email"] == "a@example.com"
    assert s.get_account_by_api_key(acct["api_key"])["id"] == acct["id"]
    assert s.get_account_by_api_key("nope") is None


def test_set_subscription_partial_update_does_not_clobber():
    s = _store()
    acct = s.create_account(plan="free")
    s.set_subscription(account_id=acct["id"], customer_id="cus_1",
                       plan="pro", status="active", current_period_end=123)
    # A later partial event (only status) must not wipe plan/customer.
    s.set_subscription(account_id=acct["id"], status="past_due")
    got = s.get_account(acct["id"])
    assert got["plan"] == "pro"
    assert got["stripe_customer_id"] == "cus_1"
    assert got["status"] == "past_due"
    assert got["current_period_end"] == 123


def test_credits_atomic_no_overdraw():
    s = _store()
    acct = s.create_account()
    assert s.add_credits(acct["id"], 5) == 5
    assert s.consume_credit(acct["id"], 3) is True
    assert s.get_account(acct["id"])["run_credits"] == 2
    # Cannot consume more than the balance.
    assert s.consume_credit(acct["id"], 5) is False
    assert s.get_account(acct["id"])["run_credits"] == 2


def test_webhook_event_dedup():
    s = _store()
    assert s.mark_event_processed("evt_1", "checkout.session.completed") is True
    # Redelivery of the same id is detected and must be skipped.
    assert s.mark_event_processed("evt_1", "checkout.session.completed") is False


def test_receipt_round_trip():
    s = _store()
    s.save_receipt(run_id="run_x", summary={"total": 2, "violations": []},
                   provider="gmail", dry_run=True, receipt_line="ok",
                   signature="deadbeef", account_id=None)
    rec = s.get_receipt("run_x")
    assert rec["summary"]["total"] == 2
    assert rec["dry_run"] is True
    assert rec["signature"] == "deadbeef"
    assert s.get_receipt("missing") is None


def test_idempotency_state_machine():
    s = _store()
    # First claim -> new.
    assert s.idempotency_begin("k1", "acp.create", "hashA")["state"] == "new"
    # Same key, still processing -> processing.
    assert s.idempotency_begin("k1", "acp.create", "hashA")["state"] == "processing"
    # Same key, different payload -> conflict.
    assert s.idempotency_begin("k1", "acp.create", "hashB")["state"] == "conflict"
    # Complete then replay returns the stored response.
    s.idempotency_complete("k1", {"ok": True})
    replay = s.idempotency_begin("k1", "acp.create", "hashA")
    assert replay["state"] == "replay"
    assert replay["response"] == {"ok": True}


def test_fulfill_once_credits_exactly_once():
    s = _store()
    acct = s.create_account()
    assert s.fulfill_once("acp_1", acct["id"], 100) is True
    assert s.get_account(acct["id"])["run_credits"] == 100
    # A replayed / concurrent second fulfillment of the same session must NOT
    # double-credit.
    assert s.fulfill_once("acp_1", acct["id"], 100) is False
    assert s.get_account(acct["id"])["run_credits"] == 100


def test_idempotency_stale_processing_is_reclaimed():
    s = _store()
    assert s.idempotency_begin("k", "scope", "hA")["state"] == "new"
    # Simulate a crash: age the 'processing' row past the timeout window.
    s._conn.execute("UPDATE idempotency_keys SET created_at = 0 WHERE key = ?", ("k",))
    s._conn.commit()
    # A retry reclaims the key instead of being locked out forever (no DoS).
    assert s.idempotency_begin("k", "scope", "hB")["state"] == "new"


def test_session_round_trip():
    s = _store()
    s.save_session(session_id="acp_1", status="ready_for_payment", currency="usd",
                   data={"response": {"id": "acp_1"}, "total_runs": 100})
    got = s.get_session("acp_1")
    assert got["status"] == "ready_for_payment"
    assert got["data"]["total_runs"] == 100
    assert s.get_session("nope") is None
