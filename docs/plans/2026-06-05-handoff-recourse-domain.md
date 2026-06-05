# Agent Handoff: Recourse.email Domain and Product Naming

**From:** Codex session | **Date:** 2026-06-05 | **Phase:** domain acquired / implementation pending

## Current State

- Repository: `/Users/4jp/Code/organvm/universal-mail--automation`
- Branch: `main`
- Git state before this handoff was written:
  - `HEAD` = `960b094255f7957d08f82101679f16b2bf726c53`
  - `origin/main` = `960b094255f7957d08f82101679f16b2bf726c53`
  - working tree was clean
- Domain purchased by user: `recourse.email`
- Existing deployed share/demo URL remains `https://uma.4444j99.dev`
- No code/config changes have yet been made to route the product through `recourse.email`.

## Completed Work

- [x] Rejected `inboxrisk.com` after user clarified the real originating need: they had not checked their inbox for about a month and needed to surface emails requiring response.
- [x] Reframed product naming around inbox catch-up, missed-response recovery, and reply triage rather than abstract risk or compliance.
- [x] Evaluated naming lanes:
  - `Reply Triage` / `replytriage.com`
  - `Re:surface` and related `surface` domains
  - `Reply Cue` / `replycue.email`
  - `ReplyQ` / `replyq.email`
  - `Recourse` / `recourse.email`
- [x] Verified `recourse.email` availability via direct `.email` registry RDAP checks before purchase:
  - `https://rdap.identitydigital.services/rdap/domain/recourse.email` returned 404
  - `https://rdap.donuts.co/rdap/domain/recourse.email` returned 404
  - DNS had no `NS` or `A` records before purchase
- [x] User purchased `recourse.email`.

## Key Decisions

| Decision | Rationale |
|---|---|
| Use `Recourse` as the serious product brand | It fits recovery, agency, remedy, and getting back to obligations after inbox drift. |
| Use `recourse.email` as canonical buyer-facing domain | Short, serious, available, and contextually tied to email without the spelling friction of `requeue.email`. |
| Do not use `Inbox Risk` | It overfit the protected-cleanup/audit framing and missed the lived job of finding emails that still need a response. |
| Keep `uma.4444j99.dev` as staging/demo/internal unless redirected | Existing CI and Worker route depend on it; changing production routing should be deliberate and verified. |
| Lead product copy with response recovery | The first job is "find what still needs your response," with protected senders and receipts as trust depth later. |

## Critical Context

- User explicitly rejected the `Inbox Risk` direction as unclear.
- The original human problem was not checking an inbox for a month and needing the system to surface messages that needed response.
- Strong product language from the corrected direction:
  - "Find what still needs your response."
  - "Recover the emails that still need you."
  - "Surface the messages you owe a reply."
- The repo currently still contains public/demo references to `uma.4444j99.dev` and some generated artifacts may still point to placeholder `mail.example.com`.
- Treat Cloudflare/production changes as production-sensitive: announce before mutating DNS, routes, Worker config, or CI deploy settings.
- Do not commit secrets, OAuth material, tokens, or logs.

## Next Actions

1. Verify Cloudflare now shows `recourse.email` in the account and determine zone status.
2. Decide routing shape:
   - apex `recourse.email` for the public app;
   - optional `www.recourse.email` redirect to apex;
   - optional `uma.4444j99.dev` retained as staging or redirected.
3. Update source/config for the canonical URL:
   - `wrangler.toml`
   - `.github/workflows/ci.yml` smoke-test base URL
   - `server.json`
   - generated `.well-known/agent.json` and `llms.txt` paths if applicable
   - `api/well_known.py` / `PUBLIC_BASE_URL` behavior
   - README and docs that mention `uma.4444j99.dev`
   - `web/index.html` brand/copy if moving from Universal Mail Automation to Recourse.
4. Deploy and verify live endpoints:
   - `GET https://recourse.email/health`
   - `GET https://recourse.email/server.json`
   - `GET https://recourse.email/.well-known/agent.json`
   - `POST https://recourse.email/v1/senders/check`
5. Watch GitHub Actions until Python CI, Cloudflare deploy/smoke, and Pages deployment are green on the final commit.

## Risks & Warnings

- Do not assume domain purchase means Cloudflare DNS zone is active; verify nameservers/zone state first.
- If both `recourse.email` and `uma.4444j99.dev` serve the app, CORS and canonical artifact URLs must not drift.
- Do not over-rotate the product into legal/compliance language too early. "Recourse" can support that later, but the first screen should stay grounded in missed-response recovery.
- `requeue.email` was available but rejected as hard to spell. Avoid similarly clever names in public copy.
- Keep the Worker/share-demo vs canonical Python backend boundary explicit; the Worker is not the full production backend.

## Recovery Protocol

If resuming cold:

1. Start in `/Users/4jp/Code/organvm/universal-mail--automation`.
2. Run `git status --short --branch` and confirm whether this handoff has been committed.
3. Verify `recourse.email` in Cloudflare before editing `wrangler.toml`.
4. Search current references with:
   - `rg -n "uma\\.4444j99|mail\\.example\\.com|PUBLIC_BASE_URL|server\\.json|Universal Mail|Recourse" .`
5. Make a small PR or direct branch for the domain migration, then deploy and smoke-test the exact live URLs.
