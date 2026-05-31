"""Request models + checkout-session shaping for the ACP surface.

Inbound request bodies are validated with Pydantic. Outbound CheckoutSession
objects are built as plain dicts by :func:`build_session` so we control the exact
spec shape (the ACP spec is fail-strict about object shape — e.g. a digital order
must still return a ``fulfillment_option``, not omit it).

All monetary amounts are integer minor units (cents), per spec.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# ACP checkout status enum (verified live values).
STATUS_NOT_READY = "not_ready_for_payment"
STATUS_READY = "ready_for_payment"
STATUS_COMPLETED = "completed"
STATUS_CANCELED = "canceled"
STATUS_EXPIRED = "expired"


class Item(BaseModel):
    id: str = Field(max_length=128)
    quantity: int = Field(default=1, ge=1, le=1000)


class Buyer(BaseModel):
    name: Optional[str] = Field(default=None, max_length=256)
    email: Optional[str] = Field(default=None, max_length=320)
    phone_number: Optional[str] = Field(default=None, max_length=64)


class PaymentData(BaseModel):
    # The Stripe Shared Payment Token (spt_...) the agent delegates to us.
    token: str = Field(max_length=512)  # allow-secret: field declaration, not a value
    provider: str = Field(default="stripe", max_length=64)


class CheckoutCreate(BaseModel):
    items: List[Item] = Field(default_factory=list)
    buyer: Optional[Buyer] = None


class CheckoutUpdate(BaseModel):
    items: Optional[List[Item]] = None
    buyer: Optional[Buyer] = None
    fulfillment_option_id: Optional[str] = Field(default=None, max_length=128)


class CheckoutComplete(BaseModel):
    buyer: Optional[Buyer] = None
    payment_data: PaymentData


# A single, zero-cost digital fulfillment option — returned (never omitted) because
# the SKU is delivered as account credits, with no shipping.
DIGITAL_FULFILLMENT = {
    "type": "digital",
    "id": "digital",
    "title": "Instant digital delivery (account credits)",
    "subtotal": 0,
    "tax": 0,
    "total": 0,
}


def build_line_items(items: List[dict], packs: dict) -> tuple:
    """Resolve requested items against the credit-pack catalog.

    Returns ``(line_items, total_runs, valid)``. An item that names no known pack
    makes the session invalid (``valid=False``) so the caller marks it
    ``not_ready_for_payment`` rather than charging for nothing.
    """
    line_items: List[dict] = []
    total_runs = 0
    valid = bool(items)
    for idx, it in enumerate(items):
        pack = packs.get(it["id"])
        if pack is None:
            valid = False
            continue
        qty = int(it.get("quantity", 1))
        base = int(pack["amount_cents"])
        subtotal = base * qty
        line_items.append({
            "id": f"li_{idx}",
            "item": {"id": pack["id"], "quantity": qty},
            "base_amount": base,
            "subtotal": subtotal,
            "tax": 0,
            "total": subtotal,
        })
        total_runs += int(pack["runs"]) * qty
    return line_items, total_runs, valid


def grand_total(line_items: List[dict]) -> int:
    return sum(li["total"] for li in line_items)


def build_totals(line_items: List[dict]) -> List[dict]:
    sub = sum(li["subtotal"] for li in line_items)
    tax = sum(li["tax"] for li in line_items)
    return [
        {"type": "subtotal", "display_text": "Subtotal", "amount": sub},
        {"type": "tax", "display_text": "Tax", "amount": tax},
        {"type": "total", "display_text": "Total", "amount": sub + tax},
    ]


def build_session(
    *,
    session_id: str,
    status: str,
    currency: str,
    line_items: List[dict],
    buyer: Optional[dict],
    links: List[dict],
    order: Optional[dict] = None,
    messages: Optional[List[dict]] = None,
) -> dict:
    """Assemble a spec-shaped CheckoutSession response object."""
    obj = {
        "id": session_id,
        "status": status,
        "currency": currency,
        "payment_provider": {
            "provider": "stripe",
            "supported_payment_methods": ["card"],
        },
        "buyer": buyer or {},
        "line_items": line_items,
        "fulfillment_options": [DIGITAL_FULFILLMENT],
        "fulfillment_option_id": DIGITAL_FULFILLMENT["id"],
        "totals": build_totals(line_items),
        "messages": messages or [],
        "links": links,
    }
    if order is not None:
        obj["order"] = order
    return obj
