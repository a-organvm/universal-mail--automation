"""Operator summary contract tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.ops_summary import OPS_HISTORY_SCHEMA, OPS_SUMMARY_SCHEMA, build_ops_snapshot, load_ops_history, write_ops_snapshot

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ops"


def _write_report(tmp_path: Path) -> Path:
    report = tmp_path / "latest.json"
    shutil.copyfile(FIXTURE_DIR / "latest.json", report)
    shutil.copyfile(FIXTURE_DIR / "latest-actions.md", tmp_path / "latest-actions.md")
    return report


def test_ops_summary_disabled_without_report_path(monkeypatch):
    monkeypatch.delenv("UMA_OPS_REPORT_PATH", raising=False)
    monkeypatch.delenv("UMA_OPS_TOKEN", raising=False)
    client = TestClient(app)

    response = client.get("/v1/ops/summary")

    assert response.status_code == 503
    assert "UMA_OPS_REPORT_PATH" in response.json()["detail"]


def test_ops_summary_requires_token_when_configured(tmp_path, monkeypatch):
    report = _write_report(tmp_path)
    monkeypatch.setenv("UMA_OPS_REPORT_PATH", str(report))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/summary").status_code == 401
    assert client.get(
        "/v1/ops/summary",
        headers={"Authorization": "Bearer wrong-token"},
    ).status_code == 401

    response = client.get(
        "/v1/ops/summary",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["schema"] == OPS_SUMMARY_SCHEMA


def test_ops_summary_is_redacted_and_aggregated(tmp_path):
    report = _write_report(tmp_path)

    now = datetime(2026, 6, 15, 18, 31, 1, tzinfo=timezone.utc)
    summary = build_ops_snapshot(report, now=now, max_age_hours=1)
    payload = json.dumps(summary, sort_keys=True)

    assert summary["schema"] == OPS_SUMMARY_SCHEMA
    assert summary["status"] == "ok"
    assert summary["source"]["filename"] == "latest.json"
    assert str(report) not in payload
    assert summary["privacy"]["redacted"] is True
    assert summary["freshness"] == {
        "checked_at": "2026-06-15T18:31:01Z",
        "max_age_hours": 1.0,
        "generated_at_parseable": True,
        "generated_at_utc": "2026-06-15T16:31:01Z",
        "age_seconds": 7200,
        "age_hours": 2.0,
        "is_stale": True,
        "status": "stale",
        "reason": "report is older than 1 hours",
    }
    assert summary["kpis"] == {
        "inbox_messages": 10,
        "inbox_unread": 4,
        "all_mail_messages": 100,
        "all_mail_unread": 8,
        "archive_messages": 90,
        "archive_unread": 4,
        "scoped_messages": 110,
        "scoped_unread": 12,
        "escaped_unread": 0,
        "active_unread": 9,
        "waiting_messages": 1,
        "closed_messages": 7,
    }
    assert {lane["id"] for lane in summary["lanes"]} >= {
        "provider_action",
        "security_verify",
        "payment_verify",
        "subscription_decision",
        "sent_waiting",
        "closed",
    }
    assert "Private Person" not in payload
    assert "private@example.test" not in payload
    assert "Private matter should not leak" not in payload
    assert "Synthetic body that must not appear" not in payload
    assert "full_source_path" in summary["privacy"]["omitted_fields"]


def test_ops_summary_api_uses_same_contract(tmp_path, monkeypatch):
    report = _write_report(tmp_path)
    monkeypatch.setenv("UMA_OPS_REPORT_PATH", str(report))
    monkeypatch.delenv("UMA_OPS_TOKEN", raising=False)
    client = TestClient(app)

    response = client.get("/v1/ops/summary")

    assert response.status_code == 200
    body = response.json()
    expected = build_ops_snapshot(report)
    assert body["schema"] == expected["schema"]
    assert body["source"] == expected["source"]
    assert body["privacy"] == expected["privacy"]
    assert body["kpis"] == expected["kpis"]
    assert body["lanes"] == expected["lanes"]
    assert body["buckets"] == expected["buckets"]
    assert body["freshness"]["generated_at_utc"] == "2026-06-15T16:31:01Z"


def test_ops_summary_cli_uses_same_redacted_contract(tmp_path):
    report = _write_report(tmp_path)

    result = subprocess.run(
        [sys.executable, "cli.py", "ops-summary", "--report", str(report)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    body = json.loads(result.stdout)
    assert body["schema"] == OPS_SUMMARY_SCHEMA
    assert body["source"] == build_ops_snapshot(report)["source"]
    assert body["kpis"] == build_ops_snapshot(report)["kpis"]
    assert body["freshness"]["generated_at_utc"] == "2026-06-15T16:31:01Z"
    assert "Private Person" not in result.stdout
    assert "Private matter should not leak" not in result.stdout


def test_ops_snapshot_history_is_redacted_and_bounded(tmp_path):
    report = _write_report(tmp_path)
    now = datetime(2026, 6, 15, 18, 31, 1, tzinfo=timezone.utc)
    snapshot = build_ops_snapshot(report, now=now)

    refresh = write_ops_snapshot(snapshot, tmp_path / "ops", history_limit=1, now=now)
    payload = json.dumps(refresh, sort_keys=True)
    history = load_ops_history(tmp_path / "ops")

    assert refresh["schema"] == "uma.ops.refresh.v1"
    assert history["schema"] == OPS_HISTORY_SCHEMA
    assert len(history["entries"]) == 1
    assert Path(refresh["latest_summary"]).is_file()
    assert Path(refresh["history_index"]).is_file()
    assert Path(refresh["history_entry"]).is_file()
    assert "Private Person" not in payload
    assert "private@example.test" not in payload
    assert "Private matter should not leak" not in payload
    assert "Synthetic body that must not appear" not in payload


def test_ops_history_api_uses_same_token_boundary(tmp_path, monkeypatch):
    report = _write_report(tmp_path)
    snapshot = build_ops_snapshot(report)
    write_ops_snapshot(snapshot, tmp_path / "ops", history_limit=2)
    monkeypatch.setenv("UMA_OPS_HISTORY_DIR", str(tmp_path / "ops"))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/history").status_code == 401

    response = client.get(
        "/v1/ops/history",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["schema"] == OPS_HISTORY_SCHEMA
    assert len(response.json()["entries"]) == 1


def test_ops_refresh_cli_writes_redacted_history(tmp_path):
    report = _write_report(tmp_path)
    output_dir = tmp_path / "ops"

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "ops-refresh",
            "--report",
            str(report),
            "--output-dir",
            str(output_dir),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    body = json.loads(result.stdout)
    assert body["schema"] == "uma.ops.refresh.v1"
    assert body["status"] == "ok"
    assert Path(body["latest_summary"]).is_file()
    assert Path(body["history_index"]).is_file()
    assert "Private Person" not in result.stdout
    assert "Private matter should not leak" not in result.stdout


def test_ops_refresh_cli_can_run_read_only_report_producer(tmp_path):
    producer = tmp_path / "fake-mail-triage.py"
    producer.write_text(
        """#!/usr/bin/env python3
import pathlib
import shutil
import sys

fixture_dir = pathlib.Path(sys.argv[1])
args = sys.argv[2:]
report_dir = pathlib.Path(args[args.index("--report-dir") + 1])
report_dir.mkdir(parents=True, exist_ok=True)
shutil.copyfile(fixture_dir / "latest.json", report_dir / "latest.json")
shutil.copyfile(fixture_dir / "latest-actions.md", report_dir / "latest-actions.md")
""",
        encoding="utf-8",
    )
    producer.chmod(0o755)
    wrapper = tmp_path / "mail-triage-wrapper"
    wrapper.write_text(
        f"#!/usr/bin/env bash\n{sys.executable} {producer} {FIXTURE_DIR} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    report_dir = tmp_path / "reports"
    output_dir = tmp_path / "ops"

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "ops-refresh",
            "--run-mail-triage",
            "--mail-triage-bin",
            str(wrapper),
            "--since",
            "2026-05-01",
            "--until",
            "2026-06-16",
            "--report-dir",
            str(report_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    body = json.loads(result.stdout)
    assert body["schema"] == "uma.ops.refresh.v1"
    assert (report_dir / "latest.json").is_file()
    assert Path(body["latest_summary"]).is_file()
    assert "Private Person" not in result.stdout


def test_ops_summary_cli_missing_report_fails_without_traceback(tmp_path):
    missing = tmp_path / "missing.json"

    result = subprocess.run(
        [sys.executable, "cli.py", "ops-summary", "--report", str(missing)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "operator report not found" in result.stderr
    assert "Traceback" not in result.stderr


def test_ops_dashboard_served():
    client = TestClient(app)

    response = client.get("/ops")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "UMA Operator Dashboard" in response.text
    assert "/v1/ops/summary" in response.text
    assert "/v1/ops/history" in response.text
    assert "/v1/ops/intelligence" in response.text
    assert "/v1/ops/action-plan" in response.text
    assert "/v1/ops/resolver-plan" in response.text
    assert "/v1/ops/resolver-ledger" in response.text
    assert "/v1/ops/github-resolver" in response.text
    assert "/v1/ops/github-resolver-receipts" in response.text
    assert "/v1/ops/followup-resolver" in response.text
    assert "/v1/ops/followup-resolver-receipts" in response.text
    assert "/v1/ops/external-resolver" in response.text
    assert "/v1/ops/external-resolver-receipts" in response.text
    assert "/v1/ops/resolver-receipts" in response.text
    assert "/v1/ops/action-ledger" in response.text
    assert "/v1/ops/action-receipts" in response.text
    assert "/v1/ops/draft-package/" in response.text
    assert "/v1/ops/draft-approvals/" in response.text
    assert "/v1/ops/delivery/" in response.text
    assert "/v1/ops/evidence/" in response.text
    assert "Action Plan" in response.text
    assert "Resolver Plan" in response.text
    assert "GitHub Resolver" in response.text
    assert "Record GitHub Proof" in response.text
    assert "Follow-up Resolver" in response.text
    assert "Record Follow-up Proof" in response.text
    assert "External Resolver" in response.text
    assert "Record External Blockers" in response.text
    assert "recordGitHubResolverReceipts" in response.text
    assert "recordFollowupResolverReceipts" in response.text
    assert "recordExternalResolverReceipts" in response.text
    assert "recordResolverReceipt" in response.text
    assert "loadResolverLedger" in response.text
    assert "loadGitHubResolver" in response.text
    assert "loadExternalResolver" in response.text
    assert "Action Ledger" in response.text
    assert "Private Draft Package" in response.text
    assert "recordDraftApproval" in response.text
    assert "recordDeliveryReceipt" in response.text
    assert "loadResolverPlan" in response.text
    assert "Private Evidence Review" in response.text
    assert "escapeHtml" in response.text
