"""platform/saas_runner.py — multi-tenant SaaS REST entrypoint for mail triage.

A thin, self-contained hosting layer over the triage engine. A caller presents a
``(token, provider, query, license)`` tuple and the runner:

  1. authenticates the call (a non-empty ``token`` is required),
  2. resolves the ``license`` to a billing tier (see :mod:`api.plans`),
  3. enforces a per-tier request **rate limit** keyed by the token,
  4. enforces the tier's provider allow-list (Free is Gmail-only), and
  5. runs a triage through the same safety-gated service the rest of the API
     uses (:func:`api.service.run_triage`), returning a JSON report (audit
     receipt + per-message disposition) annotated with the caller's remaining
     rate-limit budget.

Two surfaces are exposed:

* :func:`run_saas_triage` — a pure function (no FastAPI dependency) usable from
  any host or test.
* ``router`` / ``app`` — a FastAPI router and a standalone ASGI app exposing
  ``POST /v1/saas/triage`` and ``GET /v1/saas/limits``. Serve standalone with
  ``uvicorn platform.saas_runner:app`` or mount ``router`` into another app.

Rate limiting here is intentionally distinct from the monthly run *quota*
enforced by :mod:`api.metering`: the quota bounds total monthly volume (a billing
concern), while this limiter bounds request *burstiness* per tier (fair-use /
abuse protection). The two compose — a live run can be both rate-limited here and
metered there.
"""

from __future__ import annotations

import os
import sys

# When executed as a bare script (``python platform/saas_runner.py``) the parent
# repo root is not on sys.path, so the ``api`` / ``core`` packages would not
# import. Add it defensively; harmless when already importable as a package.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Optional

from api import metering, plans, service
from api.schemas import MAX_TRIAGE_LIMIT

logger = logging.getLogger(__name__)

# Sliding-window length for the per-tier rate limiter.
WINDOW_SECONDS = 60.0

# Requests allowed per ``WINDOW_SECONDS``, by billing tier. These bound request
# burstiness (fair use / abuse protection). The monthly *volume* caps live in
# :mod:`api.plans` (``monthly_run_cap``) and are enforced separately by
# :mod:`api.metering`. An unknown/None tier falls back to the Free limit.
TIER_RATE_LIMITS: Dict[str, int] = {
    "free": 5,
    "pro": 60,
    "business": 600,
}
DEFAULT_RATE_LIMIT = TIER_RATE_LIMITS["free"]


def rate_limit_for(tier: Optional[str]) -> int:
    """Requests-per-window allowed for ``tier`` (Free floor for unknown tiers)."""
    return TIER_RATE_LIMITS.get((tier or "").lower(), DEFAULT_RATE_LIMIT)


# --- errors ------------------------------------------------------------------
class SaaSError(RuntimeError):
    """Base class for SaaS-runner request failures (carries an HTTP status)."""

    status_code = 400


class TokenRequired(SaaSError):
    """Raised when a request arrives without a usable token."""

    status_code = 401


# --- rate limiting -----------------------------------------------------------
@dataclass
class RateLimitDecision:
    """The outcome of a single rate-limit check for one (token, tier)."""

    allowed: bool
    tier: str
    limit: int
    remaining: int
    retry_after: float  # seconds until the next request would be allowed
    reset_after: float  # seconds until the window fully clears
    window_seconds: float = WINDOW_SECONDS

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "limit": self.limit,
            "remaining": self.remaining,
            "retry_after": round(self.retry_after, 3),
            "reset_after": round(self.reset_after, 3),
            "window_seconds": self.window_seconds,
        }


class RateLimited(SaaSError):
    """Raised when a caller exceeds its per-tier request budget."""

    status_code = 429

    def __init__(self, decision: RateLimitDecision):
        super().__init__(
            "rate limit exceeded for tier '%s' (%d requests / %gs)"
            % (decision.tier, decision.limit, decision.window_seconds)
        )
        self.decision = decision


class TierRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by caller token.

    A separate window is tracked per token. The limit applied is resolved from
    the caller's tier at check time, so an upgraded license takes effect on the
    very next request without discarding existing history.

    In-memory and per-process: suitable for a single worker or as a fast local
    guard in front of a shared store. Inject ``clock`` to make tests
    deterministic.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window_seconds: float = WINDOW_SECONDS,
    ):
        self._clock = clock
        self._window = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _evict(self, hits: Deque[float], now: float) -> None:
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def check(self, token: str, tier: str) -> RateLimitDecision:
        """Account for one request; return the decision (consumes a slot if allowed)."""
        limit = rate_limit_for(tier)
        tier_id = (tier or "").lower()
        now = self._clock()
        with self._lock:
            hits = self._hits.get(token)
            if hits is None:
                hits = deque()
                self._hits[token] = hits
            self._evict(hits, now)

            if len(hits) >= limit:
                retry_after = max(0.0, hits[0] + self._window - now)
                reset_after = max(0.0, hits[-1] + self._window - now)
                return RateLimitDecision(
                    allowed=False,
                    tier=tier_id,
                    limit=limit,
                    remaining=0,
                    retry_after=retry_after,
                    reset_after=reset_after,
                    window_seconds=self._window,
                )

            hits.append(now)
            reset_after = max(0.0, hits[0] + self._window - now)
            return RateLimitDecision(
                allowed=True,
                tier=tier_id,
                limit=limit,
                remaining=limit - len(hits),
                retry_after=0.0,
                reset_after=reset_after,
                window_seconds=self._window,
            )

    def peek(self, token: str, tier: str) -> RateLimitDecision:
        """Report current budget WITHOUT consuming a slot (for status endpoints)."""
        limit = rate_limit_for(tier)
        tier_id = (tier or "").lower()
        now = self._clock()
        with self._lock:
            hits = self._hits.get(token, deque())
            self._evict(hits, now)
            used = len(hits)
            reset_after = max(0.0, hits[0] + self._window - now) if hits else 0.0
        remaining = max(0, limit - used)
        return RateLimitDecision(
            allowed=remaining > 0,
            tier=tier_id,
            limit=limit,
            remaining=remaining,
            retry_after=0.0 if remaining > 0 else reset_after,
            reset_after=reset_after,
            window_seconds=self._window,
        )


# Process-wide default limiter used by the HTTP surface.
_LIMITER = TierRateLimiter()


# --- core entrypoint ---------------------------------------------------------
def run_saas_triage(
    *,
    token: str,
    provider: str = "gmail",
    query: str = "has:nouserlabels",
    license_id: str = "free",
    limit: int = 100,
    dry_run: bool = True,
    remove_label: Optional[str] = None,
    tier_routing: bool = False,
    vip_only: bool = False,
    limiter: Optional[TierRateLimiter] = None,
    provider_factory: Optional[Callable[..., object]] = None,
) -> dict:
    """Authenticate, rate-limit by tier, then run a safety-gated triage.

    ``license_id`` is the wire ``license`` field — the caller's declared billing
    tier (``free`` / ``pro`` / ``business``); unknown values resolve to the Free
    floor, never to more access. Returns a JSON-able report::

        {"ok": True, "tier", "provider", "rate_limit": {...}, "report": {...}}

    where ``report`` is the :func:`api.service.run_triage` body (receipt + audit
    summary + per-message disposition). Defaults to a dry run so a report can be
    produced without mutating the mailbox.

    Raises :class:`TokenRequired` (401), :class:`RateLimited` (429),
    :class:`api.metering.ProviderNotAllowed` (403),
    :class:`api.service.ProviderUnavailable` (503), or
    :class:`api.service.AuditInvariantError` (the fail-closed safety gate).
    """
    token = (token or "").strip()
    if not token:
        raise TokenRequired("a non-empty API token is required")

    # Resolve the declared license to a known plan (fail-safe: unknown -> Free).
    tier = plans.plan_for(license_id).id

    # Rate limit first, so even requests we will reject below still cost a slot
    # (an attacker cannot probe disallowed providers for free).
    decision = (limiter or _LIMITER).check(token, tier)
    if not decision.allowed:
        raise RateLimited(decision)

    # Tier provider allow-list (Free = Gmail-only). Reuse the exact predicate the
    # metering layer uses so the rule lives in one place.
    entitlements = plans.entitlements_for({"plan": tier, "status": "active"})
    if not metering.provider_allowed(entitlements, provider):
        raise metering.ProviderNotAllowed(
            "provider '%s' is not included in the '%s' tier" % (provider, tier)
        )

    report = service.run_triage(
        provider=provider,
        query=query,
        limit=limit,
        dry_run=dry_run,
        remove_label=remove_label,
        tier_routing=tier_routing,
        vip_only=vip_only,
        provider_factory=provider_factory,
    )
    return {
        "ok": True,
        "tier": tier,
        "provider": provider,
        "rate_limit": decision.to_dict(),
        "report": report,
    }


def tier_catalog() -> dict:
    """Public description of per-tier rate limits + plan caps (no credentials)."""
    return {
        "window_seconds": WINDOW_SECONDS,
        "tiers": {
            plan_id: {
                "rate_limit_per_window": rate_limit_for(plan_id),
                "providers": plan.providers,
                "monthly_run_cap": plan.monthly_run_cap,
            }
            for plan_id, plan in plans.PLANS.items()
        },
    }


# --- HTTP surface (optional FastAPI) -----------------------------------------
# FastAPI is an extra (requirements-api.txt). The pure entrypoint above works
# without it; the REST surface is only defined when FastAPI is importable.
try:
    from fastapi import APIRouter, FastAPI, Header, HTTPException, Response
    from pydantic import BaseModel, Field

    _FASTAPI_AVAILABLE = True
except Exception as _e:  # pragma: no cover - exercised only when extra missing
    _FASTAPI_AVAILABLE = False
    logger.info("SaaS REST surface not built (FastAPI unavailable: %s)", _e)


def _bearer(authorization: Optional[str]) -> str:
    """Extract a token from an ``Authorization`` header (``Bearer`` or raw)."""
    if not authorization:
        return ""
    value = authorization.strip()
    if value.startswith("Bearer "):
        return value[len("Bearer ") :].strip()
    return value


if _FASTAPI_AVAILABLE:

    class SaaSTriageRequest(BaseModel):
        # The four-tuple from the task: (token, provider, query, license). The
        # token may instead be supplied via the Authorization header; the body
        # field wins when both are present.
        token: str = Field(default="", max_length=512)
        provider: str = Field(default="gmail", max_length=64)
        query: str = Field(default="has:nouserlabels", max_length=2048)
        license: str = Field(default="free", max_length=64)
        # Operational knobs, bounded like the rest of the API.
        limit: int = Field(default=100, ge=1, le=MAX_TRIAGE_LIMIT)
        dry_run: bool = True
        remove_label: Optional[str] = Field(default=None, max_length=512)
        tier_routing: bool = False
        vip_only: bool = False

    router = APIRouter(prefix="/v1/saas", tags=["saas"])

    @router.post("/triage")
    def saas_triage(
        req: SaaSTriageRequest,
        response: Response,
        authorization: Optional[str] = Header(default=None),
    ) -> dict:
        """Apply tier-rate-limited triage and return a JSON report."""
        token = req.token or _bearer(authorization)
        try:
            result = run_saas_triage(
                token=token,
                provider=req.provider,
                query=req.query,
                license_id=req.license,
                limit=req.limit,
                dry_run=req.dry_run,
                remove_label=req.remove_label,
                tier_routing=req.tier_routing,
                vip_only=req.vip_only,
            )
        except TokenRequired as e:
            raise HTTPException(status_code=401, detail=str(e))
        except RateLimited as e:
            raise HTTPException(
                status_code=429,
                detail=str(e),
                headers={
                    "Retry-After": str(int(math.ceil(e.decision.retry_after))),
                    "X-RateLimit-Limit": str(e.decision.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        except metering.ProviderNotAllowed as e:
            raise HTTPException(status_code=403, detail=str(e))
        except service.ProviderUnavailable as e:
            # Already a generic, non-sensitive message (raw error logged server-side).
            raise HTTPException(status_code=503, detail=str(e))
        except service.AuditInvariantError as e:
            # The independent audit proved a protected sender left the inbox.
            # Fail closed — never a 200. Internal ids are logged, not returned.
            logger.critical("SAFETY GATE VIOLATION (saas runner): %s", e)
            raise HTTPException(
                status_code=500,
                detail="SAFETY GATE VIOLATION: a protected sender was moved out "
                "of the inbox; the run was rejected.",
            )

        rl = result["rate_limit"]
        response.headers["X-RateLimit-Limit"] = str(rl["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rl["remaining"])
        return result

    @router.get("/limits")
    def saas_limits() -> dict:
        """Per-tier rate limits + plan caps. Public; needs no credentials."""
        return tier_catalog()

    # Standalone ASGI app: ``uvicorn platform.saas_runner:app``.
    try:
        from api import __version__ as _version
    except Exception:  # pragma: no cover
        _version = "0"

    app = FastAPI(
        title="Universal Mail Automation — SaaS Runner",
        version=_version,
        description=(
            "Tier-rate-limited SaaS entrypoint: POST (token, provider, query, "
            "license) and receive a safety-gated triage report. Free is "
            "Gmail-only; per-tier request rate limits protect fair use."
        ),
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "umail-saas-runner", "version": _version}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    if not _FASTAPI_AVAILABLE:
        raise SystemExit(
            "FastAPI is required to serve the SaaS runner: "
            "pip install -r requirements-api.txt"
        )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
