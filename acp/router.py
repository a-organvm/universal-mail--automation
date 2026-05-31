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
             account_id: Optional[str] = None) -> None:
    get_store().save_session(
        session_id=session_id, status=response["status"], currency=CURRENCY,
        account_id=account_id,
        data={"response": response, "total_runs": total_runs},
    )


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
    _persist(session_id, resp, total_runs)
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
    current = row["data"]["response"]
    if current["status"] in (models.STATUS_COMPLETED, models.STATUS_CANCELED,
                             models.STATUS_EXPIRED):
        raise ACPError(400, "invalid_state",
                       f"cannot update a {current['status']} session", "status")

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
    _persist(session_id, resp, total_runs)
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
    current = row["data"]["response"]
    total_runs = row["data"]["total_runs"]

    if current["status"] == models.STATUS_COMPLETED:
        # Already fulfilled — return the completed session idempotently.
        _complete_idempotency(ctx, current)
        return JSONResponse(current)
    if current["status"] != models.STATUS_READY:
        raise ACPError(400, "invalid_state",
                       f"session is {current['status']}, not ready_for_payment",
                       "status")

    amount = models.grand_total(current["line_items"])
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
        _persist(session_id, resp, total_runs)
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
    store.fulfill_once(session_id, account["id"], total_runs)

    order_id = "order_" + secrets.token_hex(12)
    base = str(request.base_url).rstrip("/")
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

    order = {
        "id": order_id,
        "checkout_session_id": session_id,
        "permalink_url": f"{base}/v1/audit/{order_id}",
    }
    resp = _shape(request, session_id=session_id, status=models.STATUS_COMPLETED,
                  line_items=current["line_items"],
                  buyer=(body.buyer.model_dump() if body.buyer
                         else current.get("buyer")),
                  order=order)
    _persist(session_id, resp, total_runs, account_id=account["id"])
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
    current = row["data"]["response"]
    if current["status"] == models.STATUS_COMPLETED:
        raise ACPError(400, "invalid_state", "cannot cancel a completed session",
                       "status")
    resp = _shape(request, session_id=session_id, status=models.STATUS_CANCELED,
                  line_items=current["line_items"], buyer=current.get("buyer"))
    _persist(session_id, resp, row["data"]["total_runs"])
    _complete_idempotency(ctx, resp)
    return JSONResponse(resp)
