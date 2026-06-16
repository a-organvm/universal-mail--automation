"""Redacted resolver proof receipts for UMA official-surface checks."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.mail_resolver_plan import MAIL_RESOLVER_PLAN_SCHEMA

MAIL_RESOLVER_LEDGER_SCHEMA = "uma.mail.resolver_ledger.v1"
MAIL_RESOLVER_RECEIPT_SCHEMA = "uma.mail.resolver_receipt.v1"
MAIL_INVARIANT_ROLLUP_SCHEMA = "uma.mail.invariant_rollup.v1"

RESOLVER_STATUS_VALUES = (
    "verified_waiting",
    "verified_blocked",
    "verified_resolved",
    "needs_follow_up",
    "not_found",
    "not_applicable",
)
RESOLVER_REASON_CODE_VALUES = (
    "official_surface_checked",
    "external_state_matches_mail",
    "external_state_differs",
    "awaiting_provider",
    "awaiting_reply",
    "legal_review_complete",
    "billing_verified",
    "security_reviewed",
    "github_reconciled",
    "subscription_decision_recorded",
    "blocked_no_auth",
    "blocked_provider_unavailable",
    "duplicate",
    "not_actionable",
)
RESOLVER_PROOF_TYPE_VALUES = (
    "action_receipt",
    "delivery_receipt",
    "draft_approval_receipt",
    "future_provider_send_receipt",
    "future_send_receipt_if_reply_needed",
    "github_issue_pr_billing_or_security_state",
    "legal_review_receipt",
    "manual_review_receipt",
    "official_payment_or_invoice_verification",
    "official_provider_status",
    "official_provider_verification",
    "official_subscription_status",
    "operator_decision",
)

DEFAULT_MAX_RESOLVER_LEDGER_ITEMS = 100
DEFAULT_MAX_RESOLVER_RECEIPTS = 40


class MailResolverReceiptError(ValueError):
    """Raised when resolver proof state cannot be read or written."""

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
        raise MailResolverReceiptError("resolver plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailResolverReceiptError("resolver plan input is not valid JSON") from e
    except OSError as e:
        raise MailResolverReceiptError(f"resolver plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailResolverReceiptError("resolver plan input has invalid shape")
    return data


def _coerce_resolver_plan(resolver_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(resolver_plan, dict):
        data = resolver_plan
    else:
        data = _read_json(Path(resolver_plan).expanduser())
    if data.get("schema") != MAIL_RESOLVER_PLAN_SCHEMA:
        raise MailResolverReceiptError(f"resolver plan input must be {MAIL_RESOLVER_PLAN_SCHEMA}")
    return data


def _resolver_items_by_id(resolver_plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in resolver_plan.get("items") or []:
        if isinstance(item, dict) and isinstance(item.get("action_id"), str):
            out[item["action_id"]] = item
    return out


def _validate_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized not in RESOLVER_STATUS_VALUES:
        raise MailResolverReceiptError(f"resolver_status must be one of {', '.join(RESOLVER_STATUS_VALUES)}")
    return normalized


def _validate_reason(reason_code: str) -> str:
    normalized = str(reason_code or "").strip().lower()
    if normalized not in RESOLVER_REASON_CODE_VALUES:
        raise MailResolverReceiptError(f"reason_code must be one of {', '.join(RESOLVER_REASON_CODE_VALUES)}")
    return normalized


def _validate_proof_type(proof_type: str, resolver_item: Dict[str, Any]) -> Tuple[str, bool]:
    normalized = str(proof_type or "").strip().lower()
    if normalized not in RESOLVER_PROOF_TYPE_VALUES:
        raise MailResolverReceiptError(f"proof_type must be one of {', '.join(RESOLVER_PROOF_TYPE_VALUES)}")
    required = {str(item) for item in resolver_item.get("required_proof") or []}
    matches = normalized in required
    if not matches and required:
        raise MailResolverReceiptError("proof_type is not required by the current resolver plan")
    return normalized, matches


def _external_reference(raw_reference: Optional[str]) -> Dict[str, Any]:
    raw = str(raw_reference or "").strip()
    return {
        "provided": bool(raw),
        "hash": _hash("externalref", raw) if raw else None,
        "stored_raw": False,
    }


def _external_reference_from_hash(reference_hash: Optional[str]) -> Dict[str, Any]:
    raw = str(reference_hash or "").strip()
    if not raw:
        return _external_reference(None)
    return {
        "provided": True,
        "hash": raw[:128],
        "stored_raw": False,
    }


def _receipt_sort_key(receipt: Dict[str, Any]) -> Tuple[datetime, str]:
    return (
        _parse_dt(receipt.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        str(receipt.get("receipt_id") or ""),
    )


def load_resolver_receipts(receipt_path: Union[Path, str, None]) -> List[Dict[str, Any]]:
    """Load redacted resolver receipts from JSONL."""
    if receipt_path is None:
        return []
    path = Path(receipt_path).expanduser()
    if not path.exists():
        return []
    if not path.is_file():
        raise MailResolverReceiptError("resolver receipt ledger path is not a file")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise MailResolverReceiptError(f"resolver receipt ledger could not be read: {e}") from e

    receipts: List[Dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            raise MailResolverReceiptError(f"resolver receipt ledger line {index} is not valid JSON") from e
        if not isinstance(data, dict) or data.get("schema") != MAIL_RESOLVER_RECEIPT_SCHEMA:
            raise MailResolverReceiptError(
                f"resolver receipt ledger line {index} must be {MAIL_RESOLVER_RECEIPT_SCHEMA}"
            )
        receipts.append(data)
    return receipts


def _latest_by_action(receipts: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for receipt in sorted(receipts, key=_receipt_sort_key):
        action_id = receipt.get("action_id")
        if isinstance(action_id, str):
            latest[action_id] = receipt
    return latest


def _ledger_item(item: Dict[str, Any], receipt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    status = receipt.get("resolver_status") if receipt else "not_started"
    safety = receipt.get("safety") if isinstance(receipt, dict) else {}
    if not isinstance(safety, dict):
        safety = {}
    provider_backed_read = bool(safety.get("provider_backed_read")) if receipt else False
    operator_attestation = bool(safety.get("operator_attestation_only")) if receipt else False
    return {
        "schema": "uma.mail.resolver_ledger_item.v1",
        "action_id": item.get("action_id"),
        "resolver_status": status,
        "reason_code": receipt.get("reason_code") if receipt else None,
        "last_receipt_id": receipt.get("receipt_id") if receipt else None,
        "last_updated_at": receipt.get("created_at") if receipt else None,
        "proof_type": receipt.get("proof_type") if receipt else None,
        "proof_scope": receipt.get("proof_scope") if receipt else "planned_not_receipted",
        "provider": receipt.get("provider") if receipt else None,
        "external_reference": receipt.get("external_reference") if receipt else _external_reference(None),
        "resolver_type": item.get("resolver_type"),
        "official_surface": item.get("official_surface"),
        "official_surface_label": item.get("official_surface_label"),
        "required_proof": item.get("required_proof") or [],
        "current_blocker": item.get("current_blocker"),
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "kind": item.get("kind"),
        "recommended_lane": item.get("recommended_lane"),
        "finding_count": item.get("finding_count"),
        "sample_evidence_ids": item.get("sample_evidence_ids") or [],
        "next_step": item.get("next_step"),
        "operator_attestation_only": operator_attestation,
        "provider_backed_receipt": provider_backed_read,
        "provider_backed_read": provider_backed_read,
        "send_allowed": False,
        "mailbox_mutations_allowed": False,
        "portal_mutations_allowed": False,
    }


def _ledger_kpis(items: List[Dict[str, Any]], receipts: List[Dict[str, Any]], orphaned: int) -> Dict[str, Any]:
    counts = Counter(str(item.get("resolver_status") or "not_started") for item in items)
    resolved = [item for item in items if item.get("resolver_status") == "verified_resolved"]
    unresolved = [
        item for item in items
        if item.get("resolver_status") in {"not_started", "verified_waiting", "verified_blocked", "needs_follow_up", "not_found"}
    ]
    return {
        "resolver_groups": len(items),
        "not_started": counts.get("not_started", 0),
        "verified_waiting": counts.get("verified_waiting", 0),
        "verified_blocked": counts.get("verified_blocked", 0),
        "verified_resolved": counts.get("verified_resolved", 0),
        "needs_follow_up": counts.get("needs_follow_up", 0),
        "not_found": counts.get("not_found", 0),
        "not_applicable": counts.get("not_applicable", 0),
        "findings_verified_resolved": sum(_safe_int(item.get("finding_count")) for item in resolved),
        "findings_unresolved": sum(_safe_int(item.get("finding_count")) for item in unresolved),
        "receipts": len(receipts),
        "actions_with_receipts": len({r.get("action_id") for r in receipts if isinstance(r.get("action_id"), str)}),
        "orphaned_receipts": orphaned,
        "operator_attestation_receipts": sum(
            1
            for receipt in receipts
            if not bool((receipt.get("safety") or {}).get("provider_backed_read"))
        ),
        "provider_backed_receipts": sum(
            1
            for receipt in receipts
            if bool((receipt.get("safety") or {}).get("provider_backed_read"))
        ),
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
        "portal_mutations_allowed": 0,
    }


def _ledger_answers(items: List[Dict[str, Any]], kpis: Dict[str, Any], receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
    unresolved = [
        item for item in items
        if item.get("resolver_status") in {"not_started", "verified_waiting", "verified_blocked", "needs_follow_up", "not_found"}
    ]
    recent = sorted(receipts, key=_receipt_sort_key, reverse=True)[:10]
    return {
        "what_matters_now": [
            {
                "action_id": item.get("action_id"),
                "resolver_status": item.get("resolver_status"),
                "resolver_type": item.get("resolver_type"),
                "official_surface": item.get("official_surface"),
                "finding_count": item.get("finding_count"),
                "next_step": item.get("next_step"),
            }
            for item in unresolved[:10]
        ],
        "what_is_blocked": {
            "not_started": kpis["not_started"],
            "verified_blocked": kpis["verified_blocked"],
            "needs_follow_up": kpis["needs_follow_up"],
            "findings_unresolved": kpis["findings_unresolved"],
        },
        "what_was_safely_handled": {
            "verified_resolved": kpis["verified_resolved"],
            "findings_verified_resolved": kpis["findings_verified_resolved"],
            "provider_backed_automation": 0,
            "provider_backed_read_receipts": kpis["provider_backed_receipts"],
            "mailbox_mutations": 0,
            "sends": 0,
        },
        "what_proof_exists": {
            "receipt_count": kpis["receipts"],
            "latest_receipt_ids": [receipt.get("receipt_id") for receipt in recent],
            "operator_attestation_receipts": kpis["operator_attestation_receipts"],
            "provider_backed_receipts": kpis["provider_backed_receipts"],
            "redacted": True,
            "raw_external_references_stored": False,
        },
    }


# Maps every resolver_status to exactly one of the goal's three operator-visible
# states. The mapping is intentionally strict: only verified_resolved (which is
# always receipt-backed) counts as closed-with-receipt — nothing is inflated into
# "closed". Anything not explicitly resolved or blocked stays visible as
# waiting-with-evidence ("keep it visible until resolved").
_INVARIANT_STATE_BY_STATUS = {
    "verified_resolved": "closed_with_receipt",
    "verified_blocked": "blocked_with_reason",
    "not_started": "waiting_with_evidence",
    "verified_waiting": "waiting_with_evidence",
    "needs_follow_up": "waiting_with_evidence",
    "not_found": "waiting_with_evidence",
    "not_applicable": "waiting_with_evidence",
}


def build_invariant_rollup(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll resolver-ledger items up into the goal's one test of done.

    For every item the operator must be able to see it as exactly one of:
      - closed_with_receipt   — proven handled (verified_resolved, receipt-backed)
      - blocked_with_reason   — an explicit blocker is recorded (verified_blocked)
      - waiting_with_evidence — visible and evidenced, awaiting reply/follow-up/decision

    ``invariant_holds`` is True iff every item maps to one of the three states —
    i.e. nothing escaped classification. An unrecognised status (a future or
    corrupt value) lands in ``unclassified`` and flips ``invariant_holds`` to
    False so an escaped item is surfaced, never silently dropped.
    """
    states = {
        "closed_with_receipt": {"groups": 0, "findings": 0},
        "blocked_with_reason": {"groups": 0, "findings": 0},
        "waiting_with_evidence": {"groups": 0, "findings": 0},
    }
    unclassified: Dict[str, Any] = {"groups": 0, "findings": 0, "statuses": []}
    for item in items:
        status = str(item.get("resolver_status") or "not_started")
        findings = _safe_int(item.get("finding_count"))
        state = _INVARIANT_STATE_BY_STATUS.get(status)
        if state is None:
            unclassified["groups"] += 1
            unclassified["findings"] += findings
            if status not in unclassified["statuses"]:
                unclassified["statuses"].append(status)
            continue
        states[state]["groups"] += 1
        states[state]["findings"] += findings
    total_groups = sum(s["groups"] for s in states.values()) + unclassified["groups"]
    total_findings = sum(s["findings"] for s in states.values()) + unclassified["findings"]
    return {
        "schema": MAIL_INVARIANT_ROLLUP_SCHEMA,
        "states": states,
        "unclassified": unclassified,
        "total": {"groups": total_groups, "findings": total_findings},
        "invariant_holds": unclassified["groups"] == 0,
        "send_allowed": False,
        "mailbox_mutations_allowed": False,
        "portal_mutations_allowed": False,
    }


def build_resolver_ledger(
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str, None] = None,
    max_items: int = DEFAULT_MAX_RESOLVER_LEDGER_ITEMS,
    max_receipts: int = DEFAULT_MAX_RESOLVER_RECEIPTS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Merge a redacted resolver plan with local official-surface receipts."""
    plan = _coerce_resolver_plan(resolver_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    receipts = load_resolver_receipts(receipt_path)
    resolver_items = _resolver_items_by_id(plan)
    latest = _latest_by_action(receipts)
    orphaned = sum(1 for receipt in receipts if receipt.get("action_id") not in resolver_items)
    items = [
        _ledger_item(item, latest.get(action_id))
        for action_id, item in resolver_items.items()
    ]
    items = sorted(
        items,
        key=lambda item: (
            {
                "verified_blocked": 0,
                "needs_follow_up": 1,
                "not_found": 2,
                "not_started": 3,
                "verified_waiting": 4,
                "verified_resolved": 5,
                "not_applicable": 6,
            }.get(str(item.get("resolver_status")), 9),
            -_safe_int(item.get("priority_score")),
            str(item.get("action_id")),
        ),
    )
    recent = sorted(receipts, key=_receipt_sort_key, reverse=True)[: max(0, int(max_receipts))]
    kpis = _ledger_kpis(items, receipts, orphaned)
    return {
        "schema": MAIL_RESOLVER_LEDGER_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
            "local_receipts_only": True,
            "operator_attestation_supported": True,
            "provider_backed_read_supported": True,
            "provider_backed_automation": False,
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
            "external_reference_stored_raw": False,
            "freeform_private_notes": False,
        },
        "kpis": kpis,
        "invariant_rollup": build_invariant_rollup(items),
        "answers": _ledger_answers(items, kpis, receipts),
        "items": items[: max(1, int(max_items))],
        "receipts": recent,
    }


def build_resolver_receipt(
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    action_id: str,
    resolver_status: str,
    reason_code: str,
    proof_type: str,
    receipt_path: Union[Path, str],
    provider: str = "",
    external_reference: Optional[str] = None,
    external_reference_hash: Optional[str] = None,
    proof_scope: str = "official_surface_operator_attestation",
    provider_backed_read: bool = False,
    source_snapshot_id: Optional[str] = None,
    actor: str = "operator",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Append a redacted receipt for an official-surface resolver check."""
    plan = _coerce_resolver_plan(resolver_plan)
    items = _resolver_items_by_id(plan)
    if action_id not in items:
        raise MailResolverReceiptError("action_id is not present in the current resolver plan", status_code=404)
    item = items[action_id]
    status = _validate_status(resolver_status)
    reason = _validate_reason(reason_code)
    proof, proof_matches_plan = _validate_proof_type(proof_type, item)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    occurred = _format_dt(checked_at)
    provider_name = str(provider or "").strip().lower()[:64] or "manual"
    scope = str(proof_scope or "official_surface_operator_attestation")[:80]
    backed_read = bool(provider_backed_read)
    receipt_id = _hash("resolver", occurred, action_id, status, reason, proof, provider_name, scope, source_snapshot_id)
    receipt = {
        "schema": MAIL_RESOLVER_RECEIPT_SCHEMA,
        "status": "recorded",
        "receipt_id": receipt_id,
        "created_at": occurred,
        "actor": str(actor or "operator")[:64],
        "action_id": action_id,
        "resolver_status": status,
        "reason_code": reason,
        "proof_type": proof,
        "proof_matches_plan": proof_matches_plan,
        "resolver_type": item.get("resolver_type"),
        "official_surface": item.get("official_surface"),
        "official_surface_label": item.get("official_surface_label"),
        "provider": provider_name,
        "external_reference": (
            _external_reference_from_hash(external_reference_hash)
            if external_reference_hash
            else _external_reference(external_reference)
        ),
        "proof_scope": scope,
        "source_snapshot_id": str(source_snapshot_id or "")[:80] or None,
        "privacy": {
            "redacted": True,
            "raw_mail_printed": False,
            "raw_external_state_printed": False,
            "external_reference_stored_raw": False,
            "freeform_private_notes": False,
        },
        "safety": {
            "provider_backed_read": backed_read,
            "provider_backed_automation": False,
            "operator_attestation_only": not backed_read,
            "mailbox_mutations_allowed": False,
            "portal_mutations_allowed": False,
            "send_allowed": False,
        },
    }
    path = Path(receipt_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as e:
        raise MailResolverReceiptError(f"resolver receipt could not be written: {e}") from e
    return receipt
