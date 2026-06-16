"""FastAPI application — the product's HTTP surface.

Endpoints:
  GET  /health                          liveness
  POST /v1/senders/check                is this sender protected? (pure, no mailbox)
  POST /v1/triage/preview               dry-run: what WOULD be moved (nothing touched)
  POST /v1/triage                       run a triage (fail-closed on gate violation)
  GET  /v1/audit/{run_id}               signed, re-derivable audit receipt
  GET  /v1/billing/plans                public pricing catalog (no creds)
  POST /v1/billing/{checkout,portal,webhook}   Stripe subscription billing
  *    /acp/*                           Agentic Commerce Protocol (agent checkout)
  *    /mcp                             Model Context Protocol (when mcp SDK present)
  GET  /app                             static dashboard
  GET  /ops                             private operator dashboard
  GET  /v1/ops/{summary,history,intelligence,action-plan,resolver-plan,provider-surface-plan,resolver-ledger,github-resolver,followup-resolver,external-resolver,action-ledger,draft-package,draft-approvals,delivery,evidence}  operator state/review
  POST /v1/ops/{action-receipts,resolver-receipts,github-resolver-receipts,followup-resolver-receipts,external-resolver-receipts,delivery}        append redacted local receipts

Run locally:  uvicorn api.app:app --reload
"""

from __future__ import annotations

import contextlib
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request

from acp import feed as acp_feed
from acp import router as acp_router
from api import (
    __version__,
    billing,
    metering,
    ops,
    receipts,
    schemas,
    service,
    triage_runtime,
    well_known,
)
from api.auth import require_authorized_account

logger = logging.getLogger(__name__)

# --- optional MCP (Streamable HTTP) ------------------------------------------
# The official `mcp` SDK requires Python >=3.10; the core API stays importable on
# 3.9. So the MCP app is imported lazily and mounted only when available. Its
# session manager MUST run in THIS app's lifespan — Starlette does not run a
# mounted sub-app's own lifespan (python-sdk #1367), so without this every /mcp
# call would fail at runtime.
try:
    from mcp_server.server import http_app as _mcp_http_app, mcp as _mcp
    _MCP_AVAILABLE = True
except Exception as e:  # ImportError on <3.10 / missing dep — degrade gracefully
    _mcp_http_app = None
    _mcp = None
    _MCP_AVAILABLE = False
    logger.info("MCP server not mounted (%s)", e)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        if _MCP_AVAILABLE:
            await stack.enter_async_context(_mcp.session_manager.run())
        yield


app = FastAPI(
    title="Universal Mail Automation API",
    version=__version__,
    description=(
        "Multi-provider mail triage with provable restraint: a fail-closed "
        "protected-sender gate plus an independent audit receipt. The API never "
        "bypasses the gate and refuses to report success if a protected sender "
        "was moved out of the inbox. Includes Stripe billing, an agent-facing "
        "Agentic Commerce surface, and (where available) an MCP tool endpoint."
    ),
    lifespan=lifespan,
)


@app.get("/health", response_model=schemas.HealthResponse)
def health() -> dict:
    return {
        "status": "ok",
        "service": "universal-mail-automation",
        "version": __version__,
    }


@app.post("/v1/senders/check", response_model=schemas.SenderCheckResponse)
def senders_check(req: schemas.SenderCheckRequest) -> dict:
    """Would this sender be protected (never archived), and how is it categorized?"""
    return service.check_sender(req.sender, req.subject)


@app.post("/v1/triage/preview", response_model=schemas.TriageResponse)
def triage_preview(req: schemas.TriageRequest) -> dict:
    """Dry-run: show the disposition + audit receipt without touching the mailbox."""
    return _run(req, dry_run=True)


@app.post("/v1/triage", response_model=schemas.TriageResponse)
def triage(req: schemas.TriageRequest, request: Request) -> dict:
    """Run a triage. Honors req.dry_run; fail-closed on any gate violation."""
    account = None if req.dry_run else require_authorized_account(request)
    return _run(req, dry_run=req.dry_run, account=account)


def _run(
    req: schemas.TriageRequest, *, dry_run: bool, account: Optional[dict] = None
) -> dict:
    try:
        actor = None
        auth = {"scheme": "none"}
        if account:
            actor = {"type": "api_account", "id": account.get("id"), "plan": account.get("plan")}
            auth = {"scheme": "bearer", "authenticated": True}
        return triage_runtime.run_triage_with_receipt(
            provider=req.provider,
            query=req.query,
            limit=req.limit,
            dry_run=dry_run,
            remove_label=req.remove_label,
            tier_routing=req.tier_routing,
            vip_only=req.vip_only,
            account=account,
            surface="api",
            actor=actor,
            auth=auth,
            extra={"endpoint": "/v1/triage" if not dry_run else "/v1/triage/preview"},
        )
    except triage_runtime.AccountRequired:
        raise HTTPException(status_code=401, detail="missing bearer credentials")
    except metering.ProviderNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except metering.EntitlementExhausted as e:
        raise HTTPException(status_code=402, detail=str(e))
    except service.ProviderUnavailable as e:
        # `e` is already a generic, non-sensitive message (the raw provider error
        # is logged in the service layer, never returned to the client).
        raise HTTPException(status_code=503, detail=str(e))
    except service.AuditInvariantError as e:
        # The independent audit proved a protected sender left the inbox.
        # Fail closed and surface it loudly — never a 200. The exception carries
        # the offending internal message IDs; log those server-side but return a
        # fixed message so internal identifiers do not leak to the client.
        logger.critical("SAFETY GATE VIOLATION: %s", e)
        raise HTTPException(
            status_code=500,
            detail="SAFETY GATE VIOLATION: a protected sender was moved out of "
            "the inbox; the run was rejected.",
        )


# --- additional product surfaces ---------------------------------------------
app.include_router(billing.router)
app.include_router(receipts.router)
app.include_router(ops.router)
app.include_router(acp_router.router)
app.include_router(acp_feed.router)
app.include_router(well_known.router)
acp_router.register_acp_handlers(app)

if _MCP_AVAILABLE:
    # Streamable HTTP MCP endpoint; session manager started in lifespan above.
    app.mount("/mcp", _mcp_http_app)


# --- static web frontend ------------------------------------------------------
# A zero-build dashboard served by the same app (same origin -> no CORS); it
# calls the JSON API above. Mounted last so it never shadows /health, /v1, /acp,
# or /mcp.
from pathlib import Path  # noqa: E402

from fastapi.responses import FileResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if _WEB_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    @app.get("/ops", include_in_schema=False)
    def ops_dashboard() -> FileResponse:
        return FileResponse(str(_WEB_DIR / "ops.html"))

    app.mount("/app", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
