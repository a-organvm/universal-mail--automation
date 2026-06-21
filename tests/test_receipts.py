"""Tests for signed receipts + the GET /v1/audit/{run_id} endpoint."""

from fastapi.testclient import TestClient

from api import receipts, service
from api.app import app

client = TestClient(app)


def test_sign_then_verify_roundtrip():
    body = {"run_id": "r1", "summary": {"total": 1}}
    sig = receipts.sign(body)
    assert receipts.verify(body, sig) is True
    # Tampering with the body invalidates the signature.
    body["summary"]["total"] = 2
    assert receipts.verify(body, sig) is False


class _FakeProvider:
    name = "fake"

    def connect(self):
        pass

    def disconnect(self):
        pass


def test_triage_persists_retrievable_signed_receipt(monkeypatch):
    def _fake_run_labeler(provider, *, query, limit, dry_run, remove_label,
                          state_file, tier_routing, vip_only, audit):
        audit.record(message_id="p1", sender="clerk@courts.ca.gov",
                     protected=True, archived=False)
        audit.record(message_id="n1", sender="news@deals-promo.example",
                     protected=False, archived=True)
        return {"processed_count": 2}

    monkeypatch.setattr(service, "run_labeler", _fake_run_labeler)
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _FakeProvider())

    r = client.post("/v1/triage/preview", json={"provider": "fake"})
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    assert run_id and run_id.startswith("run_")

    # The receipt is retrievable and its signature verifies over the signed body.
    rr = client.get(f"/v1/audit/{run_id}")
    assert rr.status_code == 200
    rec = rr.json()
    assert rec["algorithm"] == "HMAC-SHA256"
    assert receipts.verify(rec["signed_body"], rec["signature"]) is True
    assert rec["signed_body"]["summary"]["protected_held"] == 1


def test_unknown_receipt_is_404():
    assert client.get("/v1/audit/run_does_not_exist").status_code == 404
