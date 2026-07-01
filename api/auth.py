"""Small account-auth helpers for API-key protected HTTP endpoints."""

from __future__ import annotations

from fastapi import HTTPException, Request

from api.store import AccountRow, get_store


def bearer_api_key(request: Request) -> str | None:  # allow-secret: function name
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None
    if not auth.startswith("Bearer ") or not auth[len("Bearer "):].strip():
        raise HTTPException(status_code=401, detail="invalid bearer credentials")
    return auth[len("Bearer "):].strip()  # allow-secret: parsed header, not literal


def authorized_account(request: Request) -> AccountRow | None:
    api_key = bearer_api_key(request)  # allow-secret: variable name
    if api_key is None:
        return None
    account = get_store().get_account_by_api_key(api_key)  # allow-secret: var ref
    if account is None:
        raise HTTPException(status_code=401, detail="invalid bearer credentials")
    return account


def require_authorized_account(request: Request) -> AccountRow:
    account = authorized_account(request)
    if account is None:
        raise HTTPException(status_code=401, detail="missing bearer credentials")
    return account
