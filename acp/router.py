"""Agentic Commerce Protocol checkout endpoints (spec 2026-04-17).

Five endpoints implement the agent→merchant checkout for one digital SKU (a
triage-run credit pack):

    POST   /acp/checkout_sessions              create
    GET    /acp/checkout_sessions/{id}         retrieve
    POST   /acp/checkout_sessions/{id}         update (buyer/items)
    POST   /acp/checkout_sessions/{id}/complete   charge + fulfill
    POST   /acp/checkout_sessions/{id}/cancel     cancel

Every request passes a fail-closed gate (Authorization: Bearer, exact
``API-Version: 2026-04-17``, and — on POST — a required ``Idempotency-Key`` with
replay-dedup). Any failure returns the spec error envelope
``{type, code, message, param}``. On completion we charge the delegated Stripe
Shared Payment Token (behind :mod:`acp.payment`), credit the runs to the buyer's
account, and emit a SIGNED order receipt retrievable at ``/v1/audit/{order_id}`` —
so even an agent purchase carries the product's verifiable-receipt trust signal.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from acp import API_VERSION, models, payment
from api import plans
from api import receipts
from api.store import get_store

router = APIRouter(prefix="/acp", tags=["agentic-commerce"])

CURRENCY = "usd"


# -- spec error envelope ----------------------------------------------------
class ACPError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 param: Optional[str] = None):
        self.status = status
        self.envelope = {
            "type": "invalid_request",
            "code": code,
            "message": message,
            "param": param,
        }
        super().__init__(message)


def register_acp_handlers(app) -> None:
    """Wire the ACP error envelope as an exception handler on the parent app, so
    failures return the spec shape at the top level (not wrapped in {'detail'})."""

    @app.exception_handler(ACPError)
    async def _acp_error_handler(_request: Request, exc: ACPError):
        return JSONResponse(status_code=exc.status, content=exc.envelope)


# -- gate -------------------------------------------------------------------
@dataclass
class GateContext:
    api_key: str  # allow-secret: field declaration, not a value
    idempotency_key: Optional[str]


def _gate(request: Request, *, require_idempotency: bool) -> GateContext:
    version = request.headers.get("API-Version")
    if version != API_VERSION:
        raise ACPError(
            400, "unsupported_api_version",
            f"API-Version must be {API_VERSION}", "API-Version",
        )
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not auth[len("Bearer "):].strip():
        raise ACPError(401, "unauthorized", "missing bearer credentials",
                       "Authorization")
    api_key = auth[len("Bearer "):].strip()  # allow-secret: parsed header, not a literal

    idem = request.headers.get("Idempotency-Key")
    if require_idempotency:
        if not idem:
            raise ACPError(400, "missing_idempotency_key",
                           "Idempotency-Key is required", "Idempotency-Key")
        if len(idem) > 255:
            raise ACPError(400, "invalid_idempotency_key",
                           "Idempotency-Key exceeds 255 chars", "Idempotency-Key")
    return GateContext(api_key=api_key, idempotency_key=idem)  # allow-secret: var refs


def _request_hash(raw: bytes) -> str:
    return hashlib.sha256(raw or b"").hexdigest()


def _key_hash(api_key: str) -> str:  # allow-secret: parameter name, not a value
    """Stable hash of the caller's bearer key. Bound to a session at creation so
    only the creator can update/cancel/complete it, and so completion credits the
    CREATOR's account — never a different bearer that happens to call /complete
    (review U010). The raw key is never stored on the session."""
    return hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()


def _require_owner(ctx: GateContext, row: dict) -> None:
    """Only the bearer that CREATED a session may act on it. Sessions created
    before binding existed (no creator_key_hash) are not gated, for back-compat."""
    expected = row["data"].get("creator_key_hash")
    if expected is not None and _key_hash(ctx.api_key) != expected:
        raise ACPError(403, "session_owner_mismatch",
                       "this checkout session belongs to a different account",
                       "Authorization")


def _begin_idempotency(ctx: GateContext, raw: bytes, scope: str) -> Optional[dict]:
    """Claim the idempotency key. Returns the stored response on replay (caller
    returns it with Idempotent-Replayed: true), None to proceed. Raises ACPError
    on 409 (still processing) / 422 (same key, different payload)."""
    state = get_store().idempotency_begin(
        ctx.idempotency_key, scope, _request_hash(raw)
    )
    if state["state"] == "new":
        return None
    if state["state"] == "processing":
        raise ACPError(409, "idempotency_in_progress",
                       "a request with this Idempotency-Key is still processing",
                       "Idempotency-Key")
    if state["state"] == "conflict":
        raise ACPError(422, "idempotency_conflict",
                       "Idempotency-Key reused with a different payload",
                       "Idempotency-Key")
    return state["response"]  # replay


def _complete_idempotency(ctx: GateContext, response: dict) -> None:
    if ctx.idempotency_key:
        get_store().idempotency_complete(ctx.idempotency_key, response)


def _links(request: Request) -> list:
    base = str(request.base_url).rstrip("/")
    return [
        {"type": "terms_of_use", "url": f"{base}/terms"},
        {"type": "privacy_policy", "url": f"{base}/privacy"},
    ]


def _new_session_id() -> str:
    return "acp_cs_" + secrets.token_hex(16)


def _order_id_for(session_id: str) -> str:
    """Deterministic order id for a checkout session.

    Derived (one-way) from the session id so that the first attempt and any
    crash-recovery retry — even concurrent ones — mint the SAME receipt row,
    making one-receipt-per-paid-session a structural invariant rather than a
    locking discipline. Knowing the order id does not reveal the session id."""
    digest = hashlib.sha256(f"acp-order:{session_id}".encode()).hexdigest()
    return "order_" + digest[:24]


def _shape(
    request: Request, *, session_id: str, status: str, line_items: list,
    buyer: Optional[dict], order: Optional[dict] = None,
    messages: Optional[list] = None,
) -> dict:
    return models.build_session(
        session_id=session_id, status=status, currency=CURRENCY,
        line_items=line_items, buyer=buyer, links=_links(request),
        order=order, messages=messages,
    )


def _persist(session_id: str, response: dict, total_runs: int,
             account_id: Optional[str] = None,
             creator_key_hash: Optional[str] = None,
             charge_attempted: Optional[bool] = None) -> None:
    """Persist the session row.

    ``charge_attempted`` marks that a Stripe charge is about to be (or may
    have been) attempted for this session. It is written (True) immediately
    BEFORE the charge call; while set, update/cancel are refused: the captured
    charge and the credit are keyed to the session's CURRENT contents, and
    mutating them would make the recovered order receipt lie about what was
    actually paid. ONLY the 402 payment-failed branch clears it (False) — the
    charge definitively failed, so the session is safely mutable again. The
    default (None) PRESERVES whatever the row already says, so no incidental
    persist (a stale concurrent update, the completion write) can ever drop
    the freeze by omission."""
    if charge_attempted is None:
        existing = get_store().get_session(session_id)
        charge_attempted = bool(
            existing and existing["data"].get("charge_attempted"))
    get_store().save_session(
        session_id=session_id, status=response["status"], currency=CURRENCY,
        account_id=account_id,
        data={"response": response, "total_runs": total_runs,
              "creator_key_hash": creator_key_hash,
              "charge_attempted": charge_attempted},
    )


def _require_not_charged(session_id: str, row: dict, action: str) -> None:
    """Refuse ``action`` once money may have moved for this session.

    Two independent signals, either suffices: the pre-charge marker (covers a
    crash anywhere from the charge call onward, even before fulfillment) and
    the fulfillment row (covers credit actually applied). A session in this
    state is finished by RETRYING /complete — never by mutating it."""
    if row["data"].get("charge_attempted") or \
            get_store().get_fulfillment(session_id) is not None:
        raise ACPError(
            400, "invalid_state",
            f"a payment may already be captured for this session; it cannot "
            f"be {action} — retry /complete to finish it", "status")


def _load(session_id: str) -> dict:
    row = get_store().get_session(session_id)
    if row is None:
        raise ACPError(404, "session_not_found", "checkout session not found", "id")
    return row


# -- endpoints --------------------------------------------------------------
@router.post("/checkout_sessions")
async def create_session(body: models.CheckoutCreate, request: Request):
    ctx = _gate(request, require_idempotency=True)
    raw = await request.body()
    replay = _begin_idempotency(ctx, raw, "acp.create")
    if replay is not None:
        return JSONResponse(replay, headers={"Idempotent-Replayed": "true"})

    items = [i.model_dump() for i in body.items]
    line_items, total_runs, valid = models.build_line_items(items, plans.CREDIT_PACKS)
    status = models.STATUS_READY if valid else models.STATUS_NOT_READY
    messages = None
    if not valid:
        messages = [{
            "type": "error", "code": "invalid_items", "content_type": "plain",
            "text": "one or more items do not match a known credit pack",
        }]
    session_id = _new_session_id()
    resp = _shape(request, session_id=session_id, status=status,
                  line_items=line_items,
                  buyer=body.buyer.model_dump() if body.buyer else None,
                  messages=messages)
    _persist(session_id, resp, total_runs, creator_key_hash=_key_hash(ctx.api_key))
    _complete_idempotency(ctx, resp)
    return JSONResponse(resp)


@router.get("/checkout_sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    _gate(request, require_idempotency=False)
    row = _load(session_id)
    return JSONResponse(row["data"]["response"])


@router.post("/checkout_sessions/{session_id}")
async def update_session(session_id: str, body: models.CheckoutUpdate,
                         request: Request):
    ctx = _gate(request, require_idempotency=True)
    raw = await request.body()
    replay = _begin_idempotency(ctx, raw, "acp.update")
    if replay is not None:
        return JSONResponse(replay, headers={"Idempotent-Replayed": "true"})

    row = _load(session_id)
    _require_owner(ctx, row)
    current = row["data"]["response"]
    if current["status"] in (models.STATUS_COMPLETED, models.STATUS_CANCELED,
                             models.STATUS_EXPIRED):
        raise ACPError(400, "invalid_state",
                       f"cannot update a {current['status']} session", "status")
    _require_not_charged(session_id, row, "updated")

    # Re-derive line items if items were supplied, else keep the existing ones.
    if body.items is not None:
        items = [i.model_dump() for i in body.items]
        line_items, total_runs, valid = models.build_line_items(
            items, plans.CREDIT_PACKS)
        status = models.STATUS_READY if valid else models.STATUS_NOT_READY
    else:
        line_items = current["line_items"]
        total_runs = row["data"]["total_runs"]
        status = current["status"]

    buyer = body.buyer.model_dump() if body.buyer else current.get("buyer")
    resp = _shape(request, session_id=session_id, status=status,
                  line_items=line_items, buyer=buyer)
    _persist(session_id, resp, total_runs,
             creator_key_hash=row["data"].get("creator_key_hash"))
    _complete_idempotency(ctx, resp)
    return JSONResponse(resp)


@router.post("/checkout_sessions/{session_id}/complete")
async def complete_session(session_id: str, body: models.CheckoutComplete,
                           request: Request):
    ctx = _gate(request, require_idempotency=True)
    raw = await request.body()
    replay = _begin_idempotency(ctx, raw, "acp.complete")
    if replay is not None:
        return JSONResponse(replay, headers={"Idempotent-Replayed": "true"})

    row = _load(session_id)
    _require_owner(ctx, row)
    current = row["data"]["response"]
    total_runs = row["data"]["total_runs"]
    creator_key_hash = row["data"].get("creator_key_hash")

    if current["status"] == models.STATUS_COMPLETED:
        # Already fulfilled — return the completed session idempotently.
        _complete_idempotency(ctx, current)
        return JSONResponse(current)
    if current["status"] != models.STATUS_READY:
        raise ACPError(400, "invalid_state",
                       f"session is {current['status']}, not ready_for_payment",
                       "status")

    amount = models.grand_total(current["line_items"])
    # FREEZE the session before touching money: from here on a charge may
    # exist (even if we crash mid-call), and the captured amount is keyed to
    # the session's CURRENT contents. update/cancel refuse while this marker
    # is set, so a crash-recovery retry always re-reads the exact line items
    # the charge was made against — the recovered receipt cannot lie. The 402
    # branch below clears it (charge definitively failed, safely mutable
    # again).
    _persist(session_id, current, total_runs,
             creator_key_hash=creator_key_hash, charge_attempted=True)
    # Charge the delegated token (fail-closed: NullPaymentClient refuses). The
    # charge idempotency key is derived from the SESSION id, not the endpoint
    # Idempotency-Key — so even if a caller retries /complete with a fresh
    # Idempotency-Key, Stripe still dedups to a single charge for this session.
    result = payment.get_payment_client().charge(
        amount=amount, currency=CURRENCY,
        token=body.payment_data.token,  # allow-secret: attribute ref, not a value
        idempotency_key=f"acp-charge:{session_id}",
    )
    if not result.ok:
        # Surface the failure in-session; the session stays completable on retry.
        messages = [{
            "type": "error", "code": "payment_failed", "content_type": "plain",
            "text": result.error or "payment failed",
        }]
        resp = _shape(request, session_id=session_id, status=models.STATUS_READY,
                      line_items=current["line_items"],
                      buyer=(body.buyer.model_dump() if body.buyer
                             else current.get("buyer")),
                      messages=messages)
        # The ONLY explicit clear of the freeze marker: the charge
        # definitively failed, so the session is safely mutable again.
        _persist(session_id, resp, total_runs, creator_key_hash=creator_key_hash,
                 charge_attempted=False)
        _complete_idempotency(ctx, resp)
        return JSONResponse(resp, status_code=402)

    # Fulfillment: credit runs to the buyer's account (keyed by their api_key)
    # exactly once per session — fulfill_once is atomic, so a concurrent or retried
    # /complete cannot double-credit. Paired with the per-session charge key above,
    # the whole completion is idempotent and crash-retry-safe.
    store = get_store()
    account = store.get_account_by_api_key(ctx.api_key)
    if account is None:
        account = store.create_account(api_key=ctx.api_key, plan="free")  # allow-secret: var ref
    fulfilled = store.fulfill_once(session_id, account["id"], total_runs)

    base = str(request.base_url).rstrip("/")
    order = current.get("order")
    messages = None

    def _mint_order() -> dict:
        """Sign and persist the order receipt; return the order object.

        The order id is DETERMINISTIC per session, so every mint attempt —
        first try, crash-recovery retry, even concurrent ones — writes the
        same receipt row (save_receipt is INSERT OR REPLACE on run_id):
        exactly one receipt per paid session, with no locking."""
        order_id = _order_id_for(session_id)
        order_receipt_body = {
            "run_id": order_id,
            "provider": "acp",
            "dry_run": False,
            "summary": {
                "kind": "credit_pack_purchase",
                "runs_credited": total_runs,
                "amount": amount,
                "currency": CURRENCY,
                "payment_id": result.payment_id,
                "checkout_session_id": session_id,
            },
            "receipt_line": f"ACP order {order_id}: {total_runs} triage-run credits "
                            f"purchased for {amount} {CURRENCY} minor units.",
        }
        signature = receipts.sign(order_receipt_body)
        store.save_receipt(
            run_id=order_id, summary=order_receipt_body["summary"], provider="acp",
            dry_run=False, receipt_line=order_receipt_body["receipt_line"],
            signature=signature, account_id=account["id"],
        )
        return {
            "id": order_id,
            "checkout_session_id": session_id,
            "permalink_url": f"{base}/v1/audit/{order_id}",
        }

    if fulfilled:
        order = _mint_order()
    elif order is None:
        # The credit was applied by an EARLIER attempt that crashed before the
        # order was recorded (reviews U018/U110/U032: any raise between
        # fulfill_once and _persist left money captured, credit committed, and
        # the order permanently unrecorded — this branch used to shrug with
        # "already_fulfilled" and never mint the receipt). The charge above was
        # deduped by Stripe (per-session idempotency key), so result.payment_id
        # is the ORIGINAL payment — CONVERGE: reattach the receipt if it was
        # saved before the crash, otherwise mint it now. Either way the retry
        # ends in a completed session with exactly one receipt and no
        # duplicate charge or credit.
        existing = store.get_receipt(_order_id_for(session_id))
        if existing is not None:
            order = {
                "id": existing["run_id"],
                "checkout_session_id": session_id,
                "permalink_url": f"{base}/v1/audit/{existing['run_id']}",
            }
        else:
            order = _mint_order()
        messages = [{
            "type": "info",
            "code": "order_recovered",
            "content_type": "plain",
            "text": "Credits were already fulfilled for this checkout session; "
                    "the order receipt was recovered without a duplicate "
                    "charge or credit.",
        }]

    resp = _shape(request, session_id=session_id, status=models.STATUS_COMPLETED,
                  line_items=current["line_items"],
                  buyer=(body.buyer.model_dump() if body.buyer
                         else current.get("buyer")),
                  order=order, messages=messages)
    _persist(session_id, resp, total_runs, account_id=account["id"],
             creator_key_hash=creator_key_hash)
    _complete_idempotency(ctx, resp)
    return JSONResponse(resp)


@router.post("/checkout_sessions/{session_id}/cancel")
async def cancel_session(session_id: str, request: Request):
    ctx = _gate(request, require_idempotency=True)
    raw = await request.body()
    replay = _begin_idempotency(ctx, raw, "acp.cancel")
    if replay is not None:
        return JSONResponse(replay, headers={"Idempotent-Replayed": "true"})

    row = _load(session_id)
    _require_owner(ctx, row)
    current = row["data"]["response"]
    if current["status"] == models.STATUS_COMPLETED:
        raise ACPError(400, "invalid_state", "cannot cancel a completed session",
                       "status")
    _require_not_charged(session_id, row, "canceled")
    resp = _shape(request, session_id=session_id, status=models.STATUS_CANCELED,
                  line_items=current["line_items"], buyer=current.get("buyer"))
    _persist(session_id, resp, row["data"]["total_runs"],
             creator_key_hash=row["data"].get("creator_key_hash"))
    _complete_idempotency(ctx, resp)
    return JSONResponse(resp)
