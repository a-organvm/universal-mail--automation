"""Shared triage execution for HTTP and MCP entry points."""

from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from core.intake import build_triage_intake_packet

from api import metering, receipts, service


class AccountRequired(RuntimeError):
    """Raised when a live triage run is requested without an account."""


def run_triage_with_receipt(
    *,
    provider: str,
    query: str,
    limit: int,
    dry_run: bool,
    remove_label: Optional[str],
    tier_routing: bool,
    vip_only: bool,
    account: Optional[dict] = None,
    surface: str = "api",
    actor: Optional[Dict[str, Any]] = None,
    auth: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> dict:
    """Run triage through the safety gate, metering live mutations when needed."""
    if not dry_run and account is None:
        raise AccountRequired("live triage requires an account")

    reservation = None
    if not dry_run and account is not None:
        reservation = metering.reserve_live_run(account, provider=provider)

    try:
        result = service.run_triage(
            provider=provider,
            query=query,
            limit=limit,
            dry_run=dry_run,
            remove_label=remove_label,
            tier_routing=tier_routing,
            vip_only=vip_only,
        )
    except Exception:
        if reservation is not None:
            reservation.rollback()
        raise

    run_id = "run_" + secrets.token_hex(12)
    result["run_id"] = run_id
    receipts.persist(run_id, result, account_id=account["id"] if account else None)
    packet_result = dict(result)
    result["packet"] = build_triage_intake_packet(
        surface=surface,
        run_id=run_id,
        provider=provider,
        dry_run=dry_run,
        query=query,
        limit=limit,
        result=packet_result,
        actor=actor,
        auth=auth,
        extra=extra,
    )
    if reservation is not None:
        reservation.commit()
    return result
