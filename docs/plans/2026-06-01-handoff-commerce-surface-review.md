# Agent Handoff: commerce-surface review + runtime verification

**From:** Session 3d6b9504 (Claude Code, Haiku 4.5) | **Date:** 2026-06-01 | **Phase:** PROVE (reviewed + verified; not yet merged)
**Reciprocal to:** prior session 8ad5da31 (commerce build); see `tldrs/tldr-out-2026-06-01T09-56-24Z-7c06f54d.md`

## Current State

- **Branch:** `feat/commerce-surface`, **8 commits ahead of `main`** — HEAD `52199a4 feat(commerce): billing, MCP server, and Agentic Commerce (ACP) surfaces`.
- **NOT MERGED.** Disk truth: `git diff main...HEAD` = 67 files / +6151. Prior memory/summary claimed this was merged to main (`4039482`, PR #4 closed) — **that is false against current disk.** Verify before assuming "shipped."
- **Uncommitted working tree:**
  - `web/index.html` (+333/−140) — full product landing+app rewrite (hero, trust pillars, live no-creds sender-check demo, dry-run dashboard, live pricing + Stripe checkout CTAs, agent/MCP/ACP section). Validated as serving (23,287 bytes, HTTP 200).
  - `.gitignore` (+3) — adds `.claude/settings.local.json`.
  - `.serena/` — untracked, ignorable (MCP tool scratch).
- **Tests:** 243 claimed passing (from prior session). **NOT re-run this session** — `/verify` forbids running tests; treat as unverified-this-session.
- **Local permission rule** (`.claude/settings.local.json`, gitignored): allows `gh pr merge`/`gh pr edit`, denies `git push origin main`. Branch protection on `main` was set in a prior session (required checks `test (3.11)`/`test (3.12)`, strict, PR required, no force-push, linear history).

## Completed Work

- [x] **Code review** (`/code-review` xhigh, 9 finder angles + self-verification by code-read — NOT 20 verifier agents, for token discipline). 15 findings, all verified against source. See "Findings ledger" below.
- [x] **Runtime verification** (`/verify`): launched real `uvicorn api.app:app` on isolated `127.0.0.1:8099`, drove every no-credentials surface + the full ACP money flow with `curl`. **Verdict: PASS** for all driveable surfaces; all fail-closed behaviors confirmed live.
- [x] Confirmed the **fail-closed gate works at the live socket**: `clerk@courts.ca.gov` → `protected:true`; empty sender `""` → `protected:true` (fail-closed); spam → `protected:false`.
- [x] Confirmed **fail-closed payment**: ACP `/complete` with Stripe unconfigured → HTTP 402 `payment_failed`, session stays `ready_for_payment`, no credits minted.
- [x] Confirmed graceful 503s (billing unconfigured, provider unavailable) and clean ACP error envelopes (400 no API-Version, 401 no Bearer, 400 non-purchasable plan, 422 missing field).
- [ ] Fix the two ship-blockers (#1, #2) — NOT started.
- [ ] Commit + PR + merge `web/index.html` + commerce surface to `main` — NOT done.
- [ ] Resolve the "100 scheduled tasks" directive — target system still UNRESOLVED (user ruled out `limen`: "someone else's project").

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Verified review findings by reading source myself, not spawning ~20 verifier agents | User is acutely token-sensitive ("10% of my weekly usage" on a prior agent army). Code-read verification is equally rigorous here, far cheaper. |
| `/verify` did NOT connect real mailbox creds (`op` env) | Driving `/v1/triage/preview` live needs real Gmail OAuth → touches real PII/`op` session. Dry-run is safe but credential-touching; left unexercised by choice, flagged explicitly. |
| Did NOT run tests during `/verify` | Skill rule: verification is runtime observation, not CI re-run. |
| Handoff lives in `docs/plans/` (not `.claude/plans/`) | `docs/plans/` is the repo's established, tracked plans surface (commerce diff added `2026-05-31-provenance-evolution.md`). Don't fork a parallel substrate. |
| Frontend `web/index.html` left uncommitted | CLAUDE.md: commit only when the user asks. User has not yet said "ship it." |

## Critical Context

- **The audit is a post-hoc witness by design** (`core/audit.py`, `providers/base.py:335` — "record AFTER execution, from operations that actually ran"). Correct for the *enforcement* guarantee. The dry-run *preview* reuses that same audit, but in dry-run nothing executes → `apply_actions` (cli.py:246) is skipped → only the protected short-circuit records. This is the root of ship-blocker #1.
- **ACP `_gate` (acp/router.py:72-93) performs no authentication** — any non-empty Bearer string is accepted and (on payment success) auto-provisions an account. Runtime-confirmed with arbitrary token `uma_testkey_abc`. NOT credit theft (caller pays with their own SPT), but unbounded unauthenticated account creation. Needs a deliberate product decision, not necessarily a code fix.
- **ACP API version** = `2026-04-17` (`acp/__init__.py:19`); SPT preview version `2026-04-22.preview` (`acp/payment.py:28`). `stripe-python` is unpinned (absent from requirements).
- **`curl` gotcha for the next agent:** pass `-q` as the FIRST arg. A `!` in a heredoc `-d` body triggers shell history expansion → spurious 422s that look like server validation failures but aren't.
- **Store path** is `MAIL_DB_PATH` env (default `data/app.db`, gitignored). For any local run, redirect to a temp dir.

## Next Actions

1. **Fix ship-blocker #1 (dry-run preview reports zeros).** In dry-run, the preview must surface *intended* dispositions. Options: (a) have `run_labeler` record intended archive/move/label into the audit (or a parallel "would-do" tally) when `dry_run=True`; or (b) have `api/service.run_triage` return `result.label_stats` (already computed, line ~201 cli.py) and have `web/index.html:356` render that for the would-archive count. Add a regression test asserting a non-protected, archivable message shows `archived>0` (or `would_archive>0`) in a dry-run preview.
2. **Fix ship-blocker #2 (webhook loses paid grants).** `api/billing.py:189-198`: move `mark_event_processed` to AFTER `_handle_event` succeeds, OR re-raise inside the except so Stripe redelivers (return non-2xx). Keep signature-verify + idempotency. Add a test: handler raises → event NOT marked processed → redelivery re-applies.
3. **Decide the money-correctness items** (#4 plan not set on checkout.session.completed; #5 duplicate signed receipts on crash-retry — gate on `fulfill_once`'s return; #7 Mail.app `star()` TypeError — add `due_date=None` param). #7 is a clean ~1-line fix and breaks Mail.app starring entirely today.
4. **Decide the ACP auth model** (#6). If self-asserted bearer is intended, document it; if not, require an issued key.
5. **Ship:** commit `web/index.html` + `.gitignore`, push branch, open PR `feat/commerce-surface` → `main`, let CI go green, merge (gate is fixed — `gh pr merge` is permitted, branch protection enforces PR+CI). Only on explicit "ship it" from the conductor.
6. **Resolve the "100 scheduled tasks" directive** — ask the conductor which system this maps to (NOT `limen`).

## Findings ledger (15, ranked; full detail in this session's `/code-review` output)

- **#1 SHIP-BLOCKER** `api/service.py:133` — dry-run preview always reports archived/labeled/kept = 0 (headline demo empty). *Code-confirmed; NOT runtime-confirmed (needs creds).*
- **#2 SHIP-BLOCKER** `api/billing.py:189` — webhook marks event processed before handling + swallows errors → paid grant lost, no redelivery.
- **#3 HIGH (Mail.app)** `providers/mailapp.py:293` — `star()` lacks `due_date`; `base.py:357` passes it → TypeError on every starred Mail.app action.
- **#4 HIGH** `api/billing.py:219` — checkout.session.completed sets status=active but never plan; stale `STRIPE_PRICE_*` env or dropped subscription event → paying customer stuck on Free.
- **#5 HIGH** `acp/router.py:290` — `fulfill_once` return ignored; crash-then-fresh-key-retry mints a 2nd signed receipt for one charge.
- **#6 MED (design)** `acp/router.py:72` — no ACP auth; any bearer accepted. *Runtime-confirmed.*
- **#7 MED** `api/billing.py:202` — `_resolve_account` get-or-create race → UNIQUE(stripe_customer_id) IntegrityError, swallowed.
- **#8 MED** `api/store.py:359` — credit/entitlement economy half-wired; `run_triage` never debits credits or enforces cap.
- **#9 MED** `api/billing.py:240` — plan/status desync across divergent subscription/invoice events.
- **#10 MED (categorization)** `core/rules.py:152` — Finance/Banking & Utilities patterns narrowed to `<domain>.com`; non-canonical bank/utility mail (not in protected list) can fall to Misc/Other → archived. Mitigated: protected gate is the hard guarantee; categorization is best-effort.
- **#11 LOW-MED** `archive_sorted.py:112` — infinite loop when a full 1000-msg page is all protected senders (legacy script, fails safe but hangs).
- **#12 LOW-MED** `core/audit.py:253` — legacy scripts (icloud_triage.py, archive_sorted.py) bypass the independent audit gate.
- **#13 LOW-MED (altitude)** `providers/gmail.py:407` — Gmail re-implements the gate chokepoint; `LABEL_IS_MOVE` is a hand-maintained flag → future provider can fail open.
- **#14 LOW** `core/rules.py:635` — `_idna_decode` fails open on undecodable A-labels; stdlib `idna` ≠ UTS-46. Narrow (needs IDN protected entries).
- **#15 LOW (perf)** `cli.py:176` — `is_protected_sender` recomputed 3×/message over an unchanged input.

**Cleared (checked, not flagged):** webhook signature verification (raw body, 400 on unverified); ACP receipt signing reconstructs the same body the verify recipe expects; `web/index.html` fetches plans once + `escapeHtml`s sender fields (one minor raw `cat.tier`, currently always int); the protected-sender GATE itself is sound and fail-closed.

## Risks & Warnings

- ⚠️ **Do not assume the commerce surface is on `main`.** It is not (disk-verified). Any "it's shipped" claim from memory is stale.
- ⚠️ **`web/index.html` is uncommitted** — orphan-by-default until committed. The product front end exists only in the working tree.
- ⚠️ **Mail.app starring is fully broken today** (#3) — if Mail.app is a launch provider, this blocks it.
- ⚠️ **Finding #1 is the landing page's core proof and is code-confirmed broken but NOT runtime-confirmed** — confirm live (credentialed dry-run) before or alongside the fix.
- The "100 scheduled tasks" directive has no resolved target system; do not invent one.
