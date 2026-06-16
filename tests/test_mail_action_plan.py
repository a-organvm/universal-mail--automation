"""Action planning over redacted mail intelligence tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_plan import MAIL_ACTION_PLAN_SCHEMA, MAIL_ACTION_ITEM_SCHEMA, build_action_plan

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


def test_action_plan_is_redacted_approval_aware_and_ranked(tmp_path):
    intelligence = _write_intelligence(tmp_path)

    plan = build_action_plan(intelligence)
    payload = json.dumps(plan, sort_keys=True)

    assert plan["schema"] == MAIL_ACTION_PLAN_SCHEMA
    assert plan["mode"]["read_only"] is True
    assert plan["mode"]["mailbox_mutations"] is False
    assert plan["mode"]["sends"] is False
    assert plan["mode"]["approval_required_before_send"] is True
    assert plan["privacy"]["redacted"] is True
    assert plan["kpis"]["action_groups"] >= 2
    assert plan["kpis"]["approval_required"] == plan["kpis"]["findings"]
    assert plan["kpis"]["provider_hint_counts"]["github"] >= 1
    assert plan["kpis"]["mailbox_mutations_allowed"] == 0
    assert plan["kpis"]["send_allowed"] == 0
    assert plan["items"][0]["schema"] == MAIL_ACTION_ITEM_SCHEMA
    assert plan["items"][0]["priority_score"] >= plan["items"][-1]["priority_score"]
    assert {item["approval_type"] for item in plan["items"]} >= {"draft_approval", "portal_verification"}
    assert any(item["kind"] == "missed_lead" for item in plan["items"])
    assert any(item["kind"] == "security_or_account" for item in plan["items"])
    assert any("github" in item["provider_hints"] for item in plan["items"])
    assert plan["answers"]["what_proof_exists"]["provider_hints_are_controlled_slugs"] is True
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Private lead should not leak" not in payload


def test_action_plan_api_uses_ops_token_boundary(tmp_path, monkeypatch):
    intelligence = _write_intelligence(tmp_path)
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/action-plan").status_code == 401

    response = client.get(
        "/v1/ops/action-plan?max_items=3",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == MAIL_ACTION_PLAN_SCHEMA
    assert len(body["items"]) <= 3
    assert "Private Recruiter" not in response.text


def test_mail_action_plan_cli_uses_redacted_contract(tmp_path):
    intelligence = _write_intelligence(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-action-plan",
            "--intelligence",
            str(intelligence),
            "--max-items",
            "5",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    body = json.loads(result.stdout)
    assert body["schema"] == MAIL_ACTION_PLAN_SCHEMA
    assert len(body["items"]) <= 5
    assert body["kpis"]["send_allowed"] == 0
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout


def test_mail_action_plan_cli_missing_input_fails_without_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "cli.py", "mail-action-plan", "--intelligence", str(tmp_path / "missing.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "historical intelligence input not found" in result.stderr
    assert "Traceback" not in result.stderr
