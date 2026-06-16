"""Historical mail intelligence and ops reconciliation tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.historical_intelligence import (
    HISTORICAL_INTELLIGENCE_SCHEMA,
    MAIL_ENTITY_SCHEMA,
    MAIL_EVENT_SCHEMA,
    MAIL_OPPORTUNITY_SCHEMA,
    MAIL_RISK_SCHEMA,
    MAIL_TIMELINE_SCHEMA,
    HistoricalIntelligenceError,
    build_historical_intelligence,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "historical"
OPS_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ops"


def _write_history(tmp_path: Path) -> Path:
    target = tmp_path / "history.json"
    shutil.copyfile(HISTORICAL_FIXTURE_DIR / "latest.json", target)
    return target


def _write_ops_report(tmp_path: Path) -> Path:
    target = tmp_path / "latest.json"
    shutil.copyfile(OPS_FIXTURE_DIR / "latest.json", target)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest-actions.md", tmp_path / "latest-actions.md")
    return target


def test_historical_intelligence_is_redacted_and_answers_macro_questions(tmp_path):
    history = _write_history(tmp_path)
    now = datetime(2026, 6, 15, 18, 0, 0, tzinfo=timezone.utc)

    snapshot = build_historical_intelligence(history, now=now, stale_days=14)
    payload = json.dumps(snapshot, sort_keys=True)

    assert snapshot["schema"] == HISTORICAL_INTELLIGENCE_SCHEMA
    assert snapshot["mode"] == {
        "read_only": True,
        "mailbox_mutations": False,
        "sends": False,
        "archive_changes": False,
        "generic_vector_store": False,
    }
    assert snapshot["privacy"]["redacted"] is True
    assert snapshot["privacy"]["private_review_required_for_raw_mail"] is True
    assert snapshot["kpis"]["opportunities"] == 1
    assert snapshot["kpis"]["risks"] >= 4
    assert snapshot["kpis"]["provider_hint_counts"]["github"] >= 1
    assert snapshot["answers"]["what_proof_exists"]["provider_hints_are_controlled_slugs"] is True
    assert snapshot["answers"]["what_did_i_miss"]["missed_opportunities"] == 1
    assert snapshot["answers"]["what_matters_now"]["unresolved_risks"] >= 4
    assert snapshot["answers"]["what_was_safely_handled"]["mailbox_mutations"] == 0
    assert snapshot["entities"][0]["schema"] == MAIL_ENTITY_SCHEMA
    assert snapshot["events"][0]["schema"] == MAIL_EVENT_SCHEMA
    assert snapshot["opportunities"][0]["schema"] == MAIL_OPPORTUNITY_SCHEMA
    assert snapshot["risks"][0]["schema"] == MAIL_RISK_SCHEMA
    assert any("github" in event["provider_hints"] for event in snapshot["events"])
    assert any("github" in risk["provider_hints"] for risk in snapshot["risks"])
    assert any("github" in evidence["provider_hints"] for evidence in snapshot["evidence"])
    assert snapshot["timeline"]["schema"] == MAIL_TIMELINE_SCHEMA
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Private lead should not leak" not in payload
    assert "Could you send your availability" not in payload


def test_historical_intelligence_reconciles_findings_to_current_ops(tmp_path):
    history = _write_history(tmp_path)
    ops_report = _write_ops_report(tmp_path)
    now = datetime(2026, 6, 15, 18, 0, 0, tzinfo=timezone.utc)

    snapshot = build_historical_intelligence(
        history,
        ops_report_path=ops_report,
        now=now,
        stale_days=14,
    )

    statuses = {item["ops_lane_status"] for item in snapshot["reconciliation"]["findings"]}
    represented = [
        item for item in snapshot["reconciliation"]["findings"]
        if item["ops_lane_status"] == "represented_in_ops"
    ]

    assert "represented_in_ops" in statuses
    assert "not_represented_in_current_ops" in statuses
    assert snapshot["kpis"]["represented_in_ops"] == len(represented)
    assert any(item["recommended_lane"] == "security_verify" for item in represented)
    assert any(item["recommended_lane"] == "subscription_decision" for item in represented)


def test_historical_intelligence_api_uses_same_token_boundary(tmp_path, monkeypatch):
    history = _write_history(tmp_path)
    ops_report = _write_ops_report(tmp_path)
    monkeypatch.setenv("UMA_HISTORICAL_MAIL_PATH", str(history))
    monkeypatch.setenv("UMA_OPS_REPORT_PATH", str(ops_report))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/intelligence").status_code == 401

    response = client.get(
        "/v1/ops/intelligence",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == HISTORICAL_INTELLIGENCE_SCHEMA
    assert body["reconciliation"]["ops_source"]["supplied"] is True
    assert "Private Recruiter" not in response.text


def test_historical_intelligence_api_can_serve_redacted_cache(tmp_path, monkeypatch):
    history = _write_history(tmp_path)
    cache = tmp_path / "latest-intelligence.json"
    snapshot = build_historical_intelligence(history)
    cache.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(cache))
    monkeypatch.delenv("UMA_HISTORICAL_MAIL_PATH", raising=False)
    monkeypatch.delenv("UMA_OPS_TOKEN", raising=False)
    client = TestClient(app)

    response = client.get("/v1/ops/intelligence")

    assert response.status_code == 200
    assert response.json()["schema"] == HISTORICAL_INTELLIGENCE_SCHEMA
    assert "Private Recruiter" not in response.text


def test_historical_intelligence_api_disabled_without_input(monkeypatch):
    monkeypatch.delenv("UMA_HISTORICAL_MAIL_PATH", raising=False)
    monkeypatch.delenv("UMA_HISTORICAL_INTELLIGENCE_PATH", raising=False)
    monkeypatch.delenv("UMA_OPS_TOKEN", raising=False)
    client = TestClient(app)

    response = client.get("/v1/ops/intelligence")

    assert response.status_code == 503
    assert "UMA_HISTORICAL_MAIL_PATH" in response.json()["detail"]


def test_mail_intel_cli_uses_same_redacted_contract(tmp_path):
    history = _write_history(tmp_path)
    ops_report = _write_ops_report(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-intel",
            "--history",
            str(history),
            "--ops-report",
            str(ops_report),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    body = json.loads(result.stdout)
    assert body["schema"] == HISTORICAL_INTELLIGENCE_SCHEMA
    assert body["kpis"]["opportunities"] == 1
    assert body["reconciliation"]["ops_source"]["supplied"] is True
    assert "Private lead should not leak" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout


def test_mail_intel_cli_output_writes_cache_and_prints_receipt(tmp_path):
    history = _write_history(tmp_path)
    output = tmp_path / "latest-intelligence.json"

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-intel",
            "--history",
            str(history),
            "--output",
            str(output),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    receipt = json.loads(result.stdout)
    cached = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["schema"] == "uma.mail.intelligence.receipt.v1"
    assert receipt["output"]["schema"] == HISTORICAL_INTELLIGENCE_SCHEMA
    assert receipt["output"]["opportunities"] == 1
    assert cached["schema"] == HISTORICAL_INTELLIGENCE_SCHEMA
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout


def test_mail_intel_cli_missing_input_fails_without_traceback(tmp_path):
    missing = tmp_path / "missing.json"

    result = subprocess.run(
        [sys.executable, "cli.py", "mail-intel", "--history", str(missing)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "historical mail input not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_historical_intelligence_bad_shape_raises_clean_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"not_messages": []}', encoding="utf-8")

    try:
        build_historical_intelligence(bad)
    except HistoricalIntelligenceError as e:
        assert e.detail == "historical mail input requires a messages array"
    else:  # pragma: no cover
        raise AssertionError("expected HistoricalIntelligenceError")
