"""Tests for the Agentic Commerce Protocol surface (acp/)."""

import uuid

from fastapi.testclient import TestClient

from acp import API_VERSION, payment
from api.app import app
from api.store import get_store

client = TestClient(app)


def _account_key(key):
    if get_store().get_account_by_api_key(key) is None:
        get_store().create_account(api_key=key)  # allow-secret: test fixture key
    return key


def _headers(idempotent=True, version=API_VERSION, auth="Bearer testkey"):
    h = {"API-Version": version}
    if auth:
        if auth.startswith("Bearer "):
            _account_key(auth[len("Bearer "):])
        h["Authorization"] = auth
    if idempotent:
        h["Idempotency-Key"] = str(uuid.uuid4())
    return h


def _fixed_headers(key="testkey", idem="fixed-idempotency-key"):
    _account_key(key)
    return {
        "API-Version": API_VERSION,
        "Authorization": f"Bearer {key}",
        "Idempotency-Key": idem,
    }


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


def test_gate_rejects_unknown_bearer_without_creating_account():
    r = client.post(
        "/acp/checkout_sessions",
        json={"items": [{"id": "pack_100"}]},
        headers={
            "API-Version": API_VERSION,
            "Authorization": "Bearer unknown-agent-key",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )

    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"
    assert get_store().get_account_by_api_key("unknown-agent-key") is None


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


def test_same_idempotency_key_can_be_reused_across_endpoint_scopes():
    h = _fixed_headers(idem="same-key")
    created = client.post("/acp/checkout_sessions",
                          json={"items": [{"id": "pack_100"}]}, headers=h)
    assert created.status_code == 200
    sid = created.json()["id"]

    # Same caller key on a different endpoint scope must not replay the create
    # response or conflict against it.
    canceled = client.post(f"/acp/checkout_sessions/{sid}/cancel", json={},
                           headers=h)
    assert canceled.status_code == 200
    assert canceled.json()["id"] == sid
    assert canceled.json()["status"] == "canceled"


def test_idempotency_keys_are_isolated_by_bearer_identity():
    h1 = _fixed_headers(key="agent_one", idem="shared-key")
    h2 = _fixed_headers(key="agent_two", idem="shared-key")

    r1 = client.post("/acp/checkout_sessions",
                     json={"items": [{"id": "pack_100"}]}, headers=h1)
    r2 = client.post("/acp/checkout_sessions",
                     json={"items": [{"id": "pack_100"}]}, headers=h2)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]


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


def test_session_access_is_bound_to_bearer_identity():
    owner = _fixed_headers(key="owner")
    intruder = _fixed_headers(key="intruder")
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=owner).json()["id"]

    got = client.get(f"/acp/checkout_sessions/{sid}",
                     headers=_fixed_headers(key="intruder"))
    updated = client.post(f"/acp/checkout_sessions/{sid}",
                          json={"items": [{"id": "pack_1000"}]},
                          headers=intruder)
    canceled = client.post(f"/acp/checkout_sessions/{sid}/cancel", json={},
                           headers=intruder)

    assert got.status_code == 404
    assert updated.status_code == 404
    assert canceled.status_code == 404


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


def test_complete_after_orphan_fulfillment_recovers_order():
    # The U018/U110/U032 crash window: credit applied (fulfill_once) but the
    # process died before the order receipt was minted. The old code returned
    # "already_fulfilled" with NO order and NEVER minted the receipt — a paid
    # purchase permanently unrecorded. A retry must CONVERGE: mint the missing
    # receipt (the deduped charge supplies the original payment_id) without a
    # duplicate credit.
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions", json={"items": [{"id": "pack_100"}]},
                      headers=_headers()).json()["id"]

    store = get_store()
    acct = store.get_account_by_api_key("testkey")
    assert store.fulfill_once(sid, acct["id"], 100) is True

    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_ok"}}, headers=_headers())

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["messages"][0]["code"] == "order_recovered"
    # The order exists now, backed by a real saved receipt.
    order = body["order"]
    assert order["checkout_session_id"] == sid
    receipts_list = store.list_receipts(acct["id"])
    assert [rec["run_id"] for rec in receipts_list] == [order["id"]]
    saved = store.get_receipt(order["id"])
    assert saved["summary"]["checkout_session_id"] == sid
    assert saved["summary"]["payment_id"] == "pi_test_123"
    # No duplicate credit.
    assert store.get_account(acct["id"])["run_credits"] == 100


def test_complete_crash_before_receipt_retry_converges(monkeypatch):
    # Crash injected INSIDE the money path: save_receipt raises on the first
    # attempt (credit already committed by fulfill_once). The first request
    # fails honestly; a client retry with a fresh Idempotency-Key must end in
    # a completed session with exactly one receipt and one credit.
    payment.set_payment_client(_OKPay())
    crash_client = TestClient(app, raise_server_exceptions=False)
    sid = crash_client.post("/acp/checkout_sessions",
                            json={"items": [{"id": "pack_100"}]},
                            headers=_headers()).json()["id"]

    store = get_store()
    real_save = store.save_receipt
    calls = {"n": 0}

    def crashing_save(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated receipts-table outage")
        return real_save(**kwargs)

    monkeypatch.setattr(store, "save_receipt", crashing_save)

    r1 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r1.status_code == 500            # honest failure, money captured

    r2 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "completed"
    assert body["messages"][0]["code"] == "order_recovered"
    acct = store.get_account_by_api_key("testkey")
    assert acct["run_credits"] == 100       # exactly one credit
    assert len(store.list_receipts(acct["id"])) == 1  # exactly one receipt


def test_session_frozen_after_crash_update_and_cancel_refused(monkeypatch):
    # The skeptic's exploit: crash after the charge, UPDATE the session to a
    # bigger pack, retry — the recovered signed receipt would then lie about
    # the captured amount/runs. Once a charge may exist the session is FROZEN:
    # update and cancel are refused, so the retry re-reads exactly the line
    # items the charge was made against.
    payment.set_payment_client(_OKPay())
    crash_client = TestClient(app, raise_server_exceptions=False)
    sid = crash_client.post("/acp/checkout_sessions",
                            json={"items": [{"id": "pack_100"}]},
                            headers=_headers()).json()["id"]

    store = get_store()
    real_save = store.save_receipt
    calls = {"n": 0}

    def crashing_save(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated receipts-table outage")
        return real_save(**kwargs)

    monkeypatch.setattr(store, "save_receipt", crashing_save)
    r1 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r1.status_code == 500

    upd = crash_client.post(f"/acp/checkout_sessions/{sid}",
                            json={"items": [{"id": "pack_1000"}]},
                            headers=_headers())
    assert upd.status_code == 400
    assert upd.json()["code"] == "invalid_state"

    cxl = crash_client.post(f"/acp/checkout_sessions/{sid}/cancel", json={},
                            headers=_headers())
    assert cxl.status_code == 400          # a captured charge cannot be orphaned

    # The only way forward is the retry, which converges honestly: pack_100
    # amounts, exactly one receipt, one credit.
    r2 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "completed"
    acct = store.get_account_by_api_key("testkey")
    saved = store.get_receipt(body["order"]["id"])
    assert saved["summary"]["runs_credited"] == 100
    assert saved["summary"]["amount"] == 100
    assert acct["run_credits"] == 100


def test_session_frozen_even_when_crash_precedes_fulfillment(monkeypatch):
    # Crash BETWEEN the charge and fulfill_once (no fulfillment row yet): the
    # pre-charge marker alone must freeze the session — Stripe may have
    # captured even though no credit landed.
    payment.set_payment_client(_OKPay())
    crash_client = TestClient(app, raise_server_exceptions=False)
    sid = crash_client.post("/acp/checkout_sessions",
                            json={"items": [{"id": "pack_100"}]},
                            headers=_headers()).json()["id"]

    store = get_store()
    real_fulfill = store.fulfill_once
    calls = {"n": 0}

    def crashing_fulfill(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated fulfillment outage")
        return real_fulfill(*args, **kwargs)

    monkeypatch.setattr(store, "fulfill_once", crashing_fulfill)
    r1 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r1.status_code == 500
    assert store.get_fulfillment(sid) is None      # no credit landed

    upd = crash_client.post(f"/acp/checkout_sessions/{sid}",
                            json={"items": [{"id": "pack_1000"}]},
                            headers=_headers())
    assert upd.status_code == 400                  # marker freezes it anyway

    r2 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r2.status_code == 200
    assert r2.json()["status"] == "completed"
    acct = store.get_account_by_api_key("testkey")
    assert acct["run_credits"] == 100              # original pack, once


def test_persist_preserves_freeze_marker_by_default():
    # Defense-in-depth (skeptic finding): _persist writes the whole data dict,
    # so any incidental persist that DEFAULTED charge_attempted to False would
    # silently drop the freeze. The default must PRESERVE the existing marker;
    # only the explicit False of the 402 branch clears it.
    from acp import router as acp_router

    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers()).json()["id"]
    store = get_store()
    row = store.get_session(sid)
    resp = row["data"]["response"]

    acp_router._persist(sid, resp, 100, charge_attempted=True)
    assert store.get_session(sid)["data"]["charge_attempted"] is True

    # An incidental persist with no explicit marker must not unfreeze.
    acp_router._persist(sid, resp, 100)
    assert store.get_session(sid)["data"]["charge_attempted"] is True

    # Only the explicit clear (the 402 branch's call shape) unfreezes.
    acp_router._persist(sid, resp, 100, charge_attempted=False)
    assert store.get_session(sid)["data"]["charge_attempted"] is False


def test_402_unfreezes_session_for_update_and_cancel():
    # A DEFINITIVE charge failure clears the marker: the buyer may fix
    # payment, update items, or cancel — the session is not stuck.
    class _FailPay(payment.PaymentClient):
        configured = True

        def charge(self, *, amount, currency, token, idempotency_key):
            return payment.ChargeResult(ok=False, error="card_declined")

    payment.set_payment_client(_FailPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers()).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_bad"}},
                    headers=_headers())
    assert r.status_code == 402

    upd = client.post(f"/acp/checkout_sessions/{sid}",
                      json={"items": [{"id": "pack_1000"}]},
                      headers=_headers())
    assert upd.status_code == 200                  # mutable again
    cxl = client.post(f"/acp/checkout_sessions/{sid}/cancel", json={},
                      headers=_headers())
    assert cxl.status_code == 200


def test_complete_crash_after_receipt_retry_reattaches_same_order(monkeypatch):
    # Crash AFTER the receipt was saved but before the session persisted as
    # COMPLETED: the retry must reattach the EXISTING receipt (same order id),
    # not mint a second one.
    from acp import router as acp_router

    payment.set_payment_client(_OKPay())
    crash_client = TestClient(app, raise_server_exceptions=False)
    sid = crash_client.post("/acp/checkout_sessions",
                            json={"items": [{"id": "pack_100"}]},
                            headers=_headers()).json()["id"]

    real_persist = acp_router._persist
    state = {"armed": True}

    def crashing_persist(*args, **kwargs):
        if state["armed"] and kwargs.get("account_id") is not None:
            # Only the completion persist (carries account_id) crashes.
            state["armed"] = False
            raise RuntimeError("simulated session-store outage")
        return real_persist(*args, **kwargs)

    monkeypatch.setattr(acp_router, "_persist", crashing_persist)

    r1 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r1.status_code == 500

    store = get_store()
    acct = store.get_account_by_api_key("testkey")
    receipts_before = store.list_receipts(acct["id"])
    assert len(receipts_before) == 1        # receipt DID land before the crash

    r2 = crash_client.post(f"/acp/checkout_sessions/{sid}/complete",
                           json={"payment_data": {"token": "spt_ok"}},
                           headers=_headers())
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "completed"
    # Same order as the saved receipt — reattached, not re-minted.
    assert body["order"]["id"] == receipts_before[0]["run_id"]
    assert len(store.list_receipts(acct["id"])) == 1
    assert store.get_account(acct["id"])["run_credits"] == 100


def test_complete_by_a_different_bearer_is_rejected():
    # The session is bound to its creator's bearer; a DIFFERENT bearer must not be
    # able to complete it (and thereby be credited the runs) — review U010.
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers(auth="Bearer creator-key")).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_ok"}},
                    headers=_headers(auth="Bearer attacker-key"))
    assert r.status_code == 403
    assert r.json()["code"] == "session_owner_mismatch"
    # The rejected attempt credited no one.
    assert get_store().get_account_by_api_key("attacker-key")["run_credits"] == 0


def test_complete_credits_the_creator_bearer():
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers(auth="Bearer buyer-key")).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_ok"}},
                    headers=_headers(auth="Bearer buyer-key"))
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert get_store().get_account_by_api_key("buyer-key")["run_credits"] == 100


def test_owner_binding_survives_update_then_blocks_foreign_complete():
    # The binding must persist through an update (save_session previously could
    # drop it) and still block a foreign completer afterward.
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers(auth="Bearer owner-2")).json()["id"]
    upd = client.post(f"/acp/checkout_sessions/{sid}",
                      json={"items": [{"id": "pack_1000"}]},
                      headers=_headers(auth="Bearer owner-2"))
    assert upd.status_code == 200
    foreign = client.post(f"/acp/checkout_sessions/{sid}/complete",
                          json={"payment_data": {"token": "spt_ok"}},
                          headers=_headers(auth="Bearer someone-else"))
    assert foreign.status_code == 403


def test_complete_by_a_different_bearer_is_rejected():
    # The session is bound to its creator's bearer; a DIFFERENT bearer must not be
    # able to complete it (and thereby be credited the runs) — review U010.
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers(auth="Bearer creator-key")).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_ok"}},
                    headers=_headers(auth="Bearer attacker-key"))
    assert r.status_code == 403
    assert r.json()["code"] == "session_owner_mismatch"
    # The rejected attempt credited no one.
    assert get_store().get_account_by_api_key("attacker-key")["run_credits"] == 0


def test_complete_credits_the_creator_bearer():
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers(auth="Bearer buyer-key")).json()["id"]
    r = client.post(f"/acp/checkout_sessions/{sid}/complete",
                    json={"payment_data": {"token": "spt_ok"}},
                    headers=_headers(auth="Bearer buyer-key"))
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert get_store().get_account_by_api_key("buyer-key")["run_credits"] == 100


def test_owner_binding_survives_update_then_blocks_foreign_complete():
    # The binding must persist through an update (save_session previously could
    # drop it) and still block a foreign completer afterward.
    payment.set_payment_client(_OKPay())
    sid = client.post("/acp/checkout_sessions",
                      json={"items": [{"id": "pack_100"}]},
                      headers=_headers(auth="Bearer owner-2")).json()["id"]
    upd = client.post(f"/acp/checkout_sessions/{sid}",
                      json={"items": [{"id": "pack_1000"}]},
                      headers=_headers(auth="Bearer owner-2"))
    assert upd.status_code == 200
    foreign = client.post(f"/acp/checkout_sessions/{sid}/complete",
                          json={"payment_data": {"token": "spt_ok"}},
                          headers=_headers(auth="Bearer someone-else"))
    assert foreign.status_code == 403


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
