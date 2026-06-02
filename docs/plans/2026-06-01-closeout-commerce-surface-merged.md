# Session Closeout: Commerce Surface Merged

**Date:** 2026-06-01T13:50:19Z  
**Branch:** `feat/commerce-surface`  
**Merged PR:** https://github.com/a-organvm/universal-mail--automation/pull/6  
**Merge commit:** `cc19740ff5f6b89c74dde6a13381260ca146cdc3`

## Result

The commerce surface follow-up is shipped to `main`. The original commerce surface had already been merged remotely before this session (`origin/main` at `4039482`), while local `main` was stale. This session landed the unshipped follow-up fixes through PR #6 and verified `origin/main` advanced to `cc19740`.

## Fixes Landed

- Dry-run triage previews now record intended dispositions, so `/v1/triage/preview` surfaces nonzero `archived`/`moved` counts for mail that would leave the inbox while remaining tagged `dry_run:true`.
- Stripe webhook events are marked processed only after handler success. Handler failure returns non-2xx so Stripe redelivers, and redelivery can apply the grant.
- `checkout.session.completed` now carries and applies checkout plan metadata, so paid checkout does not depend solely on a later subscription event.
- Mail.app `star()` accepts `due_date=None`, matching the base provider call path.
- ACP `/complete` only mints an order receipt when `fulfill_once()` actually applies credit, preventing duplicate signed receipts on crash/retry.
- ACP self-asserted bearer behavior is documented in `acp/README.md` as intended for the current SPT flow.
- The refreshed `/app/` commerce dashboard is committed.

## Verification Evidence

- Local full suite after commits: `.venv/bin/python -m pytest` -> `248 passed, 1 warning`.
- GitHub CI on PR #6:
  - `test (3.11)` -> pass, 22s
  - `test (3.12)` -> pass, 25s
- Runtime uvicorn verification on `127.0.0.1:8138` with fake mail provider and fake ACP payment client:
  - `GET /health` -> `{"status":"ok","service":"universal-mail-automation","version":"0.1.0"}`
  - `GET /app/` -> HTTP `200`, `23287` bytes
  - `POST /v1/senders/check` with `clerk@courts.ca.gov` -> `protected:true`
  - `POST /v1/senders/check` with empty sender -> `protected:true`
  - `POST /v1/triage/preview` with fake provider -> `audit.total=3`, `protected_held=2`, `archived=1`, `violations=[]`; receipt says `1 would leave inbox`
  - ACP create -> `200 ready_for_payment`; ACP complete -> `200 completed`; signed receipt retrievable at `/v1/audit/order_9d64ec3e007e5edd7b11490f`

## Local State

Only local scratch directories remain untracked: `.claude/` and `.serena/`. They were intentionally not committed.
