"""API tests, including the fail-closed safety invariant at the HTTP boundary."""

from fastapi.testclient import TestClient

from api import metering, service
from api.app import app
from api.store import get_store
from core.models import EmailMessage
from providers.base import ListMessagesResult, ProviderCapabilities

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


class _DryRunProvider(_FakeProvider):
    capabilities = ProviderCapabilities.TRUE_LABELS | ProviderCapabilities.ARCHIVE

    def __init__(self):
        self.messages = {
            "n1": EmailMessage(
                id="n1",
                sender="newsletter@deals-promo.example",
                subject="50% off sale unsubscribe",
            )
        }

    def list_messages(self, query="", limit=100, page_token=None):
        if page_token:
            return ListMessagesResult(messages=[], next_page_token=None)
        return ListMessagesResult(messages=list(self.messages.values())[:limit])

    def batch_get_details(self, message_ids):
        return {msg_id: self.messages[msg_id] for msg_id in message_ids}

    def get_message_details(self, message_id):
        return self.messages.get(message_id)

    def apply_label(self, message_id, label):  # pragma: no cover - dry-run guard
        raise AssertionError("dry-run preview must not apply labels")

    def remove_label(self, message_id, label):  # pragma: no cover - dry-run guard
        raise AssertionError("dry-run preview must not remove labels")

    def archive(self, message_id):  # pragma: no cover - dry-run guard
        raise AssertionError("dry-run preview must not archive")


def _clean_triage_result():
    return {
        "dry_run": False,
        "provider": "fake",
        "receipt": "Triage receipt: 1 message(s) -- gate held.",
        "audit": {
            "total": 1,
            "protected_held": 0,
            "archived": 1,
            "moved": 0,
            "labeled": 0,
            "kept": 0,
            "violations": [],
        },
        "processed": {"processed_count": 1},
    }


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
    acct = get_store().create_account(plan="free")

    r = client.post(
        "/v1/triage",
        json={"provider": "fake", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )
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


def test_triage_preview_reports_would_archive_for_archivable_message(monkeypatch):
    import cli

    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _DryRunProvider())

    r = client.post("/v1/triage/preview", json={"provider": "fake", "limit": 1})

    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert body["audit"]["archived"] > 0
    assert "would leave inbox" in body["receipt"]


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


def test_live_triage_requires_account_bearer(monkeypatch):
    called = {"run": False}

    def _run(**_kwargs):
        called["run"] = True
        return _clean_triage_result()

    monkeypatch.setattr(service, "run_triage", _run)

    r = client.post("/v1/triage", json={"provider": "fake", "dry_run": False})

    assert r.status_code == 401
    assert called["run"] is False


def test_live_triage_reserves_monthly_allowance(monkeypatch):
    monkeypatch.setattr(service, "run_triage", lambda **_kwargs: _clean_triage_result())
    store = get_store()
    acct = store.create_account(plan="free")

    r = client.post(
        "/v1/triage",
        json={"provider": "fake", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 200
    assert store.get_usage_count(acct["id"], metering.current_period_key()) == 1
    assert r.json()["run_id"].startswith("run_")


def test_live_triage_rejects_free_account_paid_only_provider(monkeypatch):
    called = {"run": False}

    def _run(**_kwargs):
        called["run"] = True
        return _clean_triage_result()

    monkeypatch.setattr(service, "run_triage", _run)
    acct = get_store().create_account(plan="free")

    r = client.post(
        "/v1/triage",
        json={"provider": "outlook", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 403
    assert called["run"] is False


def test_live_triage_allows_paid_account_all_providers(monkeypatch):
    monkeypatch.setattr(service, "run_triage", lambda **_kwargs: _clean_triage_result())
    acct = get_store().create_account(plan="pro")

    r = client.post(
        "/v1/triage",
        json={"provider": "outlook", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 200


def test_live_triage_exhausted_entitlement_rejected_before_service(monkeypatch):
    called = {"run": False}

    def _run(**_kwargs):
        called["run"] = True
        return _clean_triage_result()

    monkeypatch.setattr(service, "run_triage", _run)
    store = get_store()
    acct = store.create_account(plan="free", run_credits=0)
    period = metering.current_period_key()
    for _ in range(50):
        assert store.reserve_live_run(acct["id"], period, cap=50) is True

    r = client.post(
        "/v1/triage",
        json={"provider": "fake", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 402
    assert called["run"] is False


def test_live_triage_uses_credit_after_monthly_cap(monkeypatch):
    monkeypatch.setattr(service, "run_triage", lambda **_kwargs: _clean_triage_result())
    store = get_store()
    acct = store.create_account(plan="free", run_credits=1)
    period = metering.current_period_key()
    for _ in range(50):
        assert store.reserve_live_run(acct["id"], period, cap=50) is True

    r = client.post(
        "/v1/triage",
        json={"provider": "fake", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 200
    assert store.get_account(acct["id"])["run_credits"] == 0
    assert store.get_usage_count(acct["id"], period) == 50


def test_live_triage_refunds_credit_on_provider_failure(monkeypatch):
    def _run(**_kwargs):
        raise service.ProviderUnavailable("provider is not available")

    monkeypatch.setattr(service, "run_triage", _run)
    store = get_store()
    acct = store.create_account(plan="free", run_credits=1)
    period = metering.current_period_key()
    for _ in range(50):
        assert store.reserve_live_run(acct["id"], period, cap=50) is True

    r = client.post(
        "/v1/triage",
        json={"provider": "fake", "dry_run": False},
        headers={"Authorization": f"Bearer {acct['api_key']}"},
    )

    assert r.status_code == 503
    assert store.get_account(acct["id"])["run_credits"] == 1
