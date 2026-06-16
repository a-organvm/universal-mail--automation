"""Provider-surface resolver frontier planning for UMA."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from core.mail_resolver_plan import MAIL_RESOLVER_PLAN_SCHEMA

PROVIDER_SURFACE_PLAN_SCHEMA = "uma.provider.surface_plan.v1"
PROVIDER_SURFACE_ITEM_SCHEMA = "uma.provider.surface_item.v1"

DEFAULT_MAX_PROVIDER_SURFACES = 20


class ProviderSurfacePlanError(ValueError):
    """Raised when a provider-surface plan cannot be built."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


PROVIDER_SURFACE_CATALOG: Dict[str, Dict[str, Any]] = {
    "github": {
        "title": "GitHub",
        "resolver_candidate": "github_resolver_expansion",
        "existing_uma_surfaces": ["mail-github-resolver", "mail-github-resolver-receipts"],
        "coverage_state": "partial_provider_read_available",
        "provider_backed_read_available": True,
        "next_build_step": "expand_github_security_billing_dependabot_and_repo_specific_receipts",
        "proof_goal": "github_issue_pr_billing_or_security_state",
        "official_surfaces": ["github_cli", "github_api"],
    },
    "linkedin": {
        "title": "LinkedIn",
        "resolver_candidate": "linkedin_followup_surface",
        "existing_uma_surfaces": ["mail-followup-resolver", "mail-followup-resolver-receipts"],
        "coverage_state": "local_receipt_bridge_only",
        "provider_backed_read_available": False,
        "next_build_step": "verify_non_browser_official_linkedin_route_or_keep_manual_followup",
        "proof_goal": "draft_approval_receipt_or_delivery_receipt",
        "official_surfaces": ["linkedin_official_inbox", "mail_provider"],
    },
    "cloudflare": {
        "title": "Cloudflare",
        "resolver_candidate": "cloudflare_cli_api_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_cloudflare_cli_api_security_billing_status_snapshot",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["cloudflare_api", "wrangler_cli", "cloudflare_dashboard"],
    },
    "stripe": {
        "title": "Stripe",
        "resolver_candidate": "stripe_billing_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_stripe_customer_invoice_subscription_snapshot",
        "proof_goal": "official_payment_or_invoice_verification",
        "official_surfaces": ["stripe_api", "stripe_cli", "stripe_dashboard"],
    },
    "google_cloud": {
        "title": "Google Cloud",
        "resolver_candidate": "google_cloud_cli_api_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_gcloud_billing_project_security_snapshot",
        "proof_goal": "official_provider_verification",
        "official_surfaces": ["gcloud_cli", "google_cloud_api", "google_cloud_console"],
    },
    "google_workspace": {
        "title": "Google Workspace",
        "resolver_candidate": "google_account_workspace_resolver",
        "existing_uma_surfaces": ["mail-external-resolver", "mail-followup-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "separate_gmail_mail_state_from_google_account_workspace_security_state",
        "proof_goal": "official_provider_verification",
        "official_surfaces": ["gmail_api", "google_account_security", "workspace_admin"],
    },
    "paypal": {
        "title": "PayPal",
        "resolver_candidate": "paypal_payment_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_payment_status_verification_or_keep_manual_portal_blocker",
        "proof_goal": "official_payment_or_invoice_verification",
        "official_surfaces": ["paypal_account", "paypal_api"],
    },
    "apple": {
        "title": "Apple",
        "resolver_candidate": "apple_account_subscription_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "map_account_subscription_security_items_to_official_apple_review",
        "proof_goal": "official_subscription_status",
        "official_surfaces": ["apple_account", "app_store_subscriptions"],
    },
    "microsoft": {
        "title": "Microsoft",
        "resolver_candidate": "microsoft_graph_account_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_graph_outlook_security_billing_snapshot_where_authorized",
        "proof_goal": "official_provider_verification",
        "official_surfaces": ["microsoft_graph", "outlook", "microsoft_account"],
    },
    "vercel": {
        "title": "Vercel",
        "resolver_candidate": "vercel_cli_api_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_vercel_project_domain_billing_snapshot",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["vercel_cli", "vercel_api", "vercel_dashboard"],
    },
    "netlify": {
        "title": "Netlify",
        "resolver_candidate": "netlify_cli_api_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_netlify_site_domain_billing_snapshot",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["netlify_cli", "netlify_api", "netlify_dashboard"],
    },
    "openai": {
        "title": "OpenAI",
        "resolver_candidate": "openai_account_billing_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_account_project_billing_usage_snapshot_where_authorized",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["openai_platform", "openai_api"],
    },
    "anthropic": {
        "title": "Anthropic",
        "resolver_candidate": "anthropic_account_billing_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "map_account_billing_security_items_to_official_review_surface",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["anthropic_console", "anthropic_api"],
    },
    "aws": {
        "title": "AWS",
        "resolver_candidate": "aws_cli_billing_security_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_aws_cli_billing_security_snapshot",
        "proof_goal": "official_provider_verification",
        "official_surfaces": ["aws_cli", "aws_console"],
    },
    "azure": {
        "title": "Azure",
        "resolver_candidate": "azure_cli_billing_security_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_azure_cli_billing_security_snapshot",
        "proof_goal": "official_provider_verification",
        "official_surfaces": ["az_cli", "azure_portal"],
    },
    "dropbox": {
        "title": "Dropbox",
        "resolver_candidate": "dropbox_account_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "map_account_storage_billing_items_to_official_review_surface",
        "proof_goal": "official_subscription_status",
        "official_surfaces": ["dropbox_account", "dropbox_api"],
    },
    "slack": {
        "title": "Slack",
        "resolver_candidate": "slack_workspace_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "map_workspace_security_billing_items_to_official_review_surface",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["slack_api", "slack_admin"],
    },
    "notion": {
        "title": "Notion",
        "resolver_candidate": "notion_workspace_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "map_workspace_billing_security_items_to_official_review_surface",
        "proof_goal": "official_subscription_status",
        "official_surfaces": ["notion_api", "notion_workspace_settings"],
    },
    "onepassword": {
        "title": "1Password",
        "resolver_candidate": "onepassword_account_security_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "add_read_only_account_security_review_if_cli_auth_is_available",
        "proof_goal": "official_provider_verification",
        "official_surfaces": ["onepassword_cli", "onepassword_account"],
    },
    "intuit": {
        "title": "Intuit",
        "resolver_candidate": "intuit_billing_tax_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "map_tax_billing_items_to_official_review_surface",
        "proof_goal": "official_payment_or_invoice_verification",
        "official_surfaces": ["intuit_account", "quickbooks"],
    },
}


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
        raise ProviderSurfacePlanError("resolver plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProviderSurfacePlanError("resolver plan input is not valid JSON") from e
    except OSError as e:
        raise ProviderSurfacePlanError(f"resolver plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise ProviderSurfacePlanError("resolver plan input has invalid shape")
    return data


def _coerce_resolver_plan(resolver_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(resolver_plan, dict):
        data = resolver_plan
    else:
        data = _read_json(Path(resolver_plan).expanduser())
    if data.get("schema") != MAIL_RESOLVER_PLAN_SCHEMA:
        raise ProviderSurfacePlanError(f"resolver plan input must be {MAIL_RESOLVER_PLAN_SCHEMA}")
    return data


def _catalog(provider: str) -> Dict[str, Any]:
    base = PROVIDER_SURFACE_CATALOG.get(provider)
    if base:
        return base
    return {
        "title": provider.replace("_", " ").title(),
        "resolver_candidate": "generic_provider_surface_resolver",
        "existing_uma_surfaces": ["mail-external-resolver"],
        "coverage_state": "planned_only",
        "provider_backed_read_available": False,
        "next_build_step": "verify_official_non_browser_surface_then_add_read_only_snapshot",
        "proof_goal": "official_provider_status",
        "official_surfaces": ["official_provider_surface"],
    }


def _add_unique(target: Set[str], values: Any) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        if isinstance(value, str) and value:
            target.add(value)


def _surface_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in items:
        counts = item.get("provider_hint_counts") or {}
        if not isinstance(counts, dict):
            continue
        for provider, raw_count in counts.items():
            provider = str(provider or "").strip()
            hint_count = _safe_int(raw_count)
            if not provider or hint_count <= 0:
                continue
            row = grouped.setdefault(
                provider,
                {
                    "provider": provider,
                    "hint_count": 0,
                    "action_count": 0,
                    "related_findings": 0,
                    "resolver_type_counts": Counter(),
                    "recommended_lane_counts": Counter(),
                    "priority_counts": Counter(),
                    "required_proof": set(),
                    "official_surfaces": set(),
                    "safe_local_steps": set(),
                    "sample_action_ids": [],
                },
            )
            row["hint_count"] += hint_count
            row["action_count"] += 1
            row["related_findings"] += _safe_int(item.get("finding_count"))
            row["resolver_type_counts"][str(item.get("resolver_type") or "unknown")] += 1
            row["recommended_lane_counts"][str(item.get("recommended_lane") or "unknown")] += 1
            row["priority_counts"][str(item.get("priority") or "unknown")] += 1
            _add_unique(row["required_proof"], item.get("required_proof") or [])
            official_surface = item.get("official_surface")
            if isinstance(official_surface, str) and official_surface:
                row["official_surfaces"].add(official_surface)
            _add_unique(row["safe_local_steps"], item.get("safe_preapproval_steps") or [])
            action_id = item.get("action_id")
            if isinstance(action_id, str) and action_id and len(row["sample_action_ids"]) < 6:
                row["sample_action_ids"].append(action_id)

    rows: List[Dict[str, Any]] = []
    for provider, raw in grouped.items():
        catalog = _catalog(provider)
        provider_backed_read = bool(catalog.get("provider_backed_read_available"))
        score = (
            _safe_int(raw["hint_count"])
            + min(_safe_int(raw["related_findings"]), 10000)
            + (500 if provider_backed_read else 0)
            + (250 if raw["priority_counts"].get("p0", 0) else 0)
        )
        blocked_by = ["official_provider_auth_or_api_verification"]
        if not provider_backed_read:
            blocked_by.append("provider_backed_resolver_not_built")
        rows.append(
            {
                "schema": PROVIDER_SURFACE_ITEM_SCHEMA,
                "provider": provider,
                "title": catalog["title"],
                "priority_score": score,
                "hint_count": _safe_int(raw["hint_count"]),
                "action_count": _safe_int(raw["action_count"]),
                "related_findings": _safe_int(raw["related_findings"]),
                "related_findings_overlap_allowed": True,
                "resolver_type_counts": dict(raw["resolver_type_counts"].most_common()),
                "recommended_lane_counts": dict(raw["recommended_lane_counts"].most_common()),
                "priority_counts": dict(raw["priority_counts"].most_common()),
                "official_surfaces": sorted(raw["official_surfaces"] | set(catalog.get("official_surfaces") or [])),
                "required_proof": sorted(raw["required_proof"]),
                "safe_local_steps": sorted(raw["safe_local_steps"]),
                "sample_action_ids": raw["sample_action_ids"],
                "existing_uma_surfaces": list(catalog.get("existing_uma_surfaces") or []),
                "coverage_state": catalog["coverage_state"],
                "resolver_candidate": catalog["resolver_candidate"],
                "next_build_step": catalog["next_build_step"],
                "proof_goal": catalog["proof_goal"],
                "future_intake_detector_candidate": True,
                "provider_backed_read_available": provider_backed_read,
                "provider_backed_automation_allowed": False,
                "mailbox_mutations_allowed": False,
                "send_allowed": False,
                "portal_mutations_allowed": False,
                "blocked_by": blocked_by,
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            -_safe_int(row.get("priority_score")),
            -_safe_int(row.get("hint_count")),
            str(row.get("provider") or ""),
        ),
    )


def _kpis(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    provider_counts = {row["provider"]: row["hint_count"] for row in rows}
    return {
        "provider_surfaces": len(rows),
        "provider_hint_total": sum(_safe_int(row.get("hint_count")) for row in rows),
        "related_findings_overlap_allowed": True,
        "provider_backed_read_resolvers_available": sum(
            1 for row in rows if row.get("provider_backed_read_available")
        ),
        "planned_provider_resolvers": sum(1 for row in rows if not row.get("provider_backed_read_available")),
        "future_intake_detector_candidates": sum(
            1 for row in rows if row.get("future_intake_detector_candidate")
        ),
        "top_provider_hint_counts": provider_counts,
        "provider_backed_automation": 0,
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
        "portal_mutations_allowed": 0,
    }


def _answers(rows: List[Dict[str, Any]], kpis: Dict[str, Any]) -> Dict[str, Any]:
    top = rows[:10]
    return {
        "what_should_be_built_next": [
            {
                "provider": row["provider"],
                "resolver_candidate": row["resolver_candidate"],
                "hint_count": row["hint_count"],
                "related_findings": row["related_findings"],
                "proof_goal": row["proof_goal"],
                "next_build_step": row["next_build_step"],
            }
            for row in top
        ],
        "what_can_be_prepared_locally": [
            {
                "provider": row["provider"],
                "safe_local_steps": row["safe_local_steps"],
                "existing_uma_surfaces": row["existing_uma_surfaces"],
            }
            for row in top
        ],
        "what_is_blocked": {
            "planned_provider_resolvers": kpis["planned_provider_resolvers"],
            "providers_without_provider_backed_read": [
                row["provider"] for row in top if not row.get("provider_backed_read_available")
            ],
            "requires_official_auth_or_api_verification": True,
        },
        "what_proof_exists": {
            "provider_hints_are_controlled_slugs": True,
            "raw_provider_state_included": False,
            "provider_backed_read_available_for": [
                row["provider"] for row in rows if row.get("provider_backed_read_available")
            ],
            "provider_backed_automation": False,
            "official_provider_proof_recorded_here": False,
        },
        "how_this_feeds_future_intake": [
            {
                "provider": row["provider"],
                "detector_candidate": row["future_intake_detector_candidate"],
                "learned_from": "historical_provider_hints_and_current_resolver_groups",
            }
            for row in top
        ],
    }


def build_provider_surface_plan(
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    max_items: int = DEFAULT_MAX_PROVIDER_SURFACES,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a redacted provider-surface resolver frontier from a resolver plan."""
    plan = _coerce_resolver_plan(resolver_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    items = [item for item in plan.get("items") or [] if isinstance(item, dict)]
    rows = _surface_rows(items)
    kpis = _kpis(rows)
    status = "ok" if rows else "no_provider_hints"
    return {
        "schema": PROVIDER_SURFACE_PLAN_SCHEMA,
        "status": status,
        "mode": {
            "read_only": True,
            "provider_backed_read": False,
            "provider_backed_automation": False,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
            "plan_only": True,
        },
        "source": {
            "resolver_plan_schema": plan.get("schema"),
            "resolver_plan_checked_at": (plan.get("source") or {}).get("checked_at"),
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "snippet", "raw_headers", "full_source_path"],
            "contains_raw_provider_identity": False,
            "contains_raw_provider_state": False,
            "provider_hints_are_controlled_slugs": True,
        },
        "kpis": kpis,
        "answers": _answers(rows, kpis),
        "items": rows[: max(1, int(max_items))],
    }
