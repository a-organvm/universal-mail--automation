"""Redacted approval receipts for private UMA draft packages."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.mail_draft_package import MAIL_DRAFT_PACKAGE_SCHEMA

MAIL_DRAFT_APPROVAL_LEDGER_SCHEMA = "uma.mail.draft_approval_ledger.v1"
MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA = "uma.mail.draft_approval_receipt.v1"

DRAFT_APPROVAL_DECISION_VALUES = ("approved", "rejected", "revise")
DRAFT_APPROVAL_REASON_CODE_VALUES = (
    "ready_to_send",
    "needs_edit",
    "fact_issue",
    "wrong_recipient",
    "stale_context",
    "legal_review",
    "duplicate",
    "not_actionable",
)

DEFAULT_MAX_APPROVAL_ITEMS = 100
DEFAULT_MAX_APPROVAL_RECEIPTS = 40


class MailDraftApprovalError(ValueError):
    """Raised when draft approval state cannot be read or written."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise MailDraftApprovalError("draft package input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailDraftApprovalError("draft package input is not valid JSON") from e
    except OSError as e:
        raise MailDraftApprovalError(f"draft package input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailDraftApprovalError("draft package input has invalid shape")
    return data


def _coerce_draft_package(draft_package: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(draft_package, dict):
        data = draft_package
    else:
        data = _read_json(Path(draft_package).expanduser())
    if data.get("schema") != MAIL_DRAFT_PACKAGE_SCHEMA:
        raise MailDraftApprovalError(f"draft package input must be {MAIL_DRAFT_PACKAGE_SCHEMA}")
    return data


def _drafts_by_id(draft_package: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    drafts: Dict[str, Dict[str, Any]] = {}
    for draft in draft_package.get("drafts") or []:
        if isinstance(draft, dict) and isinstance(draft.get("draft_id"), str):
            drafts[draft["draft_id"]] = draft
    return drafts


def _validate_decision(decision: str) -> str:
    normalized = str(decision or "").strip().lower()
    if normalized not in DRAFT_APPROVAL_DECISION_VALUES:
        raise MailDraftApprovalError(
            f"decision must be one of {', '.join(DRAFT_APPROVAL_DECISION_VALUES)}"
        )
    return normalized


def _validate_reason(reason_code: str) -> str:
    normalized = str(reason_code or "").strip().lower()
    if normalized not in DRAFT_APPROVAL_REASON_CODE_VALUES:
        raise MailDraftApprovalError(
            f"reason_code must be one of {', '.join(DRAFT_APPROVAL_REASON_CODE_VALUES)}"
        )
    return normalized


def _receipt_sort_key(receipt: Dict[str, Any]) -> Tuple[datetime, str]:
    return (
        _parse_dt(receipt.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        str(receipt.get("receipt_id") or ""),
    )


def load_draft_approval_receipts(receipt_path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    """Load redacted draft approval receipts from JSONL."""
    if receipt_path is None:
        return []
    path = Path(receipt_path).expanduser()
    if not path.exists():
        return []
    if not path.is_file():
        raise MailDraftApprovalError("draft approval receipt path is not a file")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise MailDraftApprovalError(f"draft approval receipts could not be read: {e}") from e

    receipts: List[Dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            raise MailDraftApprovalError(f"draft approval receipt line {index} is not valid JSON") from e
        if not isinstance(data, dict) or data.get("schema") != MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA:
            raise MailDraftApprovalError(
                f"draft approval receipt line {index} must be {MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA}"
            )
        receipts.append(data)
    return receipts


def _latest_by_draft(receipts: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for receipt in sorted(receipts, key=_receipt_sort_key):
        draft_id = receipt.get("draft_id")
        if isinstance(draft_id, str):
            latest[draft_id] = receipt
    return latest


def _redacted_item(draft: Dict[str, Any], receipt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    decision = receipt.get("decision") if receipt else "pending"
    next_step = "create_provider_draft_after_separate_confirmation" if decision == "approved" else "review_or_revise"
    return {
        "schema": "uma.mail.draft_approval_item.v1",
        "draft_id": draft.get("draft_id"),
        "action_id": draft.get("action_id"),
        "evidence_id": draft.get("evidence_id"),
        "decision": decision,
        "reason_code": receipt.get("reason_code") if receipt else None,
        "last_receipt_id": receipt.get("receipt_id") if receipt else None,
        "last_updated_at": receipt.get("created_at") if receipt else None,
        "approval_scope": "local_operator_draft_approval" if receipt else "pending_operator_review",
        "next_allowed_step": next_step,
        "send_allowed": False,
        "mailbox_mutations_allowed": False,
        "provider_draft_created": False,
    }


def build_draft_approval_ledger(
    draft_package: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str, None] = None,
    max_items: int = DEFAULT_MAX_APPROVAL_ITEMS,
    max_receipts: int = DEFAULT_MAX_APPROVAL_RECEIPTS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Merge private draft package ids with redacted approval receipts."""
    package = _coerce_draft_package(draft_package)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    drafts = _drafts_by_id(package)
    receipts = load_draft_approval_receipts(receipt_path)
    latest = _latest_by_draft(receipts)
    items = [_redacted_item(draft, latest.get(draft_id)) for draft_id, draft in drafts.items()]
    items = sorted(
        items,
        key=lambda item: (
            {"pending": 0, "revise": 1, "approved": 2, "rejected": 3}.get(str(item.get("decision")), 9),
            str(item.get("draft_id")),
        ),
    )
    counts = Counter(str(item.get("decision") or "pending") for item in items)
    recent = sorted(receipts, key=_receipt_sort_key, reverse=True)[: max(0, int(max_receipts))]
    return {
        "schema": MAIL_DRAFT_APPROVAL_LEDGER_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "provider_drafts": False,
            "local_receipts_only": True,
        },
        "source": {
            "draft_package_schema": package.get("schema"),
            "action_id": (package.get("action") or {}).get("id"),
            "receipt_filename": Path(receipt_path).expanduser().name if receipt_path else None,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "private_draft_content_omitted": True,
        },
        "kpis": {
            "draft_candidates": len(items),
            "pending": counts.get("pending", 0),
            "approved": counts.get("approved", 0),
            "rejected": counts.get("rejected", 0),
            "revise": counts.get("revise", 0),
            "receipts": len(receipts),
            "send_allowed": 0,
            "mailbox_mutations_allowed": 0,
            "provider_drafts_created": 0,
        },
        "answers": {
            "what_is_approved": [
                {"draft_id": item["draft_id"], "action_id": item["action_id"], "next_allowed_step": item["next_allowed_step"]}
                for item in items
                if item.get("decision") == "approved"
            ],
            "what_needs_revision": [
                {"draft_id": item["draft_id"], "action_id": item["action_id"], "reason_code": item.get("reason_code")}
                for item in items
                if item.get("decision") == "revise"
            ],
            "what_proof_exists": {
                "receipt_count": len(receipts),
                "latest_receipt_ids": [receipt.get("receipt_id") for receipt in recent[:10]],
                "redacted": True,
            },
        },
        "items": items[: max(1, int(max_items))],
        "receipts": recent,
    }


def build_draft_approval_receipt(
    draft_package: Union[Dict[str, Any], Path, str],
    *,
    draft_id: str,
    decision: str,
    reason_code: str,
    receipt_path: Union[Path, str],
    ack_private: bool = False,
    actor: str = "operator",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Append a redacted local approval receipt for a private draft candidate."""
    if not ack_private:
        raise MailDraftApprovalError("private draft approval requires ack_private=true", status_code=403)
    package = _coerce_draft_package(draft_package)
    drafts = _drafts_by_id(package)
    if draft_id not in drafts:
        raise MailDraftApprovalError("draft_id is not present in the draft package", status_code=404)

    normalized_decision = _validate_decision(decision)
    normalized_reason = _validate_reason(reason_code)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    occurred = _format_dt(checked_at)
    draft = drafts[draft_id]
    receipt_id = _hash("draftapproval", occurred, draft_id, normalized_decision, normalized_reason)
    receipt = {
        "schema": MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA,
        "status": "recorded",
        "receipt_id": receipt_id,
        "created_at": occurred,
        "actor": str(actor or "operator")[:64],
        "draft_id": draft_id,
        "action_id": draft.get("action_id"),
        "evidence_id": draft.get("evidence_id"),
        "decision": normalized_decision,
        "reason_code": normalized_reason,
        "approval_scope": "local_operator_draft_approval",
        "privacy": {
            "redacted": True,
            "raw_mail_printed": False,
            "draft_body_printed": False,
            "freeform_private_notes": False,
        },
        "safety": {
            "send_allowed": False,
            "mailbox_mutations_allowed": False,
            "provider_draft_created": False,
            "approval_does_not_send": True,
        },
    }
    path = Path(receipt_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as e:
        raise MailDraftApprovalError(f"draft approval receipt could not be written: {e}") from e
    return receipt
