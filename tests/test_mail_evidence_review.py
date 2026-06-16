"""Gated private evidence review tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.historical_intelligence import build_historical_intelligence
from core.mail_evidence_review import (
    MAIL_EVIDENCE_REVIEW_SCHEMA,
    MailEvidenceReviewError,
    build_evidence_review,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "historical"


def _write_history(tmp_path: Path) -> Path:
    target = tmp_path / "history.json"
    shutil.copyfile(HISTORICAL_FIXTURE_DIR / "latest.json", target)
    return target


def _lead_evidence_id(history: Path) -> str:
    snapshot = build_historical_intelligence(history)
    return snapshot["opportunities"][0]["evidence_ids"][0]


def test_evidence_review_requires_private_ack(tmp_path):
    history = _write_history(tmp_path)
    evidence_id = _lead_evidence_id(history)

    try:
        build_evidence_review(history, evidence_id)
    except MailEvidenceReviewError as e:
        assert e.status_code == 403
        assert "ack_private=true" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailEvidenceReviewError")


def test_evidence_review_opens_exact_private_source_when_acknowledged(tmp_path):
    history = _write_history(tmp_path)
    evidence_id = _lead_evidence_id(history)

    review = build_evidence_review(history, evidence_id, ack_private=True, body_char_limit=40)
    payload = json.dumps(review)

    assert review["schema"] == MAIL_EVIDENCE_REVIEW_SCHEMA
    assert review["mode"]["private_review"] is True
    assert review["mode"]["mailbox_mutations"] is False
    assert review["mode"]["sends"] is False
    assert review["privacy"]["contains_private_mail"] is True
    assert review["privacy"]["public_safe"] is False
    assert review["safety"]["send_allowed"] is False
    assert review["message"]["evidence_id"] == evidence_id
    assert review["message"]["sender"] == "Private Recruiter"
    assert review["message"]["address"] == "private-recruiter@example.test"
    assert review["message"]["subject"] == "Private lead should not leak"
    assert review["message"]["body"] == "Could you send your availability for a c"
    assert str(history) not in payload


def test_evidence_review_normalizes_invalid_history_shape(tmp_path):
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"schema": "uma.mail.history_export.v1"}), encoding="utf-8")

    try:
        build_evidence_review(history, "ev_missing", ack_private=True)
    except MailEvidenceReviewError as e:
        assert e.status_code == 422
        assert "messages array" in e.detail
    else:  # pragma: no cover
        raise AssertionError("expected MailEvidenceReviewError")


def test_evidence_review_api_requires_token_and_ack(tmp_path, monkeypatch):
    history = _write_history(tmp_path)
    evidence_id = _lead_evidence_id(history)
    monkeypatch.setenv("UMA_HISTORICAL_MAIL_PATH", str(history))
    monkeypatch.delenv("UMA_OPS_TOKEN", raising=False)
    client = TestClient(app)

    assert client.get(f"/v1/ops/evidence/{evidence_id}?ack_private=true").status_code == 503

    monkeypatch.setenv("UMA_OPS_TOKEN", "expected-token")
    assert client.get(f"/v1/ops/evidence/{evidence_id}?ack_private=true").status_code == 401

    no_ack = client.get(
        f"/v1/ops/evidence/{evidence_id}",
        headers={"Authorization": "Bearer expected-token"},
    )
    assert no_ack.status_code == 403

    response = client.get(
        f"/v1/ops/evidence/{evidence_id}?ack_private=true&body_char_limit=50",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["schema"] == MAIL_EVIDENCE_REVIEW_SCHEMA
    assert "Private Recruiter" in response.text
    assert "private-recruiter@example.test" in response.text


def test_mail_evidence_review_cli_requires_ack_and_can_show_private_source(tmp_path):
    history = _write_history(tmp_path)
    evidence_id = _lead_evidence_id(history)

    denied = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-evidence-review",
            "--history",
            str(history),
            "--evidence-id",
            evidence_id,
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
            "mail-evidence-review",
            "--history",
            str(history),
            "--evidence-id",
            evidence_id,
            "--ack-private",
            "--body-char-limit",
            "50",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    body = json.loads(allowed.stdout)
    assert body["schema"] == MAIL_EVIDENCE_REVIEW_SCHEMA
    assert body["message"]["sender"] == "Private Recruiter"
    assert body["safety"]["mailbox_mutations_allowed"] is False
