# Agent Handoff: Cloudflare Share Backend

**From:** current session | **Date:** 2026-06-01 | **Phase:** PROVE / share

## Current State

- Branch: `feat/commerce-surface`
- Local branch is **ahead of `origin/feat/commerce-surface` by 1 commit**: `f3e67d9 feat: cloudflare share backend`
- The repo already has the merged commerce-surface closeout docs from the earlier ship:
  - `docs/plans/2026-06-01-closeout-commerce-surface-merged.md`
  - `docs/plans/2026-06-01-handoff-commerce-surface-merged.md`
- Current working tree only shows local scratch dirs as untracked: `.claude/` and `.serena/`

## Completed Work

- [x] Added a Cloudflare Worker share backend in `cloudflare/worker.mjs`
- [x] Added `wrangler.toml` for a same-origin dashboard + API deployment
- [x] Refreshed `web/index.html` so the dashboard can run in share mode and fall back to local demo data if the backend is unavailable
- [x] Deployed the share bundle to Cloudflare Workers
- [x] Verified live endpoints for:
  - `/health`
  - `/app/`
  - `/v1/senders/check`
  - `/v1/triage/preview`
  - `/v1/billing/plans`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Use a Cloudflare Worker as the share surface | It gives a publicly shareable, same-origin frontend + backend without needing the full Python stack exposed publicly |
| Keep the worker as a demo/share backend rather than replacing the FastAPI app | The repo already has the real backend; the worker is for partner sharing and quick review, not a production migration |
| Let the dashboard degrade to local demo data when API fetches fail | The page still shows something useful even if a partner opens it before the backend is reachable |

## Critical Context

- The live share URL is:
  - `https://universal-mail-automation-demo.ivixivi.workers.dev`
- The worker serves the frontend and a minimal API from the same origin.
- The underlying Python backend in the repo is still the canonical app for the full product.
- Any claim that the repo is "fully shipped" should be separated from the share deployment. The share backend is a delivery layer for the frontend, not a rewrite of the product backend.

## Next Actions

1. Decide whether the Cloudflare share backend should remain as a permanent public demo surface or be folded into the main deployment notes.
2. If keeping it, add a short deployment note to the repo docs so the share URL and its purpose are easy to find.
3. If promoting it further, add CI/deploy automation around `wrangler deploy` so the worker can be regenerated from source without manual steps.

## Risks & Warnings

- The Cloudflare worker is a share/demo surface, not the authoritative product backend.
- `.claude/` and `.serena/` are local scratch dirs and should stay out of commits.
- Do not let the worker URL get mistaken for the canonical production API unless that is explicitly decided later.
