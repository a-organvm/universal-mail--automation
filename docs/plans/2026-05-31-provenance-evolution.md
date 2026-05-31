# PROVENANCE — Mail-Automation Evolution Plan

**Date:** 2026-05-31 · **Repo:** `organvm-iii-ergon/universal-mail--automation` (ORGAN-III, PUBLIC_PROCESS)
**Origin:** session 8ad5da31 — after a live Gmail triage (309→56) succeeded via the self-built `gmail.modify` engine.
**Status:** PLAN (artifact). Code changes here require per-session push auth + PR (Rule #12). No commits made when authored.

> Privilege: legal mail from a protected legal sender (active matter) is present and retained; the firm/case is not named here and zero case content is recorded.

---

## 1. THE GOAL

**Evolve the personal `universal-mail--automation` engine into _PROVENANCE_ — a durable, multi-provider (Gmail + iCloud + Outlook), privacy-first, client-facing inbox-triage product whose defining guarantee is that protected senders are _never_ archived — and carry it to ORGANVM GRADUATED.**

**Success criteria (what makes "done" unambiguous):**
1. All three personal accounts (Gmail ✓, iCloud, Outlook) triaged **durably** under one shared rule set (`core/rules.py`).
2. Protected-sender never-archive enforced as a **hard pre-action gate** (fail-closed), not implicit query exclusion.
3. **Stranger test passes:** a second person goes zero → successful dry-run on their own mailbox in < 30 min.
4. A **durable runner** replaces all dead LaunchAgents — no machine-freeze, bounded concurrency (16GB-safe).
5. A **client-facing surface** (onboarding wizard + storefront) is live; first usable/paying tier shipped.
6. Repo advances LOCAL → CANDIDATE → PUBLIC_PROCESS → **GRADUATED** (blocking CI, trust story, support runbook).

---

## 2. THE CADENCE LOOPS

Each loop stated as `trigger → action → output → next consumer` (Rule #7: everything is a loop).

### Loop A — Triage Loop (operational; per account)
- **Trigger:** new mail (push: Gmail `watch()`+Pub/Sub, Graph subscription) **or** scheduled sweep (iCloud/IMAP poll, no push available).
- **Action:** classify via `core/rules.py` → **protected gate** → either preview-digest (apply nothing) or auto-apply (label + archive via `batchModify`).
- **Output:** smaller inbox + append-only audit-log entry + receipt ("N protected untouched / M archived").
- **Next consumer:** the Report loop; the user's attention (only real human items remain).
- **Cadence:** continuous (push) / daily (poll fallback).

### Loop B — Credential-Health Loop (maintenance) — *directly prevents the wall we hit this session*
- **Trigger:** weekly check **or** token nearing expiry.
- **Action:** silent refresh each provider token; on `RefreshError` → flag for one re-consent (graceful once the `gmail_auth` base-fix lands).
- **Output:** green/red auth status per account.
- **Next consumer:** Triage loop (depends on live tokens); the user (only if re-consent needed).
- **Cadence:** weekly + on-demand.

### Loop C — Product-Build Loop (ORGANVM promotion)
- **Trigger:** weekly build session.
- **Action:** pull next roadmap item (§6) → branch → PR → review.
- **Output:** merged PR advancing a feature; promotion-state movement.
- **Next consumer:** the promotion gate; the storefront.
- **Cadence:** weekly.

### Loop D — Rule-Evolution Loop (event-driven)
- **Trigger:** a misfiled message or a new uncategorized sender pattern surfaces (flagged by Loop A's digest).
- **Action:** propose rule (manual or LLM) → human approve → update `core/rules.py` **and** compile to a durable provider rule (Gmail filter / Graph messageRule).
- **Output:** updated taxonomy + persisted server-side rule (zero ongoing compute for that pattern).
- **Next consumer:** Triage loop.
- **Cadence:** as-needed.

---

## 3. THE DIRECTORIES TO WORK IN (canonical surfaces — no new substrate)

| Purpose | Canonical home |
|---|---|
| **Engine code** | the repo (origin `organvm-iii-ergon/universal-mail--automation`); local checkout at the bench path below. Branch + PR to `main`; **never direct-push** (PUBLIC_PROCESS). |
| **Local checkout** | `/Users/4jp/Code/organvm/materia-collider/bench/organ-reset-2026-03-11/organ-iii/universal-mail--automation/` *(lives under a bench scratchpad — see breadcrumb note below)* |
| **Classification brain** | `core/rules.py` (the single taxonomy; kill the driver's inline-bucket fork) |
| **Providers** | `providers/{gmail,imap,outlook,mailapp}.py` + `providers/base.py` |
| **Auth substrate** | `gmail_auth.py`, `auth/onepassword.py` |
| **Triage driver** | the session's `/tmp/gmail_triage_driver.py` is ephemeral AND embeds a real-sender map — do **NOT** commit it verbatim; re-implement its logic cleanly on `core/rules.py` (config-not-source) as `triage.py` / into `cli.py` |
| **Secrets / env** | `~/.config/op/mail_automation.env.op.sh` (1Password-backed; user's unlocked shell only) |
| **Plans** | `docs/plans/` in-repo, dated `YYYY-MM-DD-slug.md` (this file) |
| **Client-facing storefront** | the repo's GitHub Pages (greenfield — `docs/` site to be built) |
| **NOT** | `/tmp` for anything durable; no forked parallel repo |

**Breadcrumb note:** the canonical PUBLIC_PROCESS repo currently lives inside `materia-collider/bench/` (a scratchpad). Either (a) it's a working clone and stays, or (b) it should be relocated to a proper ORGAN-III path with a `.MOVED-TO` breadcrumb. Confirm before heavy build work.

---

## 4. RESOLVED DECISIONS (the 4 open questions, researched)

**A) Other accounts — per-account plan.**
- **Gmail:** done; maintenance only.
- **iCloud:** *one config gap from working* (highest-value next). Provider + app-specific password exist; only blocker is an env var-name mismatch (`ICLOUD_IMAP_USER/PASS/HOST` exported vs bare `IMAP_HOST/USER/PASS` read by `imap.py`). Alias the vars → `imap_rules.py --dry-run` → `--apply`.
- **Outlook:** access token expired 2026-01-20, refresh token present → silent refresh, else one interactive sign-in; dry-run before apply.
- **Two Exchange/M365 accounts:** *needs decision + new code.* Classify personal vs employer tenant first (employer mailbox likely out of scope); only then extend `outlook.py` (tenant authority) or IMAP. Do not attempt yet.

**B) Stale third-party sales thread → ARCHIVE.** An unsolicited "overemployment" sales pitch from a personal address, declined Jan 2025, cold re-ping May 2026. Archive (retain its label), not delete (real human thread), not keep (no pending action). *(Sender handle + thread id held out of this public doc; they live in the session record.)*

**C) `gmail_auth.py` bug → BASE-FIX (not the driver workaround).** Confirmed: `get_credentials()` refresh branch (lines ~163-171) has no try/except → a dead refresh token raises `RefreshError` and crashes instead of falling to consent. Fix-bases-not-outputs: wrap refresh in `try/except RefreshError: creds=None` then a guarded `if not creds or not creds.valid:` consent fallback; add `from google.auth.exceptions import RefreshError`. Also check `auth/onepassword.py` + `providers/gmail.py` for the same pattern. **Gate:** PUBLIC_PROCESS → needs per-session push auth → branch `fix/gmail-auth-refresh-fallback` → PR, no self-merge.

**D) "Google Cloud billing" emails → PHISHING pattern (mixed).** One benign baseline (Cloud Shell deletion notice, `noreply-cloudshell@google.com`, bare on-domain links). **Four to treat as phishing** (3× "overdue/underpayment" `CloudPlatform-noreply@google.com` + 1× "suspension" `google-cloud-compliance@google.com`): every link hidden behind `c.gle` shortener / `notifications.googleapis.com/email/redirect` tokens, invented "Google Collections" dept, "Dear Customer", identical billing-account string reused on a dunning cadence, real project id used as credibility bait. **Action:** do NOT click; verify by typing `console.cloud.google.com` directly (against the real project — id held out of this public doc); "Report phishing"; do NOT auto-archive (unresolved security items).

---

## 5. CENSUS HIGHLIGHTS

**Internal automations (all in the one repo + two strays):**
- **Active:** the engine package; `core/rules.py`; `/tmp/gmail_triage_driver.py` (this session's mechanism); the op env file.
- **Dormant:** `~/.local/bin/mail-triage` (Mail.app/osascript, separate older engine, last run 2026-04-22); legacy Gmail-API one-offs (`auto_drain`, `bulk_sweeper`, `archive_sorted`, `gmail_labeler[_legacy]`, etc.); `imap_rules.py`; AppleScript Mail tools; `run_automation.sh`/`deploy.sh` (dead `Workspace/` paths).
- **Dead:** all three schedulers (`com.user.mail_automation.plist`, `com.user.gmail_labeler.plist` → nonexistent paths, not loaded; `com.4jp.mail-triage` → no plist on disk). **No live scheduler exists.**
- **No send/SMTP capability anywhere** — engine is label/archive/classify only.
- Codex/Gemini mail plugins present but disabled/empty.

**Account readiness:** Gmail ✓ working · iCloud one-alias-away · Outlook token-refresh-away · 2 Exchange need a decision.

**Two-lane verdict:** **Build-truth = HIGH** (provider abstraction, durable `batchModify`, shared taxonomy, dry-run-first, empirical 309→56 proof). **World-interface = LOW** (no live scheduler, single-tenant auth, implicit-not-enforced safety rail, no onboarding/monetization, non-blocking CI). Classic "best-kept-secret" mismatch → **stop adding engine features; build the world interface.**

---

## 6. PRODUCT BLUEPRINT DIGEST → MVP / ROADMAP

**Wedge (one sentence):** no incumbent is simultaneously **durable** (mutates real mailbox, visible in every client), **multi-provider** (Gmail+Outlook+iCloud under one policy), **private** (your own OAuth app, no vendor relay), **scriptable** (rules as diffable/version-controlled config), and **safe** (hardened protected-sender allowlist enforced before any action). Competitors pick one or two.

**Architecture moves:** capability-tiered provider interface (server-rules+push where available, polling where not) · **LLM/rules → durable provider-native rule compiler** (classify once, persist as Gmail filter / Graph messageRule) · single long-lived daemon runner (NOT per-task launchd) with preview-digest mode · 1Password BYO-OAuth (CASA-free) as flagship + envelope-encrypted multi-tenant store for the hosted tier · protected-sender **hard pre-action gate** (fail-closed).

**Ranked features:** (0) fix auth refresh crash · (1) protected never-archive gate · (2) unified cross-account rules · (3) scheduled preview-digest · (4) LLM→durable-rule compiler · (5) undo/audit log · (6) push (watch/subscriptions) · (7) phishing flag (the GCloud case is a live example) · (8) import existing filters · (9) digest reports · (10) NL rule authoring → compiles to inspectable rules · (11) MCP server · (12) JMAP.

**MVP (LOCAL→CANDIDATE):** "the honest triage run, packaged" — fix #0, canonical CLI on `core/rules.py`, hard protected gate (#1), audit receipt (#5 minimal), stranger-test onboarding for BYO-OAuth. North star: second person → dry-run in < 30 min.

**v1 (→PUBLIC_PROCESS deepened):** multi-provider (#2), daemon + preview-digest (#3), compiler (#4) + push (#6) + phishing (#7) + import (#8) + reports (#9), hosted onboarding + storefront, multi-tenant secrets.

**Moat / GRADUATED (v2+):** NL authoring (#10), MCP server (#11), JMAP (#12); blocking CI; trust story; the compound (durable+multi+private+scriptable+safe + CASA-free self-host) that a SaaS incumbent structurally cannot copy.

**Pricing hypothesis:** self-host free (wedge + proof); hosted personal ~$8-10/mo (multi-account by default — undercuts SaneBox's per-account tax); pro/small-firm ~$20-25/mo (the legal/financial guarantee as a compliance-adjacent feature).

**Top risks (premortem):** R1 Google CASA assessment for `gmail.modify` on hosted tier → lead with CASA-free BYO-OAuth, gate hosted CASA on revenue · R3 protected-gate fails open eats high-stakes mail → fail-closed hard gate + undo + receipt · R4 OAuth onboarding friction kills activation → guided wizard + verified-app hosted screen + fix #0 · R5 runner freezes machine again → single bounded daemon, push-first · R6 multi-provider auth support burden → self-host shifts ownership to user. **The killer is the world-interface lane, not a missing feature.**

---

## 7. IMMEDIATE NEXT ACTIONS (in order)

1. **Harden the protected-sender gate** in `core/rules.py` / action path (fail-closed) and reconcile the allowlist against the brief (the inline driver list omitted several org/bank variants) — *before* running any new account. **Safety-first.**
2. **Light up iCloud** (alias env vars → dry-run → apply). One config change.
3. **Refresh Outlook** token (silent → else one sign-in) → dry-run → apply.
4. **Base-fix `gmail_auth.py`** via branch + PR (needs push auth).
5. **Archive** the stale sales thread; **report** the 4 phishing emails after console check.
6. **Re-implement** the `/tmp` driver's logic cleanly on `core/rules.py` (config-not-source) — never commit the driver verbatim (it embeds a real-sender map + account-specific label IDs).
7. **Decide** on the 2 Exchange accounts (personal vs employer) before any code.
