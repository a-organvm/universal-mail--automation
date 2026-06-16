"""Redacted action planning over historical mail intelligence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.historical_intelligence import HISTORICAL_INTELLIGENCE_SCHEMA, HistoricalIntelligenceError

MAIL_ACTION_PLAN_SCHEMA = "uma.mail.action_plan.v1"
MAIL_ACTION_ITEM_SCHEMA = "uma.mail.action_item.v1"

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, None: 0}


class MailActionPlanError(ValueError):
    """Raised when an action plan cannot be built from intelligence output."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_intelligence(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise MailActionPlanError("historical intelligence input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailActionPlanError("historical intelligence input is not valid JSON") from e
    except OSError as e:
        raise MailActionPlanError(f"historical intelligence input could not be read: {e}") from e
    if not isinstance(data, dict) or data.get("schema") != HISTORICAL_INTELLIGENCE_SCHEMA:
        raise MailActionPlanError(f"historical intelligence input must be {HISTORICAL_INTELLIGENCE_SCHEMA}")
    return data


def _details_by_id(intelligence: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for collection in ("opportunities", "risks"):
        for item in intelligence.get(collection) or []:
            if isinstance(item, dict) and item.get("id"):
                by_id[item["id"]] = item
    return by_id


def _approval_type(kind: str, status: Optional[str]) -> str:
    if kind == "missed_lead":
        return "draft_approval"
    if kind == "legal_obligation":
        return "human_legal_review"
    if status == "needs_portal_verification" or kind in {"security_or_account", "provider_incident", "payment_or_billing"}:
        return "portal_verification"
    if kind == "subscription_or_spend":
        return "decision"
    if kind == "github_work":
        return "external_reconcile"
    return "human_review"


def _automation_boundary(approval_type: str) -> str:
    return {
        "draft_approval": "draft_only_until_approved",
        "human_legal_review": "manual_review_only",
        "portal_verification": "official_portal_or_cli_only",
        "decision": "decision_required_before_action",
        "external_reconcile": "external_system_reconcile",
    }.get(approval_type, "human_review_required")


def _action_type(kind: str) -> str:
    return {
        "missed_lead": "review_and_draft_follow_up",
        "legal_obligation": "legal_review",
        "security_or_account": "verify_account_security",
        "provider_incident": "verify_provider_status",
        "payment_or_billing": "verify_payment_or_billing",
        "subscription_or_spend": "decide_subscription_or_spend",
        "github_work": "reconcile_github_work",
    }.get(kind, "review_evidence")


def _lane_title(lane: str) -> str:
    return {
        "needs_reply": "Needs Reply",
        "draft_review": "Draft / Legal Review",
        "security_verify": "Security Verify",
        "provider_action": "Provider Action",
        "payment_verify": "Payment Verify",
        "finance_action": "Finance Action",
        "subscription_decision": "Subscription Decision",
        "github_ops": "GitHub Ops",
        "review": "Review",
    }.get(lane, lane.replace("_", " ").title())


def _canonical_lane(kind: str, current_lane: str) -> str:
    return {
        "missed_lead": "needs_reply",
        "legal_obligation": "draft_review",
        "security_or_account": "security_verify",
        "payment_or_billing": "payment_verify",
        "provider_incident": "provider_action",
        "subscription_or_spend": "subscription_decision",
        "github_work": "github_ops",
    }.get(kind, current_lane or "review")


def _group_key(finding: Dict[str, Any], detail: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    kind = str(finding.get("kind") or detail.get("kind") or "unknown")
    lane = _canonical_lane(kind, str(finding.get("recommended_lane") or detail.get("recommended_lane") or "review"))
    ops_status = str(finding.get("ops_lane_status") or "unknown")
    status = str(detail.get("status") or "needs_review")
    severity = str(finding.get("severity") or detail.get("severity") or "none")
    if kind == "missed_lead":
        severity = "opportunity"
        status = str(detail.get("status") or "candidate")
    return kind, lane, ops_status, status, severity


def _priority_score(group: Dict[str, Any]) -> int:
    kind = group["kind"]
    severity = group.get("severity")
    ops_status = group.get("ops_lane_status")
    status = group.get("status")
    count = _safe_int(group.get("finding_count"))
    score = 20
    score += {
        "legal_obligation": 42,
        "security_or_account": 40,
        "payment_or_billing": 36,
        "missed_lead": 34,
        "provider_incident": 28,
        "subscription_or_spend": 26,
        "github_work": 22,
    }.get(kind, 12)
    score += {"critical": 35, "high": 26, "medium": 14, "low": 6, "opportunity": 16}.get(severity, 0)
    if ops_status == "not_represented_in_current_ops":
        score += 22
    elif ops_status == "ops_not_supplied":
        score += 8
    if status in {"needs_portal_verification", "needs_human_review", "decision_needed"}:
        score += 10
    score += min(12, count // 25)
    if kind == "missed_lead":
        score += min(10, count // 50)
    return min(score, 100)


def _priority_band(score: int) -> str:
    if score >= 85:
        return "p0"
    if score >= 70:
        return "p1"
    if score >= 55:
        return "p2"
    return "p3"


def _next_action(kind: str, approval: str, ops_status: str) -> str:
    if kind == "missed_lead":
        return "Review the private evidence queue, then draft follow-ups for approval before any send."
    if kind == "legal_obligation":
        return "Review source evidence with legal context before drafting or sending anything."
    if approval == "portal_verification":
        return "Verify status directly in the official provider, account, or billing surface."
    if kind == "subscription_or_spend":
        return "Decide keep, cancel, downgrade, or verify renewal before action."
    if kind == "github_work":
        return "Reconcile against GitHub issues, PRs, billing, or security surfaces."
    if ops_status == "not_represented_in_current_ops":
        return "Promote this quiet historical finding into a current ops lane."
    return "Review redacted evidence and keep visible until resolved."


def _reason_codes(kind: str, severity: str, ops_status: str, status: str) -> List[str]:
    reasons = [kind, ops_status]
    if severity and severity != "none":
        reasons.append(f"severity:{severity}")
    if status and status != "needs_review":
        reasons.append(f"status:{status}")
    if kind in {"legal_obligation", "security_or_account", "payment_or_billing"}:
        reasons.append("high_risk_lane")
    if kind == "missed_lead":
        reasons.append("opportunity_recovery")
    return reasons


def _sample_evidence(existing: List[str], incoming: Iterable[Any], *, limit: int = 12) -> List[str]:
    seen = set(existing)
    out = list(existing)
    for item in incoming or []:
        if not isinstance(item, str) or item in seen:
            continue
        out.append(item)
        seen.add(item)
        if len(out) >= limit:
            break
    return out


def _sample_hints(existing: List[str], incoming: Iterable[Any], *, limit: int = 12) -> List[str]:
    seen = set(existing)
    out = list(existing)
    for item in incoming or []:
        if not isinstance(item, str) or item in seen:
            continue
        out.append(item)
        seen.add(item)
        if len(out) >= limit:
            break
    return out


def _build_groups(intelligence: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = _details_by_id(intelligence)
    grouped: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
    for finding in intelligence.get("reconciliation", {}).get("findings") or []:
        if not isinstance(finding, dict):
            continue
        detail = details.get(str(finding.get("id"))) or {}
        kind, lane, ops_status, status, severity = _group_key(finding, detail)
        key = kind, lane, ops_status, status, severity
        approval = _approval_type(kind, status)
        group = grouped.setdefault(
            key,
            {
                "schema": MAIL_ACTION_ITEM_SCHEMA,
                "id": _hash("action", *key),
                "kind": kind,
                "action_type": _action_type(kind),
                "recommended_lane": lane,
                "lane_title": _lane_title(lane),
                "ops_lane_status": ops_status,
                "status": status,
                "severity": severity,
                "finding_count": 0,
                "evidence_count": 0,
                "approval_type": approval,
                "automation_boundary": _automation_boundary(approval),
                "mailbox_mutations_allowed": False,
                "send_allowed": False,
                "sample_finding_ids": [],
                "sample_evidence_ids": [],
                "provider_hints": [],
                "provider_hint_counts": Counter(),
                "reason_codes": _reason_codes(kind, severity, ops_status, status),
            },
        )
        group["finding_count"] += 1
        evidence_ids = finding.get("evidence_ids") or detail.get("evidence_ids") or []
        group["evidence_count"] += len([item for item in evidence_ids if isinstance(item, str)])
        group["sample_evidence_ids"] = _sample_evidence(group["sample_evidence_ids"], evidence_ids)
        group["sample_finding_ids"] = _sample_evidence(group["sample_finding_ids"], [finding.get("id")], limit=8)
        provider_hints = detail.get("provider_hints") or []
        group["provider_hints"] = _sample_hints(group["provider_hints"], provider_hints)
        for hint in provider_hints:
            if isinstance(hint, str):
                group["provider_hint_counts"][hint] += 1

    out = []
    for group in grouped.values():
        score = _priority_score(group)
        group["priority_score"] = score
        group["priority"] = _priority_band(score)
        group["next_action"] = _next_action(group["kind"], group["approval_type"], group["ops_lane_status"])
        group["provider_hint_counts"] = dict(group["provider_hint_counts"].most_common())
        out.append(group)
    severity_order = {"critical": 0, "high": 1, "opportunity": 2, "medium": 3, "low": 4, "none": 5}
    return sorted(
        out,
        key=lambda item: (
            -_safe_int(item.get("priority_score")),
            severity_order.get(str(item.get("severity")), 9),
            str(item.get("kind")),
            str(item.get("id")),
        ),
    )


def _lane_rollups(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lanes: Dict[str, Dict[str, Any]] = {}
    for item in items:
        lane = item["recommended_lane"]
        target = lanes.setdefault(
            lane,
            {
                "lane_id": lane,
                "title": item["lane_title"],
                "finding_count": 0,
                "action_groups": 0,
                "not_represented_in_current_ops": 0,
                "approval_required": 0,
                "top_priority": "p3",
                "top_score": 0,
                "kind_counts": Counter(),
            },
        )
        target["finding_count"] += _safe_int(item.get("finding_count"))
        target["action_groups"] += 1
        target["not_represented_in_current_ops"] += (
            _safe_int(item.get("finding_count")) if item.get("ops_lane_status") == "not_represented_in_current_ops" else 0
        )
        target["approval_required"] += _safe_int(item.get("finding_count"))
        target["top_score"] = max(target["top_score"], _safe_int(item.get("priority_score")))
        target["top_priority"] = _priority_band(target["top_score"])
        target["kind_counts"][item["kind"]] += _safe_int(item.get("finding_count"))

    out = []
    for lane in lanes.values():
        lane["kind_counts"] = dict(lane["kind_counts"])
        out.append(lane)
    return sorted(out, key=lambda lane: (-lane["top_score"], -lane["finding_count"], lane["lane_id"]))


def _kpis(items: List[Dict[str, Any]], intelligence: Dict[str, Any]) -> Dict[str, Any]:
    finding_total = sum(_safe_int(item.get("finding_count")) for item in items)
    provider_counts: Counter = Counter()
    for item in items:
        counts = item.get("provider_hint_counts") or {}
        if isinstance(counts, dict):
            for hint, count in counts.items():
                provider_counts[str(hint)] += _safe_int(count)
    not_represented = sum(
        _safe_int(item.get("finding_count"))
        for item in items
        if item.get("ops_lane_status") == "not_represented_in_current_ops"
    )
    return {
        "action_groups": len(items),
        "findings": finding_total,
        "p0": sum(1 for item in items if item.get("priority") == "p0"),
        "p1": sum(1 for item in items if item.get("priority") == "p1"),
        "approval_required": finding_total,
        "portal_verification": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("approval_type") == "portal_verification"
        ),
        "draft_approval": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("approval_type") == "draft_approval"
        ),
        "human_legal_review": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("approval_type") == "human_legal_review"
        ),
        "not_represented_in_current_ops": not_represented,
        "provider_hint_counts": dict(provider_counts.most_common()),
        "source_evidence_items": _safe_int((intelligence.get("kpis") or {}).get("evidence_items")),
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
    }


def _answers(items: List[Dict[str, Any]], kpis: Dict[str, Any]) -> Dict[str, Any]:
    top = items[:10]
    return {
        "what_should_happen_next": [
            {
                "priority": item["priority"],
                "kind": item["kind"],
                "recommended_lane": item["recommended_lane"],
                "finding_count": item["finding_count"],
                "approval_type": item["approval_type"],
                "next_action": item["next_action"],
            }
            for item in top
        ],
        "what_is_blocked": {
            "approval_required": kpis["approval_required"],
            "portal_verification": kpis["portal_verification"],
            "human_legal_review": kpis["human_legal_review"],
            "not_represented_in_current_ops": kpis["not_represented_in_current_ops"],
            "top_provider_hints": list((kpis.get("provider_hint_counts") or {}).keys())[:10],
        },
        "what_is_safe_to_automate": {
            "draft_without_send_candidates": kpis["draft_approval"],
            "mailbox_mutations_allowed": 0,
            "send_allowed": 0,
        },
        "what_proof_exists": {
            "source_evidence_items": kpis["source_evidence_items"],
            "action_groups_have_evidence_ids": all(bool(item.get("sample_evidence_ids")) for item in items),
            "provider_hints_are_controlled_slugs": True,
            "redacted": True,
        },
    }


def build_action_plan(
    intelligence: Union[Dict[str, Any], Path, str],
    *,
    max_items: int = 40,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a redacted, approval-aware action plan from intelligence output."""
    if isinstance(intelligence, dict):
        data = intelligence
    else:
        data = _read_intelligence(Path(intelligence).expanduser())
    if data.get("schema") != HISTORICAL_INTELLIGENCE_SCHEMA:
        raise MailActionPlanError(f"historical intelligence input must be {HISTORICAL_INTELLIGENCE_SCHEMA}")

    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    groups = _build_groups(data)
    limited_groups = groups[: max(1, int(max_items))]
    kpis = _kpis(groups, data)
    lanes = _lane_rollups(groups)
    return {
        "schema": MAIL_ACTION_PLAN_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "approval_required_before_send": True,
            "official_surface_required_for_portal_actions": True,
        },
        "source": {
            "schema": data.get("schema"),
            "filename": (data.get("source") or {}).get("filename"),
            "generated_at": (data.get("source") or {}).get("generated_at"),
            "since": (data.get("source") or {}).get("since"),
            "until_exclusive": (data.get("source") or {}).get("until_exclusive"),
            "message_count": (data.get("source") or {}).get("message_count"),
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "private_review_required_for_source_mail": True,
        },
        "kpis": kpis,
        "answers": _answers(groups, kpis),
        "lanes": lanes,
        "items": limited_groups,
    }
