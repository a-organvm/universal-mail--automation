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

Smoke checks are covered in this repository by `ci.yml` + `deploy.yml`:

- Python 3.11/3.12 test matrix
- Python package build + `twine check`
- `umail --version` from built wheel
- Web lint/build and Cloudflare Worker tests

A production host or container host is required to fully prove the socket binding
path (`/health`, `/v1/billing/plans`, `/v1/senders/check`, `/app`).

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

1. **PR gate (external):** confirm all open PRs are merged/closed and the latest `main` CI run is green in GitHub.
2. **Production host gate (external):** pick the live hostname, set `MCP_ALLOWED_HOSTS` if `/mcp` is public, and confirm traffic to `/health`, `/app`, and `/v1` in production.
3. **Mailbox credentials gate:** set one provider auth chain on the host (`GMAIL_*`, `IMAP_*`, or `OUTLOOK_*`).
4. **Billing gate:** set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_BUSINESS`, and `STRIPE_WEBHOOK_SECRET`; wire `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, and `invoice.payment_failed` to `/v1/billing/webhook`.
5. **Cloudflare demo gate:** set `CLOUDFLARE_API_TOKEN` before rotating or claiming `https://uma.4444j99.dev` as current.

No remaining known code-level blockers in this workspace snapshot.
