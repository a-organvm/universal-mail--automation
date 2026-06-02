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
from api import service  # noqa: E402


def _tools():
    return asyncio.run(mcp.list_tools())


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
    with pytest.raises(RuntimeError) as ei:
        triage(dry_run=False)
    assert "SAFETY GATE VIOLATION" in str(ei.value)
    assert "msg-7" not in str(ei.value)  # internal id never leaks to the agent


def test_triage_provider_unavailable_maps_to_error(monkeypatch):
    def boom(**kwargs):
        raise service.ProviderUnavailable("provider is not available")

    monkeypatch.setattr(service, "run_triage", boom)
    with pytest.raises(RuntimeError):
        triage_preview()
