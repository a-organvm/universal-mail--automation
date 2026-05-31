#!/usr/bin/env python3
"""Generate the committed commerce / go-to-market artifacts from the canonical
catalog in ``api.plans`` (fix bases, not outputs).

Outputs (run ``python scripts/gen_commerce_artifacts.py``):
  * pricing.md                  human pricing page
  * llms.txt                    machine-readable B2A summary (root, llmstxt.org)
  * .well-known/agent.json      agent manifest (endpoints, protocols, scopes)
  * server.json                 Official MCP Registry manifest

Re-run after any change to api/plans.py so the artifacts never drift.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import plans  # noqa: E402
from api.well_known import build_agent_manifest, build_llms_txt  # noqa: E402

# Placeholder host; real URLs are resolved live by the served routes
# (/acp/feed.json, /.well-known/agent.json). The committed files are declarations.
BASE = os.environ.get("PUBLIC_BASE_URL", "https://mail.example.com").rstrip("/")
PKG = "io.github.a-organvm/universal-mail-automation"


def gen_pricing_md() -> str:
    lines = [
        "# Pricing",
        "",
        "**Sold on the negative guarantee, not features.** The fail-closed "
        "protected-sender gate and the independent, signed audit receipt are "
        "identical on every tier — including Free. We charge for reach (run "
        "volume, providers, agent access) and retained receipt history, never for "
        "safety.",
        "",
        "| Plan | Price | What you get |",
        "|------|-------|--------------|",
    ]
    for p in plans.PLANS.values():
        cap = "unlimited" if p.monthly_run_cap is None else f"{p.monthly_run_cap:,}/mo"
        lines.append(
            f"| **{p.name}** | {p.price_display} | {p.blurb} "
            f"_(runs: {cap}; providers: {p.providers})_ |"
        )
    lines += [
        "",
        f"**Agent / metered:** {plans.METERED_ADDON['price_display']} — "
        f"{plans.METERED_ADDON['blurb']}",
        "",
        "**Agent credit packs (one-time, via Agentic Commerce Protocol):**",
        "",
        "| Pack | Runs | Price |",
        "|------|------|-------|",
    ]
    for pk in plans.CREDIT_PACKS.values():
        lines.append(f"| {pk['title']} | {pk['runs']:,} | "
                     f"${pk['amount_cents'] / 100:.2f} |")
    lines += [
        "",
        "Subscriptions are managed via Stripe (Checkout + self-serve Customer "
        "Portal). See `docs/agent-commerce.md` for the agent surfaces.",
        "",
    ]
    return "\n".join(lines)


def gen_server_json() -> dict:
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": PKG,
        "description": (
            "Email triage an agent can't misuse: it can't archive a protected "
            "sender, and every action returns a verifiable receipt."
        ),
        "version": "0.1.0",
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "universal-mail-automation",
                "version": "0.1.0",
                "transport": {"type": "stdio"},
            }
        ],
        "remotes": [
            {"type": "streamable-http", "url": f"{BASE}/mcp"}
        ],
    }


def main() -> None:
    with open(os.path.join(ROOT, "pricing.md"), "w") as f:
        f.write(gen_pricing_md())
    with open(os.path.join(ROOT, "llms.txt"), "w") as f:
        f.write(build_llms_txt(BASE))
    wk = os.path.join(ROOT, ".well-known")
    os.makedirs(wk, exist_ok=True)
    with open(os.path.join(wk, "agent.json"), "w") as f:
        json.dump(build_agent_manifest(BASE), f, indent=2)
        f.write("\n")
    with open(os.path.join(ROOT, "server.json"), "w") as f:
        json.dump(gen_server_json(), f, indent=2)
        f.write("\n")
    print("wrote pricing.md, llms.txt, .well-known/agent.json, server.json")


if __name__ == "__main__":
    main()
