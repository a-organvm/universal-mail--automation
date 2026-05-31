"""Agentic Commerce Protocol (ACP) surface — the agent-facing buy action.

ACP here means the **Agentic Commerce Protocol** (OpenAI + Stripe), the agent→
merchant checkout standard — NOT Zed's Agent Client Protocol, NOT IBM/BeeAI's
Agent Communication Protocol, NOT Google's A2A/AP2. See ``docs/agent-commerce.md``
for the full disambiguation and why this is the right "ACP" for selling a service
to AI agents.

Scope ruling (load-bearing): Stripe Shared Payment Tokens are *one-time*-scoped,
so ACP sells a ONE-TIME digital SKU — a credit pack of N triage runs — while the
recurring human subscription goes through ``api.billing`` (Stripe Billing). Two
surfaces, one Stripe account.
"""

__all__ = ["API_VERSION"]

# The exact ACP spec/API version this surface implements. Requests carrying any
# other API-Version header are rejected (the spec is date-versioned).
API_VERSION = "2026-04-17"
