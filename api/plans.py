"""Plan catalog + entitlements — the single source of truth for pricing & limits.

ONE table drives three consumers: the public ``GET /v1/billing/plans`` endpoint,
the generated ``pricing.md`` / ``llms.txt`` marketing artifacts, and the runtime
entitlement check that caps a triage run. A price or limit change is one edit here
— never a hunt across code, docs, and the website.

Design rule, straight from the market research: **the safety mechanism is never a
paywall.** The protected-sender gate and the independent audit receipt are
identical on every tier, including Free. We monetize REACH (run volume, providers,
agent access) and RETENTION (hosted receipt history) — never restraint. So the
``limits`` below bound *how much* you triage and *what you keep*, never *whether
the gate protects you*.

Stripe price ids are NOT hard-coded — each paid plan names the ENV VAR that holds
its price id (``STRIPE_PRICE_PRO`` etc.). The ids live in the Stripe dashboard and
are injected as deploy secrets, so this file is safe to commit and the price→plan
mapping for the webhook is derived from the environment at runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Sentinel for "no cap" — distinct from 0, which would mean "no runs allowed".
UNLIMITED = None


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_cents: int                  # monthly, in USD minor units (0 = free)
    price_display: str
    monthly_run_cap: Optional[int]    # None == unlimited
    providers: str                    # "gmail" | "all"
    retained_receipt_days: int        # 0 == not retained (no hosted ledger)
    blurb: str
    features: List[str] = field(default_factory=list)
    # Env var holding this plan's Stripe Price id (None for free / non-Stripe).
    stripe_price_env: Optional[str] = None

    @property
    def stripe_price_id(self) -> Optional[str]:
        """The configured Stripe Price id, or None if billing isn't configured."""
        return os.environ.get(self.stripe_price_env) if self.stripe_price_env else None

    def public_dict(self) -> dict:
        """Catalog shape for the public API / pricing page. Deliberately omits the
        env-var name (an internal detail) and exposes only buyer-facing fields."""
        return {
            "id": self.id,
            "name": self.name,
            "price_cents": self.price_cents,
            "price_display": self.price_display,
            "monthly_run_cap": self.monthly_run_cap,
            "providers": self.providers,
            "retained_receipt_days": self.retained_receipt_days,
            "blurb": self.blurb,
            "features": self.features,
        }


# The catalog. Prices reflect the researched $9–19 prosumer band, sold on safety +
# multi-provider rather than features-per-dollar.
PLANS: Dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free / Self-host",
        price_cents=0,
        price_display="$0",
        monthly_run_cap=50,
        providers="gmail",
        retained_receipt_days=0,
        blurb="The full safety floor, free forever. Protected-sender gate + "
              "independent audit receipt, single provider, unlimited dry-runs.",
        features=[
            "Fail-closed protected-sender gate (always on)",
            "Independent, re-derivable audit receipt",
            "Unlimited dry-run / preview",
            "Gmail provider",
            "~50 live triage runs / month (unlimited self-hosted)",
        ],
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_cents=1900,
        price_display="$19/mo",
        monthly_run_cap=5000,
        providers="all",
        retained_receipt_days=90,
        blurb="All four providers, scheduled triage, downloadable + 90-day "
              "retained signed receipts.",
        features=[
            "Everything in Free",
            "All providers: Gmail, IMAP/iCloud, Outlook, Mail.app",
            "5,000 live triage runs / month",
            "Downloadable signed receipts + 90-day hosted ledger",
            "Scheduled / recurring triage + webhooks",
        ],
        stripe_price_env="STRIPE_PRICE_PRO",
    ),
    "business": Plan(
        id="business",
        name="Business",
        price_cents=4900,
        price_display="$49/mo",
        monthly_run_cap=UNLIMITED,
        providers="all",
        retained_receipt_days=365,
        blurb="Unlimited runs, multi-mailbox, retained receipt history for "
              "compliance export, plus MCP + agent-commerce access.",
        features=[
            "Everything in Pro",
            "Unlimited triage runs",
            "Multi-mailbox / team, shared protected-sender policy",
            "1-year retained signed-receipt history (compliance export)",
            "MCP server access + ACP agent-commerce surface",
            "Priority support",
        ],
        stripe_price_env="STRIPE_PRICE_BUSINESS",
    ),
}

# Usage-based add-on (how agents pay): metered per triage run via a Stripe Billing
# Meter, available on any tier. Not a subscription plan, so tracked separately.
METERED_ADDON = {
    "id": "metered",
    "name": "Agent / Metered",
    "price_display": "$0.01 / triage run",
    "unit_amount_cents": 1,
    "stripe_price_env": "STRIPE_PRICE_METERED",
    "meter_event_name": "triage_run",
    "blurb": "Pay-per-run for MCP tool calls and ACP credit-pack purchases. "
             "This is how AI agents pay for verified-safe triage.",
}

# ACP one-time credit packs (SPT is one_time-scoped — see docs/agent-commerce.md).
# An agent buys a pack; N runs are credited to the buyer's balance.
CREDIT_PACKS: Dict[str, dict] = {
    "pack_100": {"id": "pack_100", "runs": 100, "amount_cents": 100,
                 "title": "100 verified-safe triage runs"},
    "pack_1000": {"id": "pack_1000", "runs": 1000, "amount_cents": 900,
                  "title": "1,000 verified-safe triage runs"},
}

DEFAULT_PLAN_ID = "free"


def plan_for(plan_id: Optional[str]) -> Plan:
    """Resolve a plan id, defaulting to Free for unknown/None (fail-safe: an
    unrecognized plan never grants more than the free floor)."""
    return PLANS.get((plan_id or "").lower(), PLANS[DEFAULT_PLAN_ID])


def public_catalog() -> List[dict]:
    """Buyer-facing catalog for the API and the generated pricing page."""
    return [p.public_dict() for p in PLANS.values()]


def plan_id_for_price(price_id: Optional[str]) -> Optional[str]:
    """Reverse-map a Stripe Price id (from a webhook) back to a plan id, using the
    env-configured ids. Returns None if it matches no configured plan."""
    if not price_id:
        return None
    for plan in PLANS.values():
        if plan.stripe_price_id and plan.stripe_price_id == price_id:
            return plan.id
    return None


def entitlements_for(account: Optional[dict]) -> dict:
    """Resolve the effective limits for an account (or the Free floor if None).

    A non-active subscription (past_due / canceled / unpaid) is downgraded to the
    Free floor — we never honor paid limits for an unpaid account, but the safety
    gate stays fully on regardless."""
    if not account:
        plan = PLANS[DEFAULT_PLAN_ID]
    else:
        status = (account.get("status") or "active").lower()
        active = status in ("active", "trialing")
        plan = plan_for(account.get("plan")) if active else PLANS[DEFAULT_PLAN_ID]
    return {
        "plan": plan.id,
        "monthly_run_cap": plan.monthly_run_cap,
        "providers": plan.providers,
        "retained_receipt_days": plan.retained_receipt_days,
        "run_credits": int(account.get("run_credits", 0)) if account else 0,
    }
