"""Intake packet primitives for cross-surface trust envelopes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

UMA_INTAKE_PACKET_SCHEMA = "uma.intake.packet.v1"


def _now_utc_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_intake_packet(
    *,
    operation: str,
    surface: str,
    payload: Dict[str, Any],
    product: str = "uma",
    status: str = "ok",
    run_id: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
    auth: Optional[Dict[str, Any]] = None,
    request: Optional[Dict[str, Any]] = None,
    persona: Optional[Dict[str, Any]] = None,
    env: Optional[str] = None,
    schema: str = UMA_INTAKE_PACKET_SCHEMA,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a generic, redacted intake envelope used across CLI/API/MCP/worker."""
    envelope: Dict[str, Any] = {
        "schema": schema,
        "product": product,
        "surface": surface,
        "operation": operation,
        "status": status,
        "timestamp": timestamp or _now_utc_iso(),
        "payload": payload,
    }
    if run_id is not None:
        envelope["run_id"] = run_id
    if env is not None:
        envelope["env"] = env
    if actor is not None:
        envelope["actor"] = actor
    if auth is not None:
        envelope["auth"] = auth
    if request is not None:
        envelope["request"] = request
    if persona is not None:
        envelope["persona"] = persona
    return envelope


def build_triage_intake_packet(
    *,
    surface: str,
    run_id: str,
    provider: str,
    dry_run: bool,
    query: str,
    limit: int,
    result: Dict[str, Any],
    actor: Optional[Dict[str, Any]] = None,
    auth: Optional[Dict[str, Any]] = None,
    env: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a dedicated triage intake envelope."""
    request = {
        "provider": provider,
        "query": query,
        "limit": limit,
        "dry_run": dry_run,
    }
    payload: Dict[str, Any] = {
        "result": result,
        "request": request,
        "surface": surface,
    }
    if extra:
        payload["extra"] = extra
    return build_intake_packet(
        schema=UMA_INTAKE_PACKET_SCHEMA,
        operation="triage",
        surface=surface,
        product="uma",
        run_id=run_id,
        actor=actor,
        auth=auth,
        request=request,
        payload=payload,
        env=env,
        status="ok",
    )
