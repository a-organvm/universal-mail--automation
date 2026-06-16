"""Delivery intent receipt tests."""

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
from core.mail_draft_approval import build_draft_approval_receipt
from core.mail_draft_package import build_draft_package
from core.mail_delivery import (
    MAIL_DELIVERY_LEDGER_SCHEMA,
    MAIL_DELIVERY_RECEIPT_SCHEMA,
    MailDeliveryError,
    build_delivery_ledger,
    build_delivery_receipt,
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


def _package(tmp_path: Path) -> tuple[Path, Path, dict]:
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = next(item["id"] for item in plan["items"] if item["kind"] == "missed_lead")
    package = build_draft_package(plan, history, action_id, ack_private=True, max_drafts=1)
    return history, intelligence, package


def _approve(package: dict, approvals: Path) -> str:
    draft_id = package["drafts"][0]["draft_id"]
    build_draft_approval_receipt(
        package,
        draft_id=draft_id,
        decision="approved",
        reason_code="ready_to_send",
        receipt_path=approvals,
        ack_private=True,
    )
    return draft_id


def test_delivery_receipt_requires_approved_draft(tmp_path):
    _, _, package = _package(tmp_path)
    draft_id = package["drafts"][0]["draft_id"]

    try:
        build_delivery_receipt(
            package,
            draft_id=draft_id,
            delivery_status="provider_draft_requested",
            reason_code="approved_for_provider_draft",
            approval_receipt_path=tmp_path / "approvals.jsonl",
            receipt_path=tmp_path / "delivery.jsonl",
            ack_private=True,
        )
    except MailDeliveryError as e:
        assert e.status_code == 409
        assert "approved draft approval receipt" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailDeliveryError")


def test_delivery_receipt_is_redacted_and_ledger_tracks_ready_and_status(tmp_path):
    _, _, package = _package(tmp_path)
    approvals = tmp_path / "approvals.jsonl"
    delivery = tmp_path / "delivery.jsonl"
    draft_id = _approve(package, approvals)

    ready = build_delivery_ledger(package, approval_receipt_path=approvals, delivery_receipt_path=delivery)
    assert ready["schema"] == MAIL_DELIVERY_LEDGER_SCHEMA
    assert ready["kpis"]["ready_for_provider_draft"] == 1
    assert ready["kpis"]["uma_sends"] == 0

    receipt = build_delivery_receipt(
        package,
        draft_id=draft_id,
        delivery_status="provider_draft_requested",
        reason_code="approved_for_provider_draft",
        provider="gmail",
        external_reference="raw-provider-id-123",
        approval_receipt_path=approvals,
        receipt_path=delivery,
        ack_private=True,
    )
    ledger = build_delivery_ledger(package, approval_receipt_path=approvals, delivery_receipt_path=delivery)
    payload = json.dumps(ledger, sort_keys=True)

    assert receipt["schema"] == MAIL_DELIVERY_RECEIPT_SCHEMA
    assert receipt["delivery_status"] == "provider_draft_requested"
    assert receipt["safety"]["uma_created_provider_draft"] is False
    assert receipt["safety"]["uma_sent_message"] is False
    assert receipt["external_reference"]["stored_raw"] is False
    assert "raw-provider-id-123" not in json.dumps(receipt)
    assert ledger["kpis"]["provider_draft_requested"] == 1
    assert ledger["kpis"]["uma_provider_drafts_created"] == 0
    assert "Private Recruiter" not in payload
    assert "private-recruiter@example.test" not in payload
    assert "raw-provider-id-123" not in payload


def test_delivery_api_requires_token_ack_and_approval(tmp_path, monkeypatch):
    history, intelligence, package = _package(tmp_path)
    approvals = tmp_path / "approvals.jsonl"
    delivery = tmp_path / "delivery.jsonl"
    action_id = package["action"]["id"]
    draft_id = package["drafts"][0]["draft_id"]
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_HISTORICAL_MAIL_PATH", str(history))
    monkeypatch.setenv("UMA_MAIL_DRAFT_APPROVAL_PATH", str(approvals))
    monkeypatch.setenv("UMA_MAIL_DELIVERY_LEDGER_PATH", str(delivery))
    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    client = TestClient(app)

    assert client.get(f"/v1/ops/delivery/{action_id}?ack_private=true").status_code == 401

    unapproved = client.post(
        f"/v1/ops/delivery/{action_id}",
        headers={"Authorization": "Bearer expected-token"},
        json={
            "ack_private": True,
            "draft_id": draft_id,
            "delivery_status": "provider_draft_requested",
            "reason_code": "approved_for_provider_draft",
        },
    )
    assert unapproved.status_code == 409

    _approve(package, approvals)
    no_ack = client.post(
        f"/v1/ops/delivery/{action_id}",
        headers={"Authorization": "Bearer expected-token"},
        json={
            "draft_id": draft_id,
            "delivery_status": "provider_draft_requested",
            "reason_code": "approved_for_provider_draft",
        },
    )
    assert no_ack.status_code == 403

    receipt = client.post(
        f"/v1/ops/delivery/{action_id}",
        headers={"Authorization": "Bearer expected-token"},
        json={
            "ack_private": True,
            "draft_id": draft_id,
            "delivery_status": "provider_draft_requested",
            "reason_code": "approved_for_provider_draft",
            "provider": "gmail",
            "external_reference": "raw-provider-id-123",
        },
    )
    assert receipt.status_code == 200
    assert receipt.json()["schema"] == MAIL_DELIVERY_RECEIPT_SCHEMA
    assert "Private Recruiter" not in receipt.text
    assert "raw-provider-id-123" not in receipt.text

    ledger = client.get(
        f"/v1/ops/delivery/{action_id}?ack_private=true",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert ledger.status_code == 200
    assert ledger.json()["schema"] == MAIL_DELIVERY_LEDGER_SCHEMA
    assert ledger.json()["kpis"]["provider_draft_requested"] == 1


def test_delivery_cli_records_receipt_and_ledger_is_redacted(tmp_path):
    history, intelligence, package = _package(tmp_path)
    approvals = tmp_path / "approvals.jsonl"
    delivery = tmp_path / "delivery.jsonl"
    action_id = package["action"]["id"]
    draft_id = _approve(package, approvals)

    receipt_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-delivery-receipt",
            "--intelligence",
            str(intelligence),
            "--history",
            str(history),
            "--approvals",
            str(approvals),
            "--delivery",
            str(delivery),
            "--action-id",
            action_id,
            "--draft-id",
            draft_id,
            "--delivery-status",
            "provider_draft_requested",
            "--reason-code",
            "approved_for_provider_draft",
            "--provider",
            "gmail",
            "--external-reference",
            "raw-provider-id-123",
            "--ack-private",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    receipt = json.loads(receipt_result.stdout)
    assert receipt["schema"] == MAIL_DELIVERY_RECEIPT_SCHEMA
    assert "Private Recruiter" not in receipt_result.stdout
    assert "raw-provider-id-123" not in receipt_result.stdout

    ledger_result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-delivery-ledger",
            "--intelligence",
            str(intelligence),
            "--history",
            str(history),
            "--approvals",
            str(approvals),
            "--delivery",
            str(delivery),
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
    assert ledger["schema"] == MAIL_DELIVERY_LEDGER_SCHEMA
    assert ledger["kpis"]["provider_draft_requested"] == 1
    assert "private-recruiter@example.test" not in ledger_result.stdout
    assert "raw-provider-id-123" not in ledger_result.stdout
