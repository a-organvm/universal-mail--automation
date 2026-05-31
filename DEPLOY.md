# Deploy

The service is a single FastAPI app (API at `/v1/*`, dashboard at `/app`, health at
`/health`). It ships as a `Dockerfile` that honors a platform-provided `$PORT`, so it
runs unchanged on any container host.

## Local

```bash
pip install -r requirements.txt -r requirements-api.txt
uvicorn api.app:app --reload        # http://127.0.0.1:8000/app
```

## Docker (anywhere)

```bash
docker build -t mail-api .
docker run -p 8000:8000 --env-file prod.env mail-api
```

## Render (blueprint included)

Push the repo, then in Render: **New + → Blueprint** and pick this repo. `render.yaml`
provisions a Docker web service with a `/health` check. Set provider credentials as
environment variables in the dashboard (below).

## Fly.io

```bash
fly launch --dockerfile Dockerfile --internal-port 8000   # generates fly.toml
fly secrets set GMAIL_OAUTH_OP_REF=... GMAIL_TOKEN_OP_REF=...
fly deploy
```

## Credentials (set as host env vars — never commit)

Single-tenant for now: the server holds the mailbox credentials. Per provider:

| Provider | Env vars |
|---|---|
| Gmail | `GMAIL_OAUTH_OP_REF`, `GMAIL_TOKEN_OP_REF` (or the `OP_GMAIL_TOKEN_*` triplet) |
| IMAP | `IMAP_HOST`, `IMAP_USER`, `IMAP_PASS` (or 1Password refs) |
| Outlook | `OUTLOOK_CLIENT_ID`, `OUTLOOK_TOKEN_CACHE` |
| Mail.app | local macOS only (not container-deployable) |

The pure endpoints (`/health`, `/v1/senders/check`) and the dashboard's live
protected-sender check need **no** credentials — so a deployed instance is demoable
immediately, before any mailbox is connected.

## Next milestone

Multi-tenant auth (customers connect their **own** mailbox via OAuth) is not yet built —
this deploys a single-tenant instance. See the product roadmap in `docs/plans/`.
