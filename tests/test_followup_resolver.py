"""Mail/LinkedIn follow-up resolver snapshot tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.followup_resolver import (
    FOLLOWUP_RESOLVER_RECEIPTS_SCHEMA,
    FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA,
    build_followup_resolver_receipts,
    build_followup_resolver_snapshot,
)
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_plan import build_action_plan
from core.mail_delivery import build_delivery_receipt
from core.mail_draft_approval import build_draft_approval_receipt
from core.mail_draft_package import build_draft_package
from core.mail_resolver_plan import build_resolver_plan
from core.mail_resolver_receipt import build_resolver_ledger

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "historical"
OPS_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ops"


def _write_intelligence(tmp_path: Path) -> tuple[Path, Path]:
    history = tmp_path / "history.json"
    ops_report = tmp_path / "latest.json"
    shutil.copyfile(HISTORICAL_FIXTURE_DIR / "latest.json", history)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest.json", ops_report)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest-actions.md", tmp_path / "latest-actions.md")
    intelligence = build_historical_intelligence(history, ops_report_path=ops_report)
    target = tmp_path / "latest-intelligence.json"
    target.write_text(json.dumps(intelligence), encoding="utf-8")
    return target, history


def _plans(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    intelligence, history = _write_intelligence(tmp_path)
    action_plan = build_action_plan(intelligence)
    resolver_plan = build_resolver_plan(action_plan, max_items=100)
    return action_plan, resolver_plan, intelligence, history


def _followup_action_id(plan: dict) -> str:
    return next(item["action_id"] for item in plan["items"] if item["resolver_type"] == "reply_follow_up")


def test_followup_resolver_snapshot_shows_open_work_without_inventing_proof(tmp_path):
    _, resolver_plan, _, _ = _plans(tmp_path)
    snapshot = build_followup_resolver_snapshot(resolver_plan)
    payload = json.dumps(snapshot, sort_keys=True)

    assert snapshot["schema"] == FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA
    assert snapshot["status"] == "needs_private_review"
    assert snapshot["mode"]["read_only"] is True
    assert snapshot["mode"]["provider_backed_automation"] is False
    assert snapshot["kpis"]["planned_followup_actions"] == 1
    assert snapshot["kpis"]["recordable_receipt_candidates"] == 0
    assert snapshot["actions"][0]["receipt_candidate"]["operator_must_record_receipt"] is False
    assert snapshot["actions"][0]["next_step"] == "open_private_evidence_and_prepare_draft_for_approval"
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Could you send your availability" not in payload


def test_followup_resolver_receipts_record_existing_delivery_proof(tmp_path):
    action_plan, resolver_plan, _, history = _plans(tmp_path)
    action_id = _followup_action_id(resolver_plan)
    approval_path = tmp_path / "approvals.jsonl"
    delivery_path = tmp_path / "delivery.jsonl"
    resolver_ledger_path = tmp_path / "resolver-ledger.jsonl"
    package = build_draft_package(action_plan, history, action_id, ack_private=True, max_drafts=1)
    draft_id = package["drafts"][0]["draft_id"]
    build_draft_approval_receipt(
        package,
        draft_id=draft_id,
        decision="approved",
        reason_code="ready_to_send",
        receipt_path=approval_path,
        ack_private=True,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    build_delivery_receipt(
        package,
        draft_id=draft_id,
        delivery_status="provider_draft_requested",
        reason_code="approved_for_provider_draft",
        approval_receipt_path=approval_path,
        receipt_path=delivery_path,
        ack_private=True,
        provider="linkedin",
        now=datetime(2026, 6, 15, 12, 5, tzinfo=timezone.utc),
    )

    snapshot = build_followup_resolver_snapshot(
        resolver_plan,
        draft_approval_receipt_path=approval_path,
        delivery_receipt_path=delivery_path,
        now=datetime(2026, 6, 15, 12, 10, tzinfo=timezone.utc),
    )
    result = build_followup_resolver_receipts(
        snapshot,
        resolver_plan,
        receipt_path=resolver_ledger_path,
        now=datetime(2026, 6, 15, 12, 15, tzinfo=timezone.utc),
    )
    ledger = build_resolver_ledger(resolver_plan, receipt_path=resolver_ledger_path)
    payload = json.dumps({"snapshot": snapshot, "result": result, "ledger": ledger}, sort_keys=True)

    assert snapshot["status"] == "ok"
    assert snapshot["kpis"]["draft_approval_receipts"] == 1
    assert snapshot["kpis"]["delivery_receipts"] == 1
    assert snapshot["kpis"]["recordable_receipt_candidates"] == 1
    assert snapshot["actions"][0]["receipt_candidate"]["proof_type"] == "delivery_receipt"
    assert snapshot["actions"][0]["receipt_candidate"]["provider"] == "linkedin"
    assert result["schema"] == FOLLOWUP_RESOLVER_RECEIPTS_SCHEMA
    assert result["status"] == "recorded"
    assert result["kpis"]["receipts_recorded"] == 1
    assert result["kpis"]["provider_backed_automation"] == 0
    assert result["receipts"][0]["proof_scope"] == "local_followup_delivery_state"
    assert result["receipts"][0]["safety"]["provider_backed_read"] is False
    assert result["receipts"][0]["safety"]["provider_backed_automation"] is False
    assert ledger["kpis"]["needs_follow_up"] == 1
    assert ledger["kpis"]["provider_backed_receipts"] == 0
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Could you send your availability" not in payload


def test_followup_resolver_api_and_cli_are_redacted(tmp_path, monkeypatch):
    intelligence, _ = _write_intelligence(tmp_path)
    approval_path = tmp_path / "approvals.jsonl"
    delivery_path = tmp_path / "delivery.jsonl"
    resolver_ledger_path = tmp_path / "resolver-ledger.jsonl"
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_MAIL_DRAFT_APPROVAL_PATH", str(approval_path))
    monkeypatch.setenv("UMA_MAIL_DELIVERY_LEDGER_PATH", str(delivery_path))
    monkeypatch.setenv("UMA_MAIL_RESOLVER_LEDGER_PATH", str(resolver_ledger_path))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/followup-resolver").status_code == 401
    response = client.get(
        "/v1/ops/followup-resolver",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert response.status_code == 200
    assert response.json()["schema"] == FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA
    assert response.json()["status"] == "needs_private_review"
    assert "Private Recruiter" not in response.text
    assert "private-recruiter@example.test" not in response.text

    assert client.post("/v1/ops/followup-resolver-receipts").status_code == 401
    receipt_response = client.post(
        "/v1/ops/followup-resolver-receipts",
        headers={"Authorization": "Bearer expected-token"},
        json={"max_items": 5},
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["schema"] == FOLLOWUP_RESOLVER_RECEIPTS_SCHEMA
    assert receipt_response.json()["status"] == "no_receipts_recorded"
    assert receipt_response.json()["kpis"]["receipts_recorded"] == 0

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-followup-resolver",
            "--intelligence",
            str(intelligence),
            "--draft-approvals",
            str(approval_path),
            "--delivery-ledger",
            str(delivery_path),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(result.stdout)
    assert body["schema"] == FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA
    assert body["kpis"]["provider_backed_automation"] == 0
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout
