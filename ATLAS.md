# ATLAS — the `universal-mail` pillar

Spine map of the mail organism: every asset resolved to one of seven primitives, with its
durability and live-state. This is the **one pillar** the mail estate distills into. It is absorbed
into the `domus` house at `communications/inbound/` (git-subtree mirror, pull-only) and run by the
`limen` daemon's **C_MAIL** voice every 6 beats. Mirrors the `edu-organism` ATLAS pattern.

> Distilled 2026-06-22 from a 5-layer sweep of the whole mail estate (219 raw elements → 57 canonical).
> The recurrence Anthony was furious about — "why do I keep making this password" — was a **wiring**
> bug, not a missing credential: the app-password already exists in 1Password; it had simply never
> been wired to a home that reads it headlessly. See the **Connector** primitive below.

## The seven primitives (kernel = `core/` + `providers/`)

| Primitive | What it is | `edu-organism` analog | Implemented in |
|---|---|---|---|
| **Account** | one of 4 mailboxes; provider + capability flags + receipt path | Member | `core/models.py`, `providers/base.py` |
| **Message** | a single envelope (sender/subject/tier/snippet/age) | Mandate | `core/models.py`, `providers/{mailapp,imap,gmail,outlook}.py` |
| **Classifier** | rules taxonomy + Eisenhower tiers + protected-sender gate | Standard | `core/rules.py` (2nd observer: `core/audit.py`) |
| **Action/Sweep** | the reversible move: flag-fire / archive / skip | Standing | `inbox_sweep.py`, `gmail_imap_sweep.py`, `providers/mailapp.py` |
| **Obligation** | derived next-step on a 3-rung PROTOCOL→PRECEDENT→EXPLORATION cascade | Progression | `obligations_build.py`, `core/protocols.py` |
| **Draft** | voice-matched outbound reply, **never sent** | Mandate (outbound) | `draft_writer.py`, `core/voice.py` |
| **Connector** | the write-door grant that permits a real mailbox mutation | Governance | `auth/onepassword.py`, `gmail_auth.py`, `providers/imap.py` |

The protected-sender gate is an **invariant** enforced independently by `core/audit.py` (re-derives
protection from the raw sender, not a passed flag) and `providers/base.py` — a two-observer design that
cannot be silently bypassed. Local never-archive allowlist: `config/protected_senders.local.txt`
(gitignored; Lemon Squeezy / Santander / accessgrantedsystems / givingdata + self).

## How it runs (the heartbeat)

The pillar is executed by the `limen` daemon — these live in `organvm/limen` (the daemon owns them),
documented here as the runner layer:

- `limen/scripts/mail-beat.sh` — **C_MAIL** organ. Per beat: (1) `inbox_sweep.py --flag-only-gmail`
  across all Apple Mail accounts (keyless AppleScript) → (2) `obligations_build.py` rebuilds
  `obligations-ledger.json` → (2b) `draft_writer.py` enriches reply-owed items → (3) `obligations-view.py`
  renders the face. Every step time-bounded and fail-open.
- Face: `obligations.html` at `127.0.0.1:8787/obligations.html` (+ phone mirror). Ledger:
  `limen/obligations-ledger.json` (derived/ephemeral — rebuilt each beat from `audit/inbox_sweep-*.json`).
- C_MAIL is **merged & live** on `limen` main (`df36be7` / `7dd1789`).

## Provider matrix (Account × write-door)

| Account | Provider | Archive today | Notes |
|---|---|---|---|
| padavano.anthony@gmail.com | `providers/{mailapp,imap,gmail}.py` | **blocked** (label store) | Apple Mail can only *flag*, not drop `\Inbox`; needs the Connector (below) |
| a.j.padavano@icloud.com | `providers/{mailapp,imap}.py` | ✅ reliable | real folder store → AppleScript move sticks |
| a.j.padavano@outlook.com | `providers/{mailapp,outlook}.py` | ✅ (Apple Mail) | Graph path dead (no `~/.outlook_token_cache.json`) |
| ajpadavano@outlook.com | same | ✅ (Apple Mail) | second Outlook address |

Only Gmail's **label store** (not folders) defeats Apple Mail; that is the single open write-door.

## Connector — the credential home (ends the password loop)

Every mailbox mutation needs exactly one modify-capable grant (Google security-gates this; no AI path
around it). The grants **already exist and are durable** — the gap was a headless-readable home:

- **Gmail app-password** — `op://Private/gmail-app-pw-2026-06-06` (created 2026-06-06). Drives raw IMAP
  `\Inbox` drop via `gmail_imap_sweep.py` / `providers/imap.py`. *App passwords never expire.*
- **Gmail OAuth** — `op://Personal/Gmail OAuth` (`3mtueqvojjesc77vp5zlhg2coe`): `client_json` +
  `token_json` (scope `gmail.modify`, refresh-token present; access-token stale). Also holds
  `icloud_pass` + `outlook_client_id`. *7-day testing-mode expiry until the OAuth app is promoted to
  Production.*
- **claude.ai Gmail MCP connector** — readonly + compose only (no `gmail.modify`); live-session only.

**Permanent homes** (so the credential is read without a 1Password desktop unlock):
1. **Remote (ideal):** GitHub secret `GMAIL_APP_PASSWORD` on this repo + a scheduled Actions workflow
   running `gmail_imap_sweep.py --apply` on a runner. Survives every local wipe; no op-daemon; no
   desktop app. The app-pw is transplanted **once** (`op read … | gh secret set …`, never on disk).
2. **Local daemon:** a 1Password **service-account token** (`OP_SERVICE_ACCOUNT_TOKEN`) so
   `providers/imap.py`'s existing `OP_ACCOUNT/OP_ITEM/OP_FIELD` resolution works headlessly.

`providers/imap.py::_load_password` order: `IMAP_PASS` env → 1Password (`OP_ACCOUNT/OP_ITEM/OP_FIELD`).
**Note:** `~/.limen.env` currently holds a *fake* placeholder `IMAP_PASS=abcdabcdabcdabcd` — strip it;
it must resolve from the op item above, never a literal.

## Dead satellites (redundant — preserved, not deleted)

Distillation collapses these into the canonical repo; copies are left in place (reversible — let
`library-preserve` evict them after the unique content is captured):

- `~/Workspace/a-organvm/universal-mail--automation`, `~/Workspace/.home-cartridge/Code/organvm/...`,
  and 3 `.limen-worktrees/` CI clones — all duplicate this checkout. **Captured:** the cartridge's
  unique "mail-operations OS layer" (16 `core/` modules: resolvers, historical-intelligence, ops
  cockpit) is now durable on branch **`feat/operator-dashboard-mail-endzone`** (`5683549`, pushed
  2026-06-22) — awaiting its own PR/merge decision; **not** hand-merged here.

## Deprecated in-repo (superseded; kept for reference)

These are **not** called by the live pipeline; treat as historical:

- `gmail_labeler.py`, `gmail_labeler_legacy.py`, `imap_rules.py`, `auto_drain.py`, `archive_sorted.py`,
  `bulk_sweeper.py` — pre-unified-engine; several lack the protected-sender gate. Superseded by
  `inbox_sweep.py` + `gmail_imap_sweep.py` (which always enforce the gate).
- `run_automation.sh`, `icloud_triage.py` — legacy runners; `run_automation.sh` sources a non-existent
  op env file. Superseded by `mail-beat.sh`.
- `com.user.mail_automation.plist`, `com.user.gmail_labeler.plist` — stale LaunchAgent templates
  pointing at the dead `/Users/4jp/Code/organvm/...` path; never installed. The live scheduler is the
  `limen` heartbeat (`com.limen.heartbeat`); a separate read-only reporter is `com.4jp.mail-triage`.

## Surfaces (product / API)

`mcp_server/server.py` (FastMCP, dry-run default, gate-enforced) · `api/` (FastAPI: triage / senders /
billing / audit; ACP checkout) · `cloudflare/worker.mjs` → `uma.4444j99.dev` · `Dockerfile` /
`render.yaml` (container deploy) · PyPI trusted-publish (OIDC). Repo secret: `CLOUDFLARE_API_TOKEN`
(deploy only; canonical copy `op://Personal/Cloudflare API Token`).
