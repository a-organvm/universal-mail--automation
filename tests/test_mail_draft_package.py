"""Private draft package tests."""

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
from core.mail_draft_package import (
    MAIL_DRAFT_PACKAGE_SCHEMA,
    MailDraftPackageError,
    build_draft_package,
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


def _draft_action_id(intelligence: Path) -> str:
    plan = build_action_plan(intelligence)
    for item in plan["items"]:
        if item["kind"] == "missed_lead":
            return item["id"]
    raise AssertionError("missing missed_lead action")


def _non_draft_action_id(intelligence: Path) -> str:
    plan = build_action_plan(intelligence)
    for item in plan["items"]:
        if item["kind"] != "missed_lead":
            return item["id"]
    raise AssertionError("missing non-draft action")


def test_draft_package_requires_private_ack(tmp_path):
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = _draft_action_id(intelligence)

    try:
        build_draft_package(plan, history, action_id)
    except MailDraftPackageError as e:
        assert e.status_code == 403
        assert "ack_private=true" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailDraftPackageError")


def test_draft_package_builds_private_approval_gated_candidate(tmp_path):
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = _draft_action_id(intelligence)

    package = build_draft_package(plan, history, action_id, ack_private=True, user_name="Anthony", max_drafts=1)

    assert package["schema"] == MAIL_DRAFT_PACKAGE_SCHEMA
    assert package["mode"]["draft_only"] is True
    assert package["mode"]["sends"] is False
    assert package["safety"]["send_allowed"] is False
    assert package["safety"]["mailbox_mutations_allowed"] is False
    assert package["privacy"]["contains_private_mail"] is True
    assert len(package["drafts"]) == 1
    draft = package["drafts"][0]
    assert draft["schema"] == "uma.mail.draft_candidate.v1"
    assert draft["to"]["name"] == "Private Recruiter"
    assert draft["to"]["address"] == "private-recruiter@example.test"
    assert draft["subject"] == "Re: Private lead should not leak"
    assert "sorry for the slow reply" in draft["body"]
    assert draft["approval"]["required"] is True
    assert draft["approval"]["send_allowed"] is False
    assert any(fact["field"] == "subject" for fact in draft["fact_checklist"])
    assert str(history) not in json.dumps(package)


def test_draft_package_rejects_non_draft_actions(tmp_path):
    history, intelligence = _write_inputs(tmp_path)
    plan = build_action_plan(intelligence)
    action_id = _non_draft_action_id(intelligence)

    try:
        build_draft_package(plan, history, action_id, ack_private=True)
    except MailDraftPackageError as e:
        assert e.status_code == 409
        assert "missed_lead" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailDraftPackageError")


def test_draft_package_api_requires_token_and_ack(tmp_path, monkeypatch):
    history, intelligence = _write_inputs(tmp_path)
    action_id = _draft_action_id(intelligence)
    monkeypatch.setenv("UMA_HISTORICAL_INTELLIGENCE_PATH", str(intelligence))
    monkeypatch.setenv("UMA_HISTORICAL_MAIL_PATH", str(history))
    monkeypatch.delenv("UMA_OPS_TOKEN", raising=False)
    client = TestClient(app)

    assert client.get(f"/v1/ops/draft-package/{action_id}?ack_private=true").status_code == 503

    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    assert client.get(f"/v1/ops/draft-package/{action_id}?ack_private=true").status_code == 401

    no_ack = client.get(
        f"/v1/ops/draft-package/{action_id}",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert no_ack.status_code == 403

    response = client.get(
        f"/v1/ops/draft-package/{action_id}?ack_private=true&max_drafts=1",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["schema"] == MAIL_DRAFT_PACKAGE_SCHEMA
    assert "Private Recruiter" in response.text
    assert "private-recruiter@example.test" in response.text


def test_mail_draft_package_cli_requires_ack_and_can_show_private_draft(tmp_path):
    history, intelligence = _write_inputs(tmp_path)
    action_id = _draft_action_id(intelligence)

    denied = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-draft-package",
            "--intelligence",
            str(intelligence),
            "--history",
            str(history),
            "--action-id",
            action_id,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert denied.returncode == 1
    assert "ack_private=true" in denied.stderr
    assert "Private Recruiter" not in denied.stdout
    assert "Traceback" not in denied.stderr

    allowed = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-draft-package",
            "--intelligence",
            str(intelligence),
            "--history",
            str(history),
            "--action-id",
            action_id,
            "--ack-private",
            "--max-drafts",
            "1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(allowed.stdout)
    assert body["schema"] == MAIL_DRAFT_PACKAGE_SCHEMA
    assert body["drafts"][0]["to"]["name"] == "Private Recruiter"
    assert body["safety"]["send_allowed"] is False
