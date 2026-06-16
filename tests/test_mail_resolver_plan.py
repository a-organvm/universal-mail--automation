"""Resolver planning over redacted mail action plans tests."""

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
from core.mail_resolver_plan import (
    MAIL_RESOLVER_ITEM_SCHEMA,
    MAIL_RESOLVER_PLAN_SCHEMA,
    build_resolver_plan,
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


def test_resolver_plan_maps_lanes_to_official_surfaces_without_leaking_mail(tmp_path):
    intelligence = _write_intelligence(tmp_path)
    action_plan = build_action_plan(intelligence)

    plan = build_resolver_plan(action_plan)
    payload = json.dumps(plan, sort_keys=True)
    by_kind = {item["kind"]: item for item in plan["items"]}

    assert plan["schema"] == MAIL_RESOLVER_PLAN_SCHEMA
    assert plan["mode"] == {
        "read_only": True,
        "mailbox_mutations": False,
        "sends": False,
        "portal_mutations": False,
        "official_surface_plan_only": True,
    }
    assert plan["privacy"]["redacted"] is True
    assert plan["kpis"]["resolver_groups"] >= 5
    assert plan["kpis"]["github_reconcile"] == 1
    assert plan["kpis"]["mail_or_linkedin_follow_up"] == 1
    assert plan["kpis"]["security_verify"] == 1
    assert plan["kpis"]["provider_hint_counts"]["github"] >= 1
    assert plan["kpis"]["send_allowed"] == 0
    assert plan["kpis"]["mailbox_mutations_allowed"] == 0
    assert plan["kpis"]["portal_mutations_allowed"] == 0
    assert plan["items"][0]["schema"] == MAIL_RESOLVER_ITEM_SCHEMA
    assert by_kind["missed_lead"]["official_surface"] == "mail_or_linkedin_inbox"
    assert "linkedin_manual" in by_kind["missed_lead"]["supported_surfaces"]
    assert by_kind["github_work"]["official_surface"] == "github_api_cli_or_web"
    assert by_kind["github_work"]["resolver_type"] == "github_reconcile"
    assert "github" in by_kind["github_work"]["provider_hints"]
    assert by_kind["security_or_account"]["official_surface"] == "official_provider_security_surface"
    assert plan["answers"]["what_proof_exists"]["provider_hints_are_controlled_slugs"] is True
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Private lead should not leak" not in payload


def test_resolver_plan_api_uses_ops_token_boundary(tmp_path, monkeypatch):
    intelligence = _write_intelligence(tmp_path)
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/resolver-plan").status_code == 401

    response = client.get(
        "/v1/ops/resolver-plan?max_items=3",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == MAIL_RESOLVER_PLAN_SCHEMA
    assert len(body["items"]) <= 3
    assert body["kpis"]["github_reconcile"] == 1
    assert body["mode"]["sends"] is False
    assert "Private Recruiter" not in response.text


def test_mail_resolver_plan_cli_uses_redacted_contract(tmp_path):
    intelligence = _write_intelligence(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-resolver-plan",
            "--intelligence",
            str(intelligence),
            "--max-items",
            "3",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    body = json.loads(result.stdout)
    assert body["schema"] == MAIL_RESOLVER_PLAN_SCHEMA
    assert len(body["items"]) <= 3
    assert body["kpis"]["github_reconcile"] == 1
    assert body["kpis"]["send_allowed"] == 0
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout


def test_mail_resolver_plan_cli_missing_input_fails_without_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "cli.py", "mail-resolver-plan", "--intelligence", str(tmp_path / "missing.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "historical intelligence input not found" in result.stderr
    assert "Traceback" not in result.stderr
