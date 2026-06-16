"""GitHub official-surface resolver snapshot tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.github_resolver import (
    GITHUB_RESOLVER_RECEIPTS_SCHEMA,
    GITHUB_RESOLVER_SNAPSHOT_SCHEMA,
    build_github_resolver_receipts,
    build_github_resolver_snapshot,
)
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_plan import build_action_plan
from core.mail_resolver_plan import build_resolver_plan
from core.mail_resolver_receipt import build_resolver_ledger

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


class FakeGitHubRunner:
    def __init__(self, *, authenticated: bool = True) -> None:
        self.authenticated = authenticated
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="gh version 2.0.0\n", stderr="")
        if argv[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(argv, 0 if self.authenticated else 1, stdout="", stderr="raw user info")
        if argv[1:3] == ["api", "notifications"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps(
                    [
                        {
                            "unread": True,
                            "reason": "review_requested",
                            "repository": {"full_name": "secret-org/private-repo"},
                            "subject": {"title": "Private PR title should not leak"},
                            "url": "https://api.github.com/notifications/threads/raw-thread",
                        }
                    ]
                ),
                stderr="",
            )
        if argv[1:3] == ["api", "/issues"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps(
                    [
                        {
                            "repository_url": "https://api.github.com/repos/secret-org/private-repo",
                            "title": "Private assigned issue should not leak",
                            "url": "https://api.github.com/repos/secret-org/private-repo/issues/7",
                        }
                    ]
                ),
                stderr="",
            )
        if argv[1:3] == ["api", "search/issues"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps(
                    {
                        "total_count": 2,
                        "items": [
                            {
                                "repository_url": "https://api.github.com/repos/secret-org/private-repo",
                                "title": "Private PR search result should not leak",
                            }
                        ],
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="unexpected")


def test_github_resolver_snapshot_reads_official_surface_without_leaking_raw_state(tmp_path):
    runner = FakeGitHubRunner()
    snapshot = build_github_resolver_snapshot(_resolver_plan(tmp_path), runner=runner)
    payload = json.dumps(snapshot, sort_keys=True)

    assert snapshot["schema"] == GITHUB_RESOLVER_SNAPSHOT_SCHEMA
    assert snapshot["status"] == "ok"
    assert snapshot["mode"]["read_only"] is True
    assert snapshot["mode"]["provider_backed_read"] is True
    assert snapshot["mode"]["provider_backed_automation"] is False
    assert snapshot["kpis"]["planned_github_actions"] == 1
    assert snapshot["kpis"]["provider_backed_read"] == 1
    assert snapshot["kpis"]["unread_notifications"] == 1
    assert snapshot["kpis"]["assigned_open_issues"] == 1
    assert snapshot["kpis"]["open_pull_requests"] == 2
    assert snapshot["kpis"]["send_allowed"] == 0
    assert snapshot["kpis"]["mailbox_mutations_allowed"] == 0
    assert snapshot["kpis"]["portal_mutations_allowed"] == 0
    assert snapshot["actions"][0]["receipt_candidate"]["resolver_status"] == "needs_follow_up"
    assert snapshot["actions"][0]["receipt_candidate"]["reason_code"] == "official_surface_checked"
    assert snapshot["actions"][0]["receipt_candidate"]["proof_type"] == "github_issue_pr_billing_or_security_state"
    assert snapshot["actions"][0]["receipt_candidate"]["operator_must_record_receipt"] is True
    assert len(runner.calls) == 5
    assert "secret-org/private-repo" not in payload
    assert "Private PR title should not leak" not in payload
    assert "Private assigned issue should not leak" not in payload
    assert "raw-thread" not in payload
    assert "raw user info" not in payload


def test_github_resolver_snapshot_blocks_cleanly_without_auth(tmp_path):
    runner = FakeGitHubRunner(authenticated=False)
    snapshot = build_github_resolver_snapshot(_resolver_plan(tmp_path), runner=runner)

    assert snapshot["status"] == "blocked_no_auth"
    assert snapshot["auth"]["gh_cli_available"] is True
    assert snapshot["auth"]["github_auth_available"] is False
    assert snapshot["kpis"]["official_queries_attempted"] == 0
    assert snapshot["actions"][0]["receipt_candidate"]["resolver_status"] == "verified_blocked"
    assert snapshot["actions"][0]["receipt_candidate"]["reason_code"] == "blocked_no_auth"
    assert snapshot["actions"][0]["receipt_candidate"]["operator_must_record_receipt"] is True


def test_github_resolver_receipts_record_provider_backed_read_without_raw_state(tmp_path):
    plan = _resolver_plan(tmp_path)
    ledger_path = tmp_path / "resolver-ledger.jsonl"
    snapshot = build_github_resolver_snapshot(plan, runner=FakeGitHubRunner())
    result = build_github_resolver_receipts(
        snapshot,
        plan,
        receipt_path=ledger_path,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    ledger = build_resolver_ledger(plan, receipt_path=ledger_path)
    payload = json.dumps({"result": result, "ledger": ledger}, sort_keys=True)

    assert result["schema"] == GITHUB_RESOLVER_RECEIPTS_SCHEMA
    assert result["status"] == "recorded"
    assert result["kpis"]["receipts_recorded"] == 1
    assert result["kpis"]["provider_backed_read_receipts"] == 1
    assert result["kpis"]["provider_backed_automation"] == 0
    assert result["receipts"][0]["schema"] == "uma.mail.resolver_receipt.v1"
    assert result["receipts"][0]["proof_scope"] == "official_surface_provider_read_snapshot"
    assert result["receipts"][0]["source_snapshot_id"] == snapshot["snapshot_id"]
    assert result["receipts"][0]["safety"]["provider_backed_read"] is True
    assert result["receipts"][0]["safety"]["provider_backed_automation"] is False
    assert result["receipts"][0]["safety"]["operator_attestation_only"] is False
    assert ledger["kpis"]["provider_backed_receipts"] == 1
    assert ledger["kpis"]["operator_attestation_receipts"] == 0
    assert ledger["kpis"]["needs_follow_up"] == 1
    assert "secret-org/private-repo" not in payload
    assert "Private PR title should not leak" not in payload
    assert "raw-thread" not in payload


def test_github_resolver_receipts_record_auth_blocker_as_operator_attestation(tmp_path):
    plan = _resolver_plan(tmp_path)
    ledger_path = tmp_path / "resolver-ledger.jsonl"
    snapshot = build_github_resolver_snapshot(plan, runner=FakeGitHubRunner(authenticated=False))
    result = build_github_resolver_receipts(
        snapshot,
        plan,
        receipt_path=ledger_path,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    ledger = build_resolver_ledger(plan, receipt_path=ledger_path)

    assert result["status"] == "recorded"
    assert result["kpis"]["provider_backed_read_receipts"] == 0
    assert result["kpis"]["operator_attestation_receipts"] == 1
    assert result["receipts"][0]["resolver_status"] == "verified_blocked"
    assert result["receipts"][0]["reason_code"] == "blocked_no_auth"
    assert result["receipts"][0]["proof_scope"] == "official_surface_read_blocker_snapshot"
    assert result["receipts"][0]["safety"]["provider_backed_read"] is False
    assert result["receipts"][0]["safety"]["operator_attestation_only"] is True
    assert ledger["kpis"]["provider_backed_receipts"] == 0
    assert ledger["kpis"]["operator_attestation_receipts"] == 1
    assert ledger["kpis"]["verified_blocked"] == 1


def test_github_resolver_api_and_cli_plan_only_are_redacted(tmp_path, monkeypatch):
    intelligence = _write_intelligence(tmp_path)
    resolver_ledger = tmp_path / "resolver-ledger.jsonl"
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_MAIL_RESOLVER_LEDGER_PATH", str(resolver_ledger))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/github-resolver?include_provider_queries=false").status_code == 401
    response = client.get(
        "/v1/ops/github-resolver?include_provider_queries=false",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["schema"] == GITHUB_RESOLVER_SNAPSHOT_SCHEMA
    assert response.json()["status"] == "planned_only"
    assert response.json()["answers"]["what_proof_exists"]["receipt_candidates"] == 0
    assert response.json()["actions"][0]["receipt_candidate"]["operator_must_record_receipt"] is False
    assert "Private Recruiter" not in response.text
    assert "private-recruiter@example.test" not in response.text

    assert client.post(
        "/v1/ops/github-resolver-receipts",
        json={"include_provider_queries": False},
    ).status_code == 401
    receipt_response = client.post(
        "/v1/ops/github-resolver-receipts",
        headers={"Authorization": "Bearer expected-token"},
        json={"include_provider_queries": False},
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["schema"] == GITHUB_RESOLVER_RECEIPTS_SCHEMA
    assert receipt_response.json()["status"] == "no_receipts_recorded"
    assert receipt_response.json()["kpis"]["receipts_recorded"] == 0

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-github-resolver",
            "--intelligence",
            str(intelligence),
            "--skip-provider-queries",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(result.stdout)
    assert body["schema"] == GITHUB_RESOLVER_SNAPSHOT_SCHEMA
    assert body["status"] == "planned_only"
    assert body["kpis"]["provider_backed_automation"] == 0
    assert body["answers"]["what_proof_exists"]["receipt_candidates"] == 0
    assert "Private Recruiter" not in result.stdout
    assert "private-recruiter@example.test" not in result.stdout

    receipt_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-github-resolver-receipts",
            "--intelligence",
            str(intelligence),
            "--ledger",
            str(tmp_path / "cli-resolver-ledger.jsonl"),
            "--skip-provider-queries",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    receipt_body = json.loads(receipt_result.stdout)
    assert receipt_body["schema"] == GITHUB_RESOLVER_RECEIPTS_SCHEMA
    assert receipt_body["status"] == "no_receipts_recorded"
    assert receipt_body["kpis"]["receipts_recorded"] == 0
    assert "Private Recruiter" not in receipt_result.stdout
    assert "private-recruiter@example.test" not in receipt_result.stdout
