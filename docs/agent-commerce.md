# Agent commerce & agent tools: MCP + ACP

This product exposes two agent-facing surfaces. They are different protocols doing
different jobs, and "ACP" in particular is overloaded — read this before touching
either.

## MCP — Model Context Protocol (how agents *use* the tool)

Anthropic's tool-connectivity standard. Our MCP server (`mcp_server/`) exposes the
triage engine as three tools an AI agent can call:

| Tool | Effect | Annotation |
|------|--------|------------|
| `check_protected_sender` | pure check, no mailbox | `readOnlyHint` |
| `triage_preview` | dry-run, touches nothing | `readOnlyHint` |
| `triage` | applies labels/archive; `dry_run=True` by default | `destructiveHint` |

Every tool delegates to `api.service`, so the fail-closed protected-sender gate and
the independent audit receipt apply to agent calls too: **an agent physically
cannot get a success result if a protected sender was archived.** That inverts the
68+ existing Gmail MCP servers, which expose raw archive/delete with no
decision-layer restraint.

- **stdio** (local, Claude Desktop, any MCP client): `python -m mcp_server`
- **Streamable HTTP** (hosted): mounted at `/mcp` on the main app; also runnable
  standalone via `uvicorn mcp_server.server:http_app`. Set `MCP_ALLOWED_HOSTS` to
  your deploy host(s) (DNS-rebinding protection is on by default).

## ACP — Agentic Commerce Protocol (how agents *buy* the tool)

**The "ACP" we implement is the [Agentic Commerce Protocol](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol)
(OpenAI + Stripe), spec version `2026-04-17`.** It is the agent→merchant checkout
standard. We chose it because it is the only "ACP" that is a *commerce/checkout*
protocol and the only one co-developed with Stripe (our billing processor).

It is explicitly **NOT**:

- **Zed's Agent Client Protocol** — editor ↔ coding-agent IPC. Wrong layer.
- **IBM/BeeAI Agent Communication Protocol** (Linux Foundation) — agent interop.
- **Google A2A / AP2** — agent-to-agent messaging / payment authorization mandates.

If a future contributor wires one of those expecting "buy this service," that is
the predictable error this document exists to prevent.

### Scope ruling: ACP and Stripe Billing are two surfaces, not one

Stripe **Shared Payment Tokens (SPT)** — the delegated-payment mechanism ACP uses —
are *one-time*-scoped (the delegated allowance reason is literally `one_time`).
There is no recurring/subscription path through SPT today. Therefore:

- **Recurring human subscriptions → `api/billing.py`** (Stripe Checkout + Customer
  Portal + a metered usage meter). This is the primary money path.
- **One-time agent purchases → `acp/`** — a single digital SKU: a credit pack of N
  triage runs. An agent buys a pack; runs are credited to the buyer's balance.

Conflating them (trying to run a subscription through ACP/SPT) is the second
predictable error. Don't.

### The ACP surface (`acp/`)

Five endpoints implement the verified Agentic Checkout spec:

```
POST   /acp/checkout_sessions              create
GET    /acp/checkout_sessions/{id}         retrieve
POST   /acp/checkout_sessions/{id}         update
POST   /acp/checkout_sessions/{id}/complete   charge (SPT) + fulfill
POST   /acp/checkout_sessions/{id}/cancel     cancel
GET    /acp/feed.json                      product feed (discovery)
```

Every request is gated fail-closed: `Authorization: Bearer`, exact
`API-Version: 2026-04-17`, and (on POST) a required `Idempotency-Key` with
replay-dedup (409 in-progress / 422 conflict / `Idempotent-Replayed: true` on
replay). Failures return the spec error envelope `{type, code, message, param}`.

On `complete`, the delegated SPT token is charged via a confirmed Stripe
PaymentIntent (`acp/payment.py`, isolated behind an interface so the preview API
version `2026-04-22.preview` is a one-file change), runs are credited, and a
**signed order receipt** is emitted at `/v1/audit/{order_id}` — so even an agent
purchase carries the product's verifiable-receipt trust signal.

### Out of scope (this iteration)

ChatGPT Instant Checkout listing: it is physical-goods-only and application-gated
(US-first, retail-anchored), so a solo dev tool can't list there yet. The ACP
seller endpoints are an open Apache-2.0 spec any ACP-compatible agent can call, so
we ship the faithful endpoints now and treat ChatGPT distribution as later.

## Stripe configuration (deploy secrets — never commit)

| Var | Purpose |
|-----|---------|
| `STRIPE_SECRET_KEY` | enables billing + ACP charge (`sk_live`/`sk_test`) |
| `STRIPE_WEBHOOK_SECRET` | webhook signature verification (`whsec_`) |
| `STRIPE_PRICE_PRO` / `STRIPE_PRICE_BUSINESS` | subscription Price ids |
| `STRIPE_PRICE_METERED` | metered usage Price id |
| `RECEIPT_SIGNING_KEY` | HMAC key for signed receipts (durable verification) |
| `MCP_ALLOWED_HOSTS` | comma-separated hosts for the `/mcp` endpoint (or `*`) |

Absent these, the catalog and pure endpoints still work; money/charge endpoints
return a clean `503 billing is not configured`.
