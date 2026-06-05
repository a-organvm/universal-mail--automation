"""FastMCP server — the mail-triage engine as safety-gated agent tools.

Every tool delegates to :mod:`api.service`, the single chokepoint that enforces
the fail-closed protected-sender gate and the independent audit receipt. So an
agent driving these tools physically cannot get a "success" result if a protected
sender was archived — the guarantee is inherited, never re-implemented. This
inverts the 68+ existing Gmail MCP servers, which expose raw archive/delete with
no decision-layer restraint.

Two design choices that matter:
  * the destructive ``triage`` tool defaults to ``dry_run=True`` — the opposite of
    the ecosystem default — so a careless or prompt-injected agent previews by
    default and must *explicitly* ask to mutate;
  * a gate violation raises (``AuditInvariantError`` → MCP ``isError``) rather than
    returning success, and the message is generic so internal message ids never
    leak to the model.

Run:
    python -m mcp_server                         # stdio (Claude Desktop, etc.)
    uvicorn mcp_server.server:http_app           # hosted Streamable HTTP at /
"""

from __future__ import annotations

import argparse
import logging
from typing import Optional

import os

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings

from api import metering, service, triage_runtime
from api.schemas import MAX_TRIAGE_LIMIT, SenderCheckResponse, TriageResponse
from api.store import get_store

logger = logging.getLogger(__name__)


def _transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection for the hosted Streamable HTTP endpoint.

    Stays ON by default (loopback always allowed for local dev). Set
    MCP_ALLOWED_HOSTS to a comma-separated host list for production (e.g. the
    Render domain), or to "*" to disable protection when a fronting proxy already
    validates Host.
    """
    raw = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()
    if raw == "*":
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    hosts += ["localhost", "127.0.0.1", "localhost:8000", "127.0.0.1:8000"]
    origins = [f"http://{h}" for h in hosts] + [f"https://{h}" for h in hosts]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )

INSTRUCTIONS = (
    "Multi-provider email triage with provable restraint. Tools here cannot "
    "archive or move a sender the protected-sender gate classifies as protected "
    "(government, financial, legal, platform-security), and every triage returns "
    "a verifiable audit receipt. Use check_protected_sender to pre-check a sender, "
    "triage_preview to see what WOULD change (touches nothing), and triage to "
    "apply changes (dry_run=True by default; set dry_run=False and provide an "
    "account_api_key to mutate the mailbox)."
)

# stateless_http + json_response suit a horizontally-scaled hosted deploy.
# streamable_http_path="/" serves the endpoint at the app root, so mounting the
# app at "/mcp" in api.app resolves to "/mcp" (not "/mcp/mcp").
mcp = FastMCP(
    "universal-mail",
    instructions=INSTRUCTIONS,
    json_response=True,
    stateless_http=True,
    streamable_http_path="/",
    transport_security=_transport_security(),
)


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_TRIAGE_LIMIT))


@mcp.tool(annotations={"readOnlyHint": True})
def check_protected_sender(sender: str, subject: str = "") -> SenderCheckResponse:
    """Is this sender PROTECTED (never archived/moved) and how is it categorized?

    Pure — needs no mailbox credentials. Protected classes: government (.gov),
    financial, legal, and platform-security senders.
    """
    return SenderCheckResponse(**service.check_sender(sender[:4096], subject[:4096]))


@mcp.tool(annotations={"readOnlyHint": True})
def triage_preview(
    provider: str = "gmail",
    query: str = "has:nouserlabels",
    limit: int = 100,
) -> TriageResponse:
    """Dry-run a triage: return the disposition counts + audit receipt, touch
    NOTHING in the mailbox. Requires the server to hold mailbox credentials."""
    return _triage(provider, query, limit, dry_run=True, remove_label=None,
                   tier_routing=False, vip_only=False)


@mcp.tool(annotations={"destructiveHint": True, "idempotentHint": False})
def triage(
    provider: str = "gmail",
    query: str = "has:nouserlabels",
    limit: int = 100,
    remove_label: Optional[str] = None,
    tier_routing: bool = False,
    vip_only: bool = False,
    dry_run: bool = True,
    account_api_key: Optional[str] = None,  # allow-secret: tool parameter
) -> TriageResponse:
    """Apply a triage (labels + archive per the rules). dry_run=True by DEFAULT —
    pass dry_run=False and account_api_key to actually mutate the mailbox.

    FAIL-CLOSED: if the independent audit proves a protected sender left the inbox,
    this raises (the run is rejected) rather than reporting success.
    """
    return _triage(provider, query, limit, dry_run=dry_run, remove_label=remove_label,
                   tier_routing=tier_routing, vip_only=vip_only,
                   account_api_key=account_api_key)


def _triage(provider, query, limit, *, dry_run, remove_label, tier_routing,
            vip_only, account_api_key=None) -> TriageResponse:
    account = None
    if not dry_run:
        if not account_api_key:
            raise RuntimeError("live triage requires account_api_key")
        account = get_store().get_account_by_api_key(account_api_key)  # allow-secret: var ref
        if account is None:
            raise RuntimeError("invalid account_api_key")

    try:
        result = triage_runtime.run_triage_with_receipt(
            provider=provider, query=query, limit=_clamp_limit(limit),
            dry_run=dry_run, remove_label=remove_label,
            tier_routing=tier_routing, vip_only=vip_only, account=account,
        )
    except metering.EntitlementExhausted as e:
        raise RuntimeError(str(e)) from e
    except service.ProviderUnavailable as e:
        # Already generic (raw provider error logged in the service layer).
        raise RuntimeError(str(e)) from e
    except service.AuditInvariantError as e:
        logger.critical("SAFETY GATE VIOLATION via MCP: %s", e)
        raise RuntimeError(
            "SAFETY GATE VIOLATION: a protected sender was moved out of the inbox; "
            "the run was rejected."
        ) from e
    return TriageResponse(**result)


# Hosted Streamable HTTP ASGI app (its own lifespan manages the session manager,
# so running it directly with uvicorn avoids the parent-lifespan footgun).
http_app = mcp.streamable_http_app()


def main() -> None:
    parser = argparse.ArgumentParser(prog="universal-mail-mcp")
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http", "sse"], default="stdio"
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
