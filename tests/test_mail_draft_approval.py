"""Draft approval receipt tests."""

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
from core.mail_draft_package import build_draft_package
from core.mail_draft_approval import (
    MAIL_DRAFT_APPROVAL_LEDGER_SCHEMA,
    MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA,
    MailDraftApprovalError,
    build_draft_approval_ledger,
    build_draft_approval_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "historical"
OPS_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ops"


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    history = tmp_path / "history.json"
    ops_report = tmp_path / "latest.json"
    shutil.copyfile(HISTORICAL_FIXTURE_DIR / "latest.json", history)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest.json", ops_report)
    shutil.copyfile(OPS_FIXTURE_DIR / "latest-actions.md", tmp_path / "latest-actions.md")
    intelligence = build_historical_intelligence(history, ops_report_path=ops_report)
    intel_path = tmp_path / "latest-intelligence.json"
    intel_path.write_text(json.dumps(intelligence), encoding="utf-8")
    return history, intel_path


def _package(tmp_path: Path) -> dict:
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = next(item["id"] for item in plan["items"] if item["kind"] == "missed_lead")
    return build_draft_package(plan, history, action_id, ack_private=True, max_drafts=1)


def test_draft_approval_requires_private_ack(tmp_path):
    package = _package(tmp_path)
    draft_id = package["drafts"][0]["draft_id"]

    try:
        build_draft_approval_receipt(
            package,
            draft_id=draft_id,
            decision="approved",
            reason_code="ready_to_send",
            receipt_path=tmp_path / "approvals.jsonl",
        )
    except MailDraftApprovalError as e:
        assert e.status_code == 403
        assert "ack_private=true" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailDraftApprovalError")


def test_draft_approval_receipt_is_redacted_and_ledger_reflects_decision(tmp_path):
    package = _package(tmp_path)
    draft_id = package["drafts"][0]["draft_id"]
    approvals = tmp_path / "approvals.jsonl"

    receipt = build_draft_approval_receipt(
        package,
        draft_id=draft_id,
        decision="approved",
        reason_code="ready_to_send",
        receipt_path=approvals,
        ack_private=True,
    )
    ledger = build_draft_approval_ledger(package, receipt_path=approvals)
    payload = json.dumps(ledger, sort_keys=True)

    assert receipt["schema"] == MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA
    assert receipt["decision"] == "approved"
    assert receipt["safety"]["send_allowed"] is False
    assert receipt["safety"]["provider_draft_created"] is False
    assert "Private Recruiter" not in json.dumps(receipt)
    assert "private-recruiter@example.test" not in json.dumps(receipt)
    assert ledger["schema"] == MAIL_DRAFT_APPROVAL_LEDGER_SCHEMA
    assert ledger["kpis"]["approved"] == 1
    assert ledger["kpis"]["send_allowed"] == 0
    assert ledger["items"][0]["draft_id"] == draft_id
    assert ledger["items"][0]["decision"] == "approved"
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload


def test_draft_approval_api_requires_token_and_ack(tmp_path, monkeypatch):
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = next(item["id"] for item in plan["items"] if item["kind"] == "missed_lead")
    package = build_draft_package(plan, history, action_id, ack_private=True, max_drafts=1)
    draft_id = package["drafts"][0]["draft_id"]
    approvals = tmp_path / "approvals.jsonl"
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_HISTORICAL_MAIL_PATH", str(history))
    monkeypatch.setenv("UMA_MAIL_DRAFT_APPROVAL_PATH", str(approvals))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get(f"/v1/ops/draft-approvals/{action_id}?ack_private=true").status_code == 401
    assert client.post(
        f"/v1/ops/draft-approvals/{action_id}",
        json={"ack_private": True, "draft_id": draft_id, "decision": "approved", "reason_code": "ready_to_send"},
    ).status_code == 401

    no_ack = client.post(
        f"/v1/ops/draft-approvals/{action_id}",
        headers={"Authorization": "Bearer expected-token"},
        json={"draft_id": draft_id, "decision": "approved", "reason_code": "ready_to_send"},
    )
    assert no_ack.status_code == 403

    receipt = client.post(
        f"/v1/ops/draft-approvals/{action_id}",
        headers={"Authorization": "Bearer expected-token"},
        json={"ack_private": True, "draft_id": draft_id, "decision": "approved", "reason_code": "ready_to_send"},
    )
    assert receipt.status_code == 200
    assert receipt.json()["schema"] == MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA
    assert "Private Recruiter" not in receipt.text

    ledger = client.get(
        f"/v1/ops/draft-approvals/{action_id}?ack_private=true",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert ledger.status_code == 200
    assert ledger.json()["schema"] == MAIL_DRAFT_APPROVAL_LEDGER_SCHEMA
    assert ledger.json()["kpis"]["approved"] == 1


def test_draft_approval_cli_records_receipt_and_ledger_is_redacted(tmp_path):
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = next(item["id"] for item in plan["items"] if item["kind"] == "missed_lead")
    package = build_draft_package(plan, history, action_id, ack_private=True, max_drafts=1)
    draft_id = package["drafts"][0]["draft_id"]
    approvals = tmp_path / "approvals.jsonl"

    receipt_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-draft-approval",
            "--intelligence",
            str(intelligence),
            "--history",
            str(history),
            "--approvals",
            str(approvals),
            "--action-id",
            action_id,
            "--draft-id",
            draft_id,
            "--decision",
            "approved",
            "--reason-code",
            "ready_to_send",
            "--ack-private",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    receipt = json.loads(receipt_result.stdout)
    assert receipt["schema"] == MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA
    assert "Private Recruiter" not in receipt_result.stdout

    ledger_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-draft-approvals",
            "--intelligence",
            str(intelligence),
            "--history",
            str(history),
            "--approvals",
            str(approvals),
            "--action-id",
            action_id,
            "--ack-private",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    ledger = json.loads(ledger_result.stdout)
    assert ledger["schema"] == MAIL_DRAFT_APPROVAL_LEDGER_SCHEMA
    assert ledger["kpis"]["approved"] == 1
    assert "private-recruiter@example.test" not in ledger_result.stdout
