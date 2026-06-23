"""Machine-readable discovery surfaces for agents (B2A).

Serves the agent manifest and llms.txt with URLs resolved live from the request
host, so a deployed instance is self-describing without a rebuild. The committed
static copies (``.well-known/agent.json``, ``llms.txt``) are generated from the
SAME builders by ``scripts/gen_commerce_artifacts.py`` — one source, no drift.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from api import __version__

router = APIRouter(tags=["discovery"])

_MCP_REGISTRY_NAME = "io.github.a-organvm/universal-mail-automation"


def build_agent_manifest(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "schema_version": "v1",
        "name": "Universal Mail Automation",
        "description": (
            "Email triage with a fail-closed protected-sender gate and an "
            "independent, signed audit receipt."
        ),
        "protocols": {
            "mcp": {
                "transport": "streamable-http",
                "url": f"{base}/mcp",
                "stdio": "python -m mcp_server",
                "tools": ["check_protected_sender", "triage_preview", "triage"],
            },
            "agentic_commerce": {
                "spec_version": "2026-04-17",
                "checkout_url": f"{base}/acp/checkout_sessions",
                "product_feed": f"{base}/acp/feed.json",
            },
        },
        "api": {
            "base_url": base,
            "openapi": f"{base}/openapi.json",
            "pricing": f"{base}/v1/billing/plans",
            "receipt_verification": f"{base}/v1/audit/{{run_id}}",
        },
        "oauth_scopes": [],
        "safety": {
            "protected_sender_gate": "fail-closed",
            "audit_receipt": "independent, HMAC-signed, re-derivable",
            "deletion": "archive/move only — never hard-deletes",
        },
    }


def build_llms_txt(base_url: str) -> str:
    base = base_url.rstrip("/")
    return "\n".join([
        "# Universal Mail Automation",
        "",
        "> Multi-provider email triage with provable restraint: a fail-closed "
        "protected-sender gate (never archives government, financial, legal, or "
        "platform mail) plus an independent, signed audit receipt that refuses to "
        "report success if a protected sender left the inbox.",
        "",
        "## For agents",
        f"- MCP tools (Streamable HTTP): {base}/mcp ; stdio: python -m mcp_server",
        f"- Agentic Commerce checkout: {base}/acp/checkout_sessions",
        f"- Product feed: {base}/acp/feed.json",
        f"- Receipt verification: {base}/v1/audit/{{run_id}}",
        "",
        "## API",
        f"- Pricing: {base}/v1/billing/plans",
        f"- Protected-sender check (no mailbox): {base}/v1/senders/check",
        f"- Triage preview (dry-run): {base}/v1/triage/preview",
        "",
    ])


def build_server_registry(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "$schema": (
            "https://static.modelcontextprotocol.io/schemas/2025-12-11/"
            "server.schema.json"
        ),
        "name": _MCP_REGISTRY_NAME,
        "description": (
            "Email triage an agent can't misuse: it can't archive a protected "
            "sender, and every action returns a verifiable receipt."
        ),
        "version": __version__,
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "universal-mail-automation",
                "version": __version__,
                "transport": {"type": "stdio"},
            }
        ],
        "remotes": [{"type": "streamable-http", "url": f"{base}/mcp"}],
    }


@router.get("/.well-known/agent.json", include_in_schema=False)
async def agent_manifest(request: Request):
    return JSONResponse(build_agent_manifest(str(request.base_url)))


@router.get("/llms.txt", include_in_schema=False)
async def llms_txt(request: Request):
    return PlainTextResponse(build_llms_txt(str(request.base_url)))


@router.get("/server.json", include_in_schema=False)
async def server_json(request: Request):
    return JSONResponse(build_server_registry(str(request.base_url)))
