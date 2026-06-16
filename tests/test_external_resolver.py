"""External-surface resolver snapshot tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.external_resolver import (
    EXTERNAL_RESOLVER_RECEIPTS_SCHEMA,
    EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA,
    build_external_resolver_receipts,
    build_external_resolver_snapshot,
)
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_plan import build_action_plan
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


def _plans(tmp_path: Path) -> tuple[dict, dict, Path]:
    intelligence, _ = _write_intelligence(tmp_path)
    action_plan = build_action_plan(intelligence)
    resolver_plan = build_resolver_plan(action_plan, max_items=100)
    return action_plan, resolver_plan, intelligence


def test_external_resolver_snapshot_is_planned_only_without_attestation(tmp_path):
    _, resolver_plan, _ = _plans(tmp_path)
    ledger = tmp_path / "resolver-ledger.jsonl"
    snapshot = build_external_resolver_snapshot(
        resolver_plan,
        receipt_path=ledger,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    payload = json.dumps(snapshot, sort_keys=True)

    assert snapshot["schema"] == EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA
    assert snapshot["status"] == "planned_only"
    assert snapshot["mode"]["read_only"] is True
    assert snapshot["mode"]["provider_backed_read"] is False
    assert snapshot["mode"]["provider_backed_automation"] is False
    assert snapshot["kpis"]["planned_external_actions"] > 0
    assert snapshot["kpis"]["planned_external_findings"] > 0
    assert snapshot["kpis"]["provider_hint_counts"]["cloudflare"] >= 1
    assert snapshot["kpis"]["recordable_receipt_candidates"] == 0
    assert snapshot["kpis"]["send_allowed"] == 0
    assert snapshot["kpis"]["portal_mutations_allowed"] == 0
    assert all(
        not action["receipt_candidate"]["operator_must_record_receipt"]
        for action in snapshot["actions"]
    )
    assert any("cloudflare" in action["provider_hints"] for action in snapshot["actions"])
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Could you send your availability" not in payload


def test_external_resolver_records_only_explicit_operator_attestations(tmp_path):
    _, resolver_plan, _ = _plans(tmp_path)
    ledger = tmp_path / "resolver-ledger.jsonl"
    snapshot = build_external_resolver_snapshot(
        resolver_plan,
        receipt_path=ledger,
        max_items=2,
        operator_attestation_requested=True,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    result = build_external_resolver_receipts(
        snapshot,
        resolver_plan,
        receipt_path=ledger,
        max_receipts=2,
        now=datetime(2026, 6, 15, 12, 5, tzinfo=timezone.utc),
    )
    resolver_ledger = build_resolver_ledger(resolver_plan, receipt_path=ledger, max_items=20)
    payload = json.dumps({"snapshot": snapshot, "result": result, "ledger": resolver_ledger}, sort_keys=True)

    assert snapshot["status"] == "attestation_ready"
    assert snapshot["kpis"]["recordable_receipt_candidates"] == 2
    assert result["schema"] == EXTERNAL_RESOLVER_RECEIPTS_SCHEMA
    assert result["status"] == "recorded"
    assert result["kpis"]["receipts_recorded"] == 2
    assert result["kpis"]["operator_attestation_receipts"] == 2
    assert result["kpis"]["provider_backed_read_receipts"] == 0
    assert result["kpis"]["provider_backed_automation"] == 0
    assert {receipt["proof_type"] for receipt in result["receipts"]} == {"action_receipt"}
    assert {receipt["proof_scope"] for receipt in result["receipts"]} == {
        "external_surface_operator_attestation"
    }
    assert all(receipt["safety"]["provider_backed_read"] is False for receipt in result["receipts"])
    assert all(receipt["safety"]["provider_backed_automation"] is False for receipt in result["receipts"])
    assert resolver_ledger["kpis"]["needs_follow_up"] >= 2
    assert resolver_ledger["kpis"]["provider_backed_receipts"] == 0
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Could you send your availability" not in payload


def test_external_resolver_api_cli_and_noop_receipts_are_redacted(tmp_path, monkeypatch):
    _, _, intelligence = _plans(tmp_path)
    resolver_ledger_path = tmp_path / "resolver-ledger.jsonl"
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_MAIL_RESOLVER_LEDGER_PATH", str(resolver_ledger_path))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/external-resolver").status_code == 401
    response = client.get(
        "/v1/ops/external-resolver",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert response.status_code == 200
    assert response.json()["schema"] == EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA
    assert response.json()["status"] == "planned_only"
    assert response.json()["kpis"]["recordable_receipt_candidates"] == 0
    assert "Private Recruiter" not in response.text
    assert "private-recruiter@example.test" not in response.text

    assert client.post("/v1/ops/external-resolver-receipts").status_code == 401
    receipt_response = client.post(
        "/v1/ops/external-resolver-receipts",
        headers={"Authorization": "Bearer expected-token"},
        json={"max_items": 5},
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["schema"] == EXTERNAL_RESOLVER_RECEIPTS_SCHEMA
    assert receipt_response.json()["status"] == "no_receipts_recorded"
    assert receipt_response.json()["kpis"]["receipts_recorded"] == 0

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-external-resolver",
            "--intelligence",
            str(intelligence),
            "--ledger",
            str(resolver_ledger_path),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(result.stdout)
    assert body["schema"] == EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA
    assert body["kpis"]["provider_backed_automation"] == 0
    assert body["kpis"]["recordable_receipt_candidates"] == 0
    assert body["kpis"]["provider_hint_counts"]["cloudflare"] >= 1
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout
