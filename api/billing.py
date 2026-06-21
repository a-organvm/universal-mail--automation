"""Stripe billing — the recurring-subscription money path.

Three buyer-facing routes plus a webhook:

  * ``GET  /v1/billing/plans``    public catalog (no Stripe, no creds — powers the
                                   pricing page; always available)
  * ``POST /v1/billing/checkout`` start a Stripe Checkout subscription
  * ``POST /v1/billing/portal``   open the Stripe Customer Portal (self-serve)
  * ``POST /v1/billing/webhook``  the access-grant source of truth

**Fail-soft, not fail-hard.** The Stripe SDK is imported lazily *inside* the
functions that need it, and the secret key is read at call time — so the catalog
endpoint works with Stripe absent, and the money endpoints return a clean 503
("billing is not configured") rather than a 500 when keys aren't set. This mirrors
the provider layer's ProviderUnavailable→503 contract.

**The webhook is fail-CLOSED.** It verifies the Stripe signature over the RAW
request body (never re-serialized JSON — that is the classic silent-verification
bug), is idempotent on the Stripe event id (a redelivery cannot double-grant), and
an unverified or unparseable payload NEVER grants access (400). Subscription
status from Stripe is the single source of truth: we grant on active/trialing and
revoke to the Free floor on canceled/unpaid. This is the same posture as the audit
gate — an unproven claim is denied.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api import plans
from api.auth import authorized_account, require_authorized_account
from api.store import get_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])

# Events we subscribe to. Anything else is acknowledged (200) but ignored, so an
# over-broad webhook config can't crash us.
_HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
}


def _stripe():
    """Import the Stripe SDK lazily; 503 if it isn't installed."""
    try:
        import stripe  # noqa: PLC0415  (intentional lazy import)
        return stripe
    except ImportError as e:  # pragma: no cover - exercised only without the dep
        raise HTTPException(
            status_code=503, detail="billing is not configured"
        ) from e


def _client():
    """A configured StripeClient, or 503 if STRIPE_SECRET_KEY is unset."""
    stripe = _stripe()
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="billing is not configured")
    return stripe.StripeClient(key)


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


# -- models -----------------------------------------------------------------
class CheckoutRequest(BaseModel):
    plan: str = Field(max_length=64)
    account_id: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=320)
    success_url: Optional[str] = Field(default=None, max_length=2048)
    cancel_url: Optional[str] = Field(default=None, max_length=2048)


class PortalRequest(BaseModel):
    account_id: Optional[str] = Field(default=None, max_length=128)
    customer_id: Optional[str] = Field(default=None, max_length=128)
    return_url: Optional[str] = Field(default=None, max_length=2048)


# -- routes -----------------------------------------------------------------
@router.get("/v1/billing/plans")
def list_plans() -> dict:
    """Public pricing catalog. No Stripe call, no credentials — safe to cache."""
    return {
        "plans": plans.public_catalog(),
        "metered": plans.METERED_ADDON,
        "credit_packs": list(plans.CREDIT_PACKS.values()),
        "currency": "usd",
    }


@router.post("/v1/billing/checkout")
def create_checkout(req: CheckoutRequest, request: Request) -> dict:
    """Create a Stripe Checkout subscription session; returns the redirect URL."""
    plan = plans.plan_for(req.plan)
    if plan.id not in ("pro", "business"):
        raise HTTPException(status_code=400, detail="plan is not purchasable")
    price_id = plan.stripe_price_id
    if not price_id:
        # The plan exists but its Stripe Price id env var isn't set on this host.
        raise HTTPException(status_code=503, detail="billing is not configured")

    # Ensure we have an account to tie the subscription to (the grant target).
    store = get_store()
    auth_account = authorized_account(request)
    account_api_key = None  # allow-secret: response field name, not a literal secret
    if req.account_id:
        if auth_account is None:
            raise HTTPException(status_code=401, detail="missing bearer credentials")
        if auth_account["id"] != req.account_id:
            raise HTTPException(status_code=403, detail="account mismatch")
        account_id = req.account_id
    elif auth_account is not None:
        account_id = auth_account["id"]
    else:
        account = store.create_account(email=req.email, plan="free")
        account_id = account["id"]
        account_api_key = account["api_key"]  # allow-secret: generated credential

    client = _client()
    base = _base_url(request)
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": req.success_url
        or f"{base}/app/?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": req.cancel_url or f"{base}/app/?billing=cancel",
        "client_reference_id": account_id,
        "metadata": {"account_id": account_id, "plan": plan.id},
        "subscription_data": {"metadata": {"account_id": account_id, "plan": plan.id}},
        "allow_promotion_codes": True,
    }
    if req.email:
        params["customer_email"] = req.email
    try:
        session = client.v1.checkout.sessions.create(params=params)
    except Exception as e:  # Stripe API / network error
        logger.warning("stripe checkout create failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="checkout could not be created")
    response = {"url": session.url, "session_id": session.id, "account_id": account_id}
    if account_api_key is not None:
        response["account_api_key"] = account_api_key  # allow-secret: generated credential
    return response


@router.post("/v1/billing/portal")
def create_portal(req: PortalRequest, request: Request) -> dict:
    """Open the Stripe Customer Portal so a customer can self-serve their plan."""
    account = require_authorized_account(request)
    if req.account_id and req.account_id != account["id"]:
        raise HTTPException(status_code=403, detail="account mismatch")

    customer_id = account.get("stripe_customer_id")
    if req.customer_id and req.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="customer mismatch")
    if not customer_id:
        raise HTTPException(status_code=404, detail="no Stripe customer for account")

    client = _client()
    try:
        session = client.v1.billing_portal.sessions.create(
            params={
                "customer": customer_id,
                "return_url": req.return_url or f"{_base_url(request)}/app/",
            }
        )
    except Exception as e:
        logger.warning("stripe portal create failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="portal could not be created")
    return {"url": session.url}


@router.post("/v1/billing/webhook")
async def webhook(request: Request) -> dict:
    """Stripe webhook — signature-verified, idempotent, fail-closed."""
    stripe = _stripe()
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="billing is not configured")

    # RAW body — verifying re-serialized JSON would silently never match.
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        # Unverified payloads NEVER grant access. Do not echo the reason.
        raise HTTPException(status_code=400, detail="invalid signature")

    event_id = event["id"]
    event_type = event["type"]
    store = get_store()
    # Idempotent on the event id: a Stripe redelivery is acknowledged but skipped.
    if store.is_event_processed(event_id):
        return {"received": True, "duplicate": True}

    if event_type in _HANDLED_EVENTS:
        try:
            _handle_event(event_type, event["data"]["object"])
        except Exception as e:
            logger.error("error handling %s (%s): %s", event_type, event_id, e,
                         exc_info=True)
            raise HTTPException(
                status_code=500, detail="webhook handler failed"
            ) from e
    store.mark_event_processed(event_id, event_type)
    return {"received": True}


# -- webhook event handling -------------------------------------------------
def _resolve_account(account_id: Optional[str], customer_id: Optional[str]) -> str:
    """Find or create the account this event applies to.

    The Stripe customer id is the durable billing identity. It wins over stale or
    conflicting metadata account_id values, and new customer mappings are claimed
    atomically in the store so concurrent webhook deliveries deduplicate cleanly.
    """
    account = get_store().get_or_create_account_for_customer(
        customer_id, account_id=account_id, plan="free"
    )
    return account["id"]


def _handle_event(event_type: str, obj: dict) -> None:
    store = get_store()

    if event_type == "checkout.session.completed":
        account_id = obj.get("client_reference_id")
        customer_id = obj.get("customer")
        subscription_id = obj.get("subscription")
        plan_id = _checkout_plan_id(obj)
        resolved = _resolve_account(account_id, customer_id)
        store.set_subscription(
            account_id=resolved,
            customer_id=customer_id,
            subscription_id=subscription_id,
            plan=plan_id,
            status="active",
        )
        return

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        customer_id = obj.get("customer")
        meta_account = (obj.get("metadata") or {}).get("account_id")
        resolved = _resolve_account(meta_account, customer_id)
        status = "canceled" if event_type.endswith("deleted") else obj.get("status")
        # Plan from the subscribed price; unknown price -> keep current plan.
        price_id = _first_price_id(obj)
        plan_id = plans.plan_id_for_price(price_id)
        # On cancel/unpaid, drop to the Free floor (entitlements also enforce this).
        if status in ("canceled", "unpaid", "incomplete_expired"):
            plan_id = "free"
        store.set_subscription(
            account_id=resolved,
            customer_id=customer_id,
            subscription_id=obj.get("id"),
            plan=plan_id,
            status=status,
            current_period_end=_period_end(obj),
        )
        return

    if event_type == "invoice.paid":
        customer_id = obj.get("customer")
        acct = store.get_account_by_customer(customer_id) if customer_id else None
        if acct:
            store.set_subscription(account_id=acct["id"], status="active")
        return

    if event_type == "invoice.payment_failed":
        customer_id = obj.get("customer")
        acct = store.get_account_by_customer(customer_id) if customer_id else None
        if acct:
            store.set_subscription(account_id=acct["id"], status="past_due")
        return


def _first_price_id(subscription: dict) -> Optional[str]:
    try:
        return subscription["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def _checkout_plan_id(session: dict) -> Optional[str]:
    meta_plan = (session.get("metadata") or {}).get("plan")
    if meta_plan and meta_plan in plans.PLANS:
        return meta_plan
    return plans.plan_id_for_price(_first_price_id(session))


def _period_end(subscription: dict) -> Optional[int]:
    """current_period_end moved to the item level in recent API versions; check
    both so we record it regardless of the account's Stripe API version."""
    val = subscription.get("current_period_end")
    if val:
        return int(val)
    try:
        return int(subscription["items"]["data"][0]["current_period_end"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
