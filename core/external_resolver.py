"""Planned external-surface resolver snapshots for UMA."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.mail_resolver_plan import MAIL_RESOLVER_PLAN_SCHEMA
from core.mail_resolver_receipt import (
    MailResolverReceiptError,
    build_resolver_receipt,
    load_resolver_receipts,
)

EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA = "uma.external.resolver_snapshot.v1"
EXTERNAL_RESOLVER_ACTION_SCHEMA = "uma.external.resolver_action.v1"
EXTERNAL_RESOLVER_RECEIPTS_SCHEMA = "uma.external.resolver_receipts.v1"

DEFAULT_EXTERNAL_RESOLVER_MAX_ITEMS = 100

EXTERNAL_RESOLVER_TYPES = {
    "account_security_verification",
    "payment_or_billing_verification",
    "provider_status_reconcile",
    "subscription_decision",
    "legal_review",
}

PROOF_BY_RESOLVER_TYPE = {
    "account_security_verification": "action_receipt",
    "payment_or_billing_verification": "action_receipt",
    "provider_status_reconcile": "action_receipt",
    "subscription_decision": "action_receipt",
    "legal_review": "action_receipt",
}

NEXT_STEP_BY_RESOLVER_TYPE = {
    "account_security_verification": "open_official_security_surface_or_record_blocker",
    "payment_or_billing_verification": "open_financial_or_billing_surface_or_record_blocker",
    "provider_status_reconcile": "open_provider_dashboard_cli_or_api_or_record_blocker",
    "subscription_decision": "review_vendor_subscription_surface_and_record_decision",
    "legal_review": "complete_counsel_review_or_record_waiting_state",
}


class ExternalResolverError(ValueError):
    """Raised when an external-surface resolver snapshot cannot be built."""

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


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ExternalResolverError("resolver plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ExternalResolverError("resolver plan input is not valid JSON") from e
    except OSError as e:
        raise ExternalResolverError(f"resolver plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise ExternalResolverError("resolver plan input has invalid shape")
    return data


def _coerce_resolver_plan(resolver_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(resolver_plan, dict):
        data = resolver_plan
    else:
        data = _read_json(Path(resolver_plan).expanduser())
    if data.get("schema") != MAIL_RESOLVER_PLAN_SCHEMA:
        raise ExternalResolverError(f"resolver plan input must be {MAIL_RESOLVER_PLAN_SCHEMA}")
    return data


def _load_receipts(path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    try:
        return load_resolver_receipts(path)
    except MailResolverReceiptError as e:
        raise ExternalResolverError(e.detail, status_code=e.status_code) from e


def _receipt_sort_key(receipt: Dict[str, Any]) -> Tuple[datetime, str]:
    return (
        _parse_dt(receipt.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        str(receipt.get("receipt_id") or ""),
    )


def _latest(receipts: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [receipt for receipt in receipts if isinstance(receipt, dict)]
    if not valid:
        return None
    return sorted(valid, key=_receipt_sort_key)[-1]


def _by_action(receipts: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        action_id = receipt.get("action_id")
        if isinstance(action_id, str) and action_id:
            grouped[action_id].append(receipt)
    return grouped


def _planned_external_items(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in plan.get("items") or []:
        if not isinstance(item, dict):
            continue
        resolver_type = str(item.get("resolver_type") or "")
        if resolver_type in EXTERNAL_RESOLVER_TYPES:
            items.append(item)
    return sorted(
        items,
        key=lambda item: (
            -_safe_int(item.get("priority_score")),
            str(item.get("resolver_type") or ""),
            str(item.get("action_id") or ""),
        ),
    )


def _external_reference(snapshot_id: str, action_id: str) -> Dict[str, Any]:
    raw = f"external_snapshot:{snapshot_id}:{action_id}"
    return {
        "provided": True,
        "hash": _hash("externalref", raw),
        "stored_raw": False,
    }


def _candidate(
    item: Dict[str, Any],
    *,
    snapshot_id: str,
    operator_attestation_requested: bool,
    latest_receipt: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    action_id = str(item.get("action_id") or "")
    resolver_type = str(item.get("resolver_type") or "")
    if latest_receipt and latest_receipt.get("resolver_status") in {"verified_resolved", "not_applicable"}:
        status = str(latest_receipt.get("resolver_status") or "not_applicable")
        reason = str(latest_receipt.get("reason_code") or "not_actionable")
        must_record = False
    else:
        status = "needs_follow_up"
        reason = "awaiting_provider"
        must_record = operator_attestation_requested
    return {
        "action_id": action_id,
        "resolver_status": status,
        "reason_code": reason,
        "proof_type": PROOF_BY_RESOLVER_TYPE.get(resolver_type, "action_receipt"),
        "provider": "manual",
        "external_reference": _external_reference(snapshot_id, action_id),
        "provider_backed_read": False,
        "provider_backed_automation": False,
        "operator_must_record_receipt": must_record,
    }


def _next_step(item: Dict[str, Any], candidate: Dict[str, Any], latest_receipt: Optional[Dict[str, Any]]) -> str:
    if latest_receipt and latest_receipt.get("resolver_status") in {"verified_resolved", "not_applicable"}:
        return "keep_visible_for_regression_monitoring"
    if candidate.get("operator_must_record_receipt"):
        return "record_local_blocker_attestation_then_open_official_surface"
    return NEXT_STEP_BY_RESOLVER_TYPE.get(str(item.get("resolver_type") or ""), "open_official_surface_or_record_blocker")


def _action_row(
    item: Dict[str, Any],
    *,
    snapshot_id: str,
    receipts: List[Dict[str, Any]],
    operator_attestation_requested: bool,
) -> Dict[str, Any]:
    latest_receipt = _latest(receipts)
    candidate = _candidate(
        item,
        snapshot_id=snapshot_id,
        operator_attestation_requested=operator_attestation_requested,
        latest_receipt=latest_receipt,
    )
    return {
        "schema": EXTERNAL_RESOLVER_ACTION_SCHEMA,
        "action_id": str(item.get("action_id") or ""),
        "kind": item.get("kind"),
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "finding_count": _safe_int(item.get("finding_count")),
        "recommended_lane": item.get("recommended_lane"),
        "resolver_type": item.get("resolver_type"),
        "official_surface": item.get("official_surface"),
        "official_surface_label": item.get("official_surface_label"),
        "supported_surfaces": item.get("supported_surfaces") or [],
        "required_proof": item.get("required_proof") or [],
        "provider_hints": item.get("provider_hints") or [],
        "provider_hint_counts": item.get("provider_hint_counts") or {},
        "existing_resolver_receipts": len(receipts),
        "latest_resolver_status": latest_receipt.get("resolver_status") if latest_receipt else None,
        "latest_reason_code": latest_receipt.get("reason_code") if latest_receipt else None,
        "latest_proof_type": latest_receipt.get("proof_type") if latest_receipt else None,
        "external_snapshot_status": candidate["resolver_status"],
        "next_step": _next_step(item, candidate, latest_receipt),
        "receipt_candidate": candidate,
        "mailbox_mutations_allowed": False,
        "send_allowed": False,
        "portal_mutations_allowed": False,
    }


def build_external_resolver_snapshot(
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str, None] = None,
    max_items: int = DEFAULT_EXTERNAL_RESOLVER_MAX_ITEMS,
    operator_attestation_requested: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a redacted planned snapshot for external official-surface lanes."""
    plan = _coerce_resolver_plan(resolver_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    planned_items = _planned_external_items(plan)
    receipts = _load_receipts(receipt_path)
    receipts_by_action = _by_action(receipts)
    snapshot_id = _hash(
        "externalsnapshot",
        _format_dt(checked_at),
        ",".join(str(item.get("action_id") or "") for item in planned_items),
        len(receipts),
        bool(operator_attestation_requested),
    )
    bounded_items = planned_items[: max(1, int(max_items))]
    actions = [
        _action_row(
            item,
            snapshot_id=snapshot_id,
            receipts=receipts_by_action.get(str(item.get("action_id") or ""), []),
            operator_attestation_requested=operator_attestation_requested,
        )
        for item in bounded_items
    ]
    recordable = [
        action
        for action in actions
        if bool((action.get("receipt_candidate") or {}).get("operator_must_record_receipt"))
    ]
    planned_action_ids = {item.get("action_id") for item in planned_items}
    by_resolver = Counter(str(item.get("resolver_type") or "unknown") for item in planned_items)
    provider_counts: Counter = Counter()
    for item in planned_items:
        counts = item.get("provider_hint_counts") or {}
        if isinstance(counts, dict):
            for hint, count in counts.items():
                provider_counts[str(hint)] += _safe_int(count)
    receipt_statuses = Counter(
        str(receipt.get("resolver_status") or "unknown")
        for receipt in receipts
        if receipt.get("action_id") in planned_action_ids
    )
    kpis = {
        "planned_external_actions": len(planned_items),
        "planned_external_findings": sum(_safe_int(item.get("finding_count")) for item in planned_items),
        "security_verify": sum(
            _safe_int(item.get("finding_count"))
            for item in planned_items
            if item.get("resolver_type") == "account_security_verification"
        ),
        "billing_or_payment_verify": sum(
            _safe_int(item.get("finding_count"))
            for item in planned_items
            if item.get("resolver_type") == "payment_or_billing_verification"
        ),
        "provider_reconcile": sum(
            _safe_int(item.get("finding_count"))
            for item in planned_items
            if item.get("resolver_type") == "provider_status_reconcile"
        ),
        "subscription_decision": sum(
            _safe_int(item.get("finding_count"))
            for item in planned_items
            if item.get("resolver_type") == "subscription_decision"
        ),
        "legal_review": sum(
            _safe_int(item.get("finding_count")) for item in planned_items if item.get("resolver_type") == "legal_review"
        ),
        "resolver_type_counts": dict(by_resolver),
        "provider_hint_counts": dict(provider_counts.most_common()),
        "resolver_receipts": sum(1 for receipt in receipts if receipt.get("action_id") in planned_action_ids),
        "verified_resolved": receipt_statuses.get("verified_resolved", 0),
        "verified_blocked": receipt_statuses.get("verified_blocked", 0),
        "needs_follow_up": receipt_statuses.get("needs_follow_up", 0),
        "recordable_receipt_candidates": len(recordable),
        "operator_attestation_requested": 1 if operator_attestation_requested else 0,
        "provider_backed_read": 0,
        "provider_backed_automation": 0,
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
        "portal_mutations_allowed": 0,
    }

    if not planned_items:
        status = "no_external_actions"
    elif recordable:
        status = "attestation_ready"
    else:
        status = "planned_only"

    return {
        "schema": EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA,
        "status": status,
        "snapshot_id": snapshot_id,
        "mode": {
            "read_only": True,
            "provider": "external_surfaces",
            "official_surface": "provider_security_billing_subscription_legal",
            "provider_backed_read": False,
            "provider_backed_automation": False,
            "operator_attestation_requested": bool(operator_attestation_requested),
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
        },
        "source": {
            "resolver_plan_schema": plan.get("schema"),
            "resolver_plan_checked_at": (plan.get("source") or {}).get("checked_at"),
            "receipt_filename": Path(receipt_path).expanduser().name if receipt_path else None,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "contains_raw_external_state": False,
            "raw_portal_state_included": False,
            "external_reference_stored_raw": False,
        },
        "coverage": {
            "supported_lanes": sorted(EXTERNAL_RESOLVER_TYPES),
            "provider_backed_surfaces": [],
            "coverage_note": "This snapshot represents official-surface work and local resolver receipts. It does not log into portals, read external providers, or mutate accounts.",
        },
        "kpis": kpis,
        "answers": {
            "what_matters_now": [
                {
                    "action_id": action.get("action_id"),
                    "resolver_type": action.get("resolver_type"),
                    "finding_count": action.get("finding_count"),
                    "provider_hints": action.get("provider_hints") or [],
                    "candidate_status": (action.get("receipt_candidate") or {}).get("resolver_status"),
                    "next_step": action.get("next_step"),
                }
                for action in actions[:10]
            ],
            "what_is_blocked": {
                "official_surface_required": kpis["planned_external_findings"],
                "operator_attestation_requested": bool(operator_attestation_requested),
                "top_provider_hints": list((kpis.get("provider_hint_counts") or {}).keys())[:10],
                "provider_backed_surfaces": [],
            },
            "what_proof_exists": {
                "snapshot_id": snapshot_id,
                "resolver_receipts": kpis["resolver_receipts"],
                "receipt_candidates": kpis["recordable_receipt_candidates"],
                "provider_backed_automation": False,
                "raw_external_state_stored": False,
            },
        },
        "actions": actions,
    }


def build_external_resolver_receipts(
    snapshot: Dict[str, Any],
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str],
    max_receipts: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Record local resolver receipts from explicit external-lane attestations."""
    plan = _coerce_resolver_plan(resolver_plan)
    if not isinstance(snapshot, dict) or snapshot.get("schema") != EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA:
        raise ExternalResolverError(f"snapshot must be {EXTERNAL_RESOLVER_SNAPSHOT_SCHEMA}")

    actions = [item for item in snapshot.get("actions") or [] if isinstance(item, dict)]
    limit = len(actions) if max_receipts is None else max(0, int(max_receipts))
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    receipts: List[Dict[str, Any]] = []
    candidates_seen = 0
    for action in actions:
        candidate = action.get("receipt_candidate") or {}
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("operator_must_record_receipt")):
            continue
        candidates_seen += 1
        if len(receipts) >= limit:
            continue
        external_reference = candidate.get("external_reference") or {}
        external_hash = external_reference.get("hash") if isinstance(external_reference, dict) else None
        receipts.append(
            build_resolver_receipt(
                plan,
                action_id=str(candidate.get("action_id") or ""),
                resolver_status=str(candidate.get("resolver_status") or ""),
                reason_code=str(candidate.get("reason_code") or ""),
                proof_type=str(candidate.get("proof_type") or ""),
                provider=str(candidate.get("provider") or "manual"),
                external_reference_hash=str(external_hash or ""),
                proof_scope="external_surface_operator_attestation",
                provider_backed_read=False,
                source_snapshot_id=str(snapshot.get("snapshot_id") or ""),
                actor="external_resolver",
                receipt_path=receipt_path,
                now=checked_at,
            )
        )

    return {
        "schema": EXTERNAL_RESOLVER_RECEIPTS_SCHEMA,
        "status": "recorded" if receipts else "no_receipts_recorded",
        "mode": {
            "local_file_write": True,
            "provider": "external_surfaces",
            "read_only_provider_queries": False,
            "provider_backed_read": False,
            "provider_backed_automation": False,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
        },
        "source": {
            "snapshot_schema": snapshot.get("schema"),
            "snapshot_id": snapshot.get("snapshot_id"),
            "snapshot_status": snapshot.get("status"),
            "receipt_filename": Path(receipt_path).expanduser().name,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "raw_external_state_printed": False,
            "raw_external_state_stored": False,
            "external_reference_stored_raw": False,
        },
        "kpis": {
            "receipt_candidates": candidates_seen,
            "receipts_recorded": len(receipts),
            "provider_backed_read_receipts": 0,
            "operator_attestation_receipts": len(receipts),
            "provider_backed_automation": 0,
            "mailbox_mutations_allowed": 0,
            "send_allowed": 0,
            "portal_mutations_allowed": 0,
        },
        "receipts": receipts,
    }
