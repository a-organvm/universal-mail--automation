"""Read-only mail/LinkedIn follow-up resolver snapshots for UMA."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.mail_delivery import MailDeliveryError, load_delivery_receipts
from core.mail_draft_approval import MailDraftApprovalError, load_draft_approval_receipts
from core.mail_resolver_plan import MAIL_RESOLVER_PLAN_SCHEMA
from core.mail_resolver_receipt import build_resolver_receipt

FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA = "uma.followup.resolver_snapshot.v1"
FOLLOWUP_RESOLVER_ACTION_SCHEMA = "uma.followup.resolver_action.v1"
FOLLOWUP_RESOLVER_RECEIPTS_SCHEMA = "uma.followup.resolver_receipts.v1"

DEFAULT_FOLLOWUP_RESOLVER_MAX_ITEMS = 100


class FollowupResolverError(ValueError):
    """Raised when a follow-up resolver snapshot cannot be built."""

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
        raise FollowupResolverError("resolver plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FollowupResolverError("resolver plan input is not valid JSON") from e
    except OSError as e:
        raise FollowupResolverError(f"resolver plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise FollowupResolverError("resolver plan input has invalid shape")
    return data


def _coerce_resolver_plan(resolver_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(resolver_plan, dict):
        data = resolver_plan
    else:
        data = _read_json(Path(resolver_plan).expanduser())
    if data.get("schema") != MAIL_RESOLVER_PLAN_SCHEMA:
        raise FollowupResolverError(f"resolver plan input must be {MAIL_RESOLVER_PLAN_SCHEMA}")
    return data


def _planned_followup_items(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in plan.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("resolver_type") == "reply_follow_up" or item.get("official_surface") == "mail_or_linkedin_inbox":
            items.append(item)
    return sorted(
        items,
        key=lambda item: (
            -_safe_int(item.get("priority_score")),
            str(item.get("action_id") or ""),
        ),
    )


def _latest(receipts: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    sorted_receipts = sorted(
        [receipt for receipt in receipts if isinstance(receipt, dict)],
        key=lambda receipt: (
            _parse_dt(receipt.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            str(receipt.get("receipt_id") or ""),
        ),
    )
    return sorted_receipts[-1] if sorted_receipts else None


def _by_action(receipts: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        action_id = receipt.get("action_id")
        if isinstance(action_id, str) and action_id:
            grouped[action_id].append(receipt)
    return grouped


def _load_approval_receipts(path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    try:
        return load_draft_approval_receipts(path)
    except MailDraftApprovalError as e:
        raise FollowupResolverError(e.detail, status_code=e.status_code) from e


def _load_delivery_receipts(path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    try:
        return load_delivery_receipts(path)
    except MailDeliveryError as e:
        raise FollowupResolverError(e.detail, status_code=e.status_code) from e


def _external_reference(snapshot_id: str, action_id: str, source_receipt_id: str) -> Dict[str, Any]:
    raw = f"followup_snapshot:{snapshot_id}:{action_id}:{source_receipt_id}"
    return {
        "provided": bool(source_receipt_id),
        "hash": _hash("externalref", raw) if source_receipt_id else None,
        "stored_raw": False,
    }


def _reason_for_delivery(receipt: Dict[str, Any]) -> str:
    status = str(receipt.get("delivery_status") or "")
    reason = str(receipt.get("reason_code") or "")
    if status == "blocked":
        if reason == "provider_unavailable":
            return "blocked_provider_unavailable"
        if reason == "duplicate":
            return "duplicate"
        return "awaiting_provider"
    if status == "canceled":
        return "not_actionable"
    if status == "sent_recorded":
        return "awaiting_reply"
    return "official_surface_checked"


def _status_for_delivery(receipt: Dict[str, Any]) -> str:
    status = str(receipt.get("delivery_status") or "")
    if status == "blocked":
        return "verified_blocked"
    if status == "canceled":
        return "not_applicable"
    if status == "sent_recorded":
        return "verified_waiting"
    return "needs_follow_up"


def _candidate_from_state(
    *,
    snapshot_id: str,
    action_id: str,
    approvals: List[Dict[str, Any]],
    deliveries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    latest_delivery = _latest(deliveries)
    latest_approval = _latest(approvals)

    if latest_delivery:
        source_receipt_id = str(latest_delivery.get("receipt_id") or "")
        return {
            "action_id": action_id,
            "resolver_status": _status_for_delivery(latest_delivery),
            "reason_code": _reason_for_delivery(latest_delivery),
            "proof_type": "delivery_receipt",
            "provider": str(latest_delivery.get("provider") or "mail_or_linkedin")[:64],
            "supporting_receipt_schema": latest_delivery.get("schema"),
            "supporting_receipt_id": source_receipt_id,
            "external_reference": _external_reference(snapshot_id, action_id, source_receipt_id),
            "provider_backed_read": False,
            "provider_backed_automation": False,
            "operator_must_record_receipt": True,
        }

    if latest_approval:
        decision = str(latest_approval.get("decision") or "")
        source_receipt_id = str(latest_approval.get("receipt_id") or "")
        if decision == "approved":
            status = "needs_follow_up"
            reason = "official_surface_checked"
        elif decision == "rejected":
            status = "not_applicable"
            reason = "not_actionable"
        else:
            status = "needs_follow_up"
            reason = "external_state_differs"
        return {
            "action_id": action_id,
            "resolver_status": status,
            "reason_code": reason,
            "proof_type": "draft_approval_receipt",
            "provider": "mail_or_linkedin",
            "supporting_receipt_schema": latest_approval.get("schema"),
            "supporting_receipt_id": source_receipt_id,
            "external_reference": _external_reference(snapshot_id, action_id, source_receipt_id),
            "provider_backed_read": False,
            "provider_backed_automation": False,
            "operator_must_record_receipt": True,
        }

    return {
        "action_id": action_id,
        "resolver_status": "needs_follow_up",
        "reason_code": "awaiting_reply",
        "proof_type": "draft_approval_receipt",
        "provider": "mail_or_linkedin",
        "supporting_receipt_schema": None,
        "supporting_receipt_id": None,
        "external_reference": _external_reference(snapshot_id, action_id, ""),
        "provider_backed_read": False,
        "provider_backed_automation": False,
        "operator_must_record_receipt": False,
    }


def _action_row(
    item: Dict[str, Any],
    *,
    snapshot_id: str,
    approvals: List[Dict[str, Any]],
    deliveries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    action_id = str(item.get("action_id") or "")
    approval_counts = Counter(str(receipt.get("decision") or "unknown") for receipt in approvals)
    delivery_counts = Counter(str(receipt.get("delivery_status") or "unknown") for receipt in deliveries)
    candidate = _candidate_from_state(
        snapshot_id=snapshot_id,
        action_id=action_id,
        approvals=approvals,
        deliveries=deliveries,
    )
    return {
        "schema": FOLLOWUP_RESOLVER_ACTION_SCHEMA,
        "action_id": action_id,
        "kind": item.get("kind"),
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "finding_count": _safe_int(item.get("finding_count")),
        "recommended_lane": item.get("recommended_lane"),
        "resolver_type": item.get("resolver_type"),
        "official_surface": item.get("official_surface"),
        "official_surface_label": item.get("official_surface_label"),
        "supported_surfaces": item.get("supported_surfaces") or [],
        "draft_approval_receipts": len(approvals),
        "approved_drafts": approval_counts.get("approved", 0),
        "revise_drafts": approval_counts.get("revise", 0),
        "rejected_drafts": approval_counts.get("rejected", 0),
        "delivery_receipts": len(deliveries),
        "delivery_status_counts": dict(delivery_counts),
        "followup_snapshot_status": candidate["resolver_status"],
        "next_step": _next_step(candidate, approval_counts, delivery_counts),
        "receipt_candidate": candidate,
        "mailbox_mutations_allowed": False,
        "send_allowed": False,
        "portal_mutations_allowed": False,
    }


def _next_step(candidate: Dict[str, Any], approvals: Counter, deliveries: Counter) -> str:
    if deliveries.get("sent_recorded", 0):
        return "record_waiting_or_provider_send_proof_before_closure"
    if deliveries.get("provider_draft_recorded", 0):
        return "perform_final_send_review_in_official_surface"
    if deliveries.get("provider_draft_requested", 0) or deliveries.get("send_requested", 0):
        return "complete_requested_delivery_step_in_official_surface"
    if deliveries.get("blocked", 0):
        return "resolve_followup_delivery_blocker"
    if approvals.get("approved", 0):
        return "record_delivery_intent_or_provider_draft_status"
    if approvals.get("revise", 0):
        return "revise_private_draft_before_delivery"
    if approvals.get("rejected", 0):
        return "mark_followup_not_actionable_or_reopen_with_new_evidence"
    if candidate.get("operator_must_record_receipt"):
        return "record_followup_resolver_receipt"
    return "open_private_evidence_and_prepare_draft_for_approval"


def build_followup_resolver_snapshot(
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    draft_approval_receipt_path: Union[Path, str, None] = None,
    delivery_receipt_path: Union[Path, str, None] = None,
    max_items: int = DEFAULT_FOLLOWUP_RESOLVER_MAX_ITEMS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a redacted read-only snapshot of mail/LinkedIn follow-up state."""
    plan = _coerce_resolver_plan(resolver_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    planned_items = _planned_followup_items(plan)
    approval_receipts = _load_approval_receipts(draft_approval_receipt_path)
    delivery_receipts = _load_delivery_receipts(delivery_receipt_path)
    approvals_by_action = _by_action(approval_receipts)
    deliveries_by_action = _by_action(delivery_receipts)
    snapshot_id = _hash(
        "followupsnapshot",
        _format_dt(checked_at),
        ",".join(str(item.get("action_id") or "") for item in planned_items),
        len(approval_receipts),
        len(delivery_receipts),
    )
    bounded_items = planned_items[: max(1, int(max_items))]
    actions = [
        _action_row(
            item,
            snapshot_id=snapshot_id,
            approvals=approvals_by_action.get(str(item.get("action_id") or ""), []),
            deliveries=deliveries_by_action.get(str(item.get("action_id") or ""), []),
        )
        for item in bounded_items
    ]
    recordable = [
        action
        for action in actions
        if bool((action.get("receipt_candidate") or {}).get("operator_must_record_receipt"))
    ]
    delivery_counts = Counter(str(receipt.get("delivery_status") or "unknown") for receipt in delivery_receipts)
    approval_counts = Counter(str(receipt.get("decision") or "unknown") for receipt in approval_receipts)
    kpis = {
        "planned_followup_actions": len(planned_items),
        "planned_followup_findings": sum(_safe_int(item.get("finding_count")) for item in planned_items),
        "draft_approval_receipts": len(approval_receipts),
        "approved_drafts": approval_counts.get("approved", 0),
        "revise_drafts": approval_counts.get("revise", 0),
        "rejected_drafts": approval_counts.get("rejected", 0),
        "delivery_receipts": len(delivery_receipts),
        "provider_draft_requested": delivery_counts.get("provider_draft_requested", 0),
        "provider_draft_recorded": delivery_counts.get("provider_draft_recorded", 0),
        "send_requested": delivery_counts.get("send_requested", 0),
        "sent_recorded": delivery_counts.get("sent_recorded", 0),
        "blocked": delivery_counts.get("blocked", 0),
        "recordable_receipt_candidates": len(recordable),
        "provider_backed_read": 0,
        "provider_backed_automation": 0,
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
        "portal_mutations_allowed": 0,
    }

    status = "ok"
    if planned_items and not recordable:
        status = "needs_private_review"
    elif not planned_items:
        status = "no_followup_actions"

    return {
        "schema": FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA,
        "status": status,
        "snapshot_id": snapshot_id,
        "mode": {
            "read_only": True,
            "provider": "mail_or_linkedin",
            "official_surface": "mail_or_linkedin_inbox",
            "provider_backed_read": False,
            "provider_backed_automation": False,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
        },
        "source": {
            "resolver_plan_schema": plan.get("schema"),
            "resolver_plan_checked_at": (plan.get("source") or {}).get("checked_at"),
            "draft_approval_receipt_filename": (
                Path(draft_approval_receipt_path).expanduser().name if draft_approval_receipt_path else None
            ),
            "delivery_receipt_filename": Path(delivery_receipt_path).expanduser().name if delivery_receipt_path else None,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "contains_raw_external_state": False,
            "raw_linkedin_state_included": False,
            "private_draft_content_omitted": True,
        },
        "coverage": {
            "supported_surfaces": ["gmail", "mailapp", "outlook", "imap", "linkedin_manual"],
            "provider_backed_surfaces": [],
            "coverage_note": "This snapshot reconciles UMA local approval/delivery proof for mail or LinkedIn follow-ups; it does not read LinkedIn, send mail, create drafts, or mutate any mailbox.",
        },
        "kpis": kpis,
        "answers": {
            "what_matters_now": [
                {
                    "action_id": action.get("action_id"),
                    "finding_count": action.get("finding_count"),
                    "candidate_status": (action.get("receipt_candidate") or {}).get("resolver_status"),
                    "next_step": action.get("next_step"),
                }
                for action in actions[:10]
            ],
            "what_is_blocked": {
                "needs_private_review": status == "needs_private_review",
                "blocked_delivery_receipts": kpis["blocked"],
                "provider_backed_surfaces": [],
            },
            "what_proof_exists": {
                "snapshot_id": snapshot_id,
                "draft_approval_receipts": kpis["draft_approval_receipts"],
                "delivery_receipts": kpis["delivery_receipts"],
                "receipt_candidates": kpis["recordable_receipt_candidates"],
                "provider_backed_automation": False,
                "raw_external_state_stored": False,
            },
        },
        "actions": actions,
    }


def build_followup_resolver_receipts(
    snapshot: Dict[str, Any],
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str],
    max_receipts: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Record redacted resolver receipts from follow-up snapshot candidates."""
    plan = _coerce_resolver_plan(resolver_plan)
    if not isinstance(snapshot, dict) or snapshot.get("schema") != FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA:
        raise FollowupResolverError(f"snapshot must be {FOLLOWUP_RESOLVER_SNAPSHOT_SCHEMA}")

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
        proof_type = str(candidate.get("proof_type") or "")
        proof_scope = (
            "local_followup_delivery_state"
            if proof_type == "delivery_receipt"
            else "local_followup_draft_approval_state"
        )
        receipts.append(
            build_resolver_receipt(
                plan,
                action_id=str(candidate.get("action_id") or ""),
                resolver_status=str(candidate.get("resolver_status") or ""),
                reason_code=str(candidate.get("reason_code") or ""),
                proof_type=proof_type,
                provider=str(candidate.get("provider") or "mail_or_linkedin"),
                external_reference_hash=str(external_hash or ""),
                proof_scope=proof_scope,
                provider_backed_read=False,
                source_snapshot_id=str(snapshot.get("snapshot_id") or ""),
                actor="followup_resolver",
                receipt_path=receipt_path,
                now=checked_at,
            )
        )

    return {
        "schema": FOLLOWUP_RESOLVER_RECEIPTS_SCHEMA,
        "status": "recorded" if receipts else "no_receipts_recorded",
        "mode": {
            "local_file_write": True,
            "provider": "mail_or_linkedin",
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
            "raw_mail_printed": False,
            "raw_linkedin_state_printed": False,
            "private_draft_content_printed": False,
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
