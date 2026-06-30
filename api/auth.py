"""Small account-auth helpers for API-key protected HTTP endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request

from core.input_validation import InputValidationError, validate_api_token
from api.store import get_store


def bearer_api_key(request: Request) -> Optional[str]:  # allow-secret: function name
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None
    if not auth.startswith("Bearer ") or not auth[len("Bearer "):].strip():
        raise HTTPException(status_code=401, detail="invalid bearer credentials")
    try:
        return validate_api_token(
            auth[len("Bearer "):], field="bearer token"
        )  # allow-secret: parsed header, not literal
    except InputValidationError:
        raise HTTPException(status_code=401, detail="invalid bearer credentials")


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
