"""Lane-specific resolver planning over redacted UMA action plans."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.mail_action_plan import MAIL_ACTION_PLAN_SCHEMA

MAIL_RESOLVER_PLAN_SCHEMA = "uma.mail.resolver_plan.v1"
MAIL_RESOLVER_ITEM_SCHEMA = "uma.mail.resolver_item.v1"

DEFAULT_MAX_RESOLVER_ITEMS = 100


class MailResolverPlanError(ValueError):
    """Raised when a resolver plan cannot be built."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise MailResolverPlanError("action plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailResolverPlanError("action plan input is not valid JSON") from e
    except OSError as e:
        raise MailResolverPlanError(f"action plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailResolverPlanError("action plan input has invalid shape")
    return data


def _coerce_action_plan(action_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(action_plan, dict):
        data = action_plan
    else:
        data = _read_json(Path(action_plan).expanduser())
    if data.get("schema") != MAIL_ACTION_PLAN_SCHEMA:
        raise MailResolverPlanError(f"action plan input must be {MAIL_ACTION_PLAN_SCHEMA}")
    return data


def _profile(item: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(item.get("kind") or "")
    approval = str(item.get("approval_type") or "")
    if kind == "missed_lead":
        return {
            "resolver_type": "reply_follow_up",
            "official_surface": "mail_or_linkedin_inbox",
            "official_surface_label": "Mail provider or LinkedIn official inbox",
            "supported_surfaces": ["gmail", "mailapp", "outlook", "imap", "linkedin_manual"],
            "safe_preapproval_steps": ["private_evidence_review", "draft_package", "draft_approval_receipt"],
            "required_proof": ["draft_approval_receipt", "delivery_receipt", "future_provider_send_receipt"],
            "blocker": "private_review_and_final_send_confirmation",
            "next_step": "Review private evidence, prepare or revise a draft, then record approval before any delivery step.",
        }
    if kind == "legal_obligation":
        return {
            "resolver_type": "legal_review",
            "official_surface": "legal_or_counsel_review",
            "official_surface_label": "Counsel/legal review surface",
            "supported_surfaces": ["manual_legal_review", "mailapp", "gmail", "outlook"],
            "safe_preapproval_steps": ["private_evidence_review", "action_receipt_waiting_or_blocked"],
            "required_proof": ["legal_review_receipt", "action_receipt", "future_send_receipt_if_reply_needed"],
            "blocker": "human_legal_review_required",
            "next_step": "Open source evidence and keep the action visible until legal review confirms the next response.",
        }
    if kind == "security_or_account":
        return {
            "resolver_type": "account_security_verification",
            "official_surface": "official_provider_security_surface",
            "official_surface_label": "Official provider security dashboard or CLI",
            "supported_surfaces": ["provider_portal", "official_cli", "vendor_api"],
            "safe_preapproval_steps": ["private_evidence_review", "action_receipt_waiting_or_blocked"],
            "required_proof": ["official_provider_verification", "action_receipt"],
            "blocker": "official_security_surface_required",
            "next_step": "Verify the alert in the provider security surface before marking the action resolved.",
        }
    if kind == "payment_or_billing":
        return {
            "resolver_type": "payment_or_billing_verification",
            "official_surface": "financial_or_billing_portal",
            "official_surface_label": "Bank, card, billing, or vendor portal",
            "supported_surfaces": ["bank_portal", "billing_portal", "vendor_api", "official_cli"],
            "safe_preapproval_steps": ["private_evidence_review", "action_receipt_waiting_or_blocked"],
            "required_proof": ["official_payment_or_invoice_verification", "action_receipt"],
            "blocker": "official_financial_surface_required",
            "next_step": "Verify payment, invoice, or renewal state in the official financial surface.",
        }
    if kind == "provider_incident":
        return {
            "resolver_type": "provider_status_reconcile",
            "official_surface": "provider_dashboard_or_cli",
            "official_surface_label": "Provider dashboard, status page, API, or CLI",
            "supported_surfaces": ["cloudflare", "google_cloud", "vercel", "netlify", "openai", "aws", "azure", "provider_cli"],
            "safe_preapproval_steps": ["private_evidence_review", "action_receipt_waiting_or_blocked"],
            "required_proof": ["official_provider_status", "action_receipt"],
            "blocker": "official_provider_surface_required",
            "next_step": "Reconcile the alert against the provider dashboard, API, or CLI and record the outcome.",
        }
    if kind == "subscription_or_spend":
        return {
            "resolver_type": "subscription_decision",
            "official_surface": "vendor_subscription_portal",
            "official_surface_label": "Vendor billing or subscription portal",
            "supported_surfaces": ["vendor_portal", "billing_portal", "card_statement"],
            "safe_preapproval_steps": ["private_evidence_review", "decision_receipt"],
            "required_proof": ["operator_decision", "official_subscription_status", "action_receipt"],
            "blocker": "keep_cancel_or_downgrade_decision_required",
            "next_step": "Decide keep, cancel, downgrade, or investigate, then verify in the vendor portal.",
        }
    if kind == "github_work" or approval == "external_reconcile":
        return {
            "resolver_type": "github_reconcile",
            "official_surface": "github_api_cli_or_web",
            "official_surface_label": "GitHub API, CLI, issues, PRs, billing, or security",
            "supported_surfaces": ["github_cli", "github_api", "github_web"],
            "safe_preapproval_steps": ["private_evidence_review", "github_readonly_reconcile"],
            "required_proof": ["github_issue_pr_billing_or_security_state", "action_receipt"],
            "blocker": "github_state_must_be_verified",
            "next_step": "Reconcile against GitHub issues, PRs, billing, security alerts, or notifications before closing.",
        }
    return {
        "resolver_type": "human_review",
        "official_surface": "manual_review",
        "official_surface_label": "Manual review",
        "supported_surfaces": ["private_evidence_review"],
        "safe_preapproval_steps": ["private_evidence_review", "action_receipt_waiting_or_blocked"],
        "required_proof": ["action_receipt"],
        "blocker": "human_review_required",
        "next_step": "Review source evidence and record a local action receipt for the current state.",
    }


def _resolver_item(item: Dict[str, Any]) -> Dict[str, Any]:
    profile = _profile(item)
    approval = str(item.get("approval_type") or "human_review")
    finding_count = _safe_int(item.get("finding_count"))
    return {
        "schema": MAIL_RESOLVER_ITEM_SCHEMA,
        "action_id": item.get("id"),
        "kind": item.get("kind"),
        "priority": item.get("priority"),
        "priority_score": item.get("priority_score"),
        "recommended_lane": item.get("recommended_lane"),
        "ops_lane_status": item.get("ops_lane_status"),
        "finding_count": finding_count,
        "evidence_count": _safe_int(item.get("evidence_count")),
        "sample_evidence_ids": item.get("sample_evidence_ids") or [],
        "provider_hints": item.get("provider_hints") or [],
        "provider_hint_counts": item.get("provider_hint_counts") or {},
        "approval_type": approval,
        "automation_boundary": item.get("automation_boundary"),
        "resolver_type": profile["resolver_type"],
        "official_surface": profile["official_surface"],
        "official_surface_label": profile["official_surface_label"],
        "supported_surfaces": profile["supported_surfaces"],
        "safe_preapproval_steps": profile["safe_preapproval_steps"],
        "required_proof": profile["required_proof"],
        "current_blocker": profile["blocker"],
        "next_step": profile["next_step"],
        "safe_to_prepare_locally": approval in {"draft_approval", "decision", "external_reconcile"},
        "official_surface_required": profile["official_surface"] != "manual_review",
        "mailbox_mutations_allowed": False,
        "send_allowed": False,
        "portal_mutations_allowed": False,
    }


def _kpis(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    finding_total = sum(_safe_int(item.get("finding_count")) for item in items)
    by_resolver = Counter(str(item.get("resolver_type") or "unknown") for item in items)
    provider_counts: Counter = Counter()
    for item in items:
        counts = item.get("provider_hint_counts") or {}
        if isinstance(counts, dict):
            for hint, count in counts.items():
                provider_counts[str(hint)] += _safe_int(count)
    return {
        "resolver_groups": len(items),
        "findings": finding_total,
        "official_surface_required": sum(
            _safe_int(item.get("finding_count")) for item in items if item.get("official_surface_required")
        ),
        "can_prepare_locally": sum(
            _safe_int(item.get("finding_count")) for item in items if item.get("safe_to_prepare_locally")
        ),
        "github_reconcile": sum(
            _safe_int(item.get("finding_count")) for item in items if item.get("resolver_type") == "github_reconcile"
        ),
        "mail_or_linkedin_follow_up": sum(
            _safe_int(item.get("finding_count")) for item in items if item.get("resolver_type") == "reply_follow_up"
        ),
        "security_verify": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("resolver_type") == "account_security_verification"
        ),
        "billing_or_payment_verify": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("resolver_type") == "payment_or_billing_verification"
        ),
        "legal_review": sum(
            _safe_int(item.get("finding_count")) for item in items if item.get("resolver_type") == "legal_review"
        ),
        "provider_reconcile": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("resolver_type") == "provider_status_reconcile"
        ),
        "subscription_decision": sum(
            _safe_int(item.get("finding_count"))
            for item in items
            if item.get("resolver_type") == "subscription_decision"
        ),
        "resolver_type_counts": dict(by_resolver),
        "provider_hint_counts": dict(provider_counts.most_common()),
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
        "portal_mutations_allowed": 0,
    }


def _answers(items: List[Dict[str, Any]], kpis: Dict[str, Any]) -> Dict[str, Any]:
    top = items[:10]
    return {
        "what_should_happen_next": [
            {
                "action_id": item["action_id"],
                "priority": item["priority"],
                "resolver_type": item["resolver_type"],
                "official_surface": item["official_surface"],
                "finding_count": item["finding_count"],
                "next_step": item["next_step"],
            }
            for item in top
        ],
        "what_requires_official_surface": [
            {
                "action_id": item["action_id"],
                "resolver_type": item["resolver_type"],
                "official_surface_label": item["official_surface_label"],
                "required_proof": item["required_proof"],
            }
            for item in top
            if item.get("official_surface_required")
        ],
        "what_can_be_prepared_locally": [
            {
                "action_id": item["action_id"],
                "resolver_type": item["resolver_type"],
                "safe_preapproval_steps": item["safe_preapproval_steps"],
            }
            for item in top
            if item.get("safe_to_prepare_locally")
        ],
        "what_is_blocked": {
            "official_surface_required": kpis["official_surface_required"],
            "legal_review": kpis["legal_review"],
            "subscription_decision": kpis["subscription_decision"],
            "github_reconcile": kpis["github_reconcile"],
            "top_provider_hints": list((kpis.get("provider_hint_counts") or {}).keys())[:10],
        },
        "what_proof_exists": {
            "required_proof_types": sorted({proof for item in items for proof in item.get("required_proof") or []}),
            "redacted": True,
            "provider_hints_are_controlled_slugs": True,
            "official_provider_proof_recorded_here": False,
        },
    }


def build_resolver_plan(
    action_plan: Union[Dict[str, Any], Path, str],
    *,
    max_items: int = DEFAULT_MAX_RESOLVER_ITEMS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a redacted lane-specific resolver plan from an action plan."""
    plan = _coerce_action_plan(action_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    items = [_resolver_item(item) for item in plan.get("items") or [] if isinstance(item, dict)]
    items = sorted(
        items,
        key=lambda item: (
            -_safe_int(item.get("priority_score")),
            str(item.get("resolver_type")),
            str(item.get("action_id")),
        ),
    )
    kpis = _kpis(items)
    return {
        "schema": MAIL_RESOLVER_PLAN_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
            "official_surface_plan_only": True,
        },
        "source": {
            "action_plan_schema": plan.get("schema"),
            "action_plan_checked_at": (plan.get("source") or {}).get("checked_at"),
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "contains_raw_external_state": False,
        },
        "kpis": kpis,
        "answers": _answers(items, kpis),
        "items": items[: max(1, int(max_items))],
    }
