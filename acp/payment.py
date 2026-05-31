"""Payment-client seam for ACP completion.

The ACP ``/complete`` charge uses Stripe Shared Payment Tokens (SPT), which today
require a *preview* Stripe API version. Preview surfaces change, and the whole
charge path is credentials-gated (it can't run without STRIPE_SECRET_KEY). So we
isolate it behind a tiny interface:

  * :class:`StripeSPTPaymentClient` — the real charge: a PaymentIntent built from
    the delegated SPT token. No card data ever touches us (keeps PCI scope small).
  * :class:`NullPaymentClient` — used when Stripe isn't configured. It FAILS
    (never fakes success), so an unconfigured server returns an honest "payment
    not configured" rather than crediting runs for free.

Tests inject a fake client via :func:`set_payment_client`, exactly like the store.
A header/shape change in the preview API is then a one-file edit here.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Stripe preview version that gates Shared Payment Tokens (verified value).
STRIPE_SPT_API_VERSION = "2026-04-22.preview"


@dataclass
class ChargeResult:
    ok: bool
    payment_id: Optional[str] = None
    error: Optional[str] = None


class PaymentClient:
    """Interface: turn a delegated payment token into a completed charge."""

    configured: bool = False

    def charge(
        self, *, amount: int, currency: str, token: str, idempotency_key: str  # allow-secret: param names
    ) -> ChargeResult:  # pragma: no cover - interface
        raise NotImplementedError


class NullPaymentClient(PaymentClient):
    """No payment processor configured. Refuses to charge (fail-closed: we never
    credit runs without a real, settled payment)."""

    configured = False

    def charge(self, *, amount, currency, token, idempotency_key) -> ChargeResult:
        return ChargeResult(ok=False, error="payment is not configured")


class StripeSPTPaymentClient(PaymentClient):
    """Charge a Stripe Shared Payment Token via a confirmed PaymentIntent."""

    configured = True

    def __init__(self, secret_key: str):
        self._key = secret_key

    def charge(self, *, amount, currency, token, idempotency_key) -> ChargeResult:
        import stripe  # lazy: only when an actual charge runs

        client = stripe.StripeClient(self._key)
        try:
            intent = client.v1.payment_intents.create(
                params={
                    "amount": int(amount),
                    "currency": currency,
                    "confirm": True,
                    # The agent delegated this token to us; Stripe resolves it to a
                    # real payment method server-side. We never see card data.
                    "payment_method_data": {
                        "type": "card",
                        "shared_payment_granted_token": token,
                    },
                },
                options={
                    "idempotency_key": idempotency_key,
                    "stripe_version": STRIPE_SPT_API_VERSION,
                },
            )
        except Exception as e:  # Stripe/declined/network
            logger.warning("ACP SPT charge failed: %s", e, exc_info=True)
            return ChargeResult(ok=False, error="charge failed")
        if getattr(intent, "status", None) == "succeeded":
            return ChargeResult(ok=True, payment_id=intent.id)
        return ChargeResult(
            ok=False, payment_id=getattr(intent, "id", None),
            error=f"payment not completed (status={getattr(intent, 'status', '?')})",
        )


_CLIENT: Optional[PaymentClient] = None


def get_payment_client() -> PaymentClient:
    """Resolve the active payment client from the environment (Stripe if a key is
    present, else the fail-closed Null client). Cached; override in tests."""
    global _CLIENT
    if _CLIENT is None:
        key = os.environ.get("STRIPE_SECRET_KEY")
        _CLIENT = StripeSPTPaymentClient(key) if key else NullPaymentClient()
    return _CLIENT


def set_payment_client(client: Optional[PaymentClient]) -> None:
    """Inject a payment client (tests) or clear it (None) so the next
    get_payment_client() re-resolves from the environment."""
    global _CLIENT
    _CLIENT = client
