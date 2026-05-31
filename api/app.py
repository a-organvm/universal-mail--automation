"""FastAPI application — the product's HTTP surface.

Endpoints:
  GET  /health              liveness
  POST /v1/senders/check    is this sender protected? (pure, no mailbox)
  POST /v1/triage/preview   dry-run: what WOULD be moved (nothing touched)
  POST /v1/triage           run a triage (fail-closed on gate violation)

Run locally:  uvicorn api.app:app --reload
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from api import __version__, schemas, service

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Universal Mail Automation API",
    version=__version__,
    description=(
        "Multi-provider mail triage with provable restraint: a fail-closed "
        "protected-sender gate plus an independent audit receipt. The API never "
        "bypasses the gate and refuses to report success if a protected sender "
        "was moved out of the inbox."
    ),
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
def triage(req: schemas.TriageRequest) -> dict:
    """Run a triage. Honors req.dry_run; fail-closed on any gate violation."""
    return _run(req, dry_run=req.dry_run)


def _run(req: schemas.TriageRequest, *, dry_run: bool) -> dict:
    try:
        return service.run_triage(
            provider=req.provider,
            query=req.query,
            limit=req.limit,
            dry_run=dry_run,
            remove_label=req.remove_label,
            tier_routing=req.tier_routing,
            vip_only=req.vip_only,
        )
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


# --- Static web frontend ------------------------------------------------------
# A zero-build dashboard served by the same app (same origin -> no CORS); it
# calls the JSON API above. Mounted last so it never shadows /health or /v1.
from pathlib import Path  # noqa: E402

from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if _WEB_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    app.mount("/app", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
