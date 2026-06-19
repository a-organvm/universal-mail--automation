"""Account authentication helpers and API-key issuance endpoints."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api import plans
from api.store import get_store

ISSUER_TOKEN_ENV = "UMA_API_KEY_ISSUER_TOKEN"

router = APIRouter(tags=["auth"])


class IssueApiKeyRequest(BaseModel):
    email: Optional[str] = Field(default=None, max_length=320)
    plan: str = Field(default=plans.DEFAULT_PLAN_ID, max_length=64)
    status: str = Field(default="active", max_length=64)
    run_credits: int = Field(default=0, ge=0, le=1_000_000)


class ApiKeyIssueResponse(BaseModel):
    account_id: str
    api_key: str  # allow-secret: generated credential returned once to issuer
    email: Optional[str] = None
    plan: str
    status: str
    run_credits: int


class AccountVerificationResponse(BaseModel):
    authenticated: bool
    account_id: str
    email: Optional[str] = None
    plan: str
    status: str
    run_credits: int
    current_period_end: Optional[int] = None
    entitlements: dict


def bearer_api_key(request: Request) -> Optional[str]:  # allow-secret: function name
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None
    if not auth.startswith("Bearer ") or not auth[len("Bearer "):].strip():
        raise HTTPException(status_code=401, detail="invalid bearer credentials")
    return auth[len("Bearer "):].strip()  # allow-secret: parsed header, not literal


def authorized_account(request: Request) -> Optional[dict]:
    api_key = bearer_api_key(request)  # allow-secret: variable name
    if api_key is None:
        return None
    account = get_store().get_account_by_api_key(api_key)  # allow-secret: var ref
    if account is None:
        raise HTTPException(status_code=401, detail="invalid bearer credentials")
    return account


def require_authorized_account(request: Request) -> dict:
    account = authorized_account(request)
    if account is None:
        raise HTTPException(status_code=401, detail="missing bearer credentials")
    return account


def issuer_token(request: Request) -> Optional[str]:
    token = request.headers.get("X-UMA-Issuer-Token", "").strip()
    if token:
        return token
    return bearer_api_key(request)  # allow-secret: header parser reused for issuer token


def require_api_key_issuer(request: Request) -> None:
    configured = os.environ.get(ISSUER_TOKEN_ENV, "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="API-key issuance is not configured")

    presented = issuer_token(request)
    if presented is None:
        raise HTTPException(status_code=401, detail="missing issuer credentials")
    if not hmac.compare_digest(presented, configured):  # allow-secret: runtime compare
        raise HTTPException(status_code=401, detail="invalid issuer credentials")


def public_account(account: dict) -> dict:
    return {
        "authenticated": True,
        "account_id": account["id"],
        "email": account.get("email"),
        "plan": account.get("plan") or plans.DEFAULT_PLAN_ID,
        "status": account.get("status") or "active",
        "run_credits": int(account.get("run_credits", 0)),
        "current_period_end": account.get("current_period_end"),
        "entitlements": plans.entitlements_for(account),
    }


@router.post("/v1/auth/api-keys", response_model=ApiKeyIssueResponse)
def issue_api_key(req: IssueApiKeyRequest, request: Request) -> dict:
    """Issue a new account API key.

    This endpoint is operator-gated by UMA_API_KEY_ISSUER_TOKEN because the
    returned API key authorizes mailbox-reading API calls and metered live runs.
    """
    require_api_key_issuer(request)

    plan_id = (req.plan or plans.DEFAULT_PLAN_ID).lower()
    if plan_id not in plans.PLANS:
        raise HTTPException(status_code=400, detail="unknown plan")
    status = (req.status or "active").lower()
    if status not in {"active", "trialing", "past_due", "canceled", "unpaid"}:
        raise HTTPException(status_code=400, detail="unknown account status")

    account = get_store().create_account(
        email=req.email,
        plan=plan_id,
        status=status,
        run_credits=req.run_credits,
    )
    return {
        "account_id": account["id"],
        "api_key": account["api_key"],  # allow-secret: generated credential
        "email": account.get("email"),
        "plan": account["plan"],
        "status": account["status"],
        "run_credits": int(account.get("run_credits", 0)),
    }


@router.get("/v1/auth/verify", response_model=AccountVerificationResponse)
def verify_api_key(request: Request) -> dict:
    """Verify the presented account API key without returning the key itself."""
    return public_account(require_authorized_account(request))
