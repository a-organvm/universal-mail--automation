"""API tests, including the fail-closed safety invariant at the HTTP boundary."""

from fastapi.testclient import TestClient

from api import service
from api.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "universal-mail-automation"


def test_sender_check_gov_protected():
    r = client.post("/v1/senders/check", json={"sender": "clerk@courts.ca.gov"})
    assert r.status_code == 200
    assert r.json()["protected"] is True


def test_sender_check_financial_protected():
    r = client.post("/v1/senders/check", json={"sender": "alerts@chase.com"})
    assert r.status_code == 200
    assert r.json()["protected"] is True


def test_sender_check_not_protected():
    r = client.post(
        "/v1/senders/check", json={"sender": "newsletter@deals-promo.example"}
    )
    assert r.status_code == 200
    assert r.json()["protected"] is False


class _FakeProvider:
    name = "fake"

    def connect(self):
        pass

    def disconnect(self):
        pass


def test_triage_fail_closed_on_violation(monkeypatch):
    """The API must return 500 (not 200) if the audit trail proves a protected
    sender left the inbox — even if some upstream code reported it as archived."""

    def _fake_run_labeler(
        provider, *, query, limit, dry_run, remove_label, state_file,
        tier_routing, vip_only, audit,
    ):
        # Simulate a gate failure: a .gov sender observed leaving the inbox.
        audit.record(
            message_id="m1", sender="clerk@courts.ca.gov",
            protected=False, archived=True,
        )
        return {"processed_count": 1}

    monkeypatch.setattr(service, "run_labeler", _fake_run_labeler)
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _FakeProvider())

    r = client.post("/v1/triage", json={"provider": "fake", "dry_run": False})
    assert r.status_code == 500
    assert "GATE VIOLATION" in r.json()["detail"]


def test_triage_clean_run_summary(monkeypatch):
    """A clean run: protected sender held, newsletter archived, no violations."""

    def _fake_run_labeler(
        provider, *, query, limit, dry_run, remove_label, state_file,
        tier_routing, vip_only, audit,
    ):
        audit.record(
            message_id="p1", sender="clerk@courts.ca.gov",
            protected=True, archived=False,
        )
        audit.record(
            message_id="n1", sender="newsletter@deals-promo.example",
            protected=False, archived=True,
        )
        return {"processed_count": 2}

    monkeypatch.setattr(service, "run_labeler", _fake_run_labeler)
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _FakeProvider())

    r = client.post("/v1/triage/preview", json={"provider": "fake"})
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert body["audit"]["protected_held"] == 1
    assert body["audit"]["archived"] == 1
    assert body["audit"]["violations"] == []
    assert "receipt" in body and body["receipt"]


def test_triage_provider_unavailable(monkeypatch):
    """A provider that fails to connect maps to 503, not a 500."""

    class _BadProvider:
        name = "bad"

        def connect(self):
            raise RuntimeError("no credentials configured")

        def disconnect(self):
            pass

    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _BadProvider())
    r = client.post("/v1/triage", json={"provider": "bad", "dry_run": True})
    assert r.status_code == 503


def test_triage_unknown_provider_is_503_not_500():
    """An unknown provider (factory raises ValueError) must map to a clean 503,
    not an unhandled 500, and must not echo the raw input back to the client."""
    r = client.post("/v1/triage", json={"provider": "definitely-not-a-provider"})
    assert r.status_code == 503
    # The generic message must not contain the raw provider string.
    assert "definitely-not-a-provider" not in r.json()["detail"]


def test_triage_provider_error_detail_not_leaked(monkeypatch):
    """A provider connect failure must not leak its raw error (which may contain
    credential paths / config refs) into the HTTP response body."""

    class _LeakyProvider:
        name = "leaky"

        def connect(self):
            raise RuntimeError(
                "cannot read /Users/secret/.outlook_token_cache.json "
                "(op://Vault/Gmail OAuth/token_json)"
            )

        def disconnect(self):
            pass

    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _LeakyProvider())
    r = client.post("/v1/triage", json={"provider": "leaky", "dry_run": True})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "/Users/secret" not in detail
    assert "op://" not in detail
    assert "token_cache" not in detail


def test_triage_limit_upper_bound_enforced():
    """An out-of-range limit must be rejected at validation (422), never run an
    unbounded mailbox scan."""
    r = client.post(
        "/v1/triage/preview", json={"provider": "gmail", "limit": 10_000_000}
    )
    assert r.status_code == 422
    r = client.post("/v1/triage/preview", json={"provider": "gmail", "limit": 0})
    assert r.status_code == 422
