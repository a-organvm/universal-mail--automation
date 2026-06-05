# Agent Handoff: Cloudflare CI Deploy + 4444j99 Share Domain

**From:** current Codex session | **Date:** 2026-06-02 | **Phase:** prove

## Current State

- Repository: `/Users/4jp/Code/organvm/universal-mail--automation`
- Branch: `main`
- Local state before writing this handoff: clean, `0 0` with `origin/main`
- Open PRs: none
- Open issues: none
- GitHub Actions secret: `CLOUDFLARE_API_TOKEN` exists on `a-organvm/universal-mail--automation`, last updated `2026-06-02T15:31:30Z` <!-- allow-secret false-positive: secret name/status only -->
- Live share URL: `https://uma.4444j99.dev`
- Worker name: `uma`
- Worker custom domain route in source: `uma.4444j99.dev`
- Latest main CI: success
  - `26830888854` Python CI: `test (3.11)`, `test (3.12)`, and `Deploy Cloudflare share demo` all succeeded
  - `26830885735` GitHub Pages build/deploy succeeded

This handoff file itself is newly added and may be uncommitted unless the current/next agent commits it.

## Completed Work

- [x] Found Cloudflare configuration source outside the repo:
  - Local Wrangler OAuth exists under `~/.config/.wrangler`
  - 1Password item `Cloudflare API Token` contains the deploy token
  - Cloudflare account verified by `wrangler whoami`: `CF-4444j99`
- [x] Verified the 1Password Cloudflare token can deploy this Worker locally with Wrangler 4.
- [x] Set GitHub Actions secret `CLOUDFLARE_API_TOKEN` for `a-organvm/universal-mail--automation`.
- [x] Confirmed old CI behavior:
  - Before secret: deploy job skipped. <!-- allow-secret false-positive: secret name/status only -->
  - After secret: deploy job ran but failed under `cloudflare/wrangler-action@v3`, which installed Wrangler `3.90.0` and failed at Cloudflare `/memberships` with auth code `9106`. <!-- allow-secret false-positive: secret name/status only -->
- [x] Fixed CI deploy action:
  - PR #14: `cloudflare/wrangler-action@v4`
  - Pinned `wranglerVersion: "4"`
  - Main CI after merge proved deploy + smoke test.
- [x] Replaced long workers.dev URL:
  - PR #15 changed source/docs/CI from `universal-mail-automation-demo.ivixivi.workers.dev`
  - New public URL is `https://uma.4444j99.dev`
  - Added `routes = [{ pattern = "uma.4444j99.dev", custom_domain = true }]` to `wrangler.toml`
- [x] Deployed and smoke-tested `https://uma.4444j99.dev`.

## Evidence

- Main repo state before this handoff was written:
  - `git status --short --branch` -> `## main`
  - `git rev-list --left-right --count HEAD...origin/main` -> `0 0`
- Live custom-domain checks:
  - `GET https://uma.4444j99.dev/health` -> `{"status":"ok","service":"universal-mail-automation","version":"0.1.0"}`
  - `POST https://uma.4444j99.dev/v1/senders/check` with `clerk@courts.ca.gov` -> `protected: true`
- Latest commits:
  - `89a57db Merge pull request #15 from a-organvm/fix/short-cloudflare-share-url`
  - `cbe07d6 use 4444j99 cloudflare share domain`
  - `3364508 Merge pull request #14 from a-organvm/fix/cloudflare-wrangler-action-v4`
  - `6c5b231 use wrangler action v4`

## Key Decisions

| Decision | Rationale |
|---|---|
| Use `https://uma.4444j99.dev` | Short, minimal, tied to Universal Mail Automation, and uses the user's preferred new `4444j99.dev` domain. |
| Keep Worker name `uma` | Minimal Cloudflare service name and easy to remember. |
| Use a custom domain route instead of only workers.dev | User disliked the workers.dev URL; custom domain is cleaner and durable. |
| Use `cloudflare/wrangler-action@v4` and `wranglerVersion: "4"` | The same token deployed successfully under Wrangler 4.97.0, while the v3 action installed Wrangler 3.90.0 and failed. |
| Store the deploy token as repo secret, not source | Keeps credentials out of git and makes CI durable. |
| Treat the Cloudflare Worker as share/demo, not canonical production backend | Existing docs and architecture distinguish the Worker from the Python product backend. |

## Critical Context

- Do not print or commit Cloudflare token values. The deploy token came from 1Password item `Cloudflare API Token`, field `credential`.
- `wrangler.toml` now has a custom-domain route. Wrangler warned that because `workers_dev` is absent, the old workers.dev route is disabled by default. This is acceptable and aligned with the user's URL preference.
- The CI smoke test points at `https://uma.4444j99.dev`; if DNS/custom-domain routing breaks, main CI should fail in the deploy job.
- The old `universal-mail-automation-demo.ivixivi.workers.dev` URL should not be presented as current.
- PR #15's branch was force-pushed once to replace the intermediate `uma.ivixivi.workers.dev` URL with `uma.4444j99.dev`; it is merged and deleted remotely.
- GitHub Actions still emits Node 20 deprecation warnings and advisory ruff/mypy warnings. These are known non-blockers; pytest is the hard gate.

## Next Actions

1. Commit this handoff file if durable tracked handoff is desired:
   - `git add docs/plans/2026-06-02-handoff-cloudflare-ci-domain.md`
   - `git commit -m "add cloudflare ci domain handoff"`
   - `git push`
2. Re-run final state after committing:
   - `git status --short --branch`
   - `git rev-list --left-right --count HEAD...origin/main`
   - `gh run list --branch main --limit 5`
3. Optional polish:
   - Decide whether to delete/decommission the old `universal-mail-automation-demo` Worker if it still exists in Cloudflare. Do not delete without fresh proof and explicit intent.
   - Consider replacing `/app/` smoke check with `/` if the 307 redirect is undesirable; current CI accepts `/app/` because `curl -fsS` succeeds on 307.
   - Eventually clean advisory ruff/mypy findings if the project wants warning-free CI annotations.

## Risks & Warnings

- Do not rotate or overwrite `CLOUDFLARE_API_TOKEN` unless the current token fails or user explicitly asks.
- Do not assume local Wrangler OAuth equals CI deploy ability; CI uses the GitHub secret only.
- Do not claim Cloudflare is the canonical backend. It is the share/demo surface.
- If another agent creates a new custom domain or route, check Cloudflare zone state first:
  - Active zone found: `4444j99.dev`
  - Account name from Wrangler: `CF-4444j99`

## Recovery Protocol

If resuming cold:

1. Start in `/Users/4jp/Code/organvm/universal-mail--automation`.
2. Verify git state and remote parity.
3. Verify `gh secret list --repo a-organvm/universal-mail--automation` includes `CLOUDFLARE_API_TOKEN`.
4. Verify live URL with:
   - `curl -q -fsS https://uma.4444j99.dev/health`
   - protected-sender POST to `/v1/senders/check`
5. Check latest main CI run includes successful `Deploy Cloudflare share demo`.
