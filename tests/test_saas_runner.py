"""Tests for platform/saas_runner.py — the tier-rate-limited SaaS entrypoint.

The module is loaded by file path (not ``import platform.saas_runner``) because
the top-level ``platform`` package shares its name with the stdlib module, and
which one resolves for a dotted import depends on process import order. Loading
by path is deterministic and order-independent.
"""

import importlib.util
import os
import sys

import pytest

# --- load platform/saas_runner.py by path, under a non-colliding module name --
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAAS_PATH = os.path.join(_REPO_ROOT, "platform", "saas_runner.py")
_spec = importlib.util.spec_from_file_location("umail_saas_runner", _SAAS_PATH)
saas = importlib.util.module_from_spec(_spec)
sys.modules["umail_saas_runner"] = saas
_spec.loader.exec_module(saas)

from api import metering, service  # noqa: E402
from core.models import EmailMessage  # noqa: E402
from providers.base import ListMessagesResult, ProviderCapabilities  # noqa: E402


class _FakeClock:
    """Manually advanced monotonic clock for deterministic rate-limit tests."""

    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


# --- fake dry-run provider (mirrors tests/test_api.py) -----------------------
class _DryRunProvider:
    name = "fake"
    capabilities = ProviderCapabilities.TRUE_LABELS | ProviderCapabilities.ARCHIVE

    def __init__(self):
        self.messages = {
            "n1": EmailMessage(
                id="n1",
                sender="newsletter@deals-promo.example",
                subject="50% off sale unsubscribe",
            )
        }

    def connect(self):
        pass

    def disconnect(self):
        pass

    def list_messages(self, query="", limit=100, page_token=None):
        if page_token:
            return ListMessagesResult(messages=[], next_page_token=None)
        return ListMessagesResult(messages=list(self.messages.values())[:limit])

    def batch_get_details(self, message_ids):
        return {mid: self.messages[mid] for mid in message_ids}

    def get_message_details(self, message_id):
        return self.messages.get(message_id)

    def apply_label(self, message_id, label):  # pragma: no cover - dry-run guard
        raise AssertionError("dry-run must not apply labels")

    def remove_label(self, message_id, label):  # pragma: no cover - dry-run guard
        raise AssertionError("dry-run must not remove labels")

    def archive(self, message_id):  # pragma: no cover - dry-run guard
        raise AssertionError("dry-run must not archive")


@pytest.fixture(autouse=True)
def _no_throttle_sleep(monkeypatch):
    """Skip the engine's inter-batch throttle sleep so tests stay fast."""
    import cli

    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)


# --- TierRateLimiter unit tests ----------------------------------------------
def test_rate_limit_for_unknown_tier_is_free_floor():
    assert saas.rate_limit_for("free") == saas.TIER_RATE_LIMITS["free"]
    assert saas.rate_limit_for("nonsense") == saas.DEFAULT_RATE_LIMIT
    assert saas.rate_limit_for(None) == saas.DEFAULT_RATE_LIMIT


def test_limiter_allows_up_to_limit_then_blocks():
    clock = _FakeClock()
    limiter = saas.TierRateLimiter(clock=clock)
    limit = saas.rate_limit_for("free")

    decisions = [limiter.check("tok", "free") for _ in range(limit)]
    assert all(d.allowed for d in decisions)
    # remaining counts down to 0 on the last allowed request
    assert decisions[-1].remaining == 0

    blocked = limiter.check("tok", "free")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after > 0


def test_limiter_window_slides_and_reallows():
    clock = _FakeClock()
    limiter = saas.TierRateLimiter(clock=clock)
    limit = saas.rate_limit_for("free")

    for _ in range(limit):
        assert limiter.check("tok", "free").allowed
    assert limiter.check("tok", "free").allowed is False

    # After the full window elapses, the old hits expire and budget is restored.
    clock.advance(saas.WINDOW_SECONDS + 0.01)
    assert limiter.check("tok", "free").allowed is True


def test_limiter_is_per_token():
    clock = _FakeClock()
    limiter = saas.TierRateLimiter(clock=clock)
    limit = saas.rate_limit_for("free")
    for _ in range(limit):
        limiter.check("a", "free")
    assert limiter.check("a", "free").allowed is False
    # A different token has its own independent window.
    assert limiter.check("b", "free").allowed is True


def test_higher_tier_has_higher_limit():
    assert saas.rate_limit_for("pro") > saas.rate_limit_for("free")
    assert saas.rate_limit_for("business") > saas.rate_limit_for("pro")


def test_peek_does_not_consume():
    clock = _FakeClock()
    limiter = saas.TierRateLimiter(clock=clock)
    limit = saas.rate_limit_for("free")
    before = limiter.peek("tok", "free")
    assert before.remaining == limit
    # Peeking again still shows the full budget — no slot consumed.
    assert limiter.peek("tok", "free").remaining == limit


# --- run_saas_triage tests ---------------------------------------------------
def test_token_required():
    with pytest.raises(saas.TokenRequired):
        saas.run_saas_triage(token="", provider="fake")
    with pytest.raises(saas.TokenRequired):
        saas.run_saas_triage(token="   ", provider="fake")


def test_happy_path_returns_report(monkeypatch):
    limiter = saas.TierRateLimiter(clock=_FakeClock())
    result = saas.run_saas_triage(
        token="tok",
        provider="fake",
        license_id="free",
        dry_run=True,
        limit=1,
        limiter=limiter,
        provider_factory=lambda *a, **k: _DryRunProvider(),
    )
    assert result["ok"] is True
    assert result["tier"] == "free"
    assert result["provider"] == "fake"
    assert result["rate_limit"]["limit"] == saas.rate_limit_for("free")
    report = result["report"]
    assert report["dry_run"] is True
    assert "receipt" in report and report["receipt"]
    assert report["audit"]["violations"] == []


def test_unknown_license_falls_back_to_free(monkeypatch):
    monkeypatch.setattr(
        saas.service, "run_triage", lambda **kw: {"dry_run": True, "ok": "stub"}
    )
    result = saas.run_saas_triage(
        token="tok",
        provider="gmail",
        license_id="enterprise-deluxe",
        limiter=saas.TierRateLimiter(clock=_FakeClock()),
    )
    assert result["tier"] == "free"


def test_free_tier_blocks_nongmail_provider():
    with pytest.raises(metering.ProviderNotAllowed):
        saas.run_saas_triage(
            token="tok",
            provider="outlook",
            license_id="free",
            limiter=saas.TierRateLimiter(clock=_FakeClock()),
        )


def test_pro_tier_allows_nongmail_provider(monkeypatch):
    monkeypatch.setattr(
        saas.service,
        "run_triage",
        lambda **kw: {"dry_run": True, "provider": kw.get("provider")},
    )
    result = saas.run_saas_triage(
        token="tok",
        provider="outlook",
        license_id="pro",
        limiter=saas.TierRateLimiter(clock=_FakeClock()),
    )
    assert result["tier"] == "pro"
    assert result["report"]["provider"] == "outlook"


def test_rate_limited_raises_after_budget_exhausted(monkeypatch):
    monkeypatch.setattr(saas.service, "run_triage", lambda **kw: {"dry_run": True})
    limiter = saas.TierRateLimiter(clock=_FakeClock())
    limit = saas.rate_limit_for("free")
    for _ in range(limit):
        saas.run_saas_triage(
            token="tok", provider="gmail", license_id="free", limiter=limiter
        )
    with pytest.raises(saas.RateLimited) as exc:
        saas.run_saas_triage(
            token="tok", provider="gmail", license_id="free", limiter=limiter
        )
    assert exc.value.decision.allowed is False
    assert exc.value.decision.retry_after > 0


def test_rate_limit_consumed_even_for_disallowed_provider():
    """A rejected (disallowed-provider) call still costs a rate-limit slot, so an
    attacker cannot probe for free."""
    limiter = saas.TierRateLimiter(clock=_FakeClock())
    limit = saas.rate_limit_for("free")
    for _ in range(limit):
        with pytest.raises(metering.ProviderNotAllowed):
            saas.run_saas_triage(
                token="tok", provider="outlook", license_id="free", limiter=limiter
            )
    # Budget is now exhausted: the next call is rate-limited, not a provider error.
    with pytest.raises(saas.RateLimited):
        saas.run_saas_triage(
            token="tok", provider="outlook", license_id="free", limiter=limiter
        )


# --- HTTP surface tests ------------------------------------------------------
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    # Fresh limiter per test so request budgets don't bleed across tests.
    monkeypatch.setattr(saas, "_LIMITER", saas.TierRateLimiter(clock=_FakeClock()))
    return TestClient(saas.app)


def test_http_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_http_limits_catalog(client):
    r = client.get("/v1/saas/limits")
    assert r.status_code == 200
    body = r.json()
    assert body["window_seconds"] == saas.WINDOW_SECONDS
    assert body["tiers"]["free"]["rate_limit_per_window"] == saas.rate_limit_for("free")
    assert body["tiers"]["free"]["providers"] == "gmail"


def test_http_missing_token_is_401(client):
    r = client.post("/v1/saas/triage", json={"provider": "fake"})
    assert r.status_code == 401


def test_http_triage_happy_path(client, monkeypatch):
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _DryRunProvider())
    r = client.post(
        "/v1/saas/triage",
        json={"token": "tok", "provider": "fake", "limit": 1, "dry_run": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["tier"] == "free"
    assert body["report"]["dry_run"] is True
    assert r.headers["X-RateLimit-Limit"] == str(saas.rate_limit_for("free"))


def test_http_token_via_authorization_header(client, monkeypatch):
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _DryRunProvider())
    r = client.post(
        "/v1/saas/triage",
        json={"provider": "fake", "limit": 1},
        headers={"Authorization": "Bearer header-tok"},
    )
    assert r.status_code == 200, r.text


def test_http_free_tier_nongmail_is_403(client):
    r = client.post(
        "/v1/saas/triage",
        json={"token": "tok", "provider": "outlook", "license": "free"},
    )
    assert r.status_code == 403


def test_http_rate_limited_is_429(client, monkeypatch):
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _DryRunProvider())
    limit = saas.rate_limit_for("free")
    for _ in range(limit):
        ok = client.post(
            "/v1/saas/triage",
            json={"token": "burst", "provider": "fake", "limit": 1},
        )
        assert ok.status_code == 200, ok.text
    blocked = client.post(
        "/v1/saas/triage",
        json={"token": "burst", "provider": "fake", "limit": 1},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_http_fail_closed_on_gate_violation(client, monkeypatch):
    """If the independent audit proves a protected sender left the inbox, the
    endpoint returns 500 (never 200) and does not leak internal ids."""

    def _bad_run_labeler(
        provider, *, query, limit, dry_run, remove_label, state_file,
        tier_routing, vip_only, audit,
    ):
        audit.record(
            message_id="m1", sender="clerk@courts.ca.gov",
            protected=False, archived=True,
        )
        return {"processed_count": 1}

    monkeypatch.setattr(service, "run_labeler", _bad_run_labeler)
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _DryRunProvider())

    r = client.post(
        "/v1/saas/triage",
        json={"token": "tok", "provider": "fake", "dry_run": False},
    )
    assert r.status_code == 500
    assert "GATE VIOLATION" in r.json()["detail"]
    assert "m1" not in r.json()["detail"]
