# Agent Handoff: universal-mail--automation — debt / triage / dashboard / branding session

**From:** Session 4dede9c0-33fa-465d-a2b3-e20d6d0f1bf3 | **Date:** 2026-06-07 | **Phase:** COMPLETE (close-out)

## Current State

- Repo main at PR #37 merge (seed.yaml + CLAUDE.md propagation). **0 open PRs, 0 open issues.**
- CI green on main; full suite **421 passed** locally (`.venv`, Python 3.14) post-merge.
- Dashboard `web/index.html` carries per-provider brand theming (gmail/outlook/icloud/imap), verified via `tests/theme_proof.mjs` (Playwright; run `node tests/theme_proof.mjs [outdir]`).
- Gmail inbox (padavano.anthony@gmail.com): 7 threads labeled via repo's 1Password OAuth — all reversible label adds, **no drafts sent**.
- IRF at corpvs-testamentvm `9d5f655`: DONE-588..592 logged; IRF-III-060..064, IRF-APP-088, IRF-DOM-052 opened.
- Private memory (domus-genoma `e0c65d57`): full triage report + labeling script persisted; 5 memory files local:remote {1:1}.
- Agent worktree `.claude/worktrees/debt-dashboard-branding` still mounted (session-exit prompt handles removal); `.claude/worktrees/` now gitignored.

## Completed Work (evidence = merge SHAs)

- [x] DONE-588 — triage pipeline (PR #22, `3cceb31`): core/research.py, core/voice.py, core/triage.py, CLI `triage`
- [x] DONE-589 — tech-debt sweep (PR #34, `a5c2d84`): bounded dep pins, outlook silent-failure logging, legacy deprecation, README sync
- [x] DONE-590 — provider brand theming (PR #35, `f97dc14`): data-provider token swap, 700ms phase shift, 3 synced control surfaces, localStorage
- [x] DONE-591 — live Gmail triage (2026-06-06): 6 dormant income opportunities surfaced; drafts-as-graveyard failure mode named
- [x] DONE-592 — hall-monitor close-out (PR #36 `bc09315`, metadata `12cefcb`): nothing-lost rescue, worktree gitignore, theme-proof tracked
- [x] Propagation PR #37: seed.yaml capabilities + CLAUDE.md Web Dashboard section

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Label-only Gmail mutations; never send drafts | Legal (Longo) / government (Lanza/DOL) threads — human's call; labels are reversible |
| Triage report → private memory repo, NOT this public repo | Personal legal/financial thread content; same persistence guarantee, different trust boundary |
| Screenshots not committed | Regenerable outputs of tracked generator `tests/theme_proof.mjs` (fix bases, not outputs) |
| CLI key `mailapp` ↔ visual identity `icloud` via SELECT_TO_THEME map | Provider key and brand identity are different axes |
| seed.yaml org conflict NOT guessed at | Three surfaces disagree (see IRF-III-064); needs canonical adjudication, registry sync is likely root fix |
| Direct push to main only for conductor-metadata sync | Explicit per-session user authorization ("commit[all] push[origin]"); all code went through PRs + CI |

## Critical Context

- **claude.ai Gmail MCP is READ-ONLY** (label writes → "insufficient authentication scopes"). Mutations: `source ~/.config/op/mail_automation.env.op.sh` then `gmail_auth.build_gmail_service()` (NOT `get_gmail_service`). Memory: `reference-gmail-write-access-paths`.
- **`domus-memory-sync` silently no-ops** on new memory files (exit 0, no output, no sync; PostToolUse hook doesn't fire). Fallback: `chezmoi diff` then `chezmoi add`. Filed IRF-DOM-052 (P1). Verify any memory write landed in chezmoi source.
- **DONE-ID counter races are real**: a parallel session claimed 587 mid-claim; always assert `next_id` before writing (CLAIM-BEFORE-USE protocol worked as designed).
- Gmail label IDs: Label_22=To Respond, Label_32=Professional/Jobs, Label_69=Triage/Action/Today, Label_26=Actioned.
- "Deploy Cloudflare share demo" CI job skips on every observed run — dashboard deploys are effectively manual (IRF-III-062).
- Repo convention: squash-merge with `(#NN)` subjects; repo requires up-to-date branch (`gh pr update-branch`); auto-merge disabled.

## Next Actions (all filed in IRF — none in-flight)

1. **HUMAN (IRF-APP-088, P0):** send the finished Longo/Zapata draft (delete May 30 skeleton); resolve the two contradictory Lanza/DOL drafts and send the true one; reply to Lawrence Harvey Rust InMail via LinkedIn; 3 staffing re-engagements. Report: private memory `reference-triage-report-2026-06-06`.
2. IRF-III-062 (P1): root-cause the perpetually-skipping Cloudflare Pages deploy job.
3. IRF-III-060/061 (P2): promote mypy/ruff to gating; add offline imap provider tests.
4. IRF-III-063 (P2): drafts-graveyard surfacing — `in:draft` sweep in triage CLI + dashboard red badge.
5. IRF-III-064 (P2): adjudicate the seed.yaml/GitHub/CLAUDE.md org identity conflict.
6. IRF-DOM-052 (P1, domus scope): make `domus-memory-sync` fail loudly.

## Risks & Warnings

- Never auto-send the legal/government drafts — flag only (memory: `feedback-inbox-drafts-graveyard`).
- Protected files (seed.yaml, repo-registry.json, DONE counter, IRF): read-before-write, targeted additive edits only.
- Public repo: no personal inbox content in any commit; no push to main without per-session authorization.
- 16GB Tahoe machine: cap concurrent heavy processes.
