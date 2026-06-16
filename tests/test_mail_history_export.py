"""Read-only historical mail export tests."""

from __future__ import annotations

import json
import mailbox
import subprocess
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email import policy
from pathlib import Path

from core.historical_intelligence import build_historical_intelligence
from core.mail_history_export import (
    MAIL_HISTORY_EXPORT_RECEIPT_SCHEMA,
    MAIL_HISTORY_EXPORT_SCHEMA,
    MailHistoryExportError,
    build_mail_history_export,
    write_mail_history_export,
)

ROOT = Path(__file__).resolve().parents[1]


def _message(
    *,
    sender: str,
    recipient: str = "Private User <me@example.test>",
    subject: str,
    date: str,
    message_id: str,
    body: str,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Date"] = date
    msg["Message-ID"] = message_id
    msg.set_content(body)
    return msg


def _write_mbox(path: Path, messages: list[EmailMessage]) -> None:
    box = mailbox.mbox(path)
    box.lock()
    try:
        for msg in messages:
            box.add(msg)
        box.flush()
    finally:
        box.unlock()
        box.close()


def test_mail_history_export_normalizes_mbox_and_receipt_stays_redacted(tmp_path):
    mbox_path = tmp_path / "Archive.mbox"
    output = tmp_path / "latest.json"
    private_body = "Could you send your availability for this LinkedIn role?"
    _write_mbox(
        mbox_path,
        [
            _message(
                sender="Private Recruiter <private-recruiter@example.test>",
                subject="Private lead should not leak",
                date="Fri, 1 May 2026 10:00:00 -0400",
                message_id="<lead-1@example.test>",
                body=private_body,
            ),
            _message(
                sender="Security Bot <security@example.test>",
                subject="Security verify",
                date="Mon, 1 Jun 2026 09:00:00 -0400",
                message_id="<security-1@example.test>",
                body="New sign-in detected. Please verify this account login.",
            ),
        ],
    )

    export = build_mail_history_export(
        mbox_path,
        since="2026-05-01",
        until_exclusive="2026-06-16",
        self_addresses=["me@example.test"],
        now=datetime(2026, 6, 15, 18, 0, 0, tzinfo=timezone.utc),
    )
    export_payload = json.dumps(export)

    assert export["schema"] == MAIL_HISTORY_EXPORT_SCHEMA
    assert export["mode"]["read_only"] is True
    assert export["mode"]["mailbox_mutations"] is False
    assert export["privacy"]["private_raw_mail"] is True
    assert export["privacy"]["safe_for_dashboard"] is False
    assert export["source"]["message_count"] == 2
    assert private_body in export_payload
    assert str(tmp_path) not in export_payload

    receipt = write_mail_history_export(export, output, pretty=True)
    receipt_payload = json.dumps(receipt)

    assert receipt["schema"] == MAIL_HISTORY_EXPORT_RECEIPT_SCHEMA
    assert receipt["mode"]["wrote_private_export"] is True
    assert receipt["output"]["message_count"] == 2
    assert receipt["privacy"]["raw_mail_printed_to_stdout"] is False
    assert "Private Recruiter" not in receipt_payload
    assert "private-recruiter@example.test" not in receipt_payload
    assert private_body not in receipt_payload

    intelligence = build_historical_intelligence(output, now=datetime(2026, 6, 15, 18, 0, 0, tzinfo=timezone.utc))
    intelligence_payload = json.dumps(intelligence)
    assert intelligence["schema"] == "uma.mail.intelligence.v1"
    assert intelligence["kpis"]["opportunities"] == 1
    assert intelligence["kpis"]["risks"] >= 1
    assert "Private Recruiter" not in intelligence_payload
    assert private_body not in intelligence_payload


def test_mail_history_export_reads_emlx_directory_without_full_paths(tmp_path):
    source_dir = tmp_path / "Mail" / "Archive.mbox" / "Data" / "Messages"
    source_dir.mkdir(parents=True)
    msg = _message(
        sender="Provider Alert <provider@example.test>",
        subject="Provider billing notice",
        date="Wed, 10 Jun 2026 11:30:00 -0400",
        message_id="<provider-1@example.test>",
        body="Your provider billing renewal requires review before the deadline.",
    )
    raw = msg.as_bytes(policy=policy.default)
    (source_dir / "42.emlx").write_bytes(str(len(raw)).encode("ascii") + b"\n" + raw + b"\n<?xml ignored")

    export = build_mail_history_export(source_dir.parent.parent, source_type="auto")
    payload = json.dumps(export)

    assert export["schema"] == MAIL_HISTORY_EXPORT_SCHEMA
    assert export["source"]["type"] == "emlx_dir"
    assert export["source"]["message_count"] == 1
    assert export["messages"][0]["scope"] == "Archive"
    assert export["messages"][0]["source_name"] == "Archive.mbox"
    assert "provider billing renewal" in payload
    assert str(tmp_path) not in payload


def test_mail_history_export_cli_writes_receipt_not_raw_mail(tmp_path):
    jsonl = tmp_path / "history.ndjson"
    output = tmp_path / "latest.json"
    jsonl.write_text(
        json.dumps(
            {
                "sender": "Private Client <private-client@example.test>",
                "subject": "Private client project",
                "body": "Could you review this consulting opportunity?",
                "received_at": "2026-05-10T12:00:00Z",
                "direction": "inbound",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "mail-history-export",
            "--source",
            str(jsonl),
            "--output",
            str(output),
            "--pretty",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    receipt = json.loads(result.stdout)
    assert receipt["schema"] == MAIL_HISTORY_EXPORT_RECEIPT_SCHEMA
    assert receipt["output"]["message_count"] == 1
    assert output.exists()
    assert "Private Client" not in result.stdout
    assert "private-client@example.test" not in result.stdout
    assert "consulting opportunity" not in result.stdout


def test_mail_history_export_bad_window_raises_clean_error(tmp_path):
    source = tmp_path / "history.json"
    source.write_text('{"messages": []}', encoding="utf-8")

    try:
        build_mail_history_export(source, since="2026-06-16", until_exclusive="2026-06-15")
    except MailHistoryExportError as e:
        assert e.detail == "until_exclusive must be after since"
    else:  # pragma: no cover
        raise AssertionError("expected MailHistoryExportError")
