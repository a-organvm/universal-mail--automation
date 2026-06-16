"""Resolver proof ledger and receipt tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_plan import build_action_plan
from core.mail_resolver_plan import build_resolver_plan
from core.mail_resolver_receipt import (
    MAIL_INVARIANT_ROLLUP_SCHEMA,
    MAIL_RESOLVER_LEDGER_SCHEMA,
    MAIL_RESOLVER_RECEIPT_SCHEMA,
    MailResolverReceiptError,
    build_invariant_rollup,
    build_resolver_ledger,
    build_resolver_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "historical"
OPS_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ops"


def _write_intelligence(tmp_path: Path) -> Path:
    history = tmp_path / "history.json"
    ops_report = tmp_path / "latest.json"
    shutil.copyfile(HISTORICAL_FIXTURE_DIR / "latest.json", history)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest.json", ops_report)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest-actions.md", tmp_path / "latest-actions.md")
    intelligence = build_historical_intelligence(history, ops_report_path=ops_report)
    target = tmp_path / "latest-intelligence.json"
    target.write_text(json.dumps(intelligence), encoding="utf-8")
    return target


def _resolver_plan(tmp_path: Path) -> dict:
    intelligence = _write_intelligence(tmp_path)
    return build_resolver_plan(build_action_plan(intelligence), max_items=100)


def _github_action_id(plan: dict) -> str:
    return next(item["action_id"] for item in plan["items"] if item["kind"] == "github_work")


def test_resolver_receipt_records_redacted_official_surface_attestation(tmp_path):
    plan = _resolver_plan(tmp_path)
    ledger_path = tmp_path / "resolver-ledger.jsonl"
    action_id = _github_action_id(plan)

    receipt = build_resolver_receipt(
        plan,
        action_id=action_id,
        resolver_status="verified_resolved",
        reason_code="github_reconciled",
        proof_type="github_issue_pr_billing_or_security_state",
        provider="github",
        external_reference="raw-provider-id-123",
        receipt_path=ledger_path,
    )
    ledger = build_resolver_ledger(plan, receipt_path=ledger_path)
    payload = json.dumps({"receipt": receipt, "ledger": ledger}, sort_keys=True)

    assert receipt["schema"] == MAIL_RESOLVER_RECEIPT_SCHEMA
    assert receipt["proof_matches_plan"] is True
    assert receipt["external_reference"]["provided"] is True
    assert receipt["external_reference"]["stored_raw"] is False
    assert receipt["safety"] == {
        "provider_backed_read": False,
        "provider_backed_automation": False,
        "operator_attestation_only": True,
        "mailbox_mutations_allowed": False,
        "portal_mutations_allowed": False,
        "send_allowed": False,
    }
    assert ledger["schema"] == MAIL_RESOLVER_LEDGER_SCHEMA
    assert ledger["mode"]["provider_backed_automation"] is False
    assert ledger["kpis"]["verified_resolved"] == 1
    assert ledger["kpis"]["provider_backed_receipts"] == 0
    assert ledger["kpis"]["send_allowed"] == 0
    assert ledger["kpis"]["mailbox_mutations_allowed"] == 0
    assert "raw-provider-id-123" not in payload
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload


def test_resolver_receipt_rejects_proof_not_required_by_plan(tmp_path):
    plan = _resolver_plan(tmp_path)
    action_id = _github_action_id(plan)

    try:
        build_resolver_receipt(
            plan,
            action_id=action_id,
            resolver_status="verified_resolved",
            reason_code="github_reconciled",
            proof_type="official_provider_verification",
            provider="github",
            receipt_path=tmp_path / "resolver-ledger.jsonl",
        )
    except MailResolverReceiptError as e:
        assert e.detail == "proof_type is not required by the current resolver plan"
    else:  # pragma: no cover
        raise AssertionError("expected MailResolverReceiptError")


def test_resolver_ledger_api_and_receipt_use_ops_token_boundary(tmp_path, monkeypatch):
    intelligence = _write_intelligence(tmp_path)
    plan = build_resolver_plan(build_action_plan(intelligence), max_items=100)
    action_id = _github_action_id(plan)
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_MAIL_RESOLVER_LEDGER_PATH", str(tmp_path / "resolver-ledger.jsonl"))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/resolver-ledger").status_code == 401
    assert client.post("/v1/ops/resolver-receipts", json={}).status_code == 401

    response = client.get(
        "/v1/ops/resolver-ledger?max_items=3",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert response.status_code == 200
    assert response.json()["schema"] == MAIL_RESOLVER_LEDGER_SCHEMA

    receipt_response = client.post(
        "/v1/ops/resolver-receipts",
        headers={"Authorization": "Bearer expected-token"},
        json={
            "action_id": action_id,
            "resolver_status": "verified_resolved",
            "reason_code": "github_reconciled",
            "proof_type": "github_issue_pr_billing_or_security_state",
            "provider": "github",
            "external_reference": "raw-provider-id-123",
        },
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["schema"] == MAIL_RESOLVER_RECEIPT_SCHEMA
    assert "raw-provider-id-123" not in receipt_response.text
    assert "Private Recruiter" not in receipt_response.text


def test_mail_resolver_receipt_and_ledger_cli_are_redacted(tmp_path):
    intelligence = _write_intelligence(tmp_path)
    plan = build_resolver_plan(build_action_plan(intelligence), max_items=100)
    action_id = _github_action_id(plan)
    ledger_path = tmp_path / "resolver-ledger.jsonl"

    receipt_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-resolver-receipt",
            "--intelligence",
            str(intelligence),
            "--ledger",
            str(ledger_path),
            "--action-id",
            action_id,
            "--resolver-status",
            "verified_resolved",
            "--reason-code",
            "github_reconciled",
            "--proof-type",
            "github_issue_pr_billing_or_security_state",
            "--provider",
            "github",
            "--external-reference",
            "raw-provider-id-123",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    ledger_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-resolver-ledger",
            "--intelligence",
            str(intelligence),
            "--ledger",
            str(ledger_path),
            "--max-items",
            "3",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    receipt = json.loads(receipt_result.stdout)
    ledger = json.loads(ledger_result.stdout)
    assert receipt["schema"] == MAIL_RESOLVER_RECEIPT_SCHEMA
    assert ledger["schema"] == MAIL_RESOLVER_LEDGER_SCHEMA
    assert ledger["kpis"]["verified_resolved"] == 1
    assert ledger["kpis"]["send_allowed"] == 0
    assert "raw-provider-id-123" not in receipt_result.stdout
    assert "raw-provider-id-123" not in ledger_result.stdout
    assert "Private Recruiter" not in ledger_result.stdout


def test_mail_resolver_ledger_cli_missing_input_fails_without_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "cli.py", "mail-resolver-ledger", "--intelligence", str(tmp_path / "missing.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "historical intelligence input not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_invariant_rollup_maps_every_status_into_one_of_three_states():
    items = [
        {"resolver_status": "verified_resolved", "finding_count": 3},
        {"resolver_status": "verified_blocked", "finding_count": 5},
        {"resolver_status": "verified_waiting", "finding_count": 2},
        {"resolver_status": "needs_follow_up", "finding_count": 4},
        {"resolver_status": "not_started", "finding_count": 1},
        {"resolver_status": "not_found", "finding_count": 1},
        {"resolver_status": "not_applicable", "finding_count": 1},
    ]

    rollup = build_invariant_rollup(items)

    assert rollup["schema"] == MAIL_INVARIANT_ROLLUP_SCHEMA
    # Strict: only verified_resolved counts as closed-with-receipt.
    assert rollup["states"]["closed_with_receipt"] == {"groups": 1, "findings": 3}
    assert rollup["states"]["blocked_with_reason"] == {"groups": 1, "findings": 5}
    # waiting absorbs verified_waiting + needs_follow_up + not_started + not_found + not_applicable
    assert rollup["states"]["waiting_with_evidence"] == {"groups": 5, "findings": 9}
    assert rollup["unclassified"]["groups"] == 0
    assert rollup["total"] == {"groups": 7, "findings": 17}
    assert rollup["invariant_holds"] is True
    assert rollup["send_allowed"] is False


def test_invariant_rollup_flags_an_escaped_unknown_status():
    rollup = build_invariant_rollup(
        [
            {"resolver_status": "verified_resolved", "finding_count": 1},
            {"resolver_status": "some_future_status", "finding_count": 9},
        ]
    )

    assert rollup["invariant_holds"] is False
    assert rollup["unclassified"]["groups"] == 1
    assert rollup["unclassified"]["findings"] == 9
    assert rollup["unclassified"]["statuses"] == ["some_future_status"]


def test_resolver_ledger_includes_invariant_rollup_summing_all_items(tmp_path):
    plan = _resolver_plan(tmp_path)
    ledger_path = tmp_path / "resolver-ledger.jsonl"
    action_id = _github_action_id(plan)
    build_resolver_receipt(
        plan,
        action_id=action_id,
        resolver_status="verified_resolved",
        reason_code="github_reconciled",
        proof_type="github_issue_pr_billing_or_security_state",
        provider="github",
        receipt_path=ledger_path,
    )

    ledger = build_resolver_ledger(plan, receipt_path=ledger_path)
    rollup = ledger["invariant_rollup"]
    states = rollup["states"]

    assert rollup["schema"] == MAIL_INVARIANT_ROLLUP_SCHEMA
    # The one receipted action shows as closed-with-receipt; everything else stays visible.
    assert states["closed_with_receipt"]["groups"] == ledger["kpis"]["verified_resolved"] == 1
    # Rollup covers the full plan, not the truncated items list.
    assert rollup["total"]["groups"] == ledger["kpis"]["resolver_groups"]
    rolled = (
        states["closed_with_receipt"]["groups"]
        + states["blocked_with_reason"]["groups"]
        + states["waiting_with_evidence"]["groups"]
    )
    assert rolled == rollup["total"]["groups"]
    assert rollup["invariant_holds"] is True
