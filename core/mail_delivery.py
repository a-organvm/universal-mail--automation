"""Redacted delivery intent receipts for approved UMA draft packages."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.mail_draft_approval import (
    MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA,
    build_draft_approval_ledger,
)
from core.mail_draft_package import MAIL_DRAFT_PACKAGE_SCHEMA

MAIL_DELIVERY_LEDGER_SCHEMA = "uma.mail.delivery_ledger.v1"
MAIL_DELIVERY_RECEIPT_SCHEMA = "uma.mail.delivery_receipt.v1"

DELIVERY_STATUS_VALUES = (
    "provider_draft_requested",
    "provider_draft_recorded",
    "send_requested",
    "sent_recorded",
    "blocked",
    "canceled",
)
DELIVERY_REASON_CODE_VALUES = (
    "approved_for_provider_draft",
    "operator_confirmed_external_draft",
    "operator_confirmed_external_send",
    "final_review_required",
    "provider_unavailable",
    "portal_required",
    "not_current",
    "duplicate",
    "policy_blocked",
)

DEFAULT_MAX_DELIVERY_ITEMS = 100
DEFAULT_MAX_DELIVERY_RECEIPTS = 40


class MailDeliveryError(ValueError):
    """Raised when delivery state cannot be read or written."""

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
        raise MailDeliveryError("draft package input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailDeliveryError("draft package input is not valid JSON") from e
    except OSError as e:
        raise MailDeliveryError(f"draft package input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailDeliveryError("draft package input has invalid shape")
    return data


def _coerce_draft_package(draft_package: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(draft_package, dict):
        data = draft_package
    else:
        data = _read_json(Path(draft_package).expanduser())
    if data.get("schema") != MAIL_DRAFT_PACKAGE_SCHEMA:
        raise MailDeliveryError(f"draft package input must be {MAIL_DRAFT_PACKAGE_SCHEMA}")
    return data


def _drafts_by_id(draft_package: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    drafts: Dict[str, Dict[str, Any]] = {}
    for draft in draft_package.get("drafts") or []:
        if isinstance(draft, dict) and isinstance(draft.get("draft_id"), str):
            drafts[draft["draft_id"]] = draft
    return drafts


def _validate_status(delivery_status: str) -> str:
    normalized = str(delivery_status or "").strip().lower()
    if normalized not in DELIVERY_STATUS_VALUES:
        raise MailDeliveryError(f"delivery_status must be one of {', '.join(DELIVERY_STATUS_VALUES)}")
    return normalized


def _validate_reason(reason_code: str) -> str:
    normalized = str(reason_code or "").strip().lower()
    if normalized not in DELIVERY_REASON_CODE_VALUES:
        raise MailDeliveryError(f"reason_code must be one of {', '.join(DELIVERY_REASON_CODE_VALUES)}")
    return normalized


def _receipt_sort_key(receipt: Dict[str, Any]) -> Tuple[datetime, str]:
    return (
        _parse_dt(receipt.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        str(receipt.get("receipt_id") or ""),
    )


def load_delivery_receipts(receipt_path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    """Load redacted delivery receipts from JSONL."""
    if receipt_path is None:
        return []
    path = Path(receipt_path).expanduser()
    if not path.exists():
        return []
    if not path.is_file():
        raise MailDeliveryError("delivery receipt path is not a file")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise MailDeliveryError(f"delivery receipts could not be read: {e}") from e

    receipts: List[Dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            raise MailDeliveryError(f"delivery receipt line {index} is not valid JSON") from e
        if not isinstance(data, dict) or data.get("schema") != MAIL_DELIVERY_RECEIPT_SCHEMA:
            raise MailDeliveryError(f"delivery receipt line {index} must be {MAIL_DELIVERY_RECEIPT_SCHEMA}")
        receipts.append(data)
    return receipts


def _latest_by_draft(receipts: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for receipt in sorted(receipts, key=_receipt_sort_key):
        draft_id = receipt.get("draft_id")
        if isinstance(draft_id, str):
            latest[draft_id] = receipt
    return latest


def _approved_by_draft(approval_ledger: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    approved: Dict[str, Dict[str, Any]] = {}
    for item in approval_ledger.get("items") or []:
        if isinstance(item, dict) and item.get("decision") == "approved" and isinstance(item.get("draft_id"), str):
            approved[item["draft_id"]] = item
    return approved


def _external_reference(external_reference: Optional[str]) -> Dict[str, Any]:
    raw = str(external_reference or "").strip()
    return {
        "provided": bool(raw),
        "hash": _hash("externalref", raw) if raw else None,
        "stored_raw": False,
    }


def _next_step(approved: bool, receipt: Optional[Dict[str, Any]]) -> str:
    if not approved:
        return "approve_or_revise_draft"
    if receipt is None:
        return "request_provider_draft_after_separate_confirmation"
    status = receipt.get("delivery_status")
    if status == "provider_draft_requested":
        return "create_provider_draft_in_official_surface"
    if status == "provider_draft_recorded":
        return "final_send_approval_required"
    if status == "send_requested":
        return "send_in_official_surface_after_final_confirmation"
    if status == "sent_recorded":
        return "reconcile_action_receipt"
    if status == "blocked":
        return "resolve_delivery_blocker"
    if status == "canceled":
        return "no_delivery_action"
    return "review_delivery_state"


def _redacted_item(
    draft: Dict[str, Any],
    approval: Optional[Dict[str, Any]],
    receipt: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    approved = approval is not None
    status = receipt.get("delivery_status") if receipt else ("ready_for_provider_draft" if approved else "not_approved")
    return {
        "schema": "uma.mail.delivery_item.v1",
        "draft_id": draft.get("draft_id"),
        "action_id": draft.get("action_id"),
        "evidence_id": draft.get("evidence_id"),
        "approval_decision": "approved" if approved else "not_approved",
        "approval_receipt_id": approval.get("last_receipt_id") if approval else None,
        "delivery_status": status,
        "reason_code": receipt.get("reason_code") if receipt else None,
        "last_receipt_id": receipt.get("receipt_id") if receipt else None,
        "last_updated_at": receipt.get("created_at") if receipt else None,
        "provider": receipt.get("provider") if receipt else None,
        "external_reference": receipt.get("external_reference") if receipt else _external_reference(None),
        "next_allowed_step": _next_step(approved, receipt),
        "uma_created_provider_draft": False,
        "uma_sent_message": False,
        "mailbox_mutations_allowed": False,
    }


def build_delivery_ledger(
    draft_package: Union[Dict[str, Any], Path, str],
    *,
    approval_receipt_path: Union[Path, str, None] = None,
    delivery_receipt_path: Union[Path, str, None] = None,
    max_items: int = DEFAULT_MAX_DELIVERY_ITEMS,
    max_receipts: int = DEFAULT_MAX_DELIVERY_RECEIPTS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Merge draft approvals with redacted delivery intent/status receipts."""
    package = _coerce_draft_package(draft_package)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    approval_ledger = build_draft_approval_ledger(
        package,
        receipt_path=approval_receipt_path,
        max_items=max_items,
        max_receipts=max_receipts,
        now=checked_at,
    )
    approved = _approved_by_draft(approval_ledger)
    drafts = _drafts_by_id(package)
    receipts = load_delivery_receipts(delivery_receipt_path)
    latest = _latest_by_draft(receipts)
    items = [
        _redacted_item(draft, approved.get(draft_id), latest.get(draft_id))
        for draft_id, draft in drafts.items()
    ]
    items = sorted(
        items,
        key=lambda item: (
            {
                "ready_for_provider_draft": 0,
                "provider_draft_requested": 1,
                "provider_draft_recorded": 2,
                "send_requested": 3,
                "blocked": 4,
                "not_approved": 5,
                "canceled": 6,
                "sent_recorded": 7,
            }.get(str(item.get("delivery_status")), 9),
            str(item.get("draft_id")),
        ),
    )
    counts = Counter(str(item.get("delivery_status") or "unknown") for item in items)
    recent = sorted(receipts, key=_receipt_sort_key, reverse=True)[: max(0, int(max_receipts))]
    return {
        "schema": MAIL_DELIVERY_LEDGER_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "provider_drafts": False,
            "local_receipts_only": True,
            "operator_attestation_supported": True,
        },
        "source": {
            "draft_package_schema": package.get("schema"),
            "approval_receipt_schema": MAIL_DRAFT_APPROVAL_RECEIPT_SCHEMA,
            "action_id": (package.get("action") or {}).get("id"),
            "approval_receipt_filename": Path(approval_receipt_path).expanduser().name if approval_receipt_path else None,
            "delivery_receipt_filename": Path(delivery_receipt_path).expanduser().name if delivery_receipt_path else None,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "private_draft_content_omitted": True,
            "external_reference_stored_raw": False,
        },
        "kpis": {
            "draft_candidates": len(items),
            "approved": len(approved),
            "not_approved": counts.get("not_approved", 0),
            "ready_for_provider_draft": counts.get("ready_for_provider_draft", 0),
            "provider_draft_requested": counts.get("provider_draft_requested", 0),
            "provider_draft_recorded": counts.get("provider_draft_recorded", 0),
            "send_requested": counts.get("send_requested", 0),
            "sent_recorded": counts.get("sent_recorded", 0),
            "blocked": counts.get("blocked", 0),
            "canceled": counts.get("canceled", 0),
            "receipts": len(receipts),
            "uma_provider_drafts_created": 0,
            "uma_sends": 0,
            "mailbox_mutations_allowed": 0,
        },
        "answers": {
            "what_can_move_to_provider_draft": [
                {"draft_id": item["draft_id"], "action_id": item["action_id"], "next_allowed_step": item["next_allowed_step"]}
                for item in items
                if item.get("delivery_status") == "ready_for_provider_draft"
            ],
            "what_needs_final_send_review": [
                {"draft_id": item["draft_id"], "action_id": item["action_id"], "provider": item.get("provider")}
                for item in items
                if item.get("delivery_status") == "provider_draft_recorded"
            ],
            "what_proof_exists": {
                "receipt_count": len(receipts),
                "latest_receipt_ids": [receipt.get("receipt_id") for receipt in recent[:10]],
                "redacted": True,
                "official_provider_proof": False,
            },
        },
        "items": items[: max(1, int(max_items))],
        "receipts": recent,
    }


def build_delivery_receipt(
    draft_package: Union[Dict[str, Any], Path, str],
    *,
    draft_id: str,
    delivery_status: str,
    reason_code: str,
    approval_receipt_path: Union[Path, str, None],
    receipt_path: Union[Path, str],
    ack_private: bool = False,
    provider: str = "",
    external_reference: Optional[str] = None,
    actor: str = "operator",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Append a redacted local delivery receipt for an approved draft candidate."""
    if not ack_private:
        raise MailDeliveryError("mail delivery receipt requires ack_private=true", status_code=403)
    package = _coerce_draft_package(draft_package)
    drafts = _drafts_by_id(package)
    if draft_id not in drafts:
        raise MailDeliveryError("draft_id is not present in the draft package", status_code=404)

    approval_ledger = build_draft_approval_ledger(
        package,
        receipt_path=approval_receipt_path,
        max_items=DEFAULT_MAX_DELIVERY_ITEMS,
        max_receipts=DEFAULT_MAX_DELIVERY_RECEIPTS,
        now=now,
    )
    approved = _approved_by_draft(approval_ledger)
    approval = approved.get(draft_id)
    if approval is None:
        raise MailDeliveryError("draft_id does not have an approved draft approval receipt", status_code=409)

    normalized_status = _validate_status(delivery_status)
    normalized_reason = _validate_reason(reason_code)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    occurred = _format_dt(checked_at)
    draft = drafts[draft_id]
    provider_name = str(provider or "").strip().lower()[:64] or "manual"
    receipt_id = _hash("delivery", occurred, draft_id, normalized_status, normalized_reason, provider_name)
    official_proof_required = normalized_status in {"provider_draft_recorded", "sent_recorded"}
    receipt = {
        "schema": MAIL_DELIVERY_RECEIPT_SCHEMA,
        "status": "recorded",
        "receipt_id": receipt_id,
        "created_at": occurred,
        "actor": str(actor or "operator")[:64],
        "draft_id": draft_id,
        "action_id": draft.get("action_id"),
        "evidence_id": draft.get("evidence_id"),
        "approval_receipt_id": approval.get("last_receipt_id"),
        "delivery_status": normalized_status,
        "reason_code": normalized_reason,
        "provider": provider_name,
        "external_reference": _external_reference(external_reference),
        "proof_scope": "local_operator_delivery_attestation",
        "privacy": {
            "redacted": True,
            "raw_mail_printed": False,
            "draft_body_printed": False,
            "external_reference_stored_raw": False,
            "freeform_private_notes": False,
        },
        "safety": {
            "uma_created_provider_draft": False,
            "uma_sent_message": False,
            "mailbox_mutations_allowed": False,
            "operator_attestation_only": True,
            "requires_official_provider_receipt": official_proof_required,
        },
    }
    path = Path(receipt_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as e:
        raise MailDeliveryError(f"delivery receipt could not be written: {e}") from e
    return receipt
