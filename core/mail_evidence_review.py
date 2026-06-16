"""Gated private review of historical mail evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from core.historical_intelligence import (
    HistoricalIntelligenceError,
    _direction,
    _mail_triage_labels,
    _parse_dt,
    _records,
    _thread_key,
    evidence_id_for_row,
)

MAIL_EVIDENCE_REVIEW_SCHEMA = "uma.mail.evidence_review.v1"

DEFAULT_BODY_CHAR_LIMIT = 6000
DEFAULT_CONTEXT_LIMIT = 6


class MailEvidenceReviewError(ValueError):
    """Raised when private evidence review cannot be served."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_history(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise MailEvidenceReviewError("historical mail input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailEvidenceReviewError("historical mail input is not valid JSON") from e
    except OSError as e:
        raise MailEvidenceReviewError(f"historical mail input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailEvidenceReviewError("historical mail input has invalid shape")
    return data


def _text(value: Any, *, limit: Optional[int] = None) -> Optional[str]:
    if not isinstance(value, str):
        return None
    if limit is None:
        return value
    return value[: max(0, int(limit))]


def _row_time(row: Dict[str, Any]) -> Optional[datetime]:
    return _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))


def _sort_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _row_time(row) or datetime.min.replace(tzinfo=timezone.utc),
            str(row.get("message_id") or row.get("id") or ""),
        ),
    )


def _private_message(row: Dict[str, Any], *, body_char_limit: int) -> Dict[str, Any]:
    evidence_id = evidence_id_for_row(row)
    return {
        "evidence_id": evidence_id,
        "message_id": row.get("message_id") or row.get("id"),
        "thread_id": row.get("thread_id") or row.get("conversation_id") or row.get("thread"),
        "occurred_at": _format_dt(_row_time(row)),
        "direction": _direction(row),
        "scope": row.get("scope"),
        "state": row.get("state"),
        "labels": [label for label in row.get("labels") or [] if isinstance(label, str)][:12],
        "mail_triage_labels": _mail_triage_labels(row.get("labels") or []),
        "sender": _text(row.get("sender")),
        "address": _text(row.get("address")),
        "subject": _text(row.get("subject")),
        "snippet": _text(row.get("snippet"), limit=500),
        "body": _text(row.get("body"), limit=body_char_limit),
    }


def _context_message(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_id": evidence_id_for_row(row),
        "occurred_at": _format_dt(_row_time(row)),
        "direction": _direction(row),
        "scope": row.get("scope"),
        "sender": _text(row.get("sender")),
        "address": _text(row.get("address")),
        "subject": _text(row.get("subject")),
        "snippet": _text(row.get("snippet"), limit=300),
    }


def build_evidence_review(
    history_path: Union[Path, str],
    evidence_id: str,
    *,
    ack_private: bool = False,
    body_char_limit: int = DEFAULT_BODY_CHAR_LIMIT,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Open a private source message for a redacted evidence id.

    This is intentionally not a public/dashboard-safe contract. It returns raw
    sender, address, subject, snippet, and bounded body only after explicit
    acknowledgment.
    """
    if not ack_private:
        raise MailEvidenceReviewError("private evidence review requires ack_private=true", status_code=403)
    if not evidence_id:
        raise MailEvidenceReviewError("evidence_id is required")

    path = Path(history_path).expanduser()
    data = _read_history(path)
    try:
        rows = _records(data)
    except HistoricalIntelligenceError as e:
        raise MailEvidenceReviewError(e.detail, status_code=e.status_code) from e
    matched = None
    for row in rows:
        if evidence_id_for_row(row) == evidence_id:
            matched = row
            break
    if matched is None:
        raise MailEvidenceReviewError("evidence id not found in historical mail export", status_code=404)

    thread_key = _thread_key(matched)
    context_rows = [
        row for row in rows
        if _thread_key(row) == thread_key and evidence_id_for_row(row) != evidence_id
    ]
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)

    return {
        "schema": MAIL_EVIDENCE_REVIEW_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "private_review": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "approval_required_before_send": True,
        },
        "request": {
            "evidence_id": evidence_id,
            "ack_private": True,
            "body_char_limit": max(0, int(body_char_limit)),
            "context_limit": max(0, int(context_limit)),
        },
        "source": {
            "filename": path.name,
            "generated_at": data.get("generated_at"),
            "since": data.get("since"),
            "until_exclusive": data.get("until_exclusive"),
            "message_count": len(rows),
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": False,
            "contains_private_mail": True,
            "public_safe": False,
            "requires_explicit_private_review": True,
            "omits_full_source_path": True,
            "body_bounded": True,
        },
        "safety": {
            "send_allowed": False,
            "mailbox_mutations_allowed": False,
            "draft_allowed_only_after_fact_check": True,
        },
        "message": _private_message(matched, body_char_limit=max(0, int(body_char_limit))),
        "thread_context": [
            _context_message(row)
            for row in _sort_rows(context_rows)[: max(0, int(context_limit))]
        ],
    }
