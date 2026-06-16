"""Provider-surface resolver frontier tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_plan import build_action_plan
from core.mail_resolver_plan import build_resolver_plan
from core.provider_surface_plan import (
    PROVIDER_SURFACE_PLAN_SCHEMA,
    build_provider_surface_plan,
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


def _resolver_plan(tmp_path: Path) -> tuple[dict, Path]:
    intelligence = _write_intelligence(tmp_path)
    action_plan = build_action_plan(intelligence)
    resolver_plan = build_resolver_plan(action_plan, max_items=100)
    return resolver_plan, intelligence


def test_provider_surface_plan_ranks_controlled_provider_hints_without_external_proof(tmp_path):
    resolver_plan, _ = _resolver_plan(tmp_path)
    plan = build_provider_surface_plan(
        resolver_plan,
        max_items=10,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    payload = json.dumps(plan, sort_keys=True)
    by_provider = {item["provider"]: item for item in plan["items"]}

    assert plan["schema"] == PROVIDER_SURFACE_PLAN_SCHEMA
    assert plan["status"] == "ok"
    assert plan["mode"]["read_only"] is True
    assert plan["mode"]["provider_backed_read"] is False
    assert plan["mode"]["provider_backed_automation"] is False
    assert plan["kpis"]["provider_surfaces"] >= 3
    assert plan["kpis"]["provider_hint_total"] >= 3
    assert plan["kpis"]["provider_backed_automation"] == 0
    assert plan["kpis"]["send_allowed"] == 0
    assert plan["privacy"]["provider_hints_are_controlled_slugs"] is True
    assert plan["privacy"]["contains_raw_provider_state"] is False
    assert "github" in by_provider
    assert by_provider["github"]["provider_backed_read_available"] is True
    assert "mail-github-resolver" in by_provider["github"]["existing_uma_surfaces"]
    assert "cloudflare" in by_provider
    assert by_provider["cloudflare"]["provider_backed_read_available"] is False
    assert "provider_backed_resolver_not_built" in by_provider["cloudflare"]["blocked_by"]
    assert plan["answers"]["what_proof_exists"]["official_provider_proof_recorded_here"] is False
    assert any(row["provider"] == "github" for row in plan["answers"]["what_should_be_built_next"])
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Could you send your availability" not in payload


def test_provider_surface_plan_api_and_cli_are_redacted(tmp_path, monkeypatch):
    _, intelligence = _resolver_plan(tmp_path)
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/provider-surface-plan").status_code == 401
    response = client.get(
        "/v1/ops/provider-surface-plan?max_items=5",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert response.status_code == 200
    assert response.json()["schema"] == PROVIDER_SURFACE_PLAN_SCHEMA
    assert response.json()["mode"]["provider_backed_automation"] is False
    assert "Private Recruiter" not in response.text
    assert "private-recruiter@example.test" not in response.text

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-provider-surface-plan",
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
    assert body["schema"] == PROVIDER_SURFACE_PLAN_SCHEMA
    assert body["privacy"]["redacted"] is True
    assert body["kpis"]["mailbox_mutations_allowed"] == 0
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout
