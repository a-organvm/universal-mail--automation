"""Tests for the MCP server tool surface (mcp_server/).

Skipped where the optional `mcp` SDK (Python >=3.10) isn't installed, so the core
suite still passes on a 3.9 floor.
"""

import asyncio

import pytest

pytest.importorskip("mcp")

from mcp_server.server import (  # noqa: E402
    check_protected_sender,
    mcp,
    triage,
    triage_preview,
)
from api import metering, service  # noqa: E402
from api.store import get_store  # noqa: E402


def _tools():
    return asyncio.run(mcp.list_tools())


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


def test_three_tools_registered():
    names = {t.name for t in _tools()}
    assert {"check_protected_sender", "triage_preview", "triage"} <= names


def test_tools_expose_output_schemas():
    # Pydantic return types give agents machine-checkable verdicts.
    for t in _tools():
        assert t.outputSchema


def test_triage_is_marked_destructive_others_readonly():
    by_name = {t.name: t for t in _tools()}
    assert by_name["check_protected_sender"].annotations.readOnlyHint is True
    assert by_name["triage_preview"].annotations.readOnlyHint is True
    assert by_name["triage"].annotations.destructiveHint is True


def test_check_protected_sender_delegates():
    assert check_protected_sender("clerk@courts.ca.gov").protected is True
    assert check_protected_sender("news@deals-promo.example").protected is False


def test_triage_audit_violation_is_generic(monkeypatch):
    def boom(**kwargs):
        raise service.AuditInvariantError("msg-7 protected sender leaked id")

    monkeypatch.setattr(service, "run_triage", boom)
    acct = get_store().create_account(plan="free")
    with pytest.raises(RuntimeError) as ei:
        triage(dry_run=False, account_api_key=acct["api_key"])
    assert "SAFETY GATE VIOLATION" in str(ei.value)
    assert "msg-7" not in str(ei.value)  # internal id never leaks to the agent


def test_live_triage_requires_account_key(monkeypatch):
    called = {"run": False}

    def run(**_kwargs):
        called["run"] = True
        return _clean_triage_result()

    monkeypatch.setattr(service, "run_triage", run)

    with pytest.raises(RuntimeError) as ei:
        triage(dry_run=False)

    assert "account_api_key" in str(ei.value)
    assert called["run"] is False


def test_live_triage_uses_mcp_account_entitlement(monkeypatch):
    monkeypatch.setattr(service, "run_triage", lambda **_kwargs: _clean_triage_result())
    store = get_store()
    acct = store.create_account(plan="free")

    result = triage(dry_run=False, provider="fake", account_api_key=acct["api_key"])

    assert result.run_id.startswith("run_")
    assert store.get_usage_count(acct["id"], metering.current_period_key()) == 1


def test_live_triage_uses_credit_after_monthly_cap(monkeypatch):
    monkeypatch.setattr(service, "run_triage", lambda **_kwargs: _clean_triage_result())
    store = get_store()
    acct = store.create_account(plan="free", run_credits=1)
    period = metering.current_period_key()
    for _ in range(50):
        assert store.reserve_live_run(acct["id"], period, cap=50) is True

    triage(dry_run=False, provider="fake", account_api_key=acct["api_key"])

    assert store.get_account(acct["id"])["run_credits"] == 0
    assert store.get_usage_count(acct["id"], period) == 50


def test_triage_provider_unavailable_maps_to_error(monkeypatch):
    def boom(**kwargs):
        raise service.ProviderUnavailable("provider is not available")

    monkeypatch.setattr(service, "run_triage", boom)
    with pytest.raises(RuntimeError):
        triage_preview()
