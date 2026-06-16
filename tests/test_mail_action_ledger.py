"""Action ledger and receipt tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.historical_intelligence import build_historical_intelligence
from core.mail_action_ledger import (
    MAIL_ACTION_LEDGER_SCHEMA,
    MAIL_ACTION_RECEIPT_SCHEMA,
    MailActionLedgerError,
    build_action_ledger,
    build_action_receipt,
)
from core.mail_action_plan import build_action_plan

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


def _plan(tmp_path: Path) -> dict:
    return build_action_plan(_write_intelligence(tmp_path))


def test_action_ledger_defaults_to_open_and_is_redacted(tmp_path):
    plan = _plan(tmp_path)

    ledger = build_action_ledger(plan, receipt_path=tmp_path / "missing.jsonl")
    payload = json.dumps(ledger, sort_keys=True)

    assert ledger["schema"] == MAIL_ACTION_LEDGER_SCHEMA
    assert ledger["mode"]["read_only"] is True
    assert ledger["mode"]["mailbox_mutations"] is False
    assert ledger["mode"]["sends"] is False
    assert ledger["privacy"]["redacted"] is True
    assert ledger["kpis"]["action_groups"] == len(plan["items"])
    assert ledger["kpis"]["active"] == len(plan["items"])
    assert ledger["kpis"]["receipts"] == 0
    assert ledger["items"][0]["action_status"] == "open"
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "Private lead should not leak" not in payload


def test_action_receipt_records_status_and_ledger_reflects_latest(tmp_path):
    plan = _plan(tmp_path)
    action_id = plan["items"][0]["id"]
    ledger_path = tmp_path / "ledger.jsonl"

    receipt = build_action_receipt(
        plan,
        action_id=action_id,
        action_status="waiting",
        reason_code="awaiting_reply",
        evidence_ids=plan["items"][0]["sample_evidence_ids"][:1],
        receipt_path=ledger_path,
    )
    ledger = build_action_ledger(plan, receipt_path=ledger_path)

    assert receipt["schema"] == MAIL_ACTION_RECEIPT_SCHEMA
    assert receipt["action_id"] == action_id
    assert receipt["action_status"] == "waiting"
    assert receipt["safety"]["send_allowed"] is False
    assert receipt["safety"]["mailbox_mutations_allowed"] is False
    assert ledger["kpis"]["waiting"] == 1
    assert ledger["kpis"]["receipts"] == 1
    assert ledger["items"][0]["action_id"] == action_id
    assert ledger["items"][0]["action_status"] == "waiting"
    assert ledger["items"][0]["last_receipt_id"] == receipt["receipt_id"]


def test_action_receipt_rejects_unknown_action(tmp_path):
    plan = _plan(tmp_path)

    try:
        build_action_receipt(
            plan,
            action_id="action_missing",
            action_status="resolved",
            reason_code="portal_verified",
            receipt_path=tmp_path / "ledger.jsonl",
        )
    except MailActionLedgerError as e:
        assert e.status_code == 404
        assert "action_id" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailActionLedgerError")


def test_action_ledger_api_requires_token_for_receipt_write(tmp_path, monkeypatch):
    intelligence = _write_intelligence(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = plan["items"][0]["id"]
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_MAIL_ACTION_LEDGER_PATH", str(ledger_path))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get("/v1/ops/action-ledger").status_code == 401
    assert client.post(
        "/v1/ops/action-receipts",
        json={
            "action_id": action_id,
            "action_status": "waiting",
            "reason_code": "awaiting_reply",
        },
    ).status_code == 401

    receipt = client.post(
        "/v1/ops/action-receipts",
        headers={"Authorization": "Bearer expected-token"},
        json={
            "action_id": action_id,
            "action_status": "waiting",
            "reason_code": "awaiting_reply",
        },
    )
    assert receipt.status_code == 200
    assert receipt.json()["schema"] == MAIL_ACTION_RECEIPT_SCHEMA

    response = client.get(
        "/v1/ops/action-ledger",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == MAIL_ACTION_LEDGER_SCHEMA
    assert body["kpis"]["waiting"] == 1
    assert "Private Recruiter" not in response.text


def test_action_ledger_and_receipt_cli_are_redacted(tmp_path):
    intelligence = _write_intelligence(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = plan["items"][0]["id"]
    ledger_path = tmp_path / "ledger.jsonl"

    receipt_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-action-receipt",
            "--intelligence",
            str(intelligence),
            "--ledger",
            str(ledger_path),
            "--action-id",
            action_id,
            "--status",
            "waiting",
            "--reason-code",
            "awaiting_reply",
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    receipt = json.loads(receipt_result.stdout)
    assert receipt["schema"] == MAIL_ACTION_RECEIPT_SCHEMA
    assert receipt["action_status"] == "waiting"

    ledger_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-action-ledger",
            "--intelligence",
            str(intelligence),
            "--ledger",
            str(ledger_path),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(ledger_result.stdout)
    assert body["schema"] == MAIL_ACTION_LEDGER_SCHEMA
    assert body["kpis"]["waiting"] == 1
    assert "Private Recruiter" not in ledger_result.stdout
    assert "private-recruiter@example.test" not in ledger_result.stdout
