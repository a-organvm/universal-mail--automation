# Agent Handoff: Universal Mail Product Alchemy

**From:** Current Codex session | **Date:** 2026-06-02T14:34:12-0400 | **Phase:** strategy synthesis / pre-implementation

## Current State

Repository:

- Path: `/Users/4jp/Code/organvm/universal-mail--automation`
- Branch: `main`
- Verified status at handoff creation:
  - `## main`
  - untracked planning artifacts only

Untracked artifacts now present:

- `docs/plans/2026-06-02-handoff-cloudflare-ci-domain.md`
- `docs/plans/expansive-inquiry-universal-mail-product-copy/`
- `docs/plans/market-gap-universal-mail-safe-cleanup.md`
- `docs/plans/premortem-universal-mail-safe-cleanup/`
- `docs/plans/synthesis-universal-mail-product-alchemy.md`
- `docs/plans/2026-06-02-handoff-product-alchemy.md`

No implementation edits were made in this strategy pass. No tests or deployment verification were run in this pass.

## Completed Work

- [x] Reviewed screenshot feedback from Maddie:
  - page looked clean and credible;
  - copy read too abstractly / college-level;
  - needs "101 for dummies" / third-grade-simple blurbs;
  - simple language first, proof depth second.
- [x] Ran full `expansive-inquiry` for UMA product copy:
  - artifact directory: `docs/plans/expansive-inquiry-universal-mail-product-copy/`
  - main synthesis: `docs/plans/expansive-inquiry-universal-mail-product-copy/06-synthesis.md`
- [x] Ran `premortem` on safe inbox cleanup launch:
  - transcript: `docs/plans/premortem-universal-mail-safe-cleanup/premortem-transcript-20260602-125121.md`
  - report: `docs/plans/premortem-universal-mail-safe-cleanup/premortem-report-20260602-125121.html`
- [x] Ran `market-gap-analysis`:
  - artifact: `docs/plans/market-gap-universal-mail-safe-cleanup.md`
- [x] Synthesized all thought exercises into:
  - `docs/plans/synthesis-universal-mail-product-alchemy.md`

## Key Decisions

| Decision | Rationale |
|---|---|
| Lead with `Protected Inbox Audit`, not generic email automation | The buyer fear is losing consequence-bearing email, not needing more automation. |
| First promise: `Find the emails you should not lose before you clean anything.` | It compresses feedback, premortem, and market gap into one buyer-obvious job. |
| Use audit-first before cleanup | Email trust barrier is too high for autonomous cleanup as the first paid step. |
| Page hierarchy should be fear -> safety -> cleanup -> proof -> architecture | Current page starts too deep with proof/architecture language. |
| Keep MCP/ACP/agent language out of first-contact path | It is true and valuable, but dilutes the first buyer job. |
| Demo should show a full inbox scenario, not only sender protection | The current sender check proves a mechanism, not the whole buyer job. |
| Avoid absolute safety claims unless bounded by explicit rules | The product names legal/financial/government contexts, so liability boundaries must be precise. |

## Critical Context

The unified product thesis is:

> UMA is a protected inbox audit and safe-cleanup system for people whose email contains things they cannot afford to lose.

The strongest one-liner is:

> Find the emails you should not lose before you clean anything.

Recommended first offer:

- Name: `Protected Inbox Audit`
- CTA: `Check my inbox risk`
- Free path: public sender check and sample scenario
- Paid audit hypothesis: `$29-$49`
- Assisted cleanup hypothesis: `$149-$299`

Recommended buyer wedge:

- founders/operators with overloaded inboxes before cleanup, migration, tax/accounting handoff, admin delegation, or legal/admin review.

Recommended demo structure:

- show 10 sample messages;
- classify each as `must stay`, `safe to move`, or `needs review`;
- then show a receipt explaining what stayed, what moved, what needed review, and why.

Suggested first-screen copy from synthesis:

```text
Clean your inbox without losing important email.

Universal Mail Automation checks for court, bank, government, account, and client emails before cleanup begins. You see what should stay, what can move, and what needs review.
```

Sharper audit-first headline:

```text
Find the emails you should not lose before you clean anything.
```

## Next Actions

1. Verify repo state fresh before editing:
   - `git status --short --branch`
   - inspect `web/index.html`
   - inspect current Cloudflare/source docs if deployment is in scope.
2. Decide whether to stage/commit the strategy artifacts or keep them local-only.
3. Rewrite the landing page copy around `Protected Inbox Audit`:
   - first screen: fear/safety/product promise;
   - CTA: `Check my inbox risk`;
   - secondary CTA: `See a sample receipt`;
   - move MCP/ACP/agent content to an advanced section.
4. Redesign the demo narrative:
   - keep sender check as a component;
   - add full sample inbox classification and receipt.
5. Review safety language:
   - avoid broad "never" claims in first-contact copy;
   - define audit-first, dry-run, approval, and receipt boundaries.
6. Run full local verification after implementation:
   - static checks/tests available in repo;
   - browser smoke of local or deployed page;
   - Cloudflare deployment verification if page changes are shipped.

## Risks & Warnings

- Do not claim the strategy artifacts are remote-durable unless they are committed and pushed.
- Do not stage unrelated dirty files if any appear in future status checks.
- Do not collapse audit, assisted cleanup, recurring cleanup, and agent platform into one CTA.
- Do not market legal/financial/government protection as an unbounded guarantee.
- Do not delete or overwrite the prior Cloudflare/CI/domain handoff artifact unless explicitly asked.
- If deployment is attempted, distinguish source state, deployed Cloudflare state, runtime behavior, local-only artifacts, and remote-durable artifacts.

## Minimal Continuation Prompt

Resume in `/Users/4jp/Code/organvm/universal-mail--automation`.

Read:

- `docs/plans/2026-06-02-handoff-product-alchemy.md`
- `docs/plans/synthesis-universal-mail-product-alchemy.md`
- `docs/plans/market-gap-universal-mail-safe-cleanup.md`
- `docs/plans/premortem-universal-mail-safe-cleanup/premortem-transcript-20260602-125121.md`
- `docs/plans/expansive-inquiry-universal-mail-product-copy/06-synthesis.md`

Then verify disk state with `git status --short --branch` before editing. Continue by converting the current landing page from technical email automation into `Protected Inbox Audit`: audit-first copy, full inbox scenario demo, receipt-first proof, and advanced-only MCP/ACP/agent language. Keep local-only strategy artifacts distinct from committed or deployed state.
