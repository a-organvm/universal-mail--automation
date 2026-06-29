# Deploy

Universal Mail Automation is deploy-ready as a single FastAPI service:

- API: `/v1/*`
- Dashboard: `/app/`
- Health: `/health`
- Agent surfaces: `/mcp`, `/acp/*`, `/.well-known/agent.json`, `/llms.txt`

The committed `Dockerfile` honors a platform-provided `PORT`. `render.yaml`
provides the Render blueprint. The Cloudflare Worker remains a public share/demo
surface, not the canonical product backend.

## Verified locally

These checks passed on 2026-06-29:

```bash
python3 -m pytest -q                               # 517 passed
python3 -m ruff check --select E9,F63,F7,F82 .    # clean
python3 -m build --no-isolation --skip-dependency-check
python3 -m twine check dist/*
umail --version                                    # umail 0.2.0
npm run lint --prefix web -- --max-warnings=0
npm run build --prefix web
node --test cloudflare/worker.test.mjs
```

FastAPI was also smoke-tested in process with `TestClient` for `/health`,
`/v1/billing/plans`, `/v1/senders/check`, `/app/`, and
`/.well-known/agent.json`.

Socket binding and Docker smoke tests were not runnable in this sandbox:
`uvicorn` startup reached application startup, then local port binding returned
`operation not permitted`; `docker` is not installed here. The CI deploy workflow
builds and smoke-tests the same Dockerfile.

## Deploy commands

Container host:

```bash
docker build -t mail-api .
docker run -p 8000:8000 --env-file prod.env mail-api
```

Render:

```text
Render -> New + -> Blueprint -> select this repo -> set env vars below
```

Cloudflare share demo:

```bash
npm ci --prefix web
npm run build --prefix web
CLOUDFLARE_API_TOKEN=... npx wrangler@4 deploy
```

## What remains

1. ✅ **PR/CI gate** — all open PRs merged or closed (2026-06-29). CI on `main`
   is fully green: Python 3.11, 3.12, package build (wheel smoke-test including
   `umail --version`), web lint/build, Cloudflare Worker tests. No open PRs.
2. **Production host gate** — choose the live host and set its base env. A
   no-credential demo only needs the app deployed; set `MCP_ALLOWED_HOSTS` to
   the public hostname if `/mcp` is exposed.
3. **Live mailbox gate** — set provider credentials:
   `GMAIL_OAUTH_OP_REF`/`GMAIL_TOKEN_OP_REF`, or `IMAP_HOST`/`IMAP_USER`/`IMAP_PASS`,
   or `OUTLOOK_CLIENT_ID`/`OUTLOOK_TOKEN_CACHE`.
4. **Money gate** — set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`,
   `STRIPE_PRICE_BUSINESS`, and `STRIPE_WEBHOOK_SECRET`; configure Stripe to
   deliver `checkout.session.completed`, `customer.subscription.*`,
   `invoice.paid`, and `invoice.payment_failed` to
   `https://<host>/v1/billing/webhook`.
5. **Cloudflare demo gate** — set `CLOUDFLARE_API_TOKEN` in CI or the local
   deploy environment before claiming `https://uma.4444j99.dev` is current.

No code or PR blockers remain. Items 2–5 are credentials and infra decisions only.
