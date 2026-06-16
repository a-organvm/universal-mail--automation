"""Redacted action ledger and local receipts for UMA mail operations."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.mail_action_plan import MAIL_ACTION_PLAN_SCHEMA, MailActionPlanError, build_action_plan

MAIL_ACTION_LEDGER_SCHEMA = "uma.mail.action_ledger.v1"
MAIL_ACTION_RECEIPT_SCHEMA = "uma.mail.action_receipt.v1"

ACTION_STATUS_VALUES = ("open", "reviewing", "waiting", "blocked", "resolved", "ignored")
ACTION_REASON_CODE_VALUES = (
    "evidence_reviewed",
    "draft_prepared",
    "awaiting_reply",
    "portal_verified",
    "legal_waiting",
    "provider_blocked",
    "needs_human",
    "not_actionable",
    "duplicate",
    "reopened",
)

DEFAULT_MAX_LEDGER_ITEMS = 100
DEFAULT_MAX_RECEIPTS = 40


class MailActionLedgerError(ValueError):
    """Raised when an action ledger or receipt cannot be built."""

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


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise MailActionLedgerError("action plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailActionLedgerError("action plan input is not valid JSON") from e
    except OSError as e:
        raise MailActionLedgerError(f"action plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailActionLedgerError("action plan input has invalid shape")
    return data


def _coerce_action_plan(action_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(action_plan, dict):
        data = action_plan
    else:
        data = _load_json(Path(action_plan).expanduser())
    if data.get("schema") != MAIL_ACTION_PLAN_SCHEMA:
        raise MailActionLedgerError(f"action plan input must be {MAIL_ACTION_PLAN_SCHEMA}")
    return data


def build_action_plan_for_ledger(
    intelligence: Union[Dict[str, Any], Path, str],
    *,
    max_items: int = DEFAULT_MAX_LEDGER_ITEMS,
) -> Dict[str, Any]:
    """Build an action plan and normalize action-plan errors for ledger callers."""
    try:
        return build_action_plan(intelligence, max_items=max_items)
    except MailActionPlanError as e:
        raise MailActionLedgerError(e.detail, status_code=e.status_code) from e


def _action_items_by_id(action_plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in action_plan.get("items") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            out[item["id"]] = item
    return out


def _redacted_ids(values: Iterable[Any]) -> List[str]:
    out = []
    seen = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        out.append(trimmed)
        seen.add(trimmed)
    return out


def _validate_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized not in ACTION_STATUS_VALUES:
        raise MailActionLedgerError(
            f"action_status must be one of {', '.join(ACTION_STATUS_VALUES)}"
        )
    return normalized


def _validate_reason(reason_code: str) -> str:
    normalized = str(reason_code or "").strip().lower()
    if normalized not in ACTION_REASON_CODE_VALUES:
        raise MailActionLedgerError(
            f"reason_code must be one of {', '.join(ACTION_REASON_CODE_VALUES)}"
        )
    return normalized


def _receipt_sort_key(receipt: Dict[str, Any]) -> Tuple[datetime, str]:
    return (
        _parse_dt(receipt.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        str(receipt.get("receipt_id") or ""),
    )


def load_action_receipts(receipt_path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    """Load redacted action receipts from a JSONL file.

    A missing file is a valid empty ledger; malformed existing files fail closed.
    """
    if receipt_path is None:
        return []
    path = Path(receipt_path).expanduser()
    if not path.exists():
        return []
    if not path.is_file():
        raise MailActionLedgerError("action receipt ledger path is not a file")

    receipts: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise MailActionLedgerError(f"action receipt ledger could not be read: {e}") from e

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            raise MailActionLedgerError(f"action receipt ledger line {index} is not valid JSON") from e
        if not isinstance(data, dict) or data.get("schema") != MAIL_ACTION_RECEIPT_SCHEMA:
            raise MailActionLedgerError(
                f"action receipt ledger line {index} must be {MAIL_ACTION_RECEIPT_SCHEMA}"
            )
        receipts.append(data)
    return receipts


def _receipt_for_action(receipts: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for receipt in sorted(receipts, key=_receipt_sort_key):
        action_id = receipt.get("action_id")
        if isinstance(action_id, str):
            latest[action_id] = receipt
    return latest


def _ledger_item(item: Dict[str, Any], receipt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    status = receipt.get("action_status") if receipt else "open"
    return {
        "schema": "uma.mail.action_ledger_item.v1",
        "action_id": item.get("id"),
        "action_status": status,
        "reason_code": receipt.get("reason_code") if receipt else None,
        "last_receipt_id": receipt.get("receipt_id") if receipt else None,
        "last_updated_at": receipt.get("created_at") if receipt else None,
        "proof_scope": "local_operator_receipt" if receipt else "planned_not_receipted",
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "kind": item.get("kind"),
        "recommended_lane": item.get("recommended_lane"),
        "lane_title": item.get("lane_title"),
        "approval_type": item.get("approval_type"),
        "automation_boundary": item.get("automation_boundary"),
        "ops_lane_status": item.get("ops_lane_status"),
        "finding_count": item.get("finding_count"),
        "sample_evidence_ids": item.get("sample_evidence_ids") or [],
        "next_action": item.get("next_action"),
        "send_allowed": False,
        "mailbox_mutations_allowed": False,
    }


def _ledger_kpis(items: List[Dict[str, Any]], receipts: List[Dict[str, Any]], orphaned_receipts: int) -> Dict[str, Any]:
    counts = Counter(str(item.get("action_status") or "open") for item in items)
    active_statuses = {"open", "reviewing", "waiting", "blocked"}
    active_items = [item for item in items if item.get("action_status") in active_statuses]
    return {
        "action_groups": len(items),
        "open": counts.get("open", 0),
        "reviewing": counts.get("reviewing", 0),
        "waiting": counts.get("waiting", 0),
        "blocked": counts.get("blocked", 0),
        "resolved": counts.get("resolved", 0),
        "ignored": counts.get("ignored", 0),
        "active": len(active_items),
        "findings_active": sum(_safe_int(item.get("finding_count")) for item in active_items),
        "findings_resolved": sum(
            _safe_int(item.get("finding_count")) for item in items if item.get("action_status") == "resolved"
        ),
        "receipts": len(receipts),
        "actions_with_receipts": len({r.get("action_id") for r in receipts if isinstance(r.get("action_id"), str)}),
        "orphaned_receipts": orphaned_receipts,
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
    }


def _ledger_answers(items: List[Dict[str, Any]], kpis: Dict[str, Any], receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    active = [item for item in items if item.get("action_status") in {"open", "reviewing", "waiting", "blocked"}]
    latest_receipts = sorted(receipts, key=_receipt_sort_key, reverse=True)[:10]
    return {
        "what_matters_now": [
            {
                "action_id": item.get("action_id"),
                "priority": item.get("priority"),
                "action_status": item.get("action_status"),
                "kind": item.get("kind"),
                "recommended_lane": item.get("recommended_lane"),
                "finding_count": item.get("finding_count"),
                "next_action": item.get("next_action"),
            }
            for item in active[:10]
        ],
        "what_is_blocked": {
            "blocked_action_groups": kpis["blocked"],
            "waiting_action_groups": kpis["waiting"],
            "findings_active": kpis["findings_active"],
        },
        "what_was_safely_handled": {
            "resolved_action_groups": kpis["resolved"],
            "ignored_action_groups": kpis["ignored"],
            "findings_resolved": kpis["findings_resolved"],
            "mailbox_mutations": 0,
            "sends": 0,
            "proof_scope": "local_operator_receipts_only",
        },
        "what_proof_exists": {
            "receipt_count": kpis["receipts"],
            "latest_receipt_ids": [receipt.get("receipt_id") for receipt in latest_receipts],
            "redacted": True,
            "no_raw_mail": True,
        },
    }


def build_action_ledger(
    action_plan: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str, None] = None,
    max_items: int = DEFAULT_MAX_LEDGER_ITEMS,
    max_receipts: int = DEFAULT_MAX_RECEIPTS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Merge a redacted action plan with local receipts into a current ledger."""
    plan = _coerce_action_plan(action_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    receipts = load_action_receipts(receipt_path)
    actions = _action_items_by_id(plan)
    latest = _receipt_for_action(receipts)
    orphaned_receipts = sum(1 for receipt in receipts if receipt.get("action_id") not in actions)

    items = [
        _ledger_item(item, latest.get(action_id))
        for action_id, item in actions.items()
    ]
    items = sorted(
        items,
        key=lambda item: (
            {"blocked": 0, "waiting": 1, "open": 2, "reviewing": 3, "resolved": 4, "ignored": 5}.get(
                str(item.get("action_status")),
                9,
            ),
            -_safe_int(item.get("priority_score")),
            str(item.get("action_id")),
        ),
    )
    limited_items = items[: max(1, int(max_items))]
    recent_receipts = sorted(receipts, key=_receipt_sort_key, reverse=True)[: max(0, int(max_receipts))]
    kpis = _ledger_kpis(items, receipts, orphaned_receipts)
    return {
        "schema": MAIL_ACTION_LEDGER_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "local_receipts_only": True,
        },
        "source": {
            "action_plan_schema": plan.get("schema"),
            "action_plan_generated_at": (plan.get("source") or {}).get("checked_at"),
            "receipt_filename": Path(receipt_path).expanduser().name if receipt_path else None,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "freeform_private_notes": False,
        },
        "kpis": kpis,
        "answers": _ledger_answers(items, kpis, receipts),
        "items": limited_items,
        "receipts": recent_receipts,
    }


def build_action_receipt(
    action_plan: Union[Dict[str, Any], Path, str],
    *,
    action_id: str,
    action_status: str,
    reason_code: str,
    receipt_path: Union[Path, str],
    evidence_ids: Optional[Iterable[Any]] = None,
    actor: str = "operator",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Append a redacted local receipt for a planned action."""
    plan = _coerce_action_plan(action_plan)
    actions = _action_items_by_id(plan)
    if action_id not in actions:
        raise MailActionLedgerError("action_id is not present in the current action plan", status_code=404)

    status = _validate_status(action_status)
    reason = _validate_reason(reason_code)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    occurred = _format_dt(checked_at)
    ids = _redacted_ids(evidence_ids or [])
    item = actions[action_id]
    receipt_id = _hash("receipt", occurred, action_id, status, reason, ",".join(ids))
    receipt = {
        "schema": MAIL_ACTION_RECEIPT_SCHEMA,
        "status": "recorded",
        "receipt_id": receipt_id,
        "created_at": occurred,
        "actor": str(actor or "operator")[:64],
        "action_id": action_id,
        "action_status": status,
        "reason_code": reason,
        "action_kind": item.get("kind"),
        "recommended_lane": item.get("recommended_lane"),
        "approval_type": item.get("approval_type"),
        "evidence_ids": ids,
        "proof_scope": "local_operator_receipt",
        "privacy": {
            "redacted": True,
            "raw_mail_printed": False,
            "freeform_private_notes": False,
        },
        "safety": {
            "send_allowed": False,
            "mailbox_mutations_allowed": False,
            "records_external_claim_only": True,
        },
    }

    path = Path(receipt_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as e:
        raise MailActionLedgerError(f"action receipt could not be written: {e}") from e
    return receipt
