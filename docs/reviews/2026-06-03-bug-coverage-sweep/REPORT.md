# Bug-Coverage Sweep — universal-mail--automation (consolidated, 4 rounds)

**Date:** 2026-06-03 · **Stage:** coverage (UNFILTERED) · feeds a downstream verification/ranking step

> Pure-coverage output across 4 rounds (loop-until-census-exhausted). Findings are **not** filtered or verified; every issue carries `confidence` + `severity`. False positives are expected. Each finding lists the `rounds` that reported it — multi-round corroboration = stronger signal. Machine-readable: [`findings.json`](./findings.json).

**950 unique findings** (raw 952; only 2 exact-match duplicates total (none spanning rounds) — but **427 carry cross-round *line* corroboration**: a finding from a different round flags the same file+overlapping lines, i.e. independent re-discovery. Semantic re-discovery dominates; cluster by file+line, not string match.)

| Round | Scope | Findings |
|---|---|---|
| R1 | subsystem + cross-cutting (`wwi7oyy62`) | 601 |
| R2 | tail: web/data/deps/datetime/money/sqlite/imports + anti-dup (`w4si4zc11`) | 269 |
| R3 | census mop-up: deploy/docs/plists/committed-data (`w1qomjcrp`) | 72 |
| R4 | inline: create_smart_mailboxes.scpt, llms.txt | 10 |

| Severity | Count | | Confidence | Count |
|---|---|---|---|---|
| 🔴 critical | 6 | high | 268 |
| 🟠 high | 128 | medium | 425 |
| 🟡 medium | 301 | low | 257 |
| 🔵 low | 437 | | |
| ⚪ info | 78 | | |

**Categories:** correctness (134) · error-handling (84) · money-path (58) · logic (57) · api-misuse (55) · silent-failure (46) · security (42) · test-quality (40) · config (39) · none-handling (28) · concurrency (26) · resource-leak (22) · dead-code (19) · auth (18) · secrets (17) · regex (16) · injection (16) · correctness/money-arithmetic (11) · money/unit arithmetic (11) · dependency (11) · config/dependency (10) · datetime/timezone (10) · correctness/logic (8) · style (8) · config/consistency (6) · deployment (6) · api-divergence (5) · scheduling (5) · privacy (4) · race-condition (4) · state-machine (4) · perf (4) · race (3) · import-time side effect (3) · correctness / billing (2) · correctness/silent-failure (2) · correctness/regex (2) · security/protected-gate (2) · portability (2) · error-handling / silent-failure (2) · money/consistency (2) · ci/test-coverage (2) · documentation/staleness (2) · type-confusion (2) · path-parsing (2) · state-machine / idempotency (2) · correctness / data-integrity (2) · data-consistency (2) · None/empty handling (2) · routing (2) · re-export drift / public API (2) · consistency (2) · state-machine / money-correctness (1) · authorization / multi-tenancy (1) · error-handling / money-correctness (1) · error-handling/transaction-lifecycle (1) · concurrency/api-misuse (1) · auth / dead code / architecture (1) · state-file-corruption (1) · correctness/divergence (1) · correctness/security (1) · documentation/implementation-contradiction (1) · money-correctness / payment-API misuse (1) · money/unit (1) · race / state-machine (1) · correctness/transaction-boundaries (1) · auth / metering (1) · documentation (1) · schema/referential-integrity (1) · security/correctness (1) · logic/documentation-drift (1) · routing/method-handling (1) · state-consistency (1) · time (1) · broken-link (1) · stale-content (1) · input-validation (1) · packaging (1) · test-quality / import-time crash (1) · state-machine / persistence (1) · money-correctness / idempotency (1) · concurrency / error-handling (1) · state-machine / silent-failure (1) · correctness / maintainability (1) · datetime (1) · injection / correctness (1) · ci/deploy-safety (1) · documentation/dead-reference (1) · documentation/version-drift (1) · config / re-export drift (1) · import-time side effect / API misuse (1) · documentation/implementation-drift (1) · documentation/accuracy (1) · hygiene (1) · documentation/command-accuracy (1) · concurrency / mutable module global (1) · documentation/config-drift (1) · state-machine / audit-correctness (1) · state-machine / datetime (1) · money/decimal/unit-arithmetic (1) · maintainability / latent-correctness (1) · resource-leak/wal (1) · type-confusion/error-handling (1) · concurrency/transaction-isolation (1) · config/silent-failure (1) · correctness / discovery (1) · error-handling/silent-failure/bad-fallback (1) · config/divergence (1) · cors/preflight (1) · performance (1) · documentation/coverage (1) · logic-bug (1) · data-quality (1) · correctness / policy (1) · encoding (1) · security/consistency (1) · documentation/completeness (1) · correctness / spec-conformance (1) · config / silent-failure (1) · correctness / robustness (1) · money-correctness (1) · error-handling / config (1) · error-handling/serialization (1) · resource-leak/lifecycle (1) · concurrency / data-integrity (1) · correctness / smell (1) · correctness / API-misuse (1) · correctness / data-confusion (1) · coverage (1) · documentation / import-time (1) · dead code (1) · import-time / optional dependency (1) · documentation/unverified-claim (1) · observability (1) · security-hardening (1) · accessibility (1)

**Heaviest files:** `acp/router.py` (62) · `providers/outlook.py` (60) · `api/store.py` (57) · `api/billing.py` (50) · `cloudflare/worker.mjs` (44) · `core/rules.py` (39) · `providers/gmail.py` (38) · `providers/imap.py` (36) · `cli.py` (32) · `providers/mailapp.py` (24) · `api/receipts.py` (20) · `auto_drain.py` (20) · `core/config.py` (20) · `mcp_server/server.py` (19) · `auth/onepassword.py` (19) · `core/state.py` (18) · `icloud_triage.py` (16) · `.github/workflows/ci.yml` (16)

## ⚑ Downstream guidance (read before ranking)

- **known_false_positive_class** — Round-2 findings claiming FastAPI/uvicorn/pydantic/stripe/mcp are 'undeclared dependencies' are FALSE POSITIVES — they are declared in requirements-api.txt and requirements-mcp.txt (confirmed by R3 deploy-config finder). Drop these in ranking.
- **false_concern_corrected** — R3 'protected_senders.local.txt is git-tracked' concern is FALSE — it is correctly .gitignored and never committed. The REAL committed-data leak is labeler_state.json (tracked, public, 36470-email counts).
- **scope_correction** — create_smart_mailboxes.scpt is plaintext AppleScript (not a compiled binary as R1/R2 assumed) — reviewed in R4.
- **clustering_note** — Raw counts include heavy semantic clustering (e.g. the unauth+no-metering money-path defect was reported ~15x across finders/rounds). cross_round_corroborated finms (rounds>1) and same-file/same-line groups should be collapsed before triage; high corroboration = high signal.
- **verification_target** — Highest-leverage entries are the structural_gaps (whole-subsystem logic gaps), not individual line findings.

---

## ⚠️ Structural gaps (22) — whole-subsystem, highest leverage

These are architecture-level gaps (some overlap across rounds — corroboration). Verify these FIRST.

### G01 [R1] Entitlement / credit / plan-cap enforcement is dead code — /v1/triage and MCP triage have NO auth and NO metering

**Why:** api/plans.py defines entitlements_for() and api/store.py defines consume_credit() + monthly_run_cap, but a repo-wide grep shows neither is called by any request path (only by scripts/gen_commerce_artifacts.py for marketing copy). The /v1/triage and /v1/triage/preview endpoints (api/app.py:85-130) and the MCP triage tool (mcp_server/server.py:97-146) take NO Authorization/api_key, never look up an account, never check monthly_run_cap, and never debit run_credits. So the entire paid-tier model is unenforced: anyone can run unlimited live triage for free, and ACP-purchased credits are never actually consumed. This is a whole-subsystem logic gap the api-money/api-core/acp finders' visible findings do not cover.

**Where:** `api/app.py:_run (97-130), mcp_server/server.py:_triage (129-146), api/plans.py:entitlements_for (175-193), api/store.py:consume_credit (235-246), api/service.py:run_triage — trace whether any caller debits credits or enforces caps; confirm dead code`

### G02 [R1] ACP bearer token is never validated against the store; arbitrary bearer auto-provisions an account

**Why:** acp/router.py:_gate (72-93) accepts ANY non-empty 'Bearer <x>' string as api_key with no lookup. complete_session (287-289) then does get_account_by_api_key(ctx.api_key) and, on miss, create_account(api_key=ctx.api_key, plan='free') — so an attacker presenting a self-chosen bearer string mints an account and (after a successful SPT charge) gets credits attributed to a token they invented. There is no check that the bearer belongs to a real, pre-issued uma_ key. Combined with the no-metering gap above, the auth model for the agent-commerce surface is effectively absent. <!-- allow-secret false-positive: quoted source-code example -->

**Where:** `acp/router.py:_gate (72-93), complete_session (286-290); api/store.py:get_account_by_api_key (170-175), create_account (145-165) — assess whether unknown bearers should be rejected (401) instead of provisioned`

### G03 [R1] Provider date field unset → escalate command silently no-ops for Gmail/IMAP/Mail.app

**Why:** calculate_email_age_hours (core/rules.py:1163-1185) returns 0 when email_date is None. Grep shows ONLY providers/outlook.py sets date= on EmailMessage (460, 511); providers/gmail.py (157,204,286), providers/imap.py (198,261), and providers/mailapp.py (191,240) construct EmailMessage WITHOUT a date, so EmailMessage.date defaults to None. Therefore `cli.py escalate` produces age_hours=0 for every non-Outlook message and escalate_by_age never fires — a documented feature that is a silent no-op on 3 of 4 providers. The escalate finder reported the CLI-side sort bug but not this provider-layer root cause.

**Where:** `providers/gmail.py EmailMessage construction (157,204,286), providers/imap.py (198,261), providers/mailapp.py (191,240); cross-check cli.py cmd_escalate use of calculate_email_age_hours and core/rules.py:1173`

### G04 [R1] Legacy/standalone scripts perform archive/move operations with little-to-no review and inconsistent or absent protected-sender gating

**Why:** ~2300 lines across gmail_labeler.py (361), gmail_labeler_legacy.py (525), bulk_sweeper.py (131), imap_rules.py (165), auto_drain.py (202), archive_sorted.py (133), mark_rot_read.py (67), icloud_triage.py (175), final_sweep.py, organize_labels.py have essentially zero findings in the sweep yet most perform destructive ops. auto_drain.py has gate=0 (no is_protected_sender call) and 4 archive-classed ops; mark_rot_read.py marks-read with gate=1. None of these have a dedicated test. These are user-runnable entry points (CLAUDE.md lists them as supported legacy commands) so a gate regression here ships unprotected mutations.

**Where:** `auto_drain.py (full), mark_rot_read.py (full), gmail_labeler_legacy.py vs gmail_labeler.py (drift), icloud_triage.py, archive_sorted.py, bulk_sweeper.py SWEEP_RULES — verify each archive/trash path either routes through is_protected_sender or is provably inbox-internal`

### G05 [R1] core/state.py StateManager: no schema/version validation, naive last_run timestamp, silent save failures, no concurrency guard

**Why:** _load (46-56) accepts any JSON shape as state — a corrupt-but-valid-JSON file (e.g. next_page_token set to a dict, total_processed a string) is loaded and used unguarded, and a malformed page token would be replayed to the provider. save (91-95) swallows ALL write exceptions to logger.error and returns normally, so a failed state write looks like success and resume silently restarts from scratch. last_run uses datetime.now().isoformat() (naive local time) while the rest of the codebase is UTC-aware (core/audit.py, core/rules.py) — a timezone inconsistency. No file lock, so two concurrent runs on the same state_file race. state.py had no findings in the sweep.

**Where:** `core/state.py _load (46-56), save (68-95), _default_state (58-66), last_run (87); cross-check cli.py run_labeler state.save/get_token usage`

### G06 [R1] core/models.py: frozen EmailMessage with mutable Set defaults; LabelAction.merge set-dedup loses order/duplicates; combined_text used for protect-matching

**Why:** EmailMessage is @dataclass(frozen=True) yet labels/categories are mutable Set fields (49,53) — frozen prevents reassignment but a caller can still mutate the shared set in place, and field(default_factory=set) is correct but the immutability guarantee is misleading. LabelAction.merge (95-108) collapses add_labels/remove_labels through set(), dropping order and any intended duplicate semantics, and there is no guard that message_id matches (docstring only says 'assumed'). combined_text (56-58) lowercases sender+subject — this is the string the rules/protect logic matches against, the same root cause behind the .gov-anchor finding; worth a model-level note. models.py had no findings.

**Where:** `core/models.py EmailMessage (25-58), LabelAction.merge (95-108), ProcessingResult.add_label_stat (124-126) — verify mutability and merge semantics against provider apply_actions call sites`

### G07 [R1] core/config.py: unguarded int() casts, no validation of provider/log_level, custom_rules/vip_senders applied verbatim, env precedence bug

**Why:** _apply_env_config (272-273) does config.batch_size = int(os.getenv(...BATCH_SIZE)) with no try/except — a non-numeric MAIL_AUTO_BATCH_SIZE crashes config load (and thus the whole CLI/API) at startup. default_provider/log_level are taken verbatim from YAML/env with no validation against the known set, so a typo silently selects nothing or a bad logging level. custom_rules and vip_senders (249-250, 259-260) are assigned straight from untrusted YAML into the rules engine (the same path as the invalid-VIP-regex crash finding) — config-sourced rules get no schema check. Note also docstring claims 'CLI > env > config file' but load_config never applies CLI args (only yaml+env). config.py had no findings.

**Where:** `core/config.py _apply_env_config (263-297, esp. 272-273), _apply_yaml_config custom_rules/vip_senders (248-260), load_config precedence docstring (146-179)`

### G08 [R1] auth/onepassword.py: subprocess argument construction and credential-in-logs surface, no test

**Why:** op_item_edit (94-117) builds `op item edit item field=value` as an argv (no shell, so injection is limited) but a value or field containing '=' or starting with '-' could be mis-parsed by op as a flag/option; op_read/op_item_get pass user/env-derived refs straight to argv. load_secret/load_json_secret log warnings that include op_ref_env / item.field names (180,191) — low PII but could aid recon. store_json_secret error path and the FileNotFound/CalledProcessError handling are untested (no test_onepassword.py). This is the credential boundary and was only lightly touched by the xcut-secrets finder.

**Where:** `auth/onepassword.py op_item_edit (94-117), _run_op (17-46), load_secret logging (180,191), store_json_secret (233-276); add to xcut-secrets follow-up`

### G09 [R1] CI tests only Python 3.11/3.12 but code claims 3.9 importability; dependency floors are unpinned (>=)

**Why:** .github/workflows/ci.yml matrix is ["3.11","3.12"] only, yet CLAUDE.md and api/app.py:35-45 / requirements-mcp.txt explicitly architect around 'core importable on Python 3.9' (the whole lazy-MCP-import dance exists for 3.9). The 3.9 path is therefore NEVER exercised in CI, so a 3.10+ syntax/typing slip (e.g. the Optional["datetime"] forward-ref already flagged, or `X | Y` unions, match statements) would ship undetected. requirements.txt/-api/-mcp pin only lower bounds (google-api-python-client>=2.0.0, fastapi>=0.110, pydantic>=2.0, uvicorn>=0.29) except stripe and mcp — an upstream minor (e.g. pydantic, fastapi, google client) can break the build with no lockfile. ruff/mypy are advisory-only (set +e), so type/lint regressions never fail CI.

**Where:** `.github/workflows/ci.yml (matrix 3.11/3.12, advisory ruff/mypy steps), requirements.txt / requirements-api.txt / requirements-mcp.txt pin policy, pyproject.toml python_requires`

### G10 [R1] api/store.py concurrency & durability: single shared connection serialized by RLock kills SQLite WAL read concurrency; idempotency timeout race; no busy_timeout

**Why:** Store holds ONE sqlite3 connection guarded by a single RLock (127-137); every read goes through _fetch_one/_fetch_all under that same lock (425-437), so the WAL 'readers concurrent with writer' benefit the module docstring claims is negated — all access is fully serialized through one lock and one connection. idempotency_begin (313-353) re-claims a 'processing' key after IDEMPOTENCY_PROCESSING_TIMEOUT (60s) but a legitimately slow in-flight request past 60s would then have its key re-granted to a concurrent retry, allowing a double-execute of a non-idempotent ACP action. No PRAGMA busy_timeout is set (only journal_mode=WAL), so any external connection (e.g. a future second process, or a backup) hitting the file yields immediate 'database is locked' rather than waiting. store.py had findings only indirectly.

**Where:** `api/store.py __init__ (118-138), _fetch_one/_fetch_all locking (425-437), idempotency_begin stale-claim window (334-347), IDEMPOTENCY_PROCESSING_TIMEOUT (103)`

### G11 [R1] api/billing.py webhook: _resolve_account can create duplicate/orphan accounts; subscription status from Stripe written without validation; _period_end/_first_price_id swallow shape errors

**Why:** _resolve_account (208-219) falls through to create_account(account_id=account_id, plan='free') when neither the metadata account_id nor the customer maps to an existing account — a malformed or spoofable metadata account_id on a subscription event could create an orphan account, and if account_id is None it mints a random one, so a customer.subscription.updated for an unknown customer silently creates a brand-new free account rather than erroring. status from obj.get('status') (248) is written verbatim into the accounts table with no enum validation, so a future/unknown Stripe status string becomes the stored status and entitlements_for treats anything not in {active,trialing} as Free (probably intended, but unvalidated). _checkout_plan_id/_first_price_id/_period_end broadly catch (KeyError,IndexError,TypeError) and return None, which can silently leave plan unchanged on a real-but-unmatched price. billing webhook handler had no visible findings.

**Where:** `api/billing.py _resolve_account (208-219), _handle_event status write (248-262), _first_price_id/_checkout_plan_id/_period_end (280-303)`

### G12 [R1] api/receipts.py & core/audit.py signing: ephemeral key silently rotates per process; receipt body trusts unsigned summary; no signature stored-vs-recomputed check on GET

**Why:** _signing_key (44-57) falls back to a fresh secrets.token_bytes(32) per process when RECEIPT_SIGNING_KEY is unset — so in any multi-worker/multi-restart deploy (the docstring itself says horizontally-scaled hosted) receipts signed by worker A do NOT verify against worker B, and the only signal is a one-time warning log. GET /v1/audit/{run_id} (114-142) returns the STORED signature without recomputing/verifying it against the stored body, so a tampered DB row returns a body+signature pair that won't verify but the endpoint presents them as authoritative. signed_body (77-85) signs triage_result.get('audit') which is the gate's own summary — if a regression let a violation through without raising, the receipt would faithfully sign the wrong-but-self-consistent counts. These trust-artifact gaps weren't in the visible findings.

**Where:** `api/receipts.py _signing_key (44-57), get_receipt (114-142), signed_body (77-85); core/audit.py summary/assert_no_violations interplay (241-259)`

### G13 [R1] acp/models.py monetary math has no overflow/negative guard and trusts catalog ints; build_line_items KeyError on missing item id

**Why:** build_line_items (70-97) does pack = packs.get(it['id']) — but it['id'] assumes the validated Item always carries 'id' (true via pydantic) yet quantity is bounded 1..1000 (Item, models.py:27) while base*qty and total_runs accumulation (88-96) have no upper bound, so a request for 1000 x pack_1000 yields large integer charges/credits with no sanity cap. grand_total (100-101) sums li['total'] trusting every line item shape. There's no check that amount_cents/runs in the catalog are non-negative. The amount passed to payment.charge (router.py:257) is whatever grand_total returns. Low individual severity but the money-math path had no visible findings.

**Where:** `acp/models.py build_line_items (70-97), grand_total (100-101), Item quantity bound (25-27); acp/router.py amount=grand_total (257)`

### G14 [R1] Tests: no dedicated coverage for cli.py, the four providers, auth/onepassword, well_known, acp/feed, or any legacy script; coverage-driven false confidence

**Why:** ls tests/ shows no test_cli.py, test_gmail.py, test_outlook.py, test_imap.py, test_provider_base.py, test_onepassword.py, test_well_known.py, test_feed.py, or any test for the 8 legacy scripts. cli.py (1205 lines, the primary entry point with the most high-severity findings: dry-run state corruption, --limit miscount, audit-disabled-on-dry-run) is only exercised transitively via api/service.py import. The providers (gmail/outlook/imap, ~1500 lines) — where batchModify closure, label-id fallback, and protected-gate-consistency bugs live — have no unit tests. CI reports a coverage % that is inflated by the heavily-tested api/core surfaces while the highest-risk mutation paths are untested. The tests subsystem finder should flag the absence, not just the content, of these tests.

**Where:** `tests/ directory (enumerate missing test_cli.py / test_gmail.py / test_outlook.py / test_imap.py / test_onepassword.py); pyproject.toml/.coveragerc for any per-module coverage floor; cross-check cli.py and providers/*.py highest-severity findings for test backstop`

### G15 [R2] cloudflare/worker.mjs (entire 322-line file) — the LIVE production demo deployed by CI to uma.4444j99.dev; never reviewed in round 1 or 2

**Why:** This is a THIRD parallel reimplementation of the product's safety core in JavaScript, and it is the surface the user actually ships and demos. It diverges badly from both the Python engine and web/index.html and is full of unreviewed defects: (1) PROTECTED is a 3-element hardcoded Set {courts.ca.gov, chase.com, 1password.com} — line 1 — so the live demo's protected-sender guarantee covers almost nothing the marketing copy promises (legal/docusign/irs/ssa/apple/google/anthropic/banks all UNprotected on the live site). (2) senderCheck line 153 returns protected = value.includes('chase.com') || value.includes('1password.com') for the fall-through branch, but line 128 already returned for chase.com — so 1password.com is the only non-.gov non-chase domain that is protected, and the .gov branch at line 106 uses value.includes('courts.ca.gov') || value.endsWith('.gov') which both substring-matches (evil.gov.attacker.com endsWith '.gov' is false, but 'x@courts.ca.gov.evil.com' includes 'courts.ca.gov' = TRUE -> spoofable protection, and a display name containing '.gov' is matched because the whole raw sender string is lowercased without address parsing). (3) /v1/audit/{run_id} at line 281 fabricates a receipt with NO signature field at all and a hardcoded audit body {total:3, protected_held:2...} regardless of run_id — directly contradicting receipts.py's 'tamper-evident HMAC-signed' headline trust artifact; the demo's 'signed receipt' is a lie. (4) triagePreview lines 172-198 fabricates fake archived/protected counts unrelated to any real mailbox. (5) CORS access-control-allow-origin '*' on all responses (line 63). The CI smoke test (ci.yml lines 108-119) only checks /health, /app/, plans, and one .gov sender, so none of these divergences are caught.

**Where:** `cloudflare/worker.mjs (lines 1, 82-170 senderCheck, 172-198 triagePreview, 281-305 audit, 61-66 CORS); cross-ref core/rules.py is_protected_sender + api/receipts.py sign() + .github/workflows/ci.yml lines 108-119 smoke test`

### G16 [R2] AppleScript mail movers bypass the protected-sender gate entirely — archive_old_inbox.applescript and route_bulk_senders.applescript

**Why:** The product's HEADLINE guarantee (core/audit.py docstring lines 3-5: 'a protected sender ... is NEVER archived or moved out of the inbox') is enforced only in the Python engine. archive_old_inbox.applescript lines 15-21 move EVERY inbox message older than 90 days to Archive with zero sender check — it will silently archive a lawyer/bank/government email that is 91 days old, the exact scenario the gate exists to prevent. route_bulk_senders.applescript line 9 uses `theSender contains ('@' & dom) or theSender ends with dom` — the `ends with dom` arm is an unanchored substring match (sender 'x@notmailchimp.com' ends with 'mailchimp.com' -> moved; and 'mailchimp.com.attacker.com' would not, but any '...mailchimp.com' subdomain or lookalike trailing match routes mail with no boundary check). flag_important_senders.applescript line 5 uses bare `contains` too. These are documented in CLAUDE.md as shipped tools but share none of the gate/audit logic.

**Where:** `archive_old_inbox.applescript (lines 1-22, no gate); route_bulk_senders.applescript (line 9 unanchored 'ends with'); flag_important_senders.applescript (line 5 substring 'contains'); cross-ref core/audit.py docstring lines 3-9 and core/rules.py is_protected_sender`

### G17 [R2] ACP/billing identity model: any bearer string becomes a funded account with no API-key issuance or verification — acp/router.py complete_session lines 286-290 + tests/test_acp.py line 132

**Why:** complete_session does account = store.get_account_by_api_key(ctx.api_key); if None -> store.create_account(api_key=ctx.api_key). _gate (router.py lines 79-83) accepts ANY non-empty 'Bearer <x>'. So the api_key the credits are fulfilled to is the caller-supplied bearer, never an issued/verified uma_ key. test_acp.py line 132 encodes this as intended: credits land on get_account_by_api_key('testkey') where 'testkey' is an arbitrary literal. Consequences: (a) two unrelated callers who both send 'Bearer x' share one credit balance / can drain each other's runs; (b) there is no binding between the Stripe charge payer and the credited account — the charge succeeds against the delegated token while credits go to whatever bearer string accompanied the request; (c) new_api_key() mints uma_ keys (store.py line 110) but NOTHING in the request path ever issues one to a buyer or checks the bearer against the accounts table before granting. The whole 'access-grant source of truth' claim (store.py docstring) has no authentication front door. <!-- allow-secret false-positive: quoted source-code example -->

**Where:** `acp/router.py lines 72-93 (_gate) and 286-290 (account bootstrap from raw bearer); api/store.py new_api_key line 110 (issued but never wired in); tests/test_acp.py line 132 (asserts arbitrary-bearer fulfillment as correct)`

### G18 [R2] Paid metering / plan caps are never enforced — entitlements_for and consume_credit are dead code on every triage path

**Why:** api/plans.py defines entitlements_for (lines 175-193) with monthly_run_cap per plan, METERED_ADDON ($0.01/run), and CREDIT_PACKS; store.py defines consume_credit (lines 235-246, 'atomically debit ... iff balance covers it'). Grep confirms NEITHER entitlements_for NOR consume_credit is called from api/app.py, api/service.py, acp/router.py, or mcp_server/server.py. So: (1) every /v1/triage, /v1/triage/preview, and MCP triage runs with no credit debit and no monthly_run_cap check — the Free '~50 runs/month' cap and the Business 'unlimited' tiering are marketing-only; a free user runs unlimited live triage. (2) ACP credit packs credit run_credits (router.py line 290 fulfill_once) that are then never consumed by anything — buyers pay for credits that are never spent. (3) the metered Stripe meter event 'triage_run' (plans.py line 136) is never emitted. The commercial model described across plans.py/billing.py/web copy is structurally unwired from the engine.

**Where:** `api/plans.py entitlements_for lines 175-193 (uncalled); api/store.py consume_credit lines 235-246 (uncalled); the missing enforcement hook in api/app.py _run lines 97-130, api/service.py run_triage, mcp_server/server.py _triage lines 129-146, acp/router.py (no consume on run); plans.py METERED_ADDON line 136 meter event never emitted`

### G19 [R2] core/audit.py independence claim is partly self-undermined: redacted receipts lose the violation evidence and a non-list message_id breaks the trail

**Why:** The module's entire selling point (docstring lines 11-38) is an INDEPENDENT observer. Two cracks: (1) record() at line 184 appends message_id to self.violations and the summary (line 250) returns the raw list — but receipts.signed_body / api receipts only carry audit.summary() counts, and core/audit's own redact=True path (lines 209-210) only strips the per-line 'sender' field, NOT the violations list which still contains raw provider message_ids — so a 'shareable/committable' redacted receipt can still leak internal message identifiers in the violations array (the very thing app.py lines 117-122 takes care to keep server-side). (2) _independently_protected (lines 95-114) and _domain_of (lines 78-92) swallow ALL exceptions and return False/'' — so if core.rules fails to import or normalize_sender throws (e.g. the calculate_email_age naive-datetime class of bug already flagged elsewhere in rules.py), the 'independent' re-derivation silently degrades to trusting ONLY the gate's own protected flag, collapsing the two-source check into one source exactly when something is already broken. The docstring promises independence 'even [if] a gate stops recognizing a protected sender' — that promise evaporates on any rules-layer import/parse error, with no signal to the caller.

**Where:** `core/audit.py: violations list not redacted (lines 184, 209-210, 250 summary -> receipts/web); _independently_protected silent fail-open lines 110-114; _domain_of bare-except lines 88-92; cross-ref api/app.py lines 117-122 (which assumes message ids never leak)`

### G20 [R2] MCP triage tools enforce no entitlement and have a destructive default-override footgun; server.py only clamps the limit

**Why:** mcp_server/server.py exposes triage (destructiveHint, lines 109-126) and triage_preview to any connected agent. _clamp_limit (line 83-84) is the ONLY input restraint; provider/query/remove_label/tier_routing/vip_only flow straight into service.run_triage. There is no account binding, no credit check, no rate limit on the MCP surface at all (it inherits the unwired-metering gap above). Worse, the prompt-injection mitigation the docstring brags about (lines 11-13: triage defaults dry_run=True so 'a careless or prompt-injected agent previews by default') is undercut because a single injected dry_run=False argument flips it to mutate with no second factor — the 'must explicitly ask to mutate' is one boolean an injected prompt can set, not a confirmation step or capability gate. check_protected_sender (line 94) truncates sender/subject to 4096 but triage_preview/triage do not bound query length before it reaches the provider's search API.

**Where:** `mcp_server/server.py: triage dry_run default-override lines 109-126 (single-arg flip), _clamp_limit as sole guard line 83-84, no credit/entitlement check in _triage lines 129-146, query length unbounded vs 4096 cap at line 94`

### G21 [R2] Stripe billing webhook: status from Stripe is written verbatim with no allow-list, and invoice.paid force-activates regardless of plan/period

**Why:** billing.py _handle_event line 248 sets status = obj.get('status') for subscription events and writes it straight to the accounts table (set_subscription) with no validation against a known status vocabulary — a future/unknown Stripe status (e.g. 'paused', 'incomplete') is stored as-is, and entitlements_for (plans.py line 185) only treats 'active'/'trialing' as active, so an 'active'-adjacent status Stripe introduces silently downgrades a paying customer to the Free floor with no log. invoice.paid handler (lines 265-270) sets status='active' for any account matched by customer_id WITHOUT checking the subscription is the current/paid one or refreshing current_period_end — a paid invoice for a since-canceled or different subscription re-activates the account. Neither path is covered by a test asserting the status allow-list (test_billing not yet inspected here but the handler logic itself lacks the guard).

**Where:** `api/billing.py _handle_event line 248 (unbounded status write), invoice.paid lines 265-270 (force-active without period/sub validation); cross-ref api/plans.py entitlements_for line 185 active-set and api/store.py set_subscription lines 191-221`

### G22 [R2] acp/router.py update_session lets a buyer mutate line items / price after the session, and grand_total trusts stored line_items with no re-validation at charge time

**Why:** update_session (lines 200-232) re-derives line_items from body.items against CREDIT_PACKS, which is fine, but complete_session (line 257) computes amount = models.grand_total(current['line_items']) from the STORED session response and charges that, while total_runs credited comes from row['data']['total_runs'] (line 246). These two are persisted separately (router _persist line 149 stores both) and updated in lock-step only in create/update — but get_session reads data_json (store.py line 421) and the response line_items live inside data['response'] while total_runs lives in data['total_runs']; there is no invariant check at /complete that grand_total(line_items) still corresponds to total_runs * pack price. A crafted update that desyncs them (or any future code path that writes one without the other) charges one amount and credits a different run count with no reconciliation. Also models.build_line_items line 85 does int(it.get('quantity',1)) AFTER pydantic already bounded quantity 1..1000 on Item, but the update path dumps Item models so the bound holds — however id length 128 (models line 26) and 1000-qty cap mean a single session can legitimately request 1000 * pack_1000 = 1,000,000 runs / $9,000 charge with no high-value confirmation.

**Where:** `acp/router.py complete_session lines 246/257 (amount vs total_runs read from separate stored fields, no reconciliation), update_session lines 216-225; acp/models.py build_line_items line 85 + Item quantity le=1000 line 27 (1M-run / $9k single session)`

---

## 🔴 Critical (6)

#### U001 · 🔴 CRITICAL · conf: high · `auth` · rounds: R1

**Triage endpoints have NO authentication and never enforce plan entitlements or consume credits**

`api/app.py:_run / triage / triage_preview (lines 85-130)`

POST /v1/triage and POST /v1/triage/preview accept a TriageRequest and run a real mailbox triage (with dry_run=false performing live archive/move operations against a configured provider) without any Authorization header, API key check, account lookup, or rate limit. The store exposes get_account_by_api_key(), consume_credit(), and plans.entitlements_for()/monthly_run_cap, but NONE of them are referenced anywhere in app.py or service.py (verified by grep: consume_credit and entitlements_for are only defined, never called). For a live payment service this means: (1) any anonymous caller can drive provider quota / cost; (2) paid metering (run_credits, monthly_run_cap) is completely unenforced — paying customers and non-customers are treated identically and credits are never debited, so the money path collects revenue for a metered product that is given away for free. This is the central data-integrity/billing gap.

#### U002 · 🔴 CRITICAL · conf: high · `money-path` · rounds: R1

**Triage endpoints enforce NO entitlement / quota / credit debit — paid credits are never consumed**

`api/app.py:_run (97-130), triage (91-94), triage_preview (85-88)`

The /v1/triage and /v1/triage/preview endpoints (and the MCP triage tool in mcp_server/server.py:_triage) call service.run_triage and persist a receipt, but never read the caller's account, never call plans.entitlements_for, never check plans.monthly_run_cap, and never call store.consume_credit. Grep confirms consume_credit / entitlements_for / monthly_run_cap have ZERO runtime callers (only tests, plans.py definitions, and the artifact generator). The entire ACP flow sells one-time credit packs (acp/router.py credits store.fulfill_once -> run_credits), and plans.py advertises Free=50, Pro=5000, Business=unlimited monthly run caps, yet NOTHING ever debits run_credits or checks the cap when a triage actually runs. Net effect on the money path: revenue is collected for credit packs and subscriptions, but the metered service is dispensed for free and unbounded to everyone (including unauthenticated callers). A buyer's purchased credits are recognized as revenue and never decremented; a Free user can run unlimited live triage. This is the single biggest money-path break: confirm/credit happens (0->1) but the credited balance is never spent and the cap is never enforced.

#### U003 · 🔴 CRITICAL · conf: high · `auth` · rounds: R1

**POST /v1/triage has no authentication or authorization**

`api/app.py:triage (91-94), _run (97-130)`

The live, mailbox-mutating /v1/triage endpoint accepts a request with no Authorization header, no API key, and no account binding. Any unauthenticated client can drive a real triage (dry_run defaults True but the caller controls req.dry_run, so dry_run=False mutates the configured mailbox). There is no Depends(auth), no HTTPBearer, and no middleware on app (grep of api/app.py for middleware/Depends/Authorization returns nothing). Combined with the missing entitlement check, this means the paid product surface is wide open: the server's own mailbox credentials can be exercised by any anonymous caller, and there is no per-account attribution for the run. This is both an authz gap and the mechanism by which the credit/quota system is bypassed.

#### U004 · 🔴 CRITICAL · conf: high · `money-path` · rounds: R1

**Triage execution path NEVER enforces monthly_run_cap, run_credits, or plan entitlements — paid limits and purchased credits are sold but unenforced**

`api/service.py / api/app.py:run_triage() (service.py 70-135) and _run() (app.py 97-130)`

plans.entitlements_for, store.consume_credit, and monthly_run_cap have ZERO references in the live triage path (api/app.py, api/service.py, mcp_server). The POST /v1/triage and /v1/triage/preview handlers accept no account_id / api_key, do not look up an account, do not debit credits, and do not check the monthly run cap. Therefore: (1) ACP credit-pack purchases (real money via fulfill_once -> run_credits) are never consumed — a buyer pays for runs that are never decremented and an attacker gets unlimited free triage; (2) the Free 50-run/month cap and Pro 5000 cap advertised in plans.py are not applied; (3) the entire metered/credit/cap monetization model is non-functional. This is the central money-path defect: revenue features have no enforcement seam wired into the consuming loop.

#### U005 · 🔴 CRITICAL · conf: high · `correctness` · rounds: R2

**Protected-sender gate completely bypassed: every inbox message >90 days is archived with zero sender check**

`archive_old_inbox.applescript:lines 15-21`

The loop moves EVERY inbox message whose `date received < cutoffDate` to Archive (line 18) based solely on age. There is no call to is_protected_sender, no PROTECTED_SENDERS check, no audit, no dry-run. This directly violates the product's HEADLINE guarantee documented in core/audit.py docstring lines 3-5/27-30: 'a protected sender (lawyer, bank, government, your own account) is NEVER archived or moved out of the inbox.' A 91-day-old email from an attorney, a bank, irs.gov, or the user's own account is silently archived out of the inbox — the EXACT scenario the Python gate (core/rules.is_protected_sender, _gov_protected, _is_protected_domain) and the AuditInvariantError tripwire exist to make impossible. Because this script is shipped and documented in CLAUDE.md line 181 as a supported tool, the guarantee is false for any user who runs it. Round 1 reported only the bare-try swallow, mutate-while-iterate, and mailbox-resolve throw for this file; the gate bypass / data-loss class is unreported.

#### U006 · 🔴 CRITICAL · conf: high · `correctness` · rounds: R1

**COPY+DELETE fallback expunges the ENTIRE mailbox per message, deleting any other \Deleted-flagged messages**

`icloud_triage.py:archive_uid, lines 63-77`

When UID MOVE is unsupported, the fallback does UID COPY, then `imap.uid('STORE', uid, '+FLAGS', '(\\Deleted)')` and then `imap.expunge()` (line 76). `imap.expunge()` (not `UID EXPUNGE`) permanently removes ALL messages flagged \Deleted in the selected mailbox, not just this UID. If the user (or another client) has other messages already marked \Deleted in INBOX, they are silently and permanently destroyed during the per-message loop. Also it expunges once per archived message — O(n) full expunges, slow and risky. Should use UID EXPUNGE (RFC 4315) scoped to the uid, or batch the expunge once at the end.

---

## 🟠 High (128)

#### U007 · 🟠 HIGH · conf: high · `test-quality` · rounds: R1

**CI never exercises the Python 3.9 (or 3.10) floor the codebase is architected around**

`.github/workflows/ci.yml:line 15 (matrix python-version: ["3.11", "3.12"])`

The whole lazy-MCP-import dance in api/app.py:34-45 (try/except around `from mcp_server.server import ...`), the ISOLATED requirements-mcp.txt (`mcp>=1.2,<2`, commented '>=3.10'), the Dockerfile:7 comment ('core stays 3.9-importable'), and CLAUDE.md:278 ('Python 3.9+') all exist specifically to keep the core engine importable on Python 3.9. Yet the CI matrix only runs 3.11 and 3.12. The 3.9 and 3.10 import paths are NEVER executed in CI, so any 3.10+/3.11+ syntax, typing, or stdlib slip would ship undetected. Concrete latent example: core/rules.py:1163 uses `Optional["datetime"]` with no `from __future__ import annotations` (see separate finding). The advertised 3.9 support is unverified marketing. Failure mode: a 3.9 user pip-installs, the core fails to import, and nobody on the team can reproduce because CI is green on 3.11/3.12. Add 3.9 (and 3.10) to the matrix, or drop the 3.9 claim everywhere and gate the floor honestly.

#### U008 · 🟠 HIGH · conf: high · `privacy` · rounds: R3

**.gitignore does not cover *_state.json or mail_export.tsv, so runtime mailbox state will be committed on the next run**

`.gitignore:.gitignore:1-50 (no *_state.json / *.tsv rule)`

git check-ignore confirms labeler_state.json, gmail_state.json, outlook_state.json, imap_state.json, mailapp_state.json and mail_export.tsv are NONE of them ignored. core/config.py defaults each provider's state_file to '<provider>_state.json' (lines 39/48/60/70) and gmail_labeler.py:40 sets STATE_FILE='labeler_state.json'; core/state.py writes them in the CWD (the repo root). export_mail_snapshot.applescript writes mail_export.tsv. So a user who runs the tool from the repo root will produce real per-category counts (and, via mail_export.tsv, sender/subject/date rows) sitting untracked in the working tree, trivially picked up by 'git add .'. The .gitignore already (correctly) handles credentials, config/protected_senders.local.txt, audit/*.jsonl, data/ and *.log with PII comments, but the state-file class was missed. Add patterns like '*_state.json' and 'mail_export.tsv'.

#### U009 · 🟠 HIGH · conf: high · `secrets` · rounds: R1

**Docker build copies entire repo (no .dockerignore) — bakes data/app.db (API keys, Stripe customer ids) and local secrets into the image**

`Dockerfile:lines 11-14 (COPY . .), and missing .dockerignore`

The Dockerfile does `COPY . .` and there is no .dockerignore in the repo (confirmed: `ls .dockerignore` -> not found). The .gitignore excludes data/, *.db, *.log, config/protected_senders.local.txt, .outlook token cache etc. from git, but git-ignore has NO effect on the Docker build context. If an image is built from a working tree that has been run locally, data/app.db (which store.py documents as holding 'customer ids and api keys'), the SQLite WAL/SHM files, the Outlook token cache if placed in-tree, *.log files containing real sender PII, and config/protected_senders.local.txt (real lawyer/bank/gov PII per .gitignore comment) would all be copied into the published image layers and shipped to any registry. A .dockerignore mirroring .gitignore (at minimum data/, *.db*, *.log, .venv/, config/*.local.txt, *token_cache*.json) is required.

#### U010 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**Fulfillment credits the account resolved from the request's bearer api_key, not the buyer who paid / the session's original account — credits can be granted to the wrong account**

`acp/router.py:complete_session() lines 286-290`

account = store.get_account_by_api_key(ctx.api_key) (or a new account for that key) at lines 287-289, then fulfill_once(session_id, account['id'], total_runs). The account that receives credits is whichever bearer token calls /complete, NOT the account that created the session. Since create_session does not bind the session to an api_key (account_id is None in _persist at line 188), any holder of ANY valid-looking bearer token who knows a session id can call /complete and have the credits land on THEIR account. Combined with the fact that the gate (acp/router.py _gate) never validates the bearer token against the store (it accepts any non-empty Bearer string and create_account-on-the-fly), this lets an arbitrary caller claim the credits for a session, and lets unknown tokens auto-provision accounts. Charge still happens against the delegated token in the body, so the payer pays but a different account is credited.

#### U011 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**Bearer token is accepted without ANY validation against the account store — auth is effectively unauthenticated**

`acp/router.py:_gate() lines 79-93`

_gate only checks that Authorization starts with 'Bearer ' and the remainder is non-empty. It never calls get_account_by_api_key to verify the token corresponds to a real account, and complete_session auto-creates an account for any unknown key (line 289). So the ACP surface has no real authentication: any string after 'Bearer ' passes. This permits unauthenticated session creation, completion (charging a delegated token the caller supplies in the body), and credit assignment to arbitrary attacker-chosen tokens. For a money endpoint that mints account credits, accepting unvalidated bearer tokens is a security/authorization weakness.

#### U012 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**Idempotency key is not namespaced by api_key (Authorization), enabling cross-account replay / confused-deputy disclosure**

`acp/router.py:_gate / _begin_idempotency (lines 72-117) and api/store.py idempotency_begin (313-353)`

The idempotency dedup key is purely the caller-supplied `Idempotency-Key` header plus the request-body hash, scoped only by a static string like 'acp.complete' (router.py:170,205,240,346 -> store.idempotency_begin keyed on `key`). The bearer credential (ctx.api_key) is NOT part of the idempotency scope or stored alongside it. Consequence: if two different agents/accounts send the same Idempotency-Key value with the same body bytes, the SECOND caller receives the FIRST caller's stored response verbatim (store.py:350-353 returns existing response_json). That stored response can contain the first buyer's email (buyer dict), order id, and the `permalink_url` to their signed receipt (router.py:318-322), i.e. cross-account information disclosure. Because idempotency keys are client-chosen and often low-entropy (UUIDs are fine, but counters/timestamps are common), a malicious or buggy client can deliberately or accidentally collide. Fix: include the api_key (or a hash of it) in the idempotency scope/key so a key is only ever replayable to its original caller.

#### U013 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**Credits are fulfilled to whoever calls /complete, not to the account that owns/created the session; bearer token is never validated**

`acp/router.py:complete_session, lines 282-290`

Sessions are created with no bound account (create_session/_persist pass account_id=None, router.py:188). At completion the credit target is derived from the bearer presented on the /complete call: `account = store.get_account_by_api_key(ctx.api_key)` and if none exists it is auto-created with that arbitrary bearer string (router.py:287-289, create_account(api_key=ctx.api_key)). The bearer token is never authenticated against any registry (the gate at router.py:79-83 only checks the 'Bearer ' prefix and non-emptiness). So (a) a session created by token A can be completed by token B, crediting B; and (b) any attacker-chosen bearer string becomes a credited account. There is no proof that the caller of /complete is the same party that created the session or delegated the payment token. If the SPT charge succeeds, the runs are minted to the caller's self-asserted identity. This is a money/entitlement integrity hole unless an upstream proxy authenticates the bearer (no such check exists in this code). <!-- allow-secret false-positive: quoted source-code example -->

#### U014 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**No ownership check on reading ACP sessions or audit receipts — any valid bearer token reads any session/receipt**

`acp/router.py:get_session (193-197); api/receipts.py get_receipt (114-142)`

GET /acp/checkout_sessions/{id} (router.py:193-197) passes _gate (which only checks that SOME non-empty Bearer token is present — it never validates the token against a store or against the session's owner) then returns the full stored session response for ANY session_id. The session body includes buyer name/email/phone (models.Buyer) and, after completion, the order with payment_id. Likewise GET /v1/audit/{run_id} (receipts.py:114-142) has no auth at all and returns any receipt by id, including ACP order receipts whose summary contains payment_id, amount, checkout_session_id, and runs_credited. Session ids (acp_cs_+16 hex) and order ids (order_+12 hex) are unguessable, so this is mitigated by obscurity, but there is no authorization binding the reader to the account that owns the resource. Any party with a Bearer token (the gate accepts arbitrary strings) plus an id can enumerate buyer PII and payment metadata. This is an IDOR/broken-object-level-authorization gap on the commerce surface.

#### U015 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**ACP fulfillment credits a free auto-created account but those credits gate nothing downstream**

`acp/router.py:complete_session (235-339), specifically 287-290`

On a successful charge, complete_session resolves the buyer by api_key, auto-creating a plan='free' account if none exists (289), then fulfill_once credits total_runs to that account (290). The buyer is charged real money (payment.get_payment_client().charge at 262) and the runs are credited, but because no triage/MCP path ever calls consume_credit or checks run_credits, the buyer receives a balance that can never be spent through the product's own tools. The signed order receipt minted at 296-317 documents 'N triage-run credits purchased' for a capability the system does not actually meter. This is the money-in side wired with the money-is-honored side missing — a charge for an unenforced entitlement.

#### U016 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**ACP bearer token is never validated against the account store; any attacker-chosen bearer auto-provisions an account and is credited on a successful charge**

`acp/router.py:_gate (lines 72-93), complete_session (lines 287-289)`

_gate parses 'Authorization: Bearer <x>' and returns GateContext(api_key=x) for ANY non-empty string, with no lookup against the accounts table. There is no check that the bearer corresponds to a real, pre-issued uma_ key (the only legitimate issuance path, api/store.new_api_key / create_account). complete_session then calls store.get_account_by_api_key(ctx.api_key), and on miss does store.create_account(api_key=ctx.api_key, plan='free'). Failure mode: an unauthenticated caller presents a self-chosen bearer (e.g. 'Bearer hunter2'), drives a checkout to ready_for_payment, and on a successful Shared-Payment-Token charge gets run_credits attributed to an account keyed by a token they invented. The bearer is effectively an opaque self-asserted identity rather than a server-issued credential. Correct behavior: an unknown bearer should be rejected (401) at the gate (or at minimum at /complete) instead of silently provisioning an account. The auth model for the agent-commerce surface is effectively absent. NOTE on blast radius: I confirmed consume_credit() (store.py:235) is never called by any endpoint (grep shows zero callers outside tests), and /v1/triage (api/app.py:91-130) performs no auth and no credit debit, so the minted credits currently purchase nothing — which caps the *immediate* exploit value. But (a) the buyer is charged real money via the SPT, so an attacker who controls a delegated token can mint accounts/credits at will, and (b) the moment credits are wired to gate triage runs, this becomes free service. The design is a latent auth bypass. <!-- allow-secret false-positive: quoted source-code example -->

#### U017 · 🟠 HIGH · conf: high · `auth` · rounds: R1

**No ownership check on retrieve/update/cancel — any valid-format bearer can read, mutate, or cancel ANY checkout session by id (IDOR)**

`acp/router.py:get_session (lines 193-197) via _load (158-162); update_session (200-214); cancel_session (342-357)`

_load(session_id) fetches the session purely by id and never compares the stored acp_sessions.account_id (or the bearer) against ctx.api_key. get_session returns the full session response (including buyer name/email/phone captured at creation, line items, and any order/permalink) to any caller presenting any non-empty bearer with the correct API-Version. update_session and cancel_session likewise mutate state for any caller. Combined with the prior finding (any bearer is accepted), this is an unauthenticated IDOR: an attacker who guesses or learns a session id (acp_cs_ + 32 hex chars — unguessable, but ids leak via logs, the order permalink, agent error messages, etc.) can read another buyer's PII, flip their session to canceled (denial of purchase), or alter the buyer field. There is no per-account scoping anywhere in the ACP surface.

#### U018 · 🟠 HIGH · conf: high · `state-machine / money-correctness` · rounds: R2

**Credit applied before receipt minted: receipt failure loses the order permanently while returning 200 COMPLETED**

`acp/router.py:286-339 (esp. 290 then 312-317)`

complete_session ordering is: charge (262) -> fulfill_once credits the account atomically (290) -> THEN sign + save_receipt mint the order receipt (312-317). If sign() or save_receipt() raises after fulfill_once returned True, the credit is already applied but the request 500s and _complete_idempotency never runs. On a fresh-Idempotency-Key retry the charge is deduped by Stripe and fulfill_once returns False (already fulfilled), so control falls into the `elif order is None` branch (323-330): the response is HTTP 200 status=completed with NO order object, no permalink_url, and only an 'already_fulfilled' info message. The buyer paid, got credits, but the signed order receipt — the product's headline trust artifact and the only retrievable /v1/audit/{order_id} link — is lost forever, and the API reports success. Round 1 flagged 'fulfillment/persist throws' for the final _persist; this is the distinct credit-applied-then-receipt-mint gap and its 2xx-with-no-order replay outcome.

#### U019 · 🟠 HIGH · conf: high · `authorization / multi-tenancy` · rounds: R2

**Two distinct ACP callers presenting the same Bearer string share one credit balance and can drain each other**

`acp/router.py:complete_session lines 286-290; api/store.py new_api_key line 110; store.py get_account_by_api_key 170-175`

complete_session resolves the funded account purely by store.get_account_by_api_key(ctx.api_key) where ctx.api_key is the raw, attacker-chosen bearer (_gate accepts any non-empty 'Bearer <x>'). Because the accounts table is keyed on api_key with a UNIQUE column, two unrelated callers who both send 'Bearer x' resolve to and credit the SAME single account row. Caller A's purchased runs land in the same pooled balance caller B can read/consume — a confused-deputy / fund-pooling defect distinct from the round-1 'credits to wrong account' findings, which described single-account misattribution, not multi-caller balance sharing. There is no per-tenant namespacing of the api_key, and no issuance step that would give each buyer a unique key. Severity is high because it directly enables one customer to drain another's paid credits by guessing/reusing a common bearer literal.

#### U020 · 🟠 HIGH · conf: high · `correctness / billing` · rounds: R2

**ACP-purchased run credits are unredeemable: no path reads, consumes, or authenticates against run_credits**

`acp/router.py:complete_session lines 286-290; api/app.py _run 97-130; mcp_server/server.py _triage 129-146; absence of any consume_credit caller`

fulfill_once / add_credits increment accounts.run_credits, but no code path ever reads or debits it: the triage execution path (_run -> service.run_triage) takes no caller identity and never calls store.consume_credit or plans.entitlements_for, the MCP triage tools take no auth, and there is no GET endpoint exposing a balance. A grep confirms zero callers of consume_credit and zero account-read routes. So an agent that successfully pays via /complete receives credits it can never spend through any product surface, AND triage runs are free for everyone regardless. Round 1 noted 'consume_credit never called' generically; the NEW angle here is the closed loop specific to ACP: the purchase succeeds, money is captured, credits are written, and there is no redemption mechanism wired to the bearer that bought them — the buyer gets nothing usable.

#### U021 · 🟠 HIGH · conf: high · `correctness/logic` · rounds: R2

**ACP fulfillment credits run_credits and binds the account, but the credited balance gates nothing — purchased reach is non-spendable on the only execution surfaces**

`acp/router.py:complete_session fulfillment lines 282-290 + 337 (no cap/plan consequence of credits)`

complete_session resolves/creates an account (line 287-289) and persists account_id on the session (line 337) and credits total_runs via fulfill_once (line 290). This is the buy side of REACH monetization. But the credited balance is spent by no execution surface: neither api/service.run_triage, api/app._run, nor mcp_server _triage debit it, and entitlements_for (the only reader) is uncalled. So an agent completing an ACP purchase receives a durable, account-bound credit balance that is permanently unspendable — money in, value never delivered or consumed. Round 1 flagged complete_session credits a free/orphan account; the NEW angle here is that even a CORRECTLY-attributed, non-orphan account's purchased credits are inert because the consumption wiring on every triage path is absent, making the credit-pack product non-functional end-to-end (buyer pays, balance only ever grows).

#### U022 · 🟠 HIGH · conf: high · `correctness/money-arithmetic` · rounds: R2

**No invariant reconciling charged amount (grand_total of stored line_items) against credited total_runs at /complete**

`acp/router.py:complete_session lines 246 + 257 (cross-ref _persist line 149-155, store.fulfill_once line 290)`

complete_session reads two independently-persisted fields from the stored session: amount = models.grand_total(current['line_items']) (line 257, the money charged) and total_runs = row['data']['total_runs'] (line 246, the runs credited via fulfill_once line 290). These are written separately by _persist (data={'response': resp, 'total_runs': total_runs}, line 154) and are only kept in lock-step by create_session/update_session. There is NO check at /complete that grand_total(line_items) still corresponds to total_runs * pack price (e.g. total_runs == sum over packs of runs implied by the charged line_items). Any code path or crafted state that writes one without the other (a future endpoint, a partial migration, a manual DB edit, or the divergence already latent in update's else-branch at lines 223-224 where line_items and total_runs are read from two different stored locations) charges one amount and credits a different run count with zero reconciliation. Because grand_total is computed from the stored response dict rather than re-derived from CREDIT_PACKS at charge time, the charge fully trusts whatever line_items the persisted session holds.

#### U023 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**/v1/triage and /v1/triage/preview have NO authentication and NO metering — entire paid model unenforced**

`api/app.py:_run (97-130); endpoints triage_preview (85-88), triage (91-94)`

The triage endpoints accept a bare TriageRequest (api/schemas.py:39-52, which has no api_key/account field) and call service.run_triage directly. There is no Authorization/Bearer parsing, no API-key lookup, no account resolution, and no credit/cap check anywhere on this path. Confirmed by grep: api/app.py / api/service.py / mcp_server/server.py never import api.store at all (grep 'store' in those three files => exit 1, zero matches). Consequence: any anonymous caller can run unlimited LIVE triage (dry_run=False) for free against whatever mailbox credentials the server holds. The plan tiers (Free 50/mo, Pro 5000/mo, Business unlimited) in api/plans.py and the run_credits ACP packs are pure marketing — they gate nothing at runtime. This is a whole-subsystem money-path logic gap: the product sells run volume + credits but never debits or caps them.

#### U024 · 🟠 HIGH · conf: high · `concurrency` · rounds: R1

**Webhook marks event processed in a separate, non-atomic step after the handler — crash or concurrent redelivery can double-grant or drop the event**

`api/billing.py:webhook() lines 194-203`

The flow is: is_event_processed(event_id) check -> _handle_event(...) -> mark_event_processed(event_id). These are three separate statements with no surrounding transaction and no claim before processing. Two problems: (1) Race/at-least-once redelivery: Stripe can deliver the same event concurrently or in rapid succession. Both requests can pass is_event_processed() (returns False) before either calls mark_event_processed(), so _handle_event runs twice. For invoice.paid/subscription this is mostly idempotent, but combined with _resolve_account creating accounts and set_subscription it can produce duplicate side effects. The dedup primitive mark_event_processed() uses INSERT OR IGNORE+rowcount and is designed to be the atomic claim, but it is called AFTER the handler instead of being used as the gate. (2) If _handle_event succeeds but the process crashes before mark_event_processed, the event is never recorded, so a redelivery reprocesses it. Correct pattern: claim atomically via mark_event_processed BEFORE running the handler (treat rowcount==0 as duplicate), or wrap check+handle+mark in one DB transaction.

#### U025 · 🟠 HIGH · conf: high · `concurrency` · rounds: R1

**Webhook idempotency is check-then-act (TOCTOU) — concurrent redeliveries can double-process / double-grant**

`api/billing.py:webhook() lines 191-203`

Idempotency is enforced by reading is_event_processed(event_id) at line 191, handling at 196, then writing mark_event_processed(event_id) at 203. The atomic INSERT-OR-IGNORE return value of mark_event_processed (which Store.mark_event_processed is specifically designed to return: True only for the first writer) is DISCARDED. Two concurrent deliveries of the same Stripe event id (Stripe redelivers aggressively, and HTTP/2 multiplexing or a slow handler makes overlap realistic) both pass the is_event_processed read (neither row exists yet), both run _handle_event, and both call set_subscription / _resolve_account. For checkout.session.completed this can create two accounts (via _resolve_account -> create_account) and grant twice. The correct pattern is to gate on the atomic claim: `if not store.mark_event_processed(event_id, event_type): return {duplicate}` BEFORE handling, or wrap claim+handle in one transaction. The module docstring claims 'a redelivery cannot double-grant' but the implementation does not actually guarantee that under concurrency.

#### U026 · 🟠 HIGH · conf: high · `concurrency` · rounds: R1

**Webhook idempotency is a non-atomic check-then-act; concurrent redeliveries can double-grant**

`api/billing.py:webhook(), lines 191-203`

The webhook dedups by reading is_event_processed(event_id) at line 191, processing, then calling mark_event_processed(event_id) at line 203 AFTER the handler runs. This is a TOCTOU race: two concurrent Stripe redeliveries of the same event id can both pass the read at 191 (neither row exists yet), both run _handle_event (double set_subscription / double grant), and both insert later. The store provides an ATOMIC primitive for exactly this — mark_event_processed returns True only on the first INSERT OR IGNORE — but its return value is discarded here. Correct pattern: call mark_event_processed FIRST and gate the handler on its boolean. As written the money-path replay protection the module's docstring claims ('a redelivery cannot double-grant') is not actually guaranteed under concurrency. Also: marking only after the handler means a crash between handler-success and mark leaves the event un-deduped (the test test_webhook_handler_failure_not_marked relies on this for retry, but it also means a redelivery that arrives during handling is unprotected).

#### U027 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**Stripe subscription state is recorded but never enforced — plan/status writes have no runtime effect on triage**

`api/billing.py:_handle_event (222-277); webhook (170-204)`

The webhook correctly verifies signatures, dedupes on event id, and persists plan/status/current_period_end via set_subscription (231, 255, 269, 276). But the only consumer of that stored plan/status is entitlements_for (dead code) — confirmed no other reader. So a customer who pays for Pro and a customer whose subscription is canceled/past_due get identical runtime behavior on /v1/triage (unlimited, free), because the triage path never loads the account or its plan. The billing system is a recording subsystem with no authorization consumer attached; the 'subscription status is the single source of truth' claim in the module docstring (api/billing.py:21-23) is not realized for the product's core action.

#### U028 · 🟠 HIGH · conf: high · `correctness` · rounds: R1

**Unknown-customer subscription event silently mints a brand-new orphan account with a live API key**

`api/billing.py:_resolve_account, lines 208-219 (esp. 218); reached from _handle_event lines 247, 255`

For customer.subscription.created/updated, _resolve_account falls through to create_account(account_id=meta_account, plan='free') whenever neither the metadata account_id maps to an existing account nor the Stripe customer is known. A customer.subscription.updated for a customer this host has never seen (e.g. created out-of-band, in a different environment sharing the webhook secret, or via test/live key crossover) therefore does NOT error or no-op: it creates a fresh account row. create_account (store.py:155-156) auto-generates a real, usable api_key (new_api_key, uma_ prefix) for that account. The result is an orphan account holding a valid credential that no buyer ever registered, then set_subscription writes the customer/sub/plan/status onto it. The webhook is documented as 'fail-closed', but this path fails OPEN by fabricating identity state from an unauthenticated-content event. Expected behavior for an unresolvable account is to acknowledge-and-ignore (200) or 4xx, not to create one.

#### U029 · 🟠 HIGH · conf: high · `dead-code` · rounds: R1

**entitlements_for() is dead code — defined but never called by any request path**

`api/plans.py:entitlements_for (175-193)`

Repo-wide grep for 'entitlements_for' returns exactly one hit: its own definition at api/plans.py:175. No endpoint, service, MCP tool, ACP handler, or test invokes it. It computes the effective plan, monthly_run_cap, providers, retained_receipt_days, and run_credits for an account and even documents 'the effective limits ... that caps a triage run', but nothing consumes the result. The entire entitlement-resolution layer (including the past_due/canceled -> Free-floor downgrade logic) therefore has zero effect on behavior. Either wire it into the triage path or it is unreachable governance code that gives a false impression the cap is enforced.

#### U030 · 🟠 HIGH · conf: high · `security` · rounds: R1

**GET /v1/audit/{run_id} returns stored signature WITHOUT recomputing/verifying it against the stored body**

`api/receipts.py:get_receipt, lines 114-142`

The endpoint reads the row, rebuilds `body` from the stored `summary`/`provider`/`dry_run`/`receipt_line`, and returns `signature: rec['signature']` verbatim alongside `verify`-instructions claiming the response is 'everything a third party needs to verify independently.' It never calls `verify(body, rec['signature'])`. If a DB row is tampered (someone edits `summary_json` to under-report archived/violation counts but leaves the old `signature`), the endpoint serves a body+signature pair that will NOT verify, yet presents them as authoritative with no indication of mismatch. For the product's headline trust artifact, the server itself should detect and flag (or 409/500) a stored receipt whose signature no longer matches its body, rather than silently handing a broken pair to the client and relying on every client to re-run the verification. This also means the server has no integrity check on its own ledger.

#### U031 · 🟠 HIGH · conf: high · `security` · rounds: R1

**Ephemeral signing key regenerated per process; previously-signed receipts become permanently unverifiable after restart/across workers**

`api/receipts.py:_signing_key, lines 44-57`

When RECEIPT_SIGNING_KEY is unset, `_signing_key()` generates a fresh `secrets.token_bytes(32)` per process and only logs a one-time WARNING. The module docstring itself describes a 'horizontally-scaled hosted' deployment. Consequences: (1) Receipt signed by worker A cannot be verified against worker B (each holds a different ephemeral key) even within the same deployment; (2) any receipt persisted before a restart can never be re-verified afterward, because the new process holds a new key — yet `save_receipt` already wrote that now-orphaned signature to durable storage; (3) the GET endpoint (which never recomputes) cannot even surface this — it just returns a signature that will fail verification. A one-time WARNING is the only signal and is easily missed. For a tamper-evidence feature this is a silent correctness/trust failure on the common multi-worker/restart path; the safe behavior would be to fail closed (refuse to sign/persist, or serve receipts unsigned with an explicit 'unsigned' marker) when no durable key is configured, rather than minting signatures that are guaranteed to become unverifiable.

#### U032 · 🟠 HIGH · conf: high · `error-handling / money-correctness` · rounds: R2

**ACP order-receipt save is NOT best-effort (router calls store.save_receipt directly), so a receipts-table write failure 500s AFTER credit is applied**

`api/receipts.py:88-108 (persist best-effort) cross-ref acp/router.py 312-317`

receipts.persist() deliberately swallows ledger-write failures (106-108) so a triage run never errors on a receipt write. But the ACP completion path does NOT use persist() — it calls receipts.sign() then store.save_receipt() directly (router.py 312-317) with no try/except. So unlike the triage path, an ACP receipt-write failure propagates as an unhandled 500. Critically this happens AFTER fulfill_once has already committed the credit (290), so the inconsistent-state window (credit applied, receipt missing, idempotency not completed) is exactly the failure mode persist() was designed to avoid — but the protection is absent on the money path. The two receipt-write call sites have opposite error semantics on the path where it matters most.

#### U033 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**consume_credit is defined and atomic but never invoked, so credit balances are decorative — they are only ever added (add_credits/fulfill_once), never spent**

`api/store.py:consume_credit lines 235-246 (and absence of any caller)`

The store correctly implements an atomic check-and-debit. However grep shows no caller anywhere in api/ or acp/ for consume_credit. Combined with the unauthenticated /v1/triage endpoint, run_credits are purchased via ACP/Stripe and incremented but never decremented by triage runs. The entire metered-credit economy is non-functional: customers buy credits that are never consumed and free callers run triage without credits. This is the storage-layer corroboration of the missing-enforcement finding in app.py.

#### U034 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**consume_credit() is never called by any production code path — credits are sold/added but never debited**

`api/store.py:consume_credit (235-246)`

grep for 'consume_credit' returns only its definition (api/store.py:235) and two assertions in tests/test_store.py:39,42. No endpoint or service debits credits. Meanwhile acp/router.py:290 calls store.fulfill_once which ADDS run_credits on a successful ACP credit-pack purchase, and api/store.py:223 add_credits also grants them. So run_credits monotonically increases and is never spent: an agent can buy 'verified-safe triage runs' via ACP, the balance is credited, but running triage (the thing the credits supposedly pay for) never decrements it. The paid credit pack is charged for nothing enforceable. Net effect: buyers pay, get a balance, and the balance is decorative.

#### U035 · 🟠 HIGH · conf: high · `error-handling/transaction-lifecycle` · rounds: R2

**Exception mid-method leaves a dangling open write transaction on the single shared connection, poisoning all later requests**

`api/store.py:create_account 158-164; set_subscription 217-221; fulfill_once 374-389; idempotency_begin 322-344 (no rollback anywhere in file)`

Every write method opens an implicit transaction (sqlite3 default isolation_level starts a BEGIN on the first DML), then commits at the end. There is no try/except/rollback anywhere in the file. If any execute() raises (IntegrityError on the UNIQUE stripe_customer_id/api_key in create_account or set_subscription, a json.dumps failure, a disk-full/locked error, etc.) the commit() line is never reached, so the implicit BEGIN stays open. Because there is exactly ONE shared sqlite3 connection for the whole process, that open write transaction holds the WAL write lock and keeps an uncommitted snapshot indefinitely. Every subsequent request reuses the same connection, so all later reads see the poisoned in-transaction state and the next writer can deadlock/error. Round 1 noted that multi-statement methods are 'not atomic if a statement raises'; it did NOT identify that on the SHARED connection the failed transaction is never rolled back and corrupts the connection for all future requests (not just the failing one). A bare IntegrityError in create_account (a common path via the webhook _resolve_account) therefore degrades the whole process, not just that call.

#### U036 · 🟠 HIGH · conf: high · `concurrency/api-misuse` · rounds: R2

**Cross-process duplicate idempotency claim raises IntegrityError (unhandled 500) because the in-process RLock cannot serialize a second process**

`api/store.py:idempotency_begin 326-332`

idempotency_begin does check-then-insert: SELECT (no row) then INSERT with key as PRIMARY KEY. The only serialization is the per-process threading.RLock. Under any multi-process deployment (gunicorn/uvicorn --workers>1, or two pods on a shared file), two workers can both observe existing is None and both attempt the INSERT; the second hits a PRIMARY KEY UNIQUE violation. That IntegrityError is not caught, so it surfaces as a 500 to the ACP caller AND (per the dangling-transaction finding) leaves the shared connection in a poisoned open-transaction state. Round 1 flagged the TOCTOU as a logic/replay race ('cross-process it is unsafe') but did not call out that the concrete failure is an unhandled IntegrityError crash rather than a benign double-claim. The docstring at the top of the file claims 'The API is a single process' but nothing enforces single-process, and the comment on check_same_thread=False explicitly anticipates a threadpool.

#### U037 · 🟠 HIGH · conf: high · `correctness/silent-failure` · rounds: R2

**set_subscription silently no-ops on an unknown account_id (rowcount 0) and returns None, so a webhook success path can drop a subscription state change with no error**

`api/store.py:set_subscription 217-221 (UPDATE ... WHERE id = ?)`

set_subscription issues an UPDATE WHERE id = ? and returns None regardless of cur.rowcount. If account_id does not exist (e.g., a race where _resolve_account returned an id that was never actually inserted, or a metadata-supplied account_id that bypassed creation), the UPDATE matches zero rows, commits successfully, and the caller in api/billing.py:231/255/269/276 treats the webhook as fully handled and then calls mark_event_processed, permanently marking the Stripe event as done. The paid subscription state is then lost and will never be retried (Stripe sees 200). Round 1 reported the analogous silent-no-op only for fulfill_once (which at least returns a bool); set_subscription is a distinct method on a money/access-grant path that returns None and gives the caller no signal at all.

#### U038 · 🟠 HIGH · conf: high · `auth / dead code / architecture` · rounds: R2

**new_api_key() mints uma_ keys but no endpoint ever issues one to a buyer — there is no authentication front door**

`api/store.py:new_api_key line 110 (only caller create_account line 156); no request handler`

new_api_key() generates a server-issued, greppable 'uma_'-prefixed key, and the store docstring (lines 8-9) calls accounts the 'access-grant source of truth'. But new_api_key is invoked ONLY as the fallback inside create_account when api_key is omitted (the Stripe-billing path). No HTTP/MCP/ACP route ever returns an issued uma_ key to a buyer, and no route validates an inbound bearer against the accounts table before granting. The ACP path (router.py:289) explicitly stores the caller's raw bearer as the api_key, so an issued key is never required. Net effect: the entire commercial surface has issuance plumbing that is dead, and 'authentication' degrades to 'any non-empty bearer is a fundable identity'. This is the architectural root under the round-1 'bearer never validated' symptoms — the issuance/verification primitive exists but is unwired.

#### U039 · 🟠 HIGH · conf: high · `correctness/logic` · rounds: R2

**Retained receipt-history monetization is unwired — list_receipts() has no endpoint, so the 90-day/1-year 'retained receipt history' sold on Pro/Business cannot be delivered**

`api/store.py:list_receipts (lines 300-310); no caller in api/receipts.py or any router`

The Pro ($19/mo) and Business ($49/mo) plans are sold explicitly on RETENTION: plans.py advertises 'Downloadable signed receipts + 90-day hosted ledger' (line 101), '1-year retained signed-receipt history (compliance export)' (line 120), and retained_receipt_days=90/365 (lines 94, 113); pricing.md lines 3,8,9 repeat this as the core RETENTION revenue lever. But store.list_receipts() (store.py:300, the only query that lists a customer's receipts by account_id) is NEVER called: api/receipts.py exposes only GET /v1/audit/{run_id} (single receipt by id, unauthenticated). There is no GET /v1/receipts or compliance-export route anywhere. So a paying customer has no way to list/export their retained receipts, retained_receipt_days is enforced by nothing (no TTL/pruning either — round 1 noted unbounded growth, but the deeper defect is the FEATURE itself is absent), and the second of the two advertised monetization levers (REACH + RETENTION) is structurally unbuilt. This is a distinct defect class from the run-cap gap round 1 covered.

#### U040 · 🟠 HIGH · conf: high · `correctness` · rounds: R2

**AppleScript movers duplicate destructive inbox-mutation logic outside the audited engine, with no shared gate/audit — divergent-substrate safety regression**

`archive_old_inbox.applescript:lines 1-5`

archive_old_inbox, route_bulk_senders, and flag_important_senders each independently perform inbox mutations (move/flag) using their own ad-hoc sender/age matching, sharing none of the engine's safety substrate: no core.rules.is_protected_sender, no PROTECTED_SENDERS list, no core.audit.AuditLog receipt, no assert_no_violations tripwire, no dry-run. The core/audit.py docstring (lines 11-38) is explicit that the protection guarantee depends on the gate + independent audit re-checking is_protected_sender and observing real outcomes; these AppleScripts execute real destructive operations entirely outside that observer, so a protected sender they archive/move produces NO receipt and triggers NO AuditInvariantError. They are documented in CLAUDE.md (lines 181-184) as first-class shipped tools, so the system advertises a guarantee its own shipped tools silently violate. This is the architectural root cause behind the per-script findings: the safety contract is enforced only in the Python engine and the macOS AppleScript path is an unguarded parallel substrate.

#### U041 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**Pagination is broken: loops re-issue the same query and break after one full page instead of paging through nextPageToken**

`archive_sorted.py:archive_loop, lines 92-130`

The inner `while True` lists with `maxResults=1000` but never reads `nextPageToken`. After archiving, it does `if len(ids) < 1000: break` (line 126). The comment claims 'pagination via fresh query' — but the archive removes the INBOX label, so on the next loop the same `label:X label:INBOX` query naturally returns the remaining unarchived items, which works ONLY because the archive shrinks the result set. However, when `not archivable` and `len(ids) == 1000` (all 1000 on this page were protected senders), it `continue`s (line 113-115) re-running the identical query and getting the identical 1000 protected IDs forever — an infinite loop. With many protected senders sharing an archive category this is a real hang.

#### U042 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**Pagination never uses nextPageToken; relies on items leaving the query, and can infinite-loop on an all-protected full page**

`archive_sorted.py:archive_loop() lines 92-130 (pagination); lines 112-115`

The while loop always lists the FIRST page of `label:X label:INBOX` (no pageToken passed, line 94-96). It depends on archived items leaving the query so the next iteration sees new ones. But when a full page (1000 ids) is returned and EVERY sender is protected, `archivable` is empty, so line 112-115 `if not archivable: if len(ids) < 1000: break; continue` — with len(ids)==1000 it `continue`s and re-lists the IDENTICAL first page forever (nothing was archived, nothing leaves the query). This is an infinite loop / hang that never terminates and never makes progress when >=1000 protected-sender messages carry an archive-class label. Even below that threshold, re-querying page 1 each time wastes quota and the `len(ids) < 1000` break is a fragile proxy for completion.

#### U043 · 🟠 HIGH · conf: high · `concurrency` · rounds: R1

**Unbounded outer while-loop can run forever / loop indefinitely when domains keep mapping to the same Misc/Other**

`auto_drain.py:drain_loop, lines 100-199 (esp. 159-187)`

drain_loop() has an outer `while True:` (line 100) that only breaks when the source label is empty (line 111-113). Each iteration samples up to 500 messages but only fetches headers for the first 100 (line 133 `messages[:100]`). If the sample's top-100 domains all fail to actually move out of Misc/Other (e.g. the `from:domain label:Misc/Other` search returns nothing because Gmail's `from:` tokenization does not match the extracted domain string, or a classify target label is missing so it `continue`s at line 148-150), `moves_performed` stays 0, the `if moves_performed == 0` branch (190-196) just `pass`es, and the outer loop repeats forever against a still-non-empty bucket. The code comment at 191-196 literally acknowledges 'we might loop forever.' This runs against a real mailbox with only a 2s sleep between iterations — a runaway API-quota burner.

#### U044 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**Marketing keyword list contains 'off' and '%' as bare substrings, mis-classifying many domains/subjects into Marketing**

`auto_drain.py:classify_domain, line 46 + 73-76`

KEYWORDS['Marketing'] includes the 2-letter token 'off' and the single char '%'. classify_domain does `if term in combined_text` (line 75) and `if term in domain` (line 81) as plain substring checks. 'off' matches inside 'office', 'offer', 'official', 'kickoff', 'cutoff', 'payoff', etc., and even domains like 'office365' or 'officedepot'. Any subject containing a '%' (extremely common in stats/discount/encoded text) matches too. Because Marketing is checked in dict-iteration order alongside others, this silently routes large volumes of mail (e.g. anything from an 'office'-containing domain) into Marketing. Combined with the destructive bulk move, this causes systematic mis-categorization.

#### U045 · 🟠 HIGH · conf: high · `correctness` · rounds: R1

**Destructive bulk label move has NO dry-run guard and runs immediately on execution**

`auto_drain.py:module + drain_loop (no --apply / no dry-run)`

Unlike icloud_triage.py (which defaults to dry run and requires --apply), auto_drain.py performs real `batchModify` moves (add target label, remove Misc/Other) the moment it is run, with no --dry-run flag, no confirmation, and an aggressive 'fallback to Notification' default (line 88) plus the broken classifier above. It also does NOT enforce the protected-sender gate (the docstring admits this at lines 11-14). For a script that re-labels potentially thousands of messages across the whole mailbox, the absence of any guard is a real blast-radius concern.

#### U046 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**auto_drain has NO protected-sender gate on its category moves and builds Gmail queries from untrusted sender domains**

`auto_drain.py:drain_loop() line 157; bulk move query construction`

auto_drain.py performs bulk batchModify moves (addLabelIds=[target], removeLabelIds=[source]) for ALL mail of a domain (line 171-178) with zero is_protected_sender() check — the file header even admits gate=0. While it claims to only move BETWEEN category labels (not removing INBOX), the classify_domain fallback is 'Notification' for everything (line 88), and a protected sender (your bank, lawyer) sitting in Misc/Other gets relabeled to e.g. 'Notification'/'Marketing'. If a downstream pass (archive_sorted lists Notification + Marketing in ARCHIVE_CATEGORIES) then archives by that label, the protected sender's mail is mis-routed then archived. The sender-based gate is exactly what protects against this and it is absent here. This is a latent never-archive-guarantee bypass when scripts are chained, which run_automation-style daily runs encourage.

#### U047 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**Bulk move inner loop never advances pageToken; infinite loop if a batchModify silently fails to clear the query**

`auto_drain.py:drain_loop() line 157, 161-186 (inner bulk search loop)`

The inner `while True` (line 159) lists `from:{domain} label:Misc/Other` first page (no pageToken, line 161-163), batchModifies, then `if 'nextPageToken' not in search_res: break` (line 185). Because the batchModify removes the Misc/Other label, the same query is expected to return fewer items next loop. But the loop NEVER passes nextPageToken — it always re-fetches page 1. If batchModify raises HttpError it is caught and swallowed with a 5s sleep (line 181-183) WITHOUT breaking, but moves_performed isn't incremented and the same page is re-fetched: if the modify keeps failing (e.g. a permanent 400 on a bad label id) this spins forever hammering the API. The outer `while True` (line 100) also has no termination guard beyond an empty source label, and the 'moves_performed == 0' branch (line 190-196) just `pass`es, so a sample full of unmovable domains loops the outer loop indefinitely too.

#### U048 · 🟠 HIGH · conf: high · `correctness` · rounds: R1

**Substring keyword matching massively over-categorizes (e.g. 'off', 'pay', 'work', 'code' match inside unrelated words)**

`auto_drain.py:classify_domain() lines 66-88; KEYWORDS line 39-49`

classify_domain does `if term in combined_text` over short tokens. KEYWORDS['Marketing'] includes 'off' and '%', 'invite'; 'Finance/Banking' includes 'pay','tax','account'; 'Professional/Jobs' includes 'work','offer'. Verified: 'off' matches 'offering', 'offsite', 'official'; 'pay' matches 'paypal'/'repayment'; 'work' matches 'network'/'framework'. Because KEYWORDS is iterated dict-order and returns on first hit (line 73-76), a 'Finance/Banking' miscategorization fires on any subject containing 'pay'/'account'/'transfer'. Combined with the absent protected gate, this means a domain whose sample subjects merely contain 'off' gets ALL its mail bulk-moved to Marketing. High misroute rate on a destructive bulk operation.

#### U049 · 🟠 HIGH · conf: high · `api-misuse` · rounds: R1

**Pagination never advances pageToken — relies on mutation to terminate, can loop/stall or miss messages**

`bulk_sweeper.py:run_sweep, while loop lines 97-123 (pagination)`

The list() call at lines 98-102 never passes pageToken=, so every iteration requests the FIRST page only. The loop relies on the batchModify removing the source label so the query no longer matches those messages, shrinking the result set each pass. The termination check at line 122 (`if "nextPageToken" not in results: break`) is contradictory with this design: if more than BATCH_SIZE (1000) messages match, nextPageToken WILL be present, so the loop continues — but because pageToken is never sent, it re-fetches and re-modifies the same first page repeatedly until those finally drop out of the query, which is wasteful and fragile. Conversely, if the add label equals a label that doesn't change query-match- status, or if Gmail's eventual-consistency lags, the same page can be reprocessed. Worse: if 'remove' label resolution fails (remove_id is None, line 114) the messages keep matching the query forever and the loop becomes effectively infinite (or only bounded by the missing nextPageToken). Proper pagination (carry results.get('nextPageToken') into the next list call) is absent.

#### U050 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**Pagination never advances pageToken; loop relies on label removal to drain the query and can busy-loop if remove_id is None**

`bulk_sweeper.py:run_sweep() lines 97-123`

The while loop lists page 1 of rule['query'] (no pageToken, line 98-102) and only breaks when no messages OR 'nextPageToken' not in results (line 122). It assumes the batchModify removes the source label so the query shrinks. But if remove_id is None (the 'remove' label doesn't exist — line 114 sends removeLabelIds=[]), the matched messages still match `from:X label:Misc/Other` after the modify (Misc/Other never removed), the result set never shrinks, AND if the page also carries a nextPageToken the break-on-missing-token never trips — infinite loop re-listing the same first page and re-applying addLabelIds forever. Also, re-listing page 1 each iteration (rather than paging) is quota-wasteful even in the working case.

#### U051 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**Dry-run inflates success_count and processed_count by the full action list, masking nothing applied**

`cli.py:run_labeler, lines 282-294`

In dry-run, the else branch (line 288-291) does `result.success_count += len(actions)` and then unconditionally `processed_this_run += len(actions)` / `result.processed_count += len(actions)` / `total_processed += len(actions)`. So a dry run reports success_count == processed_count as if all actions succeeded, even though nothing was applied. The exit code path (cmd_label line 457 returns 0 if error_count==0) will always be success for dry-runs, which is acceptable, but the printed PROCESSING STATISTICS conflate previewed-with-applied. More importantly, in dry-run with a state_file, line 299-300 still calls state.save(page_token, total_processed, ...) advancing the persisted page token and total even though no changes were applied — a subsequent non-dry-run resume would skip those pages. Dry-run should not mutate the state file.

#### U052 · 🟠 HIGH · conf: high · `state-file-corruption` · rounds: R1

**Dry-run persists/advances state file page token, corrupting later real resume**

`cli.py:run_labeler, lines 297-300 (state.save in dry-run)`

When --state-file is provided AND --dry-run is set, the loop still executes `if state: state.save(page_token, total_processed, stats, provider=provider.name)` on every iteration (line 299-300) and on KeyboardInterrupt (319) / Exception (323). A dry run is supposed to be side-effect-free, but it overwrites the on-disk resume token and total_processed. A user who dry-runs then does a real run with the same state file will resume from the advanced token and silently skip all the messages the dry-run 'previewed', leaving them unlabeled. This is a dry-run-still-mutates defect on the persistence path.

#### U053 · 🟠 HIGH · conf: high · `correctness/divergence` · rounds: R2

**Live demo's protected-sender set is 3 domains vs the engine's 14+ — IRS/SSA/DocuSign/Apple/Google/Anthropic/1Password-equivalents all UNprotected on the shipped site**

`cloudflare/worker.mjs:line 1 (PROTECTED set) cross-ref core/rules.py:559-573 EXAMPLE_PROTECTED_SENDERS`

PROTECTED = {courts.ca.gov, chase.com, 1password.com}. The real engine (core/rules.py EXAMPLE_PROTECTED_SENDERS) protects docusign.net, irs.gov, ssa.gov, studentaid.gov, login.gov, apple.com, appleid.com, google.com, accounts.google.com, anthropic.com, 1password.com, meta.com, facebookmail.com, chase.com. The marketing copy (web/index.html:354 'We check court, bank, gov, account, and client mail first') promises protection the live worker does not deliver: a user who types security@apple.com, no-reply@accounts.google.com, or their attorney's docusign envelope into the live demo gets 'Can move' (unprotected). Round 1's finding (PROTECTED dead-code) noted the set is unused; this is the distinct product-correctness defect that the actual protection coverage is a tiny fraction of what is sold and re-derived by the Python core.

#### U054 · 🟠 HIGH · conf: high · `correctness/regex` · rounds: R2

**Legitimate .gov senders are NOT protected when From contains a display name or angle brackets — endsWith('.gov') runs against the whole raw, unparsed sender string**

`cloudflare/worker.mjs:senderCheck line 106 (value.endsWith('.gov')); cross-ref core/rules.py:652-656 _gov_protected`

senderCheck does value = String(sender||'').trim().toLowerCase() with NO address extraction, then checks value.endsWith('.gov'). A normal From header like 'IRS Refunds <noreply@irs.gov>' lowercases to 'irs refunds <noreply@irs.gov>' which does NOT end with '.gov' (ends with '>') -> protected:false. So the live site fails to protect real government mail whenever the sender arrives as a display-name/angle-bracket header (the common case). The Python engine parses the address out (_iter_sender_domains) and anchors on the terminal label of the recovered domain. This is the under-protection inverse of round-1's 'over-protects every .gov' finding and a different, more dangerous defect: the gate silently FAILS OPEN for legitimate gov mail.

#### U055 · 🟠 HIGH · conf: high · `correctness/security` · rounds: R2

**Live /v1/audit/{run_id} fabricates an UNSIGNED, hardcoded receipt — the demo's 'tamper-evident signed receipt' headline trust artifact is fake**

`cloudflare/worker.mjs:GET /v1/audit/{run_id} lines 281-305; cross-ref api/receipts.py sign()/get_receipt() lines 66-142`

The worker's audit endpoint returns a fixed body {run_id, receipt:`Signed receipt for ${runId}`, audit:{total:3,protected_held:2,archived:1,...}} regardless of run_id, with NO signature, NO signed_body, NO algorithm field. The real api/receipts.py get_receipt() returns signed_body + signature (HMAC-SHA256) + algorithm + a verify recipe, which the README/receipts.py docstring (lines 9-13) sells as the product's headline 'tamper-evident HMAC-signed' artifact. On the live deployed site every audit lookup is a literal string 'Signed receipt for <id>' with no cryptographic content — an auditing agent that fetches /v1/audit/{id} and tries to verify gets nothing to verify. This directly contradicts the central trust claim and is unverifiable. Round 1 reported no worker audit findings.

#### U056 · 🟠 HIGH · conf: high · `documentation/implementation-contradiction` · rounds: R3

**Demo /v1/audit returns a fabricated 'Signed receipt' string with no signature — contradicts the product's headline 'signed, independently verifiable' claim**

`cloudflare/worker.mjs:281-305`

The canonical API (api/receipts.py:114-142) returns a real receipt object: {signed_body, signature (HMAC-SHA256 hex), algorithm: 'HMAC-SHA256', verify: '...recompute HMAC...'}. The Cloudflare share worker's /v1/audit/{run_id} instead returns receipt: `Signed receipt for ${runId}` — a literal label string with NO signature field, NO signed_body, NO algorithm, and counts hardcoded to total:3/protected_held:2/archived:1 regardless of the run. docs/cloudflare-share-demo.md lists /v1/audit as a 'Verified Demo Endpoint' and llms.txt/agent.json advertise 'receipt_verification' and 'independent, HMAC-signed, re-derivable' receipts. A reviewer hitting the live share URL gets an unsigned, fabricated payload that calls itself 'Signed receipt' — directly contradicting the implementation and the safety marketing. The worker /v1/audit shape also diverges from the real API shape (no signed_body/signature/algorithm keys), so any client written against the real API breaks on the demo.

#### U057 · 🟠 HIGH · conf: high · `security/protected-gate` · rounds: R3

**1password.com protection is substring-based and the chase.com fallback check is dead code**

`cloudflare/worker.mjs:150-169 (final senderCheck branch) and 128-148`

The final fall-through branch returns `protected: value.includes("chase.com") || value.includes("1password.com")`. (a) `value.includes("chase.com")` here is DEAD CODE — any chase.com sender already returned at line 128, so this disjunct is never true in the fall-through; it is misleading and suggests the author thought this branch still gates chase. (b) `1password.com` is matched by raw substring on the full lowercased From value, so `notify@1password.com.attacker.com` or display-name spoof `"1password.com" <evil@x.com>` is wrongly marked protected:true — and conversely a legitimate `1password.com` address is the ONLY domain handled here (courts/.gov handled above, chase handled above), so the entire PROTECTED Set on line 1 is never consulted by senderCheck. The Set at line 1 is effectively unused by this function. This is a different defect from the round-2 '.gov/chase substring spoof' note because it covers the 1password substring + the unused PROTECTED Set + the dead chase disjunct.

#### U058 · 🟠 HIGH · conf: high · `api-divergence` · rounds: R3

**Worker serves a frontend that links to /.well-known/agent.json, /server.json, /mcp, /acp/checkout_sessions, /openapi.json, /docs — none of which the worker implements**

`cloudflare/worker.mjs:whole file (no handlers for these paths) vs web/index.html:630-642,667 and api/well_known.py`

web/index.html (served by the worker via ASSETS) renders links/cards to `/.well-known/agent.json` (line 638), `/server.json` (638), `/mcp` (630/667), `/acp/checkout_sessions` (634), `/docs` and API reference (666), and the worker's own llms.txt + well_known.py advertise `/openapi.json`, `/acp/feed.json`, `/.well-known/agent.json`. The worker dispatch (238-322) handles none of these; they all fall through to `env.ASSETS.fetch` and return the SPA HTML or a static 404. On the live share domain every 'For builders' / 'Discovery' link is broken, and an agent reading the advertised agent.json/server.json discovery surface gets HTML or 404 instead of the manifest. This is a worker-vs-API route divergence: the API mounts all of these; the worker exposes none.

#### U059 · 🟠 HIGH · conf: high · `api-divergence` · rounds: R3

**Worker exposes POST /v1/triage as an alias of the dry-run preview, contradicting the real API where /v1/triage performs a live, fail-closed run**

`cloudflare/worker.mjs:172-198 (triagePreview) and 260-263 (/v1/triage)`

In api/app.py, `POST /v1/triage` honors `req.dry_run` and actually runs a triage through the engine + independent audit gate (service.run_triage), and can return a 500 SAFETY GATE VIOLATION. The worker (lines 260-263) routes /v1/triage to the SAME `triagePreview()` as /v1/triage/preview and always returns `dry_run: true` with a fixed run_id 'demo_preview'. An agent that calls /v1/triage on the share host believing it triggers a real (or at least dry_run-respecting) run gets a hardcoded preview that ignores the `dry_run` field in the body entirely. The contract for the most consequential endpoint (the one that moves mail) silently differs between the two surfaces.

#### U060 · 🟠 HIGH · conf: high · `portability` · rounds: R3

**Hardcoded absolute /Users/4jp paths make plist non-portable to any other machine/user**

`com.user.gmail_labeler.plist:lines 9-17, 13`

ProgramArguments[1] is '/Users/4jp/Code/organvm/universal-mail--automation/run_automation.sh', WorkingDirectory is '/Users/4jp/Code/organvm/universal-mail--automation', and the log paths are '/Users/4jp/System/Logs/mail_automation/...'. These are checked into the repo as static files. On any machine where the username is not '4jp' or the repo lives elsewhere, launchd will fail to launch the job (script path not found / cannot chdir). The committed plist is effectively a personal artifact, not a template. deploy.sh copies the *.plist verbatim (deploy.sh:48 'cp "$PLIST_SRC" "$PLIST_DEST"') with no path substitution, so a fresh clone on a different machine yields a broken LaunchAgent. Same issue exists in com.user.mail_automation.plist.

#### U061 · 🟠 HIGH · conf: high · `portability` · rounds: R3

**Same hardcoded /Users/4jp absolute paths (ProgramArguments, WorkingDirectory, logs) — the plist deploy.sh actually installs**

`com.user.mail_automation.plist:lines 9-17, 13`

This is the plist deploy.sh copies to ~/Library/LaunchAgents and bootstraps (deploy.sh:9-10,48,60). It hardcodes the script path, WorkingDirectory, and StandardOut/ErrorPath all under /Users/4jp. Because deploy.sh does no envsubst/sed templating, installing on a machine with a different home dir produces a LaunchAgent that points at non-existent paths and silently never runs correctly. The repo's own provenance doc (docs/plans/2026-05-31-provenance-evolution.md:99) already records both schedulers as 'Dead ... nonexistent paths, not loaded.' Root cause is shipping a literal plist instead of generating it from $REPO_DIR/$HOME at deploy time.

#### U062 · 🟠 HIGH · conf: high · `error-handling` · rounds: R1

**Unguarded int() cast on MAIL_AUTO_BATCH_SIZE crashes entire CLI/config load at startup**

`core/config.py:_apply_env_config, lines 272-273`

`config.batch_size = int(os.getenv(f"{prefix}BATCH_SIZE"))` has no try/except. If MAIL_AUTO_BATCH_SIZE is set to any non-integer value (e.g. "100x", "abc", "", "1_000" is OK but "1.5" is not), int() raises ValueError. Because load_config() is called near the top of every CLI command handler (cli.py:422, 523, 718, 828) and re-exported via core/__init__, a single typo in this env var crashes the whole tool before any command runs, with an unhelpful raw traceback instead of a clear config error. The other numeric path here (DRY_RUN, IMAP_GMAIL_EXTENSIONS) defensively use string-membership parsing; batch_size is the lone unguarded cast.

#### U063 · 🟠 HIGH · conf: high · `regex` · rounds: R1

**vip_senders regex patterns from untrusted YAML are never validated; invalid regex crashes categorization**

`core/config.py:_apply_yaml_config, lines 259-260 -> apply_vip_senders_from_config 313-322 -> core/rules.py check_vip_sender:885`

vip_senders is assigned verbatim from YAML (259-260) and apply_vip_senders_from_config (313-322) forwards vip_data['pattern'] straight into add_vip_sender -> VIP_SENDERS without re.compile validation. Patterns are matched lazily via re.search(vip.pattern, ...) in core/rules.py:885 (and pattern fields generally), so a malformed config regex (e.g. `pattern: "["` or `pattern: "(?P<"`) does not fail at config load — it raises re.error mid-run while categorizing a message, aborting the labeling pass partway through. Also tier/star (319-320) are taken via .get with no type check, so a YAML `tier: high` would propagate a string tier into the Eisenhower logic. No schema check on config-sourced VIP entries.

#### U064 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**Priority ties resolved by dict-insertion order silently misroute critical mail (gov mail with 'unsubscribe'/'newsletter' -> Marketing/Reference)**

`core/rules.py:_find_best_label (lines 1025-1038) + LABEL_RULES priorities; demonstrated at 468-507`

_find_best_label uses a STRICT `<` comparison (`if rule_config['priority'] < best_priority`), so when two rules share a priority the FIRST one in LABEL_RULES dict-insertion order wins and later same-priority rules can never override it. Seven priority collisions exist: priority 17 is shared by Marketing (tier 4), Tech/Storage (tier 3), and Personal/Government (tier 1, Critical) IN THAT INSERTION ORDER. Because Marketing is defined before Personal/Government, any .gov email whose subject/sender contains a Marketing keyword (`unsubscribe`, `newsletter`, `promo`, `discount`, etc. -- ubiquitous in legitimate government mailing-list footers) is categorized as Marketing/tier-4/Reference and archived, instead of Personal/Government/tier-1/Critical. Reproduced: categorize_with_tier('Benefits <noreply@ssa.gov>','newsletter: your benefits update, unsubscribe here') -> label='Marketing', tier=4. Same for any arbitrary city/state .gov sender. Other harmful ties: priority 9 Tech/Security beats Personal/Health and Tech/Google; priority 8 Finance/Payments beats Finance/Tax. The tie-break is undocumented and fragile to reordering.

#### U065 · 🟠 HIGH · conf: high · `logic` · rounds: R1

**irs.gov / ssa.gov / studentaid.gov never categorize as Personal/Government (Critical) because lower-priority earlier rules match first**

`core/rules.py:Personal/Government rule patterns 468-479; categorize path _find_best_label 1030-1036`

The Personal/Government rule (priority 17, tier 1 Critical) is intended to capture government mail, but `irs.gov` is ALSO listed in Finance/Tax (priority 8) and matches the bare substring `irs\.gov` there first; `ssa.gov` matches `social.*security`/`ssa\.gov` only inside Personal/Government but is beaten by any priority<17 keyword. Reproduced: categorize_with_tier('IRS <noreply@irs.gov>','Your tax refund status') -> label='Finance/Tax', tier=2, NOT Personal/Government tier 1. The user-facing tier table promises government mail is Critical (tier 1, starred, kept in inbox); this silently downgrades it to Important (tier 2).

#### U066 · 🟠 HIGH · conf: high · `regex` · rounds: R1

**Government .gov anchors are wrong because regex runs against combined 'sender subject' text, not the sender alone**

`core/rules.py:Personal/Government patterns: r'\.gov$' (470) and r'@.*\.gov' (471)`

_find_best_label searches `combined_text = f"{sender} {subject}".lower()`. The pattern r'\.gov$' anchors to the END of that combined string, so it only matches when the SUBJECT (the last token of the combined text) ends in '.gov' -- never when the SENDER domain is .gov (the sender is followed by the subject). The pattern r'@.*\.gov' uses a greedy `.*` across the whole combined string, so it matches whenever an '@' appears anywhere before any '.gov' anywhere later -- e.g. 'me@evil.com talked about x.gov stuff' matches (false positive), while a real gov sender with no '@...gov...' ordering in the combined text can miss. The two anchors are effectively broken for their stated purpose of identifying the sender domain.

#### U067 · 🟠 HIGH · conf: high · `error-handling` · rounds: R1

**Non-UTF-8 local protected_senders config crashes the module at import time, disabling the entire safety gate**

`core/rules.py:_load_local_protected lines 599-612`

The function opens the user's local config with encoding='utf-8' and only catches (FileNotFoundError, OSError). A non-UTF-8 byte raises UnicodeDecodeError, which is a subclass of ValueError (NOT OSError), so it is NOT caught and propagates out of the module body (this runs at import time on line 616). Reproduced: a config file containing byte 0xff causes `import core.rules` to raise UnicodeDecodeError, taking down is_protected_sender, categorize_message, and every consumer (cli.py, gmail_labeler.py, providers/base.py). The docstring explicitly promises 'Never raises.' Should catch UnicodeDecodeError / use errors='replace' / broaden to `except Exception`.

#### U068 · 🟠 HIGH · conf: high · `error-handling` · rounds: R1

**Invalid user-supplied VIP regex pattern raises re.error and crashes categorization with no guard**

`core/rules.py:check_vip_sender lines 883-887`

VIP patterns are user-supplied regex (via add_vip_sender / config) and are compiled live with re.search(vip.pattern, ...). A malformed pattern (e.g. '[unclosed') raises re.error, which is uncaught and propagates up through categorize_with_tier -> categorize_message, crashing the whole triage run. Reproduced: a VIPSender(pattern=r'[unclosed') makes check_vip_sender('anyone@x.com') raise 'unterminated character set'. The same exposure exists for any future config-loaded VIP. Patterns should be re.compile-validated on add (and skipped/logged on failure), or the search wrapped in try/except.

#### U069 · 🟠 HIGH · conf: high · `correctness/logic` · rounds: R2

**Government mail demoted to archived Marketing on a same-priority (17) tie**

`core/rules.py:lines 429, 454, 468-483 (priority 17 shared) + _find_best_label 1030-1036`

Marketing (line 449), Tech/Storage (463) and Personal/Government (480) ALL declare priority=17. _find_best_label uses a strict '<' comparison and 'break's on the first pattern match, so on a tie the dict-insertion order wins. Because Marketing is defined BEFORE Personal/Government, any genuine .gov email whose subject contains an extremely common bulk-mail keyword ('unsubscribe'/'newsletter'/'promo'/'discount') is categorized as Marketing Tier 4 (archived/Reference) instead of Personal/Government Tier 1 Critical. Verified: categorize_with_tier('noreply@cityplanning.lacounty.gov','Public meeting notice — unsubscribe here') -> Marketing tier 4; ('clerk@records.ny.gov','Newsletter: civic updates') -> Marketing tier 4. This is distinct from round-1's gov-vs-LOWER-priority finding: here Government has EQUAL priority and is still demoted purely by ordering, stripping Critical/starred status (the protected-sender gate prevents archival, but tier, starring, escalation and summary are all wrong).

#### U070 · 🟠 HIGH · conf: high · `race-condition` · rounds: R1

**Non-atomic state-file write can corrupt resume state on crash**

`core/state.py:save() lines 91-95`

save() opens the target state file directly in 'w' mode and json.dump()s into it. If the process is killed (or disk fills) mid-write, the file is left truncated/half-written. On the next run StateManager._load() will hit json.JSONDecodeError and silently reset to default state (next_page_token=None), so the entire resume position is lost and processing restarts from scratch (or, worse, a partially-valid JSON could load a corrupt token). save() is called repeatedly mid-run (gmail_labeler.py:308/322/332/335, cli.py:300/319/323), exactly the window where a crash is plausible. The crash-recovery feature this module exists to provide is defeated by a non-atomic write. Fix: write to a temp file in the same dir then os.replace() to atomically swap.

#### U071 · 🟠 HIGH · conf: high · `correctness` · rounds: R1

**No schema/version validation: corrupt-but-valid JSON is loaded and used unguarded**

`core/state.py:_load, lines 46-56 (and _default_state 58-66)`

_load() returns json.load(f) directly for any file that is syntactically valid JSON. There is no check that the loaded value is a dict, nor that required keys exist with the expected types. A state file whose top-level JSON is a list, string, number, or null is returned as `self.state`; subsequent `self.state.get(...)` calls then raise AttributeError (e.g. on a list/str/int) or, for null, the file silently becomes None and every getter raises. Even when it is a dict, individual fields (next_page_token, total_processed, history) are trusted to be of the right type. There is no version field, so a future schema change cannot be detected or migrated. The existing test only covers `NOT VALID JSON` (decode error) -> defaults; it never covers valid-JSON-wrong-shape, which is the dangerous gap. Failure mode: a partially-written or externally-corrupted-but-parseable state file is silently accepted and crashes the run later, or replays bad values.

#### U072 · 🟠 HIGH · conf: high · `none-handling` · rounds: R1

**get_history crashes when stored 'history' is a non-mapping (TypeError/ValueError)**

`core/state.py:get_history, lines 105-112; consumed in cli.py:174 / cli.py:238 / save:86`

get_history() does `defaultdict(int, self.state.get('history', {}))`. If a corrupt-but-valid state file stores `history` as a string, list, or number (rather than an object), defaultdict's constructor raises: a string raises ValueError ('dictionary update sequence element ... length 1'), a list/int raises TypeError ('object is not iterable'). This propagates straight out of run_labeler (cli.py:174 `stats = state.get_history()`) and crashes the labeling run on a common code path with an unhelpful traceback. Verified empirically. Should coerce to {} when the stored value is not a dict.

#### U073 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**save() swallows ALL write exceptions and returns normally — failed persist looks like success**

`core/state.py:save, lines 91-95`

save() wraps the file write in `try/except Exception` and only logs `logger.error`, then returns None as if it succeeded. A failed state write (disk full, permission denied, read-only mount, transient I/O error) is therefore indistinguishable from a successful one to the caller. In cli.py:300/319/323 the return value is ignored, so the run continues believing its progress is persisted. On the next run, resume reads the stale/empty/old state and silently restarts processing from scratch (or from a wrong page token), re-labeling already-processed mail. There is no flag, return value, or raised exception for the caller to detect this. The catch is also overly broad (Exception, not OSError) so it would also mask a json.dump TypeError from a non-serializable state value. Compare core/audit.py:_append which at least sets a `write_error` field the CLI can surface — save() has no such mechanism. No test covers a failing save.

#### U074 · 🟠 HIGH · conf: high · `concurrency` · rounds: R1

**No concurrency guard / file lock — two concurrent runs race and corrupt the state file**

`core/state.py:class StateManager, save 68-95 / _load 46-56 / clear 122-129`

StateManager has no file locking and no atomic-write strategy. The CLAUDE.md describes a launchd daily job plus manual ad-hoc CLI runs against the same default state_file (e.g. gmail_state.json). If two processes run concurrently (a scheduled run overlapping a manual one, or a hung previous run), they interleave: each reads its own page_token at start, both increment total_processed independently, and the last save() wins — losing the other's progress and double-processing mail. Worse, save() writes in place with `open(self.filename, 'w')` (truncate-then-write, not write-to-temp-then-rename), so a crash or concurrent reader mid-write can observe a truncated/partial JSON file; that partial file then trips _load's decode path (or, if it happens to be valid-but-incomplete JSON, the schema gap above). A lockfile (or atomic os.replace of a tempfile) plus a stale-lock check would prevent both the race and the torn-write corruption.

#### U075 · 🟠 HIGH · conf: high · `regex` · rounds: R1

**Double-escaped regex patterns can never match real email text**

`gmail_labeler_legacy.py:LABEL_RULES patterns: lines 62 (render\\.com), 64 (pieces\\.app), 79 (meta\\.com), 95 (self\\.inc), 235 (builtin\\.com), 239 (e\\.godaddy\\.com), 273 (ibo\\.org)`

Several patterns in the legacy LABEL_RULES use a double backslash before the dot: r"render\\.com", r"self\\.inc", r"pieces\\.app", r"meta\\.com", r"builtin\\.com", r"e\\.godaddy\\.com", r"ibo\\.org". In a raw string r"render\\.com" the regex sees a literal backslash followed by a literal dot, so it only matches the text 'render\.com' (with an actual backslash character), which never appears in From/Subject headers. Verified empirically: re.search(r"render\\.com", "render.com") returns None. As a result Backblaze/Render infra mail, self.inc finance mail, meta.com, builtin.com jobs, GoDaddy domain mail, and ibo.org marketing all silently fall through to the catch-all 'Uncategorized'. core/rules.py uses the correct single-escape (r"render\.com" etc.), so this is stale/divergent legacy code that miscategorizes. Even though legacy is relabel-only (non-destructive), it produces wrong labels.

#### U076 · 🟠 HIGH · conf: high · `correctness` · rounds: R1

**COPY+EXPUNGE fallback expunges the WHOLE mailbox, not just the one message, risking data loss of other \Deleted mail**

`icloud_triage.py:archive_uid() lines 63-77`

When UID MOVE is unsupported, the fallback does UID COPY, then UID STORE +FLAGS \Deleted on the single uid, then imap.expunge() (line 76) with NO argument. Plain EXPUNGE permanently removes EVERY message in the selected mailbox currently flagged \Deleted — including messages the USER or another client flagged \Deleted but did not intend to purge yet. Running this per-message in a loop (lines 161-165) also EXPUNGEs after each, which is slow and repeatedly purges. The safe primitive is UID EXPUNGE (RFC 4315) scoped to the copied uid, or a single batched expunge with care. On a real iCloud account this is a latent data-loss path for unrelated \Deleted mail.

#### U077 · 🟠 HIGH · conf: high · `correctness` · rounds: R2

**COPY-fallback archive runs unscoped EXPUNGE, risking deletion of other \Deleted messages in the mailbox**

`icloud_triage.py:archive_uid 63-77`

Same class as the providers/imap.py archive bug: when UID MOVE is unsupported, archive_uid does COPY then STORE +FLAGS \Deleted on the single uid then `imap.expunge()` — an unscoped expunge that removes EVERY \Deleted message in the selected mailbox, not just this one. On servers without RFC 6851 MOVE this can destroy unrelated mail. UID EXPUNGE scoped to the uid is required.

#### U078 · 🟠 HIGH · conf: high · `privacy` · rounds: R3

**labeler_state.json (real mailbox stats) is git-tracked in a public repo despite CLAUDE.md flagging *_state.json as runtime state to avoid**

`labeler_state.json:labeler_state.json:1-15 (whole file)`

labeler_state.json is TRACKED (committed since the initial commit 00ff9d7) and is currently in HEAD. It contains the user's real mailbox statistics: total_processed=36470 and a per-category breakdown of their actual email (Misc/Other=35521, Tech/Security=372, Finance/Payments=302, Finance/Banking=151, Professional/Jobs=79, etc.). CLAUDE.md 'Files to Avoid Modifying' explicitly lists '*_state.json (runtime state for resumption)'. This is runtime/state data leaked into a public GitHub repo (remote https://github.com/a-organvm/universal-mail--automation.git). It exposes the size and composition of the owner's private inbox. It should be removed from tracking (git rm --cached) and added to .gitignore; because it is in history since the first commit, the value is also recoverable from git log even after removal.

#### U079 · 🟠 HIGH · conf: high · `money-path` · rounds: R1

**MCP triage tool has no auth/account/metering — unlimited free live triage for any connected agent**

`mcp_server/server.py:_triage (129-146); triage (109-126); triage_preview (97-107)`

The MCP triage tools delegate to service.run_triage with no api_key, no account lookup, and no credit/cap check (mcp_server/server.py never imports api.store). The docstring at api/plans.py claims MCP + ACP agent-commerce access is a Business-tier ($49/mo) feature and the metered add-on (api/plans.py:130-139) claims '$0.01 / triage run ... how AI agents pay for verified-safe triage', but no Stripe Billing Meter event is ever emitted and no credit is consumed on a tool call. Any agent that can reach the /mcp endpoint runs unlimited live mailbox mutations (dry_run can be set False) at no charge and against no quota. The only guard present is DNS-rebinding transport security; there is no authorization layer.

#### U080 · 🟠 HIGH · conf: high · `correctness/logic` · rounds: R2

**MCP triage tool is the agent-facing paid surface yet performs no credit debit, no cap check, and emits no meter event — agents triage unlimited for free**

`mcp_server/server.py:triage tool lines 109-126 / _triage lines 129-146 (no credit/cap/meter)`

The MCP `triage` tool (server.py:109) is explicitly positioned as the agent monetization surface ('how AI agents pay for verified-safe triage', plans.py:137; manifest advertises MCP tools). It calls service.run_triage (server.py:132) with provider/query/limit only — no account identity, no consume_credit, no entitlements_for, no monthly_run_cap check, and no Stripe meter event for METERED_ADDON.meter_event_name='triage_run'. Round 1 focused its [crit]/[high] enforcement findings on api/app.py and api/service.py; this is the SAME gap at the MCP entry point specifically, where the metered/agent business model is supposed to live. Any MCP client can drive unlimited live (dry_run=False) triage against the server's mailbox credentials with zero billing, and a credit-pack-buying agent's balance is never decremented.

#### U081 · 🟠 HIGH · conf: high · `config` · rounds: R2

**Hosted /mcp endpoint is dead-on-arrival in production: default allowed_hosts excludes the real deploy domain so every request 421s**

`mcp_server/server.py:_transport_security() lines 48-58; render.yaml (no MCP_ALLOWED_HOSTS); DEPLOY.md:73`

When MCP_ALLOWED_HOSTS is unset (the render.yaml blueprint default; autoDeploy=true), _transport_security() returns enable_dns_rebinding_protection=True with allowed_hosts limited to ['localhost','127.0.0.1','localhost:8000','127.0.0.1:8000'] (lines 51-52). The installed MCP SDK does EXACT Host-header matching (transport_security.py _validate_host: only a literal match or a ':*' wildcard-port suffix). A real Render/Fly request arrives with Host: <app>.onrender.com, which is not in the list, so validate_request returns HTTP 421 'Invalid Host header' for EVERY /mcp call until an operator manually sets MCP_ALLOWED_HOSTS. The one-click render.yaml never sets it, and the module docstring/INSTRUCTIONS advertise the hosted endpoint as ready. This is a hard outage of the entire MCP surface on a fresh deploy, distinct from round 1's report which only covered the MCP_ALLOWED_HOSTS='*' (protection-fully-disabled) case.

#### U082 · 🟠 HIGH · conf: high · `security` · rounds: R2

**Prompt-injection 'preview by default' guarantee is a single model-controlled boolean (dry_run=False), not a capability gate or confirmation step**

`mcp_server/server.py:triage() lines 109-126; module docstring lines 10-13; INSTRUCTIONS lines 60-68`

The docstring (lines 10-13) and INSTRUCTIONS (lines 60-68) sell the dry_run=True default as the anti-prompt-injection control: a 'careless or prompt-injected agent previews by default and must explicitly ask to mutate.' But dry_run is an ordinary tool argument the model fully controls. A single injected instruction ('call triage with dry_run=false') flips the only barrier to a live mailbox mutation in one step. There is no second factor, no out-of-band confirmation, no per-call capability/entitlement check, and the destructiveHint annotation (line 109) is advisory metadata the client MAY ignore. So the advertised mitigation reduces to 'the attacker must set one boolean it can already set' — it does not raise the bar against the exact prompt-injection threat the docstring names. This is a distinct defect class from round 1's 'no auth/metering' finding (the control exists but is structurally ineffective).

#### U083 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**Gmail provider never populates EmailMessage.date, so escalate/pending age logic is a silent no-op**

`providers/gmail.py:157-161, 204-211, 286-293 (EmailMessage construction); 177, 243 (metadataHeaders)`

All three EmailMessage constructions in the Gmail provider (list_messages line 157, get_message_details line 204, _parse_message_response line 286) omit the `date=` field, so it defaults to None (core/models.py:48). Worse, the underlying Gmail API fetches request `metadataHeaders=["From", "Subject"]` (lines 177 and 243) and `format="metadata"`, so the `Date` header / internalDate is never even retrieved — there is no data from which a date could be parsed. Downstream, cli.py cmd_escalate calls `calculate_email_age_hours(msg.date)` (cli.py:883), which returns 0 when the date is None (core/rules.py:1173-1174). escalate_by_age then hits the `email_age_hours < 24` branch (core/rules.py:1122) and returns should_escalate=False for every message. Result: the documented `cli.py escalate` feature (and the age column in `cli.py pending`, cli.py:667) is a complete silent no-op for the Gmail provider — every email reports age 0h and nothing is ever escalated. This is a documented feature (CLAUDE.md 'Time-Based Escalation Rules') that does nothing on Gmail. Failure mode: user runs `escalate`, sees 'Messages escalated: 0' regardless of how stale the inbox is, and wrongly believes nothing needs escalation.

#### U084 · 🟠 HIGH · conf: high · `api-misuse` · rounds: R1

**IMAP search passes raw query string with charset=None; Gmail-style queries (label:, has:) are NOT valid IMAP SEARCH and will error or mis-search**

`providers/imap.py:list_messages 184`

`self._connection.uid("search", None, query)` forwards the user query verbatim as IMAP SEARCH criteria. The CLI and docs pass Gmail search syntax (e.g. `label:Misc/Other`, `has:nouserlabels` at cli.py:481 `f"label:{label}"`). These are not valid IMAP SEARCH keys; the server will return BAD/NO causing `RuntimeError(IMAP search failed)`, or with some servers silently mis-parse. The IMAP provider has no translation from the app's query dialect to IMAP criteria. Common-path wrong behavior for any non-trivial query.

#### U085 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**imaplib uid(STORE/...) errors are exceptions OR ('NO', ...) tuples; success returned True without checking response status**

`providers/imap.py:apply_label 279, remove_label 303, star 331, unstar 340, mark_read 364, mark_unread 373, archive 321`

apply_label (gmail-ext branch), remove_label (gmail-ext), star, unstar, mark_read, mark_unread call `self._connection.uid('STORE', ...)` and unconditionally `return True`, only catching exceptions. imaplib does NOT raise on a 'NO'/'BAD' server response for these (it returns ('NO', [...])); it only raises on protocol errors. So a server-rejected STORE (label doesn't exist, permission denied, invalid flag) is reported as success=True. This silently reports failed label/flag operations as successful — and apply_actions records them in the audit as applied. Should inspect the (typ, data) return and return typ=='OK'. Contrast: apply_label's standard-IMAP COPY branch and ensure_label_exists DO check res.

#### U086 · 🟠 HIGH · conf: high · `correctness` · rounds: R1

**IMAP archive() for Gmail extensions removes \Inbox but does not verify the STORE succeeded; standard-IMAP archive COPY+\Deleted+EXPUNGE is non-atomic data-loss risk**

`providers/imap.py:archive(), lines 312-326`

Two issues on the destructive archive path: (1) the Gmail-extensions branch calls remove_label(message_id, '\\Inbox') which itself returns True regardless of the actual STORE result (see the unchecked-return finding), so archive() can report success when the message was never removed from the inbox. (2) The standard-IMAP branch does COPY -> STORE +\Deleted -> expunge(). expunge() is mailbox-wide: it permanently deletes EVERY \Deleted-flagged message in the selected mailbox, not just this UID. If another concurrent operation (or a prior failed archive) left other messages flagged \Deleted, this expunge destroys them. Also, if STORE +\Deleted fails silently (return unchecked), the message is left COPIED to Archive but still in INBOX (duplicate), or expunge runs on a stale set. A per-UID MOVE (RFC 6851, as icloud_triage.py uses) or UID EXPUNGE would be safer than mailbox-wide expunge.

#### U087 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**IMAP provider never populates EmailMessage.date; no INTERNALDATE/Date fetched → escalate no-op**

`providers/imap.py:198-202 (list_messages), 261-268 (get_message_details); fetch spec line 219`

Both EmailMessage constructions in the IMAP provider (list_messages line 198, get_message_details line 261) omit `date=`, defaulting to None. The fetch in get_message_details requests only `(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])` (line 219) — neither the `Date` header field nor IMAP `INTERNALDATE` is fetched, so age cannot be computed even in principle. As with Gmail, calculate_email_age_hours(None) returns 0 (core/rules.py:1173) and escalate_by_age takes the <24h branch, so `cli.py escalate --provider imap` never escalates anything and `cli.py pending` shows every item as 0h old. Silent no-op of a documented feature.

#### U088 · 🟠 HIGH · conf: high · `error-handling / silent-failure` · rounds: R2

**Gmail-extension IMAP STORE for label add/remove/archive ignores the IMAP response status and always returns True**

`providers/imap.py:apply_label line 279, remove_label line 303, archive line 314-315`

apply_label (X-GM-LABELS +) and remove_label (X-GM-LABELS -) call self._connection.uid('STORE', ...) and unconditionally return True without inspecting the (typ, data) result tuple. imaplib does not raise on a server 'NO'/'BAD' response — it returns it. So a STORE that the server rejects reports success. archive() for the gmail-extension path is remove_label('\\Inbox'), so a FAILED inbox-removal is reported as a successful archive. In the audit flow (base.apply_actions records did_leave_inbox from remove_label's True return) this means a non-protected message that the server refused to move out of inbox is recorded as archived — a false success on the product's headline trust surface. Round-1 IMAP coverage did not flag the swallowed STORE status.

#### U089 · 🟠 HIGH · conf: high · `correctness` · rounds: R2

**Standard-IMAP archive expunges the whole mailbox, deleting unrelated messages**

`providers/imap.py:archive 312-326 (standard IMAP branch)`

For non-Gmail IMAP, archive() does COPY to "Archive", then STORE +FLAGS \Deleted on the one UID, then `self._connection.expunge()`. expunge() permanently removes EVERY message currently flagged \Deleted in the selected mailbox, not just this UID — if any other message in INBOX already carries \Deleted (common: clients flag-then-expunge later), this silently destroys them. UID EXPUNGE (RFC 4315) scoped to the single UID is required. This is a data-loss bug on the archive path.

#### U090 · 🟠 HIGH · conf: high · `injection` · rounds: R1

**AppleScript injection: message_id and label interpolated unescaped into osascript source**

`providers/mailapp.py:apply_label/get_message_details/star/mark_read/ensure_label_exists, lines 211-356`

Every Mail.app operation builds an AppleScript by f-string interpolation of message_id and label directly into the script text (e.g. 'first message whose id is {message_id}', 'mailbox "{label}"', 'make new mailbox with properties {{name:"{label}"}}'). message_id is treated as a numeric in 'whose id is {message_id}' but is a free-form string from the provider; a label containing a double-quote or AppleScript syntax (labels are hierarchical user/rule-derived strings) breaks out of the string literal and executes arbitrary AppleScript via osascript. Because the gate/categorization labels come from rules and config (and ultimately from email content for some flows), this is an injection sink on a destructive (move/delete) surface. Values should be validated (id is integer) and string-escaped, or passed via osascript argv (-e with 'on run argv') rather than source interpolation.

#### U091 · 🟠 HIGH · conf: high · `injection` · rounds: R1

**AppleScript injection via mailbox and account names interpolated into osascript**

`providers/mailapp.py:list_messages, lines 131-169 (account_filter line 133, mailbox line 139)`

list_messages builds an AppleScript via f-string interpolating `mailbox` (default 'INBOX' but caller-controllable) and `self.account` directly: `mailbox "{mailbox}"` and `of account "{self.account}"`. A mailbox or account name containing a double-quote, backslash, or AppleScript syntax (e.g. `INBOX"
set x to do shell script "...`) breaks out of the string literal and injects arbitrary AppleScript, which osascript will execute. Account/mailbox names can originate from untrusted/synced IMAP folder names. No escaping is performed anywhere in this module. Same class of bug as a shell-injection: full code execution in the user's Mail.app/osascript context.

#### U092 · 🟠 HIGH · conf: high · `injection` · rounds: R1

**AppleScript injection via message_id and label interpolated unescaped into osascript**

`providers/mailapp.py:get_message_details line 213; apply_label lines 263-270; star/unstar/mark_read/mark_unread (e.g. 295-301, 360-366); ensure_label_exists 335-345`

Every mutating method interpolates `message_id` and/or `label` directly into AppleScript: e.g. `first message whose id is {message_id}` (no quotes — message_id is assumed numeric but is typed as str and never validated; a value like `1 or true` or `1\ntell application \"Finder\"...` injects code/AppleScript) and `mailbox "{label}"` / `make new mailbox with properties {{name:"{label}"}}` (a label containing `"` or `\` breaks out). Labels come from core.rules taxonomy (currently static) but ensure_label_exists/apply_label accept arbitrary label strings, and message_id flows from list output / get_message_details whose values are not sanitized. Any quote/backslash/newline in these values yields AppleScript injection -> arbitrary code execution. Fix: pass values as osascript arguments (`osascript -e ... arg1 ...` with `on run argv`) or rigorously escape quotes/backslashes.

#### U093 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**Mail.app provider never populates EmailMessage.date; AppleScript fetches no date received → escalate no-op**

`providers/mailapp.py:191-197 (list_messages), 240-247 (get_message_details); AppleScript at 211-228`

Both EmailMessage constructions in the Mail.app provider (list_messages line 191, get_message_details line 240) omit `date=`, defaulting to None. The list_messages AppleScript returns only id/sender/subject/read/flagged (mailapp.py:160) and the get_message_details AppleScript returns sender/subject/read/flagged/mailbox (line 226) — the message `date received` property is never queried, so no date is available. Consequently calculate_email_age_hours(None) returns 0 (core/rules.py:1173), escalate_by_age never fires, and `cli.py escalate --provider mailapp` plus the age column in `cli.py pending` are silent no-ops. Documented feature with no effect on this provider.

#### U094 · 🟠 HIGH · conf: high · `security` · rounds: R2

**AppleScript injection via unescaped label/mailbox/account/message_id interpolation**

`providers/mailapp.py:apply_label 263-270, ensure_label_exists 335-346, get_message_details 211-228, list_messages 135-169`

Every AppleScript is built with f-strings that interpolate untrusted values directly into the script body with no escaping: label (folder name), self.account, mailbox, and message_id. A label or account containing a double-quote or a newline (e.g. a label derived from a category name, or an attacker-controlled folder name) breaks out of the quoted AppleScript string and can run arbitrary `tell application` statements. message_id is interpolated unquoted into `whose id is {message_id}`, so a non-numeric id injects code. osascript runs with the user's full privileges. This is an injection/RCE-class weakness on the Mail.app path.

#### U095 · 🟠 HIGH · conf: high · `api-misuse` · rounds: R1

**Access token never refreshed mid-run; long sweeps fail with 401 once the token expires**

`providers/outlook.py:_get_session (196-211) + _api_get/_api_post/_api_patch (213-232); token acquired once in connect() at 234-239`

connect() calls _acquire_token() once and stores the result in self._access_token. _get_session() bakes that token into the Session Authorization header exactly once (the `if self._session: return self._session` short-circuit means the header is set only on first creation). Microsoft Graph access tokens typically expire after ~60-90 minutes. The CLI label loop (cli.py 183-309) paginates and processes potentially thousands of messages in a single connection, but there is no token-refresh path: no call to acquire_token_silent between batches, and the session header is never updated even if _access_token changed. A long-running sweep will start returning HTTP 401 once the token expires, and since _api_* calls do raise_for_status() with no 401-aware retry/refresh, every subsequent operation throws and is counted as an error (or aborts list_messages). This is a real correctness/reliability bug for the system's stated bulk-relabeling use case.

#### U096 · 🟠 HIGH · conf: high · `silent-failure` · rounds: R1

**Folder lookup fallback can silently return the label string instead of a real folder ID, causing wrong-destination move**

`providers/outlook.py:ensure_label_exists, 610-651 (esp. 644-651)`

In the create-or-find fallback: if _api_post fails (633) and the subsequent _api_get filter returns no value (the `if result.get('value')` at 644 is false), no exception is raised inside the inner try and parent_id/_folder_cache are not updated. Execution continues to the next loop part (or exits the loop). At the end, `return self._folder_cache.get(label, label)` (651) returns the *label string itself* as a fallback. apply_label (527-530) then issues a Graph /move with destinationId=<the label text> (e.g. "Work/Dev/GitHub"), which is not a valid folder ID. Best case Graph 400s; worst case it matches a well-known folder name and the message is moved to the WRONG folder. The function's contract is to return a folder ID; silently returning the raw label violates it. Also note partial hierarchy creation: if part N is created but part N+1 fails to be found, parent_id points at part N and the final get(label,...) miss returns the full path string.

#### U097 · 🟠 HIGH · conf: high · `error-handling` · rounds: R1

**Broad except swallows all errors (auth, network, 5xx) and degrades to empty/false, hiding real failures**

`providers/outlook.py:list_messages 436-440 (and get_message_details 480-484, apply_category 346-350, _init_folder_cache 261-262, _init_category_cache 284-285)`

Multiple methods catch bare `Exception` and degrade silently: list_messages returns ListMessagesResult(messages=[]) on ANY error (438-440), which the CLI interprets as end-of-results and stops — so a 401/429/503 mid-pagination silently ends the run as if completed successfully. apply_category swallows the GET of current categories (349-350) and proceeds with current_cats=[], which can DROP existing categories on the message (see separate finding). _init_folder_cache (261) and _init_category_cache (284) log a warning and continue with empty caches, so later ensure_label_exists/apply_category behave as if no folders/categories exist. These broad excepts conflate transient/auth/permanent errors and prevent retry/backoff.

#### U098 · 🟠 HIGH · conf: high · `config/dependency` · rounds: R2

**`requests` is mislabeled "Optional: Outlook" but is a MANDATORY runtime dependency for Gmail OAuth token refresh**

`requirements.txt:lines 6-8 ("# Optional: Outlook.com support" then msal/requests)`

requirements.txt groups `requests>=2.28.0` under the comment `# Optional: Outlook.com support (Microsoft Graph API)`. But gmail_auth.py:12 hard-imports `from google.auth.transport.requests import Request` and calls `creds.refresh(Request())` at gmail_auth.py:167. `google.auth.transport.requests` requires the `requests` library to be installed (it is an optional extra of google-auth, NOT installed by google-api-python-client/google-auth-httplib2 by default). So a user who reads the comment and skips `requests` because they only use Gmail will get an ImportError the moment a token needs refreshing. `requests` is a core Gmail dependency, not an Outlook-only one. The dependency classification is wrong and will produce a crash on the common Gmail path (every expired-token refresh).

#### U099 · 🟠 HIGH · conf: high · `security` · rounds: R2

**Bulk-sender router moves protected mail with no protected-sender gate (and unanchored substring match)**

`route_bulk_senders.applescript:line 9`

is_bulk_sender returns true and the message is moved out of the inbox to the Newsletters folder (line 28) whenever `theSender contains ("@" & dom)` OR `theSender ends with dom`, with NO protected-sender check anywhere. Two compounding defects beyond round 1's F211 (which framed this only as a 'wrong-folder move' correctness issue): (1) GATE BYPASS — if a protected/important sender's address ever matches a configured bulk domain (or a lookalike), the message is moved out of the inbox, violating the core/audit.py guarantee that protected senders are never moved out of the inbox; this is a data-loss/safety defect, not merely a misfiling. (2) UNANCHORED `ends with dom` — for dom='mailchimp.com', a sender string `noreply@notmailchimp.com` ends with `mailchimp.com` (no leading-dot boundary), so it matches; this is the same class of substring-spoofing the Python gate explicitly defends against in core/rules._domain_matches (line 659-663: 'equality OR proper subdomain ... kills substring embeds'). The AppleScript has no equivalent boundary check, so any '...mailchimp.com' lookalike or subdomain trailing match routes mail. Reported here as a security/safety boundary defect distinct from round 1's correctness-only framing.

#### U100 · 🟠 HIGH · conf: high · `error-handling` · rounds: R1

**set -u aborts iCloud step (and whole script) if ICLOUD_IMAP_* env vars are unset**

`run_automation.sh:lines 5, 47-50`

The script runs under `set -euo pipefail`. Lines 47-49 expand `$ICLOUD_IMAP_HOST`, `$ICLOUD_IMAP_USER`, `$ICLOUD_IMAP_PASS` directly. With `set -u` (nounset), if any of these is not exported by the sourced op env file (e.g. the user only configured Gmail/Outlook, or the 1Password lookup silently produced nothing), bash aborts immediately with 'unbound variable'. Because `set -e` is also on, the entire daily automation run terminates at the iCloud block, even though Gmail/Outlook already succeeded above and the rest of the script (the completion banner) never executes. The Gmail/Outlook commands themselves are guarded with `|| echo "... failed"`, showing intent to be resilient, but the unguarded variable expansion defeats that. Use `${ICLOUD_IMAP_HOST:-}` defaults or guard the block with a presence check.

#### U101 · 🟠 HIGH · conf: high · `config/consistency` · rounds: R2

**server.json advertises a PyPI package that the repo cannot build or publish (no [project]/[build-system] in pyproject.toml)**

`server.json:lines 6-15 (packages[].registryType=pypi, identifier=universal-mail-automation, version 0.1.0); cross-ref pyproject.toml (whole file) and scripts/gen_commerce_artifacts.py gen_server_json lines 82-89`

server.json (and its generator gen_server_json) declare an MCP-registry package entry `{registryType: pypi, identifier: "universal-mail-automation", version: "0.1.0", transport: stdio}`. The repo's pyproject.toml contains ONLY a `[tool.pytest.ini_options]` table — there is no `[project]`, no `[build-system]`, no setup.py/setup.cfg, no MANIFEST.in. So no installable distribution named `universal-mail-automation` can be built from this tree, and `pip install universal-mail-automation` / `python -m mcp_server` over stdio (the advertised install+launch path) does not resolve to anything this repo produces. An MCP registry client trusting server.json's pypi entry would fail to install. Round 1 only flagged the placeholder `mail.example.com` remote URL — this is a separate, harder defect: the manifest claims a shipping artifact that does not exist. Either publish real packaging metadata or drop the pypi package block.

#### U102 · 🟠 HIGH · conf: high · `test-quality` · rounds: R2

**Test suite asserts credits are ADDED and that consume_credit works as a unit, but no test asserts a triage run ever DEBITS a credit or hits a cap — masking the unwired metering**

`tests/test_api.py:whole file (no credit-debit/cap assertion); cf. tests/test_acp.py:117-153 and tests/test_store.py:35-43`

The reason the dead-metering bug shipped: the tests give false confidence. tests/test_store.py:35-43 asserts consume_credit debits correctly as a unit; tests/test_acp.py:117-153 asserts ACP completion ADDS 100/200 run_credits and is idempotent. But there is NO test anywhere that drives /v1/triage (or the MCP triage tool, or ACP) and then asserts run_credits DECREASED, or that a Free account is blocked after its monthly_run_cap, or that entitlements_for is consulted on a run. test_api.py exercises /v1/triage and /v1/triage/preview with NO account/credit context at all and asserts only the gate/503/422 behavior. So every test passes while the paid model (debit-on-run, cap enforcement, metered Stripe event) is entirely absent. A single integration test 'buy a pack, run triage, assert balance fell by 1' would have caught the gap; its absence is the root test-quality defect behind the residual scope.

#### U103 · 🟠 HIGH · conf: high · `correctness` · rounds: R2

**Offline sender-check fallback is fail-OPEN: only 3 hardcoded patterns are protected, contradicting the safety promise**

`web/index.html:line 753 (localSenderCheck default return) vs lines 706-708`

localSenderCheck is the client-side fallback used whenever the API call fails (line 809: `ok && data ? data : localSenderCheck(sender)`). It marks a sender protected ONLY if the value ends in '.gov', or contains 'chase.com' or '1password.com' (line 708), and otherwise returns `protected: isProtected` = false (line 753). The page's headline promise is that it 'checks court, bank, gov, account, and client mail first.' But in offline/static-share mode a genuinely protected sender such as alerts@bankofamerica.com, legal@law-firm.com, or any non-Chase bank renders the green 'Can move. Show it in the dry run first.' verdict (line 818) — the opposite of the fail-CLOSED guarantee the product is built on. The server-side gate is fail-closed; this client mirror is fail-open, so the most trust-sensitive surface can actively tell a user a protected sender is movable.

#### U104 · 🟠 HIGH · conf: high · `money/consistency` · rounds: R2

**Static-demo fallback renders different plan NAMES and prices than checkout actually charges (Inbox safety audit/$29-$49 vs Pro/$19) — buyer deception on the live Cloudflare demo**

`web/index.html:lines 679-704 (SAMPLE_PLANS) and 932-933 (catch -> localPlans() fallback render); cross-ref api/plans.py PLANS pro/business (name="Pro"/"Business", price_display $19/$49) and startCheckout(p.id)`

When GET /v1/billing/plans is unreachable, the page falls back to SAMPLE_PLANS (line 933). The documented deployment (docs/plans/2026-06-02-handoff-cloudflare-ci-domain.md, cloudflare-share-demo.md) is a STATIC Cloudflare-hosted demo with NO API backend, so this fallback is the live path, not an edge case. SAMPLE_PLANS uses plan id `pro` but name "Inbox safety audit" at price_display "$29-$49", and id `business` named "Assisted cleanup" at "$149-$299". The buy button calls startCheckout(p.id) -> POST /v1/billing/checkout for plan id `pro`/`business`, which plans.py prices at $19/mo ("Pro") and $49/mo ("Business"). So a visitor sees a product called "Inbox safety audit" priced "$29-$49" but the actual Stripe checkout (when wired) charges $19/mo for "Pro". This is a deeper instance than round 1's price-divergence note: not just the number differs, the plan NAME/product identity differs and the divergent values are the ones actually served on the public deployment. Whichever wins, the displayed offer and the charged offer disagree.

#### U105 · 🟠 HIGH · conf: medium · `money/unit arithmetic` · rounds: R2

**Feed advertises price as integer cents (100/900) under currency 'USD' — ambiguous unit risks a 100x agent-facing mispricing vs the actual cents charge**

`acp/feed.py:build_feed lines 48-50 (price=pack['amount_cents'], currency='USD'); acp/product_feed.json lines 13/15, 33/35`

The product feed emits `"price": pack["amount_cents"]` (100 for pack_100, 900 for pack_1000) with `"currency": "USD"`. The internal catalog amount_cents=100 means $1.00 (pricing.md renders $1.00 / $9.00, and the ACP charge uses grand_total = the same cents value via PaymentIntent amount, which IS minor units). But a product `price` field paired with a 3-letter ISO `currency` is conventionally a MAJOR-unit amount in agentic-commerce / merchant product feeds. An ACP agent that interprets `price: 100, currency: USD` as $100.00 (and `price: 900` as $900.00) sees a 100x markup versus the $1.00 / $9.00 that is actually charged at /complete. Nothing in the code or docs declares the feed `price` unit, and the displayed feed price is sourced from amount_cents while the charged amount is also amount_cents — so feed and charge agree numerically only if the consuming agent also treats `price` as minor units, which is not the documented product-feed convention. This is a direct displayed-vs-charged unit hazard on the public agent discovery surface.

#### U106 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**Charge treats only status=='succeeded' as ok, dropping 'requires_action'/'processing' into a permanent failure that strands a real payment**

`acp/payment.py:StripeSPTPaymentClient.charge (89-97)`

After payment_intents.create(confirm=True), the code returns ok=True only if intent.status=='succeeded', else ok=False (payment.py:92-97). For SPT/card flows an intent can legitimately return 'processing' (async settlement) or 'requires_action'. Here both are surfaced as a 402 'payment not completed' and the session stays READY, so the agent retries — but the original PaymentIntent may still settle asynchronously at Stripe, while the retry (new behavior depends on the per-session idempotency key) either dedups to the same intent or the buyer is left believing payment failed when funds were actually captured. There is no polling/webhook reconciliation for the ACP PaymentIntent (unlike the subscription path which has a webhook). Net: a payment that settles in 'processing' will NEVER credit runs (fulfillment only happens on the synchronous ok=True path), so the buyer pays and gets nothing. This is a confirm-without-settlement-handling gap in the opposite direction (settle-without-confirm).

#### U107 · 🟠 HIGH · conf: medium · `money-correctness / payment-API misuse` · rounds: R2

**Synchronous confirm with no return_url: a 3DS/requires_action result is treated as a hard failure, stranding an authorized-but-uncaptured charge**

`acp/payment.py:70-93 (PaymentIntent.create with confirm=True)`

charge() calls payment_intents.create with confirm=True and no return_url / off_session flag. For any card requiring authentication (3DS / SCA in the EU), Stripe returns the intent in status 'requires_action' rather than 'succeeded'. Line 92 treats only 'succeeded' as ok, so requires_action falls to the failure return (94-97). The router then surfaces 'payment_failed' and re-persists the session as READY (273-280). But the PaymentIntent still exists on Stripe in a pending state, and depending on the payment method the funds may be authorized/held. The buyer's agent gets a clean 402 'payment failed' while a real, chargeable intent is left dangling with no cancellation — money can be held/captured later with nothing delivered. Round 1 noted requires_action is dropped to failure; the NEW correctness angle is the absence of any cancel/return_url, so the dangling intent is never voided and can still settle.

#### U108 · 🟠 HIGH · conf: medium · `money/unit` · rounds: R2

**ACP product feed emits price as a bare integer of minor units (cents), not major units / decimal — an agent can over-read price by 100x**

`acp/product_feed.json:lines 13, 33 ("price": 100 / "price": 900); source acp/feed.py build_feed line 48 ("price": pack["amount_cents"])`

The product feed sets `"price": 100` for the $1.00 pack and `"price": 900` for the $9.00 pack, copied verbatim from `pack["amount_cents"]`. ACP / agentic-commerce product feeds express the displayed price as major-unit decimals (e.g. "1.00" / a `{amount, currency}` shape), not raw cents. An agent that interprets `price: 900` together with `currency: USD` as $900.00 (the natural reading of a product-feed price field paired with an ISO currency) would advertise/charge a price 100x too high — or, conversely, treat the $1.00 pack's `price: 100` as $100. The internal checkout path is unaffected (build_line_items uses amount_cents as cents correctly), but the public DISCOVERY surface that agents read to decide what to buy carries an ambiguous/likely-wrong-unit price. Round 1 flagged only the currency CASE (USD vs usd) and the image_url; the price-unit/type defect is new and is a money-path issue on the buyer-facing surface.

#### U109 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**Charge is executed BEFORE the fulfillment dedup, so a session that was fulfilled-but-not-marked-completed re-charges; relies entirely on Stripe idempotency_key, which the fail-closed/Null path and any non-Stripe processor do not provide**

`acp/router.py:complete_session() lines 257-290`

On /complete the order: (1) compute amount, (2) payment.charge(...) at line 262, (3) only afterward fulfill_once at line 290. If a prior /complete charged and fulfilled but crashed before _persist set status=COMPLETED (line 332-337), the session is still READY, so a retry re-enters the charge at line 262. Double-charge is prevented ONLY by passing idempotency_key=f'acp-charge:{session_id}' to Stripe (line 265). This is sound for StripeSPTPaymentClient but is an implicit, fragile contract: any payment client that does not honor that idempotency key (a future processor, or a misconfigured Stripe call) will charge twice while fulfill_once returns False — money taken, no extra credit. The correct design charges only after confirming the session is not already fulfilled, or records the charge intent transactionally with fulfillment. The 'crash-retry-safe' claim in the docstring is only true for one specific processor.

#### U110 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**Charge can succeed while fulfillment/persist throws, leaving money captured and session left in ready_for_payment with no completion record**

`acp/router.py:complete_session, lines 262-339`

After `result = payment...charge(...)` returns ok (line 262-267), the code calls store.get_account_by_api_key / store.create_account / store.fulfill_once / receipts.sign / store.save_receipt / _persist / _complete_idempotency (lines 286-338). If ANY of these raises (DB locked/IO error, save_receipt failure, JSON serialization, etc.), the exception propagates as an unhandled 500: the session is NOT persisted as completed, the idempotency key is NOT completed (left 'processing'), but the Stripe charge already captured funds. Recovery depends entirely on the client retrying within the 60s idempotency window (store.py:103) AND the Stripe idempotency key (acp-charge:{session_id}) deduping the re-charge. If the client does not retry, or retries after 60s with a different body/key, the buyer has paid and received nothing, and no order receipt exists. The charge-then-credit ordering has no compensating action (no refund, no durable 'charged-but-unfulfilled' marker). At minimum the post-charge work should be wrapped so a failure marks the session recoverable and the idempotency key is not stranded.

#### U111 · 🟠 HIGH · conf: medium · `auth` · rounds: R1

**ACP bearer token is never validated against issued keys — any attacker-supplied token mints/credits an account**

`acp/router.py:complete_session, lines 287-290 (and _gate lines 79-93)`

The ACP gate (_gate) accepts ANY non-empty `Authorization: Bearer <x>` value as `api_key` with no verification that it is a real, issued key. In complete_session, `store.get_account_by_api_key(ctx.api_key)` is looked up and, if not found, `store.create_account(api_key=ctx.api_key, plan='free')` creates a brand-new account whose api_key is exactly the attacker-chosen string. This means (a) authentication is effectively absent — the bearer token is self-asserted, and (b) an attacker who later guesses or learns another tenant's api_key string can complete a checkout and have credits applied to that account; conversely a caller controls what api_key value seeds a new account. There is no allowlist, no signature, no hashing — the credential and the account identity are whatever the client sends. For a money/credit path this is an auth weakness: credits are granted on the strength of an unverified, client-chosen secret. <!-- allow-secret false-positive: quoted source-code example -->

#### U112 · 🟠 HIGH · conf: medium · `auth` · rounds: R1

**ACP bearer token is never authenticated — any non-empty string is accepted as the buyer identity**

`acp/router.py:_gate (72-93)`

_gate extracts the Bearer token and only checks it is non-empty (router.py:80-83). It is never compared against a stored/known API key. In complete_session the same unauthenticated ctx.api_key becomes the account key: store.get_account_by_api_key(ctx.api_key) and, if missing, store.create_account(api_key=ctx.api_key) (router.py:287-289). Consequences: (1) an attacker can pick any api_key value and have credits fulfilled to an account they control, or to a victim's account if they learn/guess the victim's api_key (api keys are uma_+token_urlsafe(32) so guessing is hard, but there is no auth boundary preventing a chosen-key takeover where the attacker is the one paying); (2) because the token is self-asserted, credit attribution is entirely client-controlled. The bigger issue is the same token is used elsewhere (triage) where it grants no entitlement at all. At minimum the ACP gate should authenticate the bearer token against issued keys rather than accept any string. <!-- allow-secret false-positive: quoted source-code example -->

#### U113 · 🟠 HIGH · conf: medium · `race / state-machine` · rounds: R2

**Completed session's created_at preserved but data_json fully replaced each persist — concurrent failed and successful /complete race to last-writer-wins on the whole row including status**

`acp/router.py:337 _persist + store.save_session 407 INSERT OR REPLACE`

save_session uses INSERT OR REPLACE keyed on id (store.py 407-413). Two concurrent /complete requests (one that succeeds charge+fulfill, one whose charge fails) each call _persist at the end. There is no compare-and-set on status; whichever commits last wins the entire data_json blob. A failed-payment _persist (status=READY, account_id=NULL) committing AFTER the success _persist (status=COMPLETED, account_id=acct) will overwrite the row back to READY with the order/account_id dropped — even though fulfill_once already, atomically and correctly, applied the credit. The durable session state then says READY while the buyer is credited, making the session completable again (re-charge attempt) and the order receipt orphaned. Round 1 mentioned last-write-wins resurrecting READY over COMPLETED at medium; this pins the exact INSERT OR REPLACE mechanism and the resulting re-completability after a real credit.

#### U114 · 🟠 HIGH · conf: medium · `correctness/money-arithmetic` · rounds: R2

**IDOR at /complete: a second account completing the same session is charged but credited nothing (fulfill_once keyed by session_id, not account)**

`acp/router.py:complete_session lines 287-290 + store.fulfill_once line 365-389 (PRIMARY KEY session_id)`

fulfill_once dedups on session_id alone (acp_fulfillments PRIMARY KEY is session_id, store.py line 93). complete_session resolves/creates the account from the CALLER's bearer (lines 287-289), then calls fulfill_once(session_id, account['id'], total_runs). Because get_session/complete have no ownership check (round-1 IDOR), a DIFFERENT bearer B can call /complete on account A's READY session. The charge at line 262 still executes against B's delegated token (B is charged real money), but fulfill_once returns False (session already fulfilled by A's earlier completion, or fulfills to B leaving A uncredited). On the already-fulfilled path the order branch is skipped, B gets status=completed with an 'already_fulfilled' info message and NO credits and NO order receipt — B paid and received nothing. This is a money-loss consequence of the IDOR distinct from the round-1 'credits to wrong account' finding: here the charge and the credit land on different parties because the dedup key ignores the payer.

#### U115 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**subscription.updated with missing/None status silently skips status write, risking stale access grants**

`api/billing.py:_handle_event lines 248-262 (subscription.updated) -> store.set_subscription`

For customer.subscription.updated, status = obj.get('status'). If Stripe's payload lacks a 'status' field (or it is null), status is None. set_subscription only writes non-None fields, so the account's status column is silently left unchanged while plan IS updated from the price. This can leave an account with a paid plan but a stale/incorrect status, and entitlements_for() keys access off status (active/trialing). A subscription.updated that should downgrade but arrives without an explicit recognized status will not revoke. More generally, relying on obj.get('status') being one of the known strings is fragile; an unexpected status string flows straight into the DB and into entitlement gating.

#### U116 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**_resolve_account can create a brand-new free account on subscription events, fragmenting customer state**

`api/billing.py:_resolve_account lines 208-219`

If account_id is absent/unknown AND customer_id has no existing mapping (e.g. a customer.subscription.updated whose metadata.account_id was lost, or arriving before checkout.session.completed linked the customer), _resolve_account falls through to store.create_account(account_id=account_id, plan='free'). When account_id is None this mints a NEW random acct_ id that is unlinked from the real buyer, and the subscription state is applied to that orphan account. The paying user's real account never receives the grant. Webhook ordering from Stripe is not guaranteed, so subscription.created/updated can legitimately precede checkout.session.completed.

#### U117 · 🟠 HIGH · conf: medium · `auth` · rounds: R1

**Checkout/portal accept arbitrary account_id with no ownership/auth check — an attacker can attach a subscription to or open a billing portal for someone else's account_id**

`api/billing.py:create_checkout lines 105-143 and create_portal lines 146-167`

create_checkout takes req.account_id and create_portal takes req.account_id/customer_id with no authentication that the caller owns that account. create_portal will look up get_account(req.account_id), pull its stripe_customer_id, and open a Stripe Customer Portal session for it — letting an attacker who guesses/knows an account_id manage another customer's billing (cancel, change plan, view invoices). account_ids are acct_+token_hex(12) (96 bits) so not trivially guessable, but the portal endpoint performs no authorization and returns a working portal URL for any resolvable customer. This is an IDOR/authz gap on the billing surface.

#### U118 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**_resolve_account silently creates a NEW free account when metadata account_id and customer mapping both miss — can orphan the real grant**

`api/billing.py:_resolve_account() lines 208-219`

If account_id is present but store.get_account(account_id) returns None (e.g. the account row was never created, or the id is stale/foreign), AND customer_id has no existing mapping, the function falls through to create_account(account_id=account_id, plan='free') and returns the NEW id. For checkout.session.completed this means the subscription/grant is written onto a freshly-minted account that the buyer's session/api-key may never reference, so the paying customer never receives entitlements (money taken, access not granted). It also means a webhook with an attacker-controlled metadata account_id (Stripe metadata is set at checkout creation, but a compromised or malformed event) silently provisions accounts. At minimum this should not silently fabricate an account on the grant path without linking the customer id.

#### U119 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**checkout.session.completed grants 'active' without verifying payment_status; an unpaid/async checkout can grant access**

`api/billing.py:_handle_event() checkout.session.completed lines 225-238`

On checkout.session.completed the handler unconditionally calls set_subscription(status='active'). Stripe sends checkout.session.completed even when payment_status is 'unpaid' (e.g. async payment methods, or mode=subscription with a trial/incomplete) — the canonical guidance is to check session.payment_status == 'paid' (or rely solely on invoice.paid / subscription.status). Here obj.get('payment_status') is never inspected, so a session completed but not paid grants active paid entitlements until a later subscription event corrects it (and per the other findings, that correction can no-op). This is a 'access granted without settlement' path.

#### U120 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**invoice.paid blindly sets status='active', resurrecting canceled/expired subscriptions**

`api/billing.py:_handle_event invoice.paid branch (265-270)`

On invoice.paid the handler does store.set_subscription(account_id=acct['id'], status='active') for whatever account maps to the customer, with no check of the current subscription state and without setting/validating the plan. Stripe can emit invoice.paid for a final proration, a past invoice, or an out-of-order redelivery after a customer.subscription.deleted already dropped the account to plan='free'/status='canceled'. Because set_subscription only writes the fields passed (status), this flips status back to 'active' while leaving plan='free' — but entitlements_for treats status active + plan free as Free floor, so the immediate grant impact is bounded. The real hazard is ordering: if invoice.paid arrives AFTER an updated event that set plan='pro' and then a delete that set plan='free', or interleaves with a past_due, the account can end up 'active' on a stale plan. Status should be derived from the subscription object, not assumed active on any paid invoice. Subscription status from Stripe is supposed to be the single source of truth (per the module docstring), but this branch overrides it with an assumption.

#### U121 · 🟠 HIGH · conf: medium · `security` · rounds: R1

**Attacker-influenced subscription metadata.account_id is used verbatim as the new account primary key**

`api/billing.py:_resolve_account line 218; create_account in store.py:155`

_handle_event line 246 reads meta_account = obj['metadata']['account_id'] and passes it to _resolve_account, which at line 218 calls create_account(account_id=meta_account, ...). Subscription metadata originates from whoever created the subscription/checkout session, not from a trusted server-side source. If that id does not already exist, the value is used directly as the accounts.id primary key (store.py:155 only generates a random id when account_id is falsy). This lets the metadata author choose/predict the primary key of a freshly created account (account-id squatting / pre-creation of a known id), and if account_id is None a random account is minted instead. Combined with the orphan-creation path above, the webhook turns Stripe-event metadata into write access over the accounts identity table.

#### U122 · 🟠 HIGH · conf: medium · `error-handling` · rounds: R1

**set_subscription can hit the UNIQUE(stripe_customer_id) constraint, raising 500 and an infinite Stripe retry loop**

`api/billing.py:_handle_event lines 255-262; store.set_subscription store.py:206-219; schema store.py:45 (stripe_customer_id TEXT UNIQUE)`

accounts.stripe_customer_id has a UNIQUE constraint (store.py:45). In _handle_event, a subscription event resolved via metadata.account_id to account B (because meta_account exists) then calls set_subscription(account_id=B, customer_id=cus_1). If cus_1 is already linked to a different account A (e.g. A was created/linked by an earlier checkout.session.completed, or two events for the same customer interleave under different account_ids), the UPDATE setting stripe_customer_id=cus_1 on B violates UNIQUE and raises sqlite3.IntegrityError. That exception is not caught in set_subscription, so it propagates up to the webhook handler (lines 197-202) as a 500. Because the event is then NOT marked processed (mark_event_processed only runs after a clean _handle_event), Stripe will redeliver indefinitely, and every redelivery 500s again — a stuck, alerting-noisy event that never drains.

#### U123 · 🟠 HIGH · conf: medium · `logic` · rounds: R1

**Receipt signs the gate's own self-reported summary, not an independently re-derived one — attests 'server emitted these counts', not 'counts are true'**

`api/receipts.py:signed_body, lines 77-85 (with core/audit.py summary/assert_no_violations 241-259, api/service.py 127-133)`

`signed_body` signs `triage_result.get('audit')`, which is exactly `audit.summary()` — the AuditLog's own counters. The fail-closed boundary `assert_no_violations()` and `summary()['violations']` both read the same `self.violations` list that `record()` populated. So the signature only attests that the server emitted a self-consistent count, not that the count is correct. If a regression caused `record()` to mis-derive protection or mis-classify a left-inbox disposition such that `violations` stayed empty while a protected sender actually left the inbox, then (a) `assert_no_violations` would NOT raise, the run returns 200, and (b) the receipt faithfully signs the wrong-but-self-consistent body. The cryptographic signature gives the receipt an air of independent authority it does not have: it is a signature over the gate's own self-report, computed in the same process from the same in-memory counters. There is no second, divergent re-derivation feeding the signed body. This is the trust-artifact gap the docs imply is closed ('independent receipt') but is not at the signing layer.

#### U124 · 🟠 HIGH · conf: medium · `money-path` · rounds: R1

**fulfill_once credits the account but does NOT verify the account row exists; an INSERT-OR-IGNORE fulfillment + UPDATE on a nonexistent account silently credits nothing yet returns True**

`api/store.py:fulfill_once() lines 365-389`

fulfill_once inserts the fulfillment row (rowcount checked) then UPDATE accounts SET run_credits = run_credits + ? WHERE id = ?. If account_id does not exist (e.g. a race where the account was deleted, or a wrong id passed), the UPDATE affects 0 rows but rowcount is not checked, and the function still returns True. The caller (router.complete_session) treats True as 'credited' and mints a signed order receipt claiming runs_credited=N. Result: receipt asserts N runs credited, but the balance was never incremented — a receipt that lies about settlement. The fulfillment row is also now recorded as done, so a retry will NOT re-credit. The UPDATE rowcount should be asserted > 0 inside the same transaction.

#### U125 · 🟠 HIGH · conf: medium · `concurrency` · rounds: R1

**60s stale-claim re-grant of an idempotency key can double-execute a non-idempotent action (acp.create mints a duplicate, orphaned session)**

`api/store.py:334-347 (idempotency_begin stale-claim window) + acp/router.py 166-190 (create_session)`

When an idempotency key is in status 'processing' and more than IDEMPOTENCY_PROCESSING_TIMEOUT (60s, line 103) has elapsed since created_at, idempotency_begin rebinds the row to the new request_hash and returns {'state':'new'} (lines 337-344), letting the caller proceed. The comment assumes the original holder crashed. But the timeout cannot distinguish a crashed request from a legitimately slow in-flight one. Two concrete double-execute paths: (1) acp.create -- create_session (router 183) generates a FRESH session id via _new_session_id() on every 'new' return. If the original create is still running at 60s (e.g. blocked on the serialized lock above, or slow body parse), a retry re-claims the key and creates a SECOND checkout session. The two sessions get different ids; whichever idempotency_complete (line 189) runs last overwrites the stored response, so the buyer's retry sees session B while session A is orphaned in acp_sessions -- and either session can later be completed/charged independently. (2) acp.complete -- if a /complete is genuinely slow past 60s, the retry re-claims 'new' and re-enters the charge+fulfill path. Here the session-keyed Stripe idempotency_key (router 265) and fulfill_once (store 365) DO dedup the money, so no double charge -- but the 60s window is the wrong guard: it should be much larger than any plausible request latency, or the reclaim should be gated on additional liveness signal. Net: the value of the timeout is real (prevents permanent 409 DoS) but 60s is aggressive enough that on the lock-serialized hot path a backlog could legitimately exceed it, defeating the at-most-once guarantee for the not-otherwise-deduped acp.create/update/cancel scopes.

#### U126 · 🟠 HIGH · conf: medium · `correctness/transaction-boundaries` · rounds: R2

**Webhook dedup mark and the handler's side-effect writes are not in one transaction, so a crash between them re-processes the event (or marks-then-loses it)**

`api/store.py:mark_event_processed 253-260 + api/billing.py 191-203 (separate commits on shared connection)`

In billing.py the flow is: is_event_processed -> _handle_event (which performs its own committed set_subscription/create_account writes) -> mark_event_processed (a separate INSERT+commit). Each store method commits independently on the single shared connection; there is no enclosing transaction spanning the side effects and the dedup record. If the process crashes (or set_subscription's transaction is left dangling per the other finding) after _handle_event commits but before mark_event_processed commits, Stripe redelivers and _handle_event runs again. While set_subscription is mostly idempotent, _resolve_account -> create_account is NOT fully idempotent (it can create a second account when the customer mapping is not yet linked), so the re-run can fork accounts. The store offers no transactional API to bundle the dedup insert with the effect, which defeats the 'never double-grant or double-credit' guarantee the module docstring claims. Round 1's store.py findings do not mention mark_event_processed or its non-atomicity with the handler.

#### U127 · 🟠 HIGH · conf: medium · `regex` · rounds: R1

**combined_text space-joins sender and subject, letting subject tokens satisfy sender/domain-anchored patterns (the .gov-anchor root cause)**

`core/models.py:combined_text property lines 55-58`

combined_text returns f"{self.sender} {self.subject}".lower() — sender and subject flattened into ONE string with a single space separator. The categorization engine matches LABEL_RULES regex patterns against exactly this shape (core/rules.py:1007-1008 builds the identical f"{sender} {subject}".lower() and core/rules.py:1032 does re.search(pattern, combined_text)). Because there is no boundary marker between the sender field and the subject field, a pattern intended to anchor on a *sender domain* (e.g. a '.gov' or 'bank.com' substring) can be satisfied by text appearing only in the SUBJECT — an attacker or a quirky subject line ('Re: my new bank.com password', 'forwarded from irs.gov') can cause mis-categorization into a higher-trust/priority label. This is a model-level expression of the same root cause behind the .gov-anchor finding: the single combined string conflates two semantically distinct fields. Note also the rules engine duplicates this string inline rather than calling msg.combined_text, so any hardening of the property would not propagate. Fix: match sender and subject separately (or insert a separator the patterns can anchor against / restrict domain-anchored patterns to the sender field only).

#### U128 · 🟠 HIGH · conf: medium · `correctness` · rounds: R1

**IMAP archive COPY+\Deleted+EXPUNGE per message calls mailbox-wide expunge in a loop; unchecked STORE and expunge can delete unrelated flagged mail or leave duplicates**

`icloud_triage.py:archive_uid(), lines 63-77`

When UID MOVE is unsupported, the fallback does COPY -> 'STORE +FLAGS \Deleted' -> imap.expunge(). expunge() permanently removes EVERY message flagged \Deleted in the selected mailbox, not just this uid — if any other message in INBOX already carries \Deleted (or a prior iteration flagged one whose COPY later failed), it is destroyed. Called once per archivable uid inside the loop (main lines 161-165), so it's repeated mailbox-wide expunges (slow and broad). The STORE result is not checked; if +\Deleted fails, the message is COPIED to Archive but remains in INBOX (duplicate). Safer: collect uids, COPY all, then a single UID EXPUNGE (RFC 3501 UIDPLUS) scoped to those uids, or rely on MOVE only. The protected gate itself looks correct (fail-closed on empty From).

#### U129 · 🟠 HIGH · conf: medium · `correctness` · rounds: R1

**COPY+Delete+EXPUNGE fallback expunges entire mailbox, not just the message**

`icloud_triage.py:archive_uid lines 70-77 (COPY fallback)`

When UID MOVE is unsupported, the fallback does `COPY` then `STORE +FLAGS \Deleted` then `imap.expunge()`. expunge() (non-UID) permanently removes ALL messages in the selected mailbox that carry the \Deleted flag — not just this uid. If any other message in INBOX already has \Deleted set (e.g. from a prior interrupted run or another client), this loop will permanently delete those too. Should use UID EXPUNGE (RFC 3501 UID EXPUNGE / `imap.uid('EXPUNGE', uid)` where supported) or batch the expunge once at the end with explicit awareness. Potential unintended permanent deletion.

#### U130 · 🟠 HIGH · conf: medium · `auth / metering` · rounds: R2

**MCP triage tool exposes destructive mailbox mutation (dry_run=False) with no authentication, metering, or credit consumption**

`mcp_server/server.py:triage tool lines 109-127 (dry_run default True, no auth/metering)`

The MCP 'triage' tool, when called with dry_run=False, drives service.run_triage which actually archives/moves mail. The MCP endpoint is mounted at /mcp with only DNS-rebinding host protection (no bearer/auth, no plan check, no consume_credit). This is the MCP-layer instance of the round-1 'triage endpoints unauthenticated/unmetered' finding (which cited api/app.py), but it is a distinct, separately-reachable surface: an agent reaching /mcp can mutate the server operator's connected mailbox and consume provider quota for free. Reported as a NEW location of the same class.

#### U131 · 🟠 HIGH · conf: medium · `correctness` · rounds: R1

**Standard-IMAP archive does COPY then unconditional +FLAGS \\Deleted but never EXPUNGE; message remains until expunge and is destructive without confirmation**

`providers/imap.py:archive 312-326`

For non-Gmail IMAP, archive copies to 'Archive' then sets \Deleted on the original. (1) It never EXPUNGEs, so the message stays in INBOX marked deleted — not actually archived from the user's view until something expunges; and many clients hide \Deleted, making it look gone while still present. (2) If a later expunge runs (by this or another client/session), the original is permanently destroyed; combined with the COPY-status-only check, if COPY reported OK but the copy is incomplete the original could be lost. Data-loss-adjacent behavior on the archive path. Also 'Archive' folder is assumed to exist (no ensure_label_exists call) — COPY to a nonexistent folder returns NO and archive returns False, but the message was not deleted (safe) — still, behavior is inconsistent with the gmail branch.

#### U132 · 🟠 HIGH · conf: medium · `injection` · rounds: R1

**AppleScript injection / breakage via unescaped message_id interpolated as a raw literal**

`providers/mailapp.py:apply_label / move script line 263-270; get_message_details 211-228; star 295-301; unstar 311-317; mark_read 360-366; mark_unread 376-382`

message_id is f-string interpolated directly into AppleScript as `whose id is {message_id}` (an unquoted token) across apply_label, get_message_details, star, unstar, mark_read, mark_unread. Although Mail.app message ids are normally integers, the value originates from list_messages parsing (msg_id = parts[0] of a tab-split osascript line) and is typed str throughout EmailMessage.id with no validation. If an id ever contains non-numeric content (e.g. a sender field bled into the id column on a malformed/blank line, or a future provider id scheme), the script either errors or executes attacker-influenced AppleScript. Because it is placed as a bare expression (not a quoted string), any whitespace/operators in the value change the script's meaning. This is the classic AppleScript-injection vector the task calls out. Validate that message_id matches ^[0-9]+$ before interpolation.

#### U133 · 🟠 HIGH · conf: medium · `injection` · rounds: R1

**AppleScript injection via unescaped mailbox/label/account names with embedded double-quotes**

`providers/mailapp.py:list_messages 135-169 (account_filter/mailbox), apply_label 263-270 (label), ensure_label_exists 335-346 (label), get_mailboxes 411-417`

label, mailbox, and self.account are interpolated into AppleScript inside double quotes (e.g. `mailbox "{label}"`, `of account "{self.account}"`, `make new mailbox with properties {{name:"{label}"}}`). A label or account name containing a double-quote or backslash terminates/escapes the AppleScript string literal, breaking the script or allowing arbitrary AppleScript to be appended. Labels come from the rule taxonomy and config (`vip_senders`/custom rules can introduce arbitrary label strings), and account names are user config. No escaping of `"` or `\` is performed anywhere before interpolation.

#### U134 · 🟠 HIGH · conf: medium · `api-misuse` · rounds: R2

**Graph rejects $orderby + $filter on different properties with HTTP 400 — the primary 'isRead eq false' pending/list query fails**

`providers/outlook.py:list_messages, lines 428-434 ($orderby 'receivedDateTime desc' combined with arbitrary $filter)`

list_messages always sets $orderby=receivedDateTime desc AND, when query is non-empty, $filter=<query>. Microsoft Graph imposes the constraint that when $orderby and $filter are combined, the $orderby properties must also appear (in order) at the start of the $filter, otherwise it returns 400 'The restriction or sort order is too complex...'. The cli passes query='isRead eq false' for Outlook pending (cli.py:642) and 'has:nouserlabels' as the default for all providers (round 1 #299). 'isRead eq false' + '$orderby receivedDateTime desc' is exactly the unsupported combination and will 400. The broad except at 436-440 then swallows it and returns an EMPTY result, so Outlook pending/filtered listing silently returns nothing. Round 1 flagged the $top concern (635) and the empty-on-error swallow (628) but not the structural $orderby+$filter 400 incompatibility that makes any filtered Outlook listing fail.

---

## 🟡 Medium (301)

| ID | Conf | Rounds | Category | Location | Title |
|---|---|---|---|---|---|
| U135 | high | R1 | test-quality | `.github/workflows/ci.yml:lines 33-63 (ruff step `set +e`; mypy step `set +e`)` | ruff and mypy run advisory-only (set +e) — lint/type regressions can never fail CI |
| U136 | high | R3 | ci/test-coverage | `.github/workflows/ci.yml:108-119 (smoke test)` | Cloudflare smoke test validates only a thin happy-path slice and would not catch the method/route/contract divergences |
| U137 | high | R3 | documentation/staleness | `AGENTS.md:5-16` | AGENTS.md describes only the legacy Gmail scripts and omits the entire unified CLI / multi-provider / API architecture |
| U138 | high | R3 | documentation | `CLAUDE.md:line 104 (Scheduling section) vs deploy.sh:62 / README.md:553` | Doc/install mismatch: CLAUDE.md tells users to check 'launchctl list \| grep com.user.gmail_labeler' but deploy installs com.user.mail_automation |
| U139 | high | R3 | deployment | `Dockerfile:line 12 (COPY . .)` | Dockerfile COPY . . ships logs, state, caches, and any local secrets into the image |
| U140 | high | R1 | config | `README.md:line 2 (Python-3.10+ badge) and line 241 (Prerequisites: Python 3.10 or later) vs CLAUDE.md:278 and api/app.py:34 / requirements-mcp.txt:2-3 / Dockerfile:7` | Three-way contradiction on the minimum Python version (3.9 vs 3.10) |
| U141 | high | R2 | test-quality | `acp/feed.py:build_feed lines 33-64 (and committed acp/product_feed.json); no test references build_feed` | No test asserts feed price equals the amount actually charged — a price/unit drift between feed and /complete charge would ship undetected |
| U142 | high | R1 | api-misuse | `acp/router.py:create_session/update_session/complete_session signatures (lines 167, 201-202, 236-237) vs _gate (72-93)` | Pydantic body validation runs before the auth/version gate, so malformed bodies bypass the gate and return a non-spec error envelope |
| U143 | high | R1 | api-misuse | `analyze_strategic_value.py:main lines 173-176 + analyze_dataset line 98` | Only fetches up to SAMPLE_SIZE but messages.list maxResults=2000 exceeds Gmail's 500 cap, silently returning fewer |
| U144 | high | R1 | resource-leak | `api/app.py:_run lines 124-130` | Receipts are persisted (and run_ids minted) even for dry_run previews, mixing speculative previews into the durable audit ledger |
| U145 | high | R2 | correctness | `api/billing.py:_period_end 294-303 / set_subscription current_period_end` | current_period_end is read but a None/expired value never downgrades entitlements — and _period_end only set on subscription.* events, never on invoice.paid |
| U146 | high | R1 | dead-code | `api/plans.py:entitlements_for (181-193)` | entitlements_for trusts account['run_credits'] via int(...) without guarding non-int/None stored values, and is dead code on the live path |
| U147 | high | R1 | money-path | `api/plans.py:monthly_run_cap field (37) and per-plan values (74, 92, 111)` | monthly_run_cap is consumed only by the marketing-artifact generator, never by runtime enforcement |
| U148 | high | R1 | money-path | `api/plans.py:METERED_ADDON (130-139)` | Metered per-run billing advertised but no Stripe Meter event is ever emitted |
| U149 | high | R2 | dead-code | `api/plans.py:entitlements_for return dict, line 192 (run_credits) — combined with no caller` | entitlements_for surfaces run_credits but, being uncalled, the credit balance is read by nothing for any access decision — deeper instance than round 1's consume_credit note |
| U150 | high | R1 | money-path | `api/service.py:run_triage (70-135)` | run_triage is the single triage chokepoint and accepts no caller identity — enforcement has no insertion point that is actually used |
| U151 | high | R1 | money-path | `api/store.py:schema (41-98); add_credits (223-233); fulfill_once (365-389)` | run_credits is a write-only balance — granted by ACP fulfillment and add_credits, never read for an access decision |
| U152 | high | R1 | concurrency | `api/store.py:118-138, 425-437 (Store.__init__, _fetch_one/_fetch_all)` | Single shared connection serialized by one RLock negates WAL read concurrency (docstring claim is false) |
| U153 | high | R1 | concurrency | `api/store.py:130-137 (Store.__init__ PRAGMA block)` | No PRAGMA busy_timeout set: any second connection to the DB file fails immediately with 'database is locked' |
| U154 | high | R2 | schema/referential-integrity | `api/store.py:_SCHEMA 62-97 (no FOREIGN KEY); __init__ 130-137 (no PRAGMA foreign_keys=ON)` | No foreign-key constraints or enforcement: receipts/acp_sessions/acp_fulfillments accept arbitrary account_id, allowing orphaned ledger and credit rows |
| U155 | high | R2 | correctness/logic | `api/well_known.py:build_agent_manifest lines 17-51 (protocols/agentic_commerce, oauth_scopes); cf. api/plans.py METERED_ADDON line 130, gen_commerce_artifacts.py` | Agent discovery manifest advertises a metered/credit-pack commerce surface and verified-safe paid runs that the engine never meters or debits — false self-description to autonomous agents |
| U156 | high | R1 | silent-failure | `archive_old_inbox.applescript:lines 16-20` | Bare try with no on-error swallows all move failures silently |
| U157 | high | R1 | secrets | `auth/onepassword.py:op_item_edit, lines 111-117` | Secret passed as 1Password CLI argument is exposed in process listing / shell history |
| U158 | high | R1 | secrets | `auth/onepassword.py:_run_op, lines 33-39` | Secret value passed as a command-line argument is exposed in process listing / argv |
| U159 | high | R1 | test-quality | `auth/onepassword.py:store_json_secret, lines 233-276; op_item_edit, lines 94-117` | No test coverage for the credential write/store boundary (store_json_secret, op_item_edit, FileNotFound/CalledProcessError paths) |
| U160 | high | R1 | silent-failure | `auto_drain.py:extract_domain() line 61-64; classify_domain() lines 66-88; callback line 121-129` | Bare 'except:' swallows all errors in domain extraction and batch callback, plus a too-loose keyword classifier |
| U161 | high | R1 | error-handling | `auto_drain.py:extract_domain() lines 60-64` | Bare except: swallows all errors and the domain split is fragile against display-name From headers |
| U162 | high | R1 | error-handling | `bulk_sweeper.py:run_sweep() lines 97-123` | batchModify and list calls have no error handling, no pagination, and an unchecked remove-label can erase intent |
| U163 | high | R1 | logic | `cli.py:run_labeler, lines 183-185, 293` | --limit counts built actions, not messages scanned; vip-only/protected/skip runs fetch far more than limit |
| U164 | high | R1 | resource-leak | `cli.py:cmd_health lines 504-517` | health connect/disconnect not in try/finally; failure after connect leaks the connection |
| U165 | high | R1 | correctness | `cli.py:cmd_label/cmd_summary/cmd_vip/cmd_escalate call load_config()+apply_vip_senders_from_config but cmd_pending does NOT` | cmd_pending omits VIP config loading, so pending output's is_vip/tier reflects only built-in VIPs, inconsistent with other commands |
| U166 | high | R1 | silent-failure | `cli.py:880-890 (cmd_escalate loop)` | cmd_escalate trusts age_hours=0 without detecting that the provider supplied no date |
| U167 | high | R1 | correctness | `cli.py:667, 675-676, 680, 694, 704 (cmd_pending)` | cmd_pending age column is always 0h and sort key is degenerate for non-Outlook providers |
| U168 | high | R1 | type-confusion | `cli.py:run_labeler, line 173 + 295 (total_processed = state.get_total(); total_processed += len(actions))` | Type confusion: corrupt state with non-int total_processed crashes run on first batch |
| U169 | high | R2 | security | `cloudflare/worker.mjs:senderCheck line 106 (value.includes('courts.ca.gov'))` | courts.ca.gov protection is spoofable via substring — 'x@courts.ca.gov.evil.com' matches includes() and is wrongly reported protected |
| U170 | high | R2 | security | `cloudflare/worker.mjs:senderCheck line 128 (chase.com) and line 153 fall-through (value.includes('chase.com'))` | chase.com protected only as a substring — 'support@chase.com.phish.net' reported protected, and any display name containing 'chase.com' triggers tier-1 Finance verdict |
| U171 | high | R2 | correctness | `cloudflare/worker.mjs:GET /v1/audit/{run_id} lines 282, 288-304` | /v1/audit returns identical 'protected_held:2, archived:1' counts for every run_id — receipts are not tied to any run and any enumerated id returns a 200 success receipt |
| U172 | high | R2 | correctness | `cloudflare/worker.mjs:triagePreview lines 172-198; reached from /v1/triage and /v1/triage/preview lines 255-263` | triagePreview fabricates archived/protected/labeled counts unrelated to any mailbox — the live 'triage' endpoints invent results from the limit parameter alone |
| U173 | high | R2 | test-quality | `cloudflare/worker.mjs:.github/workflows/ci.yml lines 108-119 (smoke test) vs worker behaviors above` | CI smoke test only asserts /health, /app/, plans-present, and one courts.ca.gov sender — none of the worker's protection/receipt divergences are caught |
| U174 | high | R2 | security/correctness | `cloudflare/worker.mjs:senderCheck lines 82-170 vs core/rules.py is_protected_sender (787-805), _decode_mime (624-633), _idna_decode (636-649), relay handling (676+)` | Worker omits MIME-decode, IDNA/punycode normalization, iCloud-relay recovery and self-mailbox match — homoglyph/relay/encoded protected senders are unprotected on the live site |
| U175 | high | R3 | deployment | `cloudflare/worker.mjs:lines 224-236 (serveApp) vs wrangler.toml lines 9-11` | Agent-discovery surfaces /.well-known/agent.json, /server.json, /pricing.md 404 on the Cloudflare share demo |
| U176 | high | R3 | logic/documentation-drift | `cloudflare/worker.mjs:150-169` | Worker senderCheck protected-sender logic is partially dead/incorrect vs documented protection set |
| U177 | high | R3 | routing/method-handling | `cloudflare/worker.mjs:238-322 (fetch dispatch) and 224-236 (serveApp)` | Wrong-method requests to API routes fall through to the static asset server instead of returning 405 |
| U178 | high | R3 | path-parsing | `cloudflare/worker.mjs:281-305` | /v1/audit/ with an empty run_id fabricates a receipt for the literal id 'demo' |
| U179 | high | R3 | api-divergence | `cloudflare/worker.mjs:153 vs 200-214 (billingPlans) and api/billing.py:94-103` | Worker /v1/billing/plans omits metered/credit_packs/currency that the real API returns |
| U180 | high | R3 | error-handling | `cloudflare/worker.mjs:216-222 (readJson) and 250-263` | readJson swallows all parse errors to {} so malformed/empty/non-JSON POST bodies return a 200 'success' instead of 400 |
| U181 | high | R3 | state-consistency | `cloudflare/worker.mjs:172-198 (triagePreview run_id) vs api/app.py:127 and web/index.html:642` | Preview always returns run_id 'demo_preview', but the UI/llms.txt promise 'each run gets a run_id' fetchable at /v1/audit/{run_id} |
| U182 | high | R3 | scheduling | `com.user.gmail_labeler.plist:whole file vs com.user.mail_automation.plist` | Two plists invoke the same run_automation.sh at the same 9:00 time — duplicate/overlapping schedule risk if both loaded |
| U183 | high | R3 | scheduling | `com.user.mail_automation.plist:lines 14-17` | Non-standard log directory (~/System/Logs) hardcoded — launchd will not create it and will fail to start the job if missing |
| U184 | high | R2 | security | `core/audit.py:lines 197-210 (record/_append entry), redact gating at 209-210; docstring 40-42` | Redacted ('shareable/committable') audit JSONL still writes raw provider message_id on every line |
| U185 | high | R1 | error-handling | `core/config.py:_apply_env_config() lines 273 and 263-297` | BATCH_SIZE env var crashes on non-integer value |
| U186 | high | R1 | config | `core/config.py:_apply_yaml_config, lines 194-195, 217-218, 196-197` | YAML batch_size/port/throttle_seconds assigned verbatim with no type validation or coercion |
| U187 | high | R1 | config | `core/config.py:_apply_yaml_config (189) and _apply_env_config (266-267)` | default_provider taken verbatim from YAML/env with no validation against the known provider set |
| U188 | high | R1 | config | `core/config.py:_apply_yaml_config (191) and _apply_env_config (268-269); consumed (not) at cli.py:48 and 1194-1195` | log_level loaded but never applied, and not validated against valid logging levels |
| U189 | high | R1 | dead-code | `core/config.py:_apply_yaml_config, lines 248-250; field declared 96; dataclass Config` | custom_rules loaded into Config but never applied to the rules engine (dead config knob) |
| U190 | high | R1 | silent-failure | `core/rules.py:1163-1185 (calculate_email_age_hours), specifically 1173-1174` | calculate_email_age_hours returns 0 for None date, conflating 'unknown age' with 'brand new' and masking the provider gap |
| U191 | high | R2 | regex | `core/rules.py:Tech/Security patterns lines 216-218 (r'login.*detected', r'new.*device', r'verification.*code')` | Tech/Security greedy .* patterns elevate ordinary marketing mail to Tier 1 Critical |
| U192 | high | R2 | regex | `core/rules.py:Personal/Government patterns lines 472-478 (r'passport', r'dmv', r'social.*security', r'state\.fl\.us')` | Government Tier-1 patterns 'passport'/'dmv'/'social.*security' bare-match generic subjects |
| U193 | high | R1 | silent-failure | `core/state.py:save() lines 91-95; _load() lines 48-56; clear() lines 125-129` | State save failure is logged and swallowed; corrupt state file falls back to default silently, risking reprocessing or skipped resumption |
| U194 | high | R1 | resource-leak | `core/state.py:save lines 91-95` | State file written non-atomically; crash mid-write corrupts resume state |
| U195 | high | R1 | time | `core/state.py:save, line 87 (last_run = datetime.now().isoformat())` | last_run uses naive local time while the rest of the codebase is UTC-aware |
| U196 | high | R1 | resource-leak | `core/state.py:save, line 92 (in-place truncating write)` | Non-atomic write: a crash or kill during save() can leave a truncated/corrupt state file |
| U197 | high | R4 | correctness | `create_smart_mailboxes.scpt:line 11` | Smart mailbox ships with literal placeholder 'your-name' — 'Needs Action' view is broken/empty unless hand-edited |
| U198 | high | R3 | broken-link | `docs/pitch/index.html:line 242` | CTA "View on GitHub" link points to stale/renamed org (organvm-iii-ergon) that only resolves via GitHub's rename redirect |
| U199 | high | R3 | stale-content | `docs/pitch/index.html:lines 199-205 (#market section) and 176-178 (#features)` | Pitch page shows placeholder marketing copy that contradicts the shipped, detailed pricing and feature set |
| U200 | high | R2 | correctness | `flag_important_senders.applescript:line 5` | Important-sender match uses substring `contains` on full From string — over-matches and is display-name spoofable |
| U201 | high | R1 | error-handling | `gmail_auth.py:get_credentials() lines 165-173` | Refresh catches only RefreshError; transient network errors crash and a post-refresh write-back failure is not isolated |
| U202 | high | R1 | dead-code | `gmail_labeler.py:_init_labels lines 120-122; process_batch lines 187, 224-226; categorize via core returns 'Misc/Other'` | Dead 'Uncategorized' removal logic — core categorizer returns 'Misc/Other', not 'Uncategorized' |
| U203 | high | R1 | correctness | `gmail_labeler_legacy.py:LABEL_RULES line 282; categorize_email line 364; label_all_unlabeled_emails lines 386,430` | Legacy catch-all label is 'Uncategorized' while core uses 'Misc/Other' (taxonomy divergence) |
| U204 | high | R1 | correctness | `gmail_labeler_legacy.py:LABEL_RULES (whole dict, lines 39-283) vs core/rules.py LABEL_RULES` | Legacy LABEL_RULES is a stale fork missing many categories and hardened patterns |
| U205 | high | R1 | regex | `gmail_labeler_legacy.py:LABEL_RULES lines 60, 95, 235, 239, 273 (patterns r"render\\.com", r"self\\.inc", r"builtin\\.com", r"e\\.godaddy\\.com", r"ibo\\.org")` | Double-backslash regex patterns match a literal backslash, so these senders never categorize |
| U206 | high | R1 | logic | `imap_rules.py:main, slice line 144: uids = uids[max(0, len(uids) - args.start - args.limit) : len(uids) - args.start]` | Paging slice computes a negative end index when start > len(uids), selecting wrong (oldest) messages |
| U207 | high | R4 | config | `llms.txt:lines 6-14` | All advertised endpoints use placeholder host mail.example.com, not the live uma.4444j99.dev |
| U208 | high | R4 | correctness | `llms.txt:line 3` | Headline trust claim ('signed audit receipt', 'never archives government/financial/legal/platform mail') contradicts the live worker.mjs |
| U209 | high | R3 | privacy | `mail_export.tsv:mail_export.tsv:1-2` | mail_export.tsv is git-tracked; currently header-only but the schema is sender/subject PII and the file is the AppleScript export target |
| U210 | high | R1 | correctness | `mark_rot_read.py:docstring line 3 vs query line 41` | Docstring says '>30 days' but query uses 'older_than:7d' (also comment says 7 days) — stale/inconsistent threshold |
| U211 | high | R1 | input-validation | `mcp_server/server.py:triage() lines 109-126, _triage() 129-146` | MCP triage tool does not bound/validate query and remove_label inputs |
| U212 | high | R2 | correctness | `mcp_server/server.py:_triage() lines 129-146 and triage()/triage_preview() return paths; cf. api/app.py:_run lines 124-130` | MCP triage returns no persisted/signed run_id receipt — the advertised 'verifiable audit receipt' is unverifiable on the MCP surface |
| U213 | high | R2 | error-handling | `providers/gmail.py:batch_get_details, line 248 (self._execute_with_backoff(batch.execute, "batch get"))` | Non-rate-limit error from batch.execute() is unhandled and crashes the entire triage/summary/escalate run |
| U214 | high | R1 | error-handling | `providers/imap.py:apply_label() / remove_label() / star() / mark_read() etc., lines 277-283, 301-307, 328-344, 361-377` | IMAP X-GM-LABELS / FLAGS STORE operations return True without checking the IMAP response status |
| U215 | high | R2 | error-handling / silent-failure | `providers/imap.py:star line 331, unstar line 340, mark_read line 364, mark_unread line 373` | IMAP star/unstar/mark_read/mark_unread ignore STORE response and report success on server rejection |
| U216 | high | R1 | correctness | `providers/mailapp.py:list_messages 160 and parsing 188-197` | Tab/newline in sender or subject corrupts TSV parsing of osascript output |
| U217 | high | R1 | silent-failure | `providers/mailapp.py:_run_applescript 81-84 / list_messages 171-175` | Timeout/osascript failure in list_messages silently returns empty result, masking errors and ending pagination early |
| U218 | high | R1 | injection | `providers/outlook.py:ensure_label_exists, 641-643` | OData $filter injection / breakage on folder names containing a single quote |
| U219 | high | R1 | silent-failure | `providers/outlook.py:apply_category, 343-364` | Read-modify-write of categories races and silently drops categories when the GET fails |
| U220 | high | R1 | api-misuse | `providers/outlook.py:_init_folder_cache, 253 and _fetch_child_folders 268` | Folder cache pagination not followed ($top 100 only) — mailboxes with >100 folders miss entries, causing duplicate folder creation |
| U221 | high | R1 | api-misuse | `providers/outlook.py:_api_get/_api_post/_api_patch, 213-232` | No handling of HTTP 429 throttling / Retry-After; raise_for_status turns throttling into a hard error with no backoff |
| U222 | high | R1 | silent-failure | `providers/outlook.py:_fetch_child_folders(), lines 264-274` | Bare 'except: pass' silently produces an incomplete folder cache, causing duplicate folders / wrong moves |
| U223 | high | R2 | datetime/timezone | `providers/outlook.py:line 574 (star, due_str = due_date.strftime("%Y-%m-%dT00:00:00Z"))` | Outlook due-date strftime hard-codes 'Z' (UTC) and zeroes the clock, mislabeling naive/local or non-UTC due_date at the wrong UTC date |
| U224 | high | R2 | error-handling | `providers/outlook.py:_api_get/_api_post/_api_patch 213-232; no 429 Retry-After handling on mutation calls` | No 429/Retry-After backoff on apply_label/apply_category/star mutation calls — bulk tier-routing aborts each item on throttle with no retry |
| U225 | high | R2 | security | `providers/outlook.py:ensure_label_exists 641-643` | OData injection in folder lookup ($filter displayName eq '{part}') |
| U226 | high | R3 | packaging | `pyproject.toml:lines 1-3 (entire file)` | pyproject.toml has no [project] table / build backend / console_scripts — package is not installable |
| U227 | high | R3 | correctness | `pyproject.toml:pyproject.toml (entire file) vs server.json:6-14` | server.json advertises a PyPI package universal-mail-automation 0.1.0 that the repo cannot build (pyproject.toml has no [project] metadata) |
| U228 | high | R1 | dependency | `requirements.txt:lines 2-11 (all `>=` lower bounds, no upper caps); also requirements-api.txt:3-8 (fastapi>=0.110, uvicorn>=0.29, httpx>=0.27, pydantic>=2.0)` | Dependency floors are unpinned (>= only) with no lockfile — an upstream minor can break the build silently |
| U229 | high | R2 | correctness | `route_bulk_senders.applescript:lines 9, 26-27` | Domain match runs against full From string including display name — display-name spoofing routes legitimate mail |
| U230 | high | R2 | config/consistency | `scripts/gen_commerce_artifacts.py:module docstring lines 5-11 and main() lines 96-109 (writes pricing.md, llms.txt, .well-known/agent.json, server.json — but NOT acp/product_feed.json)` | Commerce-artifact generator does not regenerate acp/product_feed.json — the feed is on a second, separate generation path and can drift |
| U231 | high | R1 | test-quality | `tests/test_acp.py:_OKPay.charge (26-27) used by test_complete_success_credits_and_emits_signed_order_receipt (117-138) and test_complete_is_idempotent_no_double_credit (141-153)` | Fake payment client ignores amount/currency/token/idempotency_key — charged amount never asserted |
| U232 | high | R2 | test-quality | `tests/test_acp.py:line 132 (and 153, 162)` | Test encodes the arbitrary-bearer-funding defect as intended behavior, locking in the broken identity model |
| U233 | high | R2 | test-quality | `tests/test_acp.py:whole file — no POST /acp/checkout_sessions/{id} update test (grep confirms only create/get/complete/cancel exercised)` | update_session (a price/items-mutating, money-relevant endpoint) has zero test coverage |
| U234 | high | R2 | test-quality | `tests/test_acp.py:_OKPay.charge lines 26-27 and test_complete_success_credits... lines 117-138` | Success-charge fake ignores the amount argument, so no test asserts the charged amount equals grand_total / equals the credited runs' price |
| U235 | high | R1 | test-quality | `tests/test_billing.py:module docstring (lines 1-5) and test_webhook_subscription_event_grants_and_dedups (52-85), test_webhook_handler_failure_not_marked_and_redelivery_grants (88-130)` | Docstring claims 'real signature path' but every grant test monkeypatches construct_event away |
| U236 | high | R2 | test-quality / import-time crash | `tests/test_billing.py:line 7 (import stripe) and line 14 (client = TestClient(app)); same module-level TestClient in test_api.py:10, test_acp.py:11, test_receipts.py:8, test_web.py:7` | Test modules construct TestClient(app) and import stripe at import time with no importorskip guard — pytest collection hard-crashes when optional API deps are absent |
| U237 | high | R1 | test-quality | `tests/test_store.py:test for consume_credit (39-43) and add_credits (38)` | Tests exercise consume_credit/add_credits in isolation, masking that no production path calls them |
| U238 | high | R1 | money-path | `web/index.html:PLANS array lines 688-703 (pro price_display '$29-$49', business '$149-$299')` | Pricing displayed on the web app diverges from the source-of-truth plans.py ($19/mo Pro, $49/mo Business) — customers see wrong prices |
| U239 | high | R2 | correctness | `web/index.html:static sample table line 522-525 (founder@client.example -> 'Stays') vs localSenderCheck lines 751-762` | Static sample-audit table disagrees with the live sender-check tool on the same demo senders |
| U240 | medium | R1 | correctness | `.github/workflows/ci.yml:lines 108-119` | Smoke test runs immediately after wrangler deploy with no propagation wait — flaky failures |
| U241 | medium | R1 | test-quality | `.github/workflows/ci.yml:line 30 (single combined `pip install -r requirements.txt -r requirements-api.txt -r requirements-mcp.txt`)` | The 3.9-isolation contract is undermined by always installing requirements-mcp.txt in CI |
| U242 | medium | R1 | security | `acp/feed.py:feed (lines 67-69) -> build_feed (33-64); also router.py _links (125-130) and permalink_url (321)` | Host header reflected into absolute feed/checkout/seller URLs (Host-header injection / cache-poisoning of the agent discovery surface) |
| U243 | medium | R2 | money/unit arithmetic | `acp/models.py:build_line_items lines 86-96 (base = int(pack['amount_cents']); subtotal = base * qty; total_runs += int(pack['runs']) * qty)` | Line-item subtotal and total_runs are unbounded int*qty products with no per-session amount cap before charging |
| U244 | medium | R2 | money/unit arithmetic | `acp/models.py:grand_total lines 100-101 and build_line_items lines 86-94 (base_amount/subtotal/total all integer cents); build_totals 104-111` | grand_total sums line_items 'total' which equals subtotal (tax always 0) — totals math diverges from build_totals and bakes in a no-tax assumption on the charged amount |
| U245 | medium | R2 | correctness/money-arithmetic | `acp/models.py:Item.quantity Field le=1000 line 27 + build_line_items line 96 (total_runs += runs*qty); plans.CREDIT_PACKS pack_1000 line 146-147` | Single ACP session can legitimately bill ~$9,000 / credit 1,000,000 runs with no high-value confirmation or per-session cap |
| U246 | medium | R2 | correctness/money-arithmetic | `acp/models.py:build_line_items line 79 (valid = bool(items)) + router.py create line 176/188 (_persist with total_runs)` | Empty-items create yields valid=False but is still persisted; downstream relies solely on status guard, not on amount/runs being zero |
| U247 | medium | R1 | error-handling | `acp/payment.py:charge except Exception (89-91)` | ACP charge swallows all exceptions into a generic 'charge failed', masking declines vs network vs config errors and any settlement ambiguity |
| U248 | medium | R2 | state-machine / idempotency | `acp/payment.py:67-97 (no idempotent re-read of an existing intent)` | Charge retry under same idempotency_key returns Stripe's replayed intent but never reconciles a previously-succeeded-then-uncredited charge |
| U249 | medium | R1 | auth | `acp/router.py:complete_session, lines 248-251 and 267-280 (idempotency interplay)` | Re-completing an already-completed session via a fresh Idempotency-Key skips charge but the early-return path also stores the completed response under the new key without re-validating ownership |
| U250 | medium | R1 | money-path | `acp/router.py:complete_session, lines 323-330 (already_fulfilled branch)` | On idempotent re-completion where fulfilled=False and a prior order exists, no order is re-attached but response still reports status completed — order may be dropped from the response |
| U251 | medium | R1 | auth | `acp/router.py:_gate, lines 79-83` | Bearer credential length is unbounded and unvalidated; arbitrary attacker-chosen strings become account api_keys |
| U252 | medium | R1 | auth | `acp/router.py:complete_session(), lines 286-290` | ACP /complete auto-creates an account from the bearer token, so any unauthenticated bearer can mint an account and be credited paid runs after a (configured) charge |
| U253 | medium | R1 | money-path | `acp/router.py:complete_session (267-280)` | Failed-charge 402 response is cached under the Idempotency-Key, locking out retries with that key |
| U254 | medium | R1 | money-path | `acp/router.py:complete_session (282-290)` | Charge happens before account resolution; a post-charge failure path credits nothing but already captured funds |
| U255 | medium | R1 | money-path | `acp/router.py:_begin_idempotency / create_session etc. (100-117, 166-190)` | Idempotency-Key is global (PRIMARY KEY on key alone), not scoped per api_key — cross-tenant key collision can leak another caller's response |
| U256 | medium | R1 | concurrency | `acp/router.py:complete_session (lines 287-289)` | TOCTOU race between get_account_by_api_key and create_account can raise an unhandled IntegrityError (500) |
| U257 | medium | R1 | money-path | `acp/router.py:complete_session charge block (262-290)` | Buyer is charged before the account is resolved/created and before fulfill_once — a non-fulfilling state path can charge money without minting a retrievable order |
| U258 | medium | R1 | logic | `acp/router.py:complete_session (287-289) and _persist account_id binding (149-155, 337)` | Account auto-provisioned at /complete is keyed only by api_key with no email/customer linkage, so ACP-purchased credits are orphaned from the Stripe-billing identity |
| U259 | medium | R2 | money/unit arithmetic | `acp/router.py:complete_session lines 257, 262-266, 304-310 (amount = grand_total; receipt summary 'amount': amount + 'currency': CURRENCY)` | Charged amount is taken from the stored session line_items, which an update_session call can re-price between create and complete with no re-binding to the original quoted price |
| U260 | medium | R2 | money/unit arithmetic | `acp/router.py:complete_session lines 257-266 (amount = grand_total(...); charge(amount=amount)) — no amount > 0 guard before charging` | No positive-amount guard before charging: a READY session whose line_items sum to 0 charges/fulfills $0 (deeper instance — a future zero-priced or mis-edited pack) |
| U261 | medium | R2 | state-machine / persistence | `acp/router.py:273-280 vs 337 (save_session via _persist)` | Payment-failed re-persist drops account_id binding via INSERT OR REPLACE |
| U262 | medium | R2 | money-correctness / idempotency | `acp/router.py:262-266, 282-290` | Stripe charge idempotency keyed on session_id, but fulfill dedup also keyed on session_id — an update that re-prices then re-completes cannot re-charge the delta |
| U263 | medium | R2 | state-machine | `acp/router.py:248-251 (already-completed early return) + 290` | Re-completing a COMPLETED session under a NEW Idempotency-Key returns the stored completed response but never charges — yet a session marked completed with fulfilled=False (credit-applied-but-not-persisted) is indistinguishable |
| U264 | medium | R2 | concurrency / error-handling | `acp/router.py:complete_session lines 287-290, 337` | create_account at /complete uses account['id'] without handling a concurrent-insert IntegrityError or None return |
| U265 | medium | R2 | correctness/money-arithmetic | `acp/router.py:complete_session line 257 vs acp/models.py build_totals line 104-111 / build_session line 138` | Buyer-displayed totals.total and the amount actually charged are derived from two different code paths and never compared |
| U266 | medium | R2 | correctness/money-arithmetic | `acp/router.py:update_session lines 217-225 (else branch keeps current['line_items'] but pulls total_runs from row['data']['total_runs'])` | update_session without items reads line_items and total_runs from two different stored locations, then re-shapes — desync entry point |
| U267 | medium | R2 | error-handling | `acp/router.py:complete_session line 290 fulfill_once + lines 295-317 order minting (order_id minted only when fulfilled=True, but charge already succeeded)` | Charge succeeds then fulfill_once True but save_receipt/save_session can raise, leaving funds captured with no retry path that re-mints the order |
| U268 | medium | R2 | error-handling | `api/app.py:lines 38-45 (try/except around `from mcp_server.server import http_app, mcp`)` | MCP import failure (including a missing/renamed `mcp` internal symbol) silently downgrades a paid `/mcp` endpoint to 404 at INFO log level |
| U269 | medium | R2 | correctness | `api/app.py:_run 127-129 / receipts.persist` | persist() always called with account_id=None on the public triage path, so every triage receipt is unattributed and list_receipts can never return them |
| U270 | medium | R1 | dependency | `api/billing.py:construct_event / _stripe lines 173-185` | Webhook references stripe.error.SignatureVerificationError without guaranteeing the attribute exists across Stripe SDK major versions |
| U271 | medium | R1 | concurrency | `api/billing.py:webhook() lines 194-204 vs mark_event_processed ordering` | Event marked processed only after success, but a handler that raises 500 leaves the read-gate open while a redelivery may already be mid-flight |
| U272 | medium | R1 | money-path | `api/billing.py:_handle_event() lines 240-262 (subscription.updated/created)` | status from obj.get('status') may be None and is written verbatim; entitlements then treat unknown/None status oddly |
| U273 | medium | R1 | money-path | `api/billing.py:_handle_event() lines 248-262, plan_id_for_price + 'unknown price -> keep current plan'` | Unknown Stripe price maps to plan_id=None, which is then written as the account plan, demoting a paying customer |
| U274 | medium | R1 | money-path | `api/billing.py:_handle_event() invoice.paid lines 265-270` | invoice.paid forces status='active' but never refreshes plan, so a downgraded plan stays downgraded while invoice.paid re-activates |
| U275 | medium | R1 | money-path | `api/billing.py:_period_end() lines 294-303` | current_period_end stored as raw Stripe epoch int with no timezone/units validation; entitlement code never enforces it |
| U276 | medium | R1 | money-path | `api/billing.py:_resolve_account (208-219)` | Webhook _resolve_account silently creates a brand-new free account when metadata account_id does not exist |
| U277 | medium | R1 | silent-failure | `api/billing.py:_first_price_id 280-284 + _handle_event 250-251; _checkout_plan_id 287-291; relies on plans.plan_id_for_price returning None` | Real subscription on an unconfigured/unmatched price silently leaves the plan unchanged with no log |
| U278 | medium | R1 | correctness | `api/billing.py:_handle_event line 248 (status = obj.get('status')) and 253 (drop-to-free set)` | Stripe status written verbatim with no validation; non-active states (incomplete/paused) keep the paid plan stored |
| U279 | medium | R1 | race-condition | `api/billing.py:_handle_event invoice.paid 265-270 and subscription events 240-263; no event ordering guard` | Out-of-order or replayed events (invoice.paid after subscription.deleted) can re-activate a canceled account |
| U280 | medium | R2 | state-machine | `api/billing.py:225-237 (checkout.session.completed)` | checkout.session.completed reads obj.get('subscription') which is None for one-time/payment-mode or async-payment sessions, writing subscription_id=NULL while granting active |
| U281 | medium | R2 | state-machine | `api/billing.py:253-260 (drop-to-free) + store.set_subscription 200-221` | On cancel/unpaid the handler sets plan='free' but does NOT clear stripe_subscription_id/customer_id, and status may still be a verbatim non-canceled Stripe value |
| U282 | medium | R2 | state-machine / idempotency | `api/billing.py:194-203 (handler exception -> 500) vs 191 (is_event_processed)` | A handler that partially succeeds then raises leaves a partial DB mutation but the event un-marked, so the full retry re-applies the already-applied partial writes |
| U283 | medium | R2 | state-machine / silent-failure | `api/billing.py:265-277 (invoice.paid / invoice.payment_failed both require customer_id)` | invoice.* events with no resolvable customer silently no-op, so a paid invoice for an account whose customer link was never written never activates |
| U284 | medium | R2 | correctness / data-integrity | `api/billing.py:_handle_event lines 245-262; obj.get('metadata') for subscription events` | Subscription events read metadata.account_id off the subscription object, but checkout-set metadata lives on subscription_data — orphan-account creation on real flows |
| U285 | medium | R2 | correctness | `api/billing.py:_handle_event customer.subscription.* 245-262; _resolve_account 208-219` | subscription.updated/created can move a Stripe customer_id onto a different account, and resolution prefers metadata account_id over the existing customer mapping |
| U286 | medium | R2 | api-misuse | `api/billing.py:_handle_event 222-277 obj.get('customer')` | Expanded Stripe objects: obj.get('customer'/'subscription') may be a dict (when expanded), used as a string id in get_account_by_customer/set_subscription |
| U287 | medium | R2 | correctness | `api/billing.py:cross-ref store.run_credits (ledger) vs entitlements_for line 192 — credits exposed but triage never debits` | entitlements_for returns run_credits (line 192) but no triage path reads or debits it; the number is reported to clients as a balance that never decreases |
| U288 | medium | R1 | money-path | `api/plans.py:entitlements_for() lines 175-193` | entitlements_for downgrades to free only on non-(active\|trialing) status but never checks current_period_end, and defaults missing status to 'active' — an account row with no/blank status keeps paid plan |
| U289 | medium | R1 | money-path | `api/plans.py:entitlements_for, line 184; cross-ref api/billing.py _handle_event line 248` | Account with NULL/unknown subscription status defaults to 'active', so an incomplete/unset-status subscription can be honored as paid |
| U290 | medium | R2 | money/unit arithmetic | `api/plans.py:METERED_ADDON lines 130-139 (unit_amount_cents=1, '$0.01 / triage run') vs CREDIT_PACKS lines 144-147` | Metered price ($0.01/run) and credit-pack prices are inconsistent: pack_1000 charges $9.00 for 1000 runs ($0.009/run) but metered advertises $0.01/run — overlapping price surfaces disagree |
| U291 | medium | R1 | security | `api/receipts.py:_signing_key() lines 44-57` | Ephemeral signing key fallback means receipts signed before RECEIPT_SIGNING_KEY is set verify as valid against a different (random) key, and silently become unverifiable after restart — a tamper-evidence gap |
| U292 | medium | R1 | money-path | `api/receipts.py:_signing_key (44-57)` | Ephemeral per-process signing key makes receipts unverifiable after restart and differ across replicas |
| U293 | medium | R1 | correctness | `api/receipts.py:_canonical lines 60-63 and get_receipt verify-instruction lines 137-140` | Published verification recipe omits ensure_ascii, breaking independent verification of receipts containing non-ASCII (e.g. the audit's ⚠ violation marker, unicode receipt_line) |
| U294 | medium | R1 | silent-failure | `api/receipts.py:persist, lines 88-108` | Receipt persistence is fully best-effort: a ledger write failure means the run returns 200 with a run_id whose GET will 404, with no signal to the client |
| U295 | medium | R2 | correctness / maintainability | `api/receipts.py:94-95 (sign over body) cross-ref acp/router.py 312` | Two independent receipt signing paths can diverge: ACP order receipt body shape (router 297-311) is hand-built and not produced by signed_body(), risking signature/verify mismatch if signed_body() ever changes |
| U296 | medium | R1 | concurrency | `api/store.py:idempotency_begin lines 313-353` | Idempotency claim has a check-then-insert TOCTOU race under the RLock-but-multi-statement design only protects within a process; cross-process it is unsafe, and even in-process the 'new' path is fine but stale-reclaim rebinds without verifying status |
| U297 | medium | R1 | error-handling | `api/store.py:create_account lines 145-165` | create_account does not handle UNIQUE constraint violations (stripe_customer_id / api_key), surfacing IntegrityError as an unhandled 500 |
| U298 | medium | R1 | concurrency | `api/store.py:idempotency_begin() lines 313-353 and idempotency_complete() lines 355-362` | Idempotency 'processing' stale-timeout rebinds the key to a new payload but a slow original request can still complete and overwrite the rebind, allowing two operations under one key |
| U299 | medium | R1 | secrets | `api/store.py:get_account_by_api_key, lines 170-175; schema line 50` | API keys stored in plaintext and matched by direct SQL equality (no hashing, not constant-time) |
| U300 | medium | R1 | concurrency | `api/store.py:idempotency_begin(), lines 334-344` | Stale 'processing' idempotency reclaim rebinds the key without resetting status to 'processing', and the 60s timeout can let a still-running original double-execute |
| U301 | medium | R1 | concurrency | `api/store.py:Store single shared connection + RLock, class-level; idempotency_begin lines 322-353` | Single global SQLite connection serialized by one RLock makes all DB writes a process-wide bottleneck and INSERT race window in idempotency_begin spans a non-transactional read+insert |
| U302 | medium | R1 | money-path | `api/store.py:idempotency_begin (334-347)` | Stale 'processing' idempotency entry is re-claimed as 'new', allowing the protected operation to re-run |
| U303 | medium | R1 | money-path | `api/store.py:save_session / _persist usage in acp/router.py update_session (200-232)` | ACP update_session can mutate a session's items/total without re-binding to the original idempotent create, enabling price/quantity change before complete |
| U304 | medium | R1 | auth | `api/store.py:create_account (145-165) and get_account_by_api_key (170-175)` | create_account silently accepts an arbitrary externally-supplied api_key, conflating server-issued credentials with caller-asserted strings |
| U305 | medium | R1 | concurrency | `api/store.py:355-362 (idempotency_complete) vs 337-344 (stale reclaim)` | idempotency_complete writes status='done' + response unconditionally — a stale-reclaimed key lets a late original writer clobber the retry's result (last-writer-wins on a rebound key) |
| U306 | medium | R1 | money-path | `api/store.py:118-138 (no isolation_level / synchronous configured)` | Default autocommit isolation_level left implicit; explicit per-method commit() means multi-statement methods are NOT atomic if a statement raises mid-way |
| U307 | medium | R2 | datetime/timezone | `api/store.py:line 337 (if _now() - existing["created_at"] > IDEMPOTENCY_PROCESSING_TIMEOUT) with _now()=time.time() at line 106-107` | Idempotency 'processing' abandonment window uses non-monotonic wall clock (time.time), so a clock step can prematurely free or permanently wedge a key |
| U308 | medium | R2 | correctness/silent-failure | `api/store.py:idempotency_complete 355-362` | idempotency_complete silently no-ops if the key row is absent (rowcount unchecked), so a lost claim leaves the key permanently un-finalized |
| U309 | medium | R2 | race | `api/store.py:idempotency_begin 322-353` | idempotency stale-reclaim updates request_hash/created_at but NOT status, so a crashed 'processing' key can be reclaimed yet still read as processing by a racing third request |
| U310 | medium | R1 | security | `api/well_known.py:agent_manifest() / llms_txt() lines 78-85, build_agent_manifest 17-51` | Manifest/llms.txt reflect the raw request base_url (Host header) — Host-header spoofing makes the self-describing surface advertise attacker-controlled URLs |
| U311 | medium | R2 | security | `api/well_known.py:agent_manifest 78-80 / llms_txt 83-85` | Discovery endpoints reflect request base_url into manifest URLs with no Host allowlist (cache-poisoning / link-spoofing) |
| U312 | medium | R1 | correctness | `archive_old_inbox.applescript:lines 15-21` | Mutating inbox collection while iterating skips messages (move during repeat-over-messages) |
| U313 | medium | R1 | error-handling | `archive_old_inbox.applescript:lines 9-13` | Resolving Archive mailbox can throw before the loop with no handling |
| U314 | medium | R1 | error-handling | `archive_sorted.py:archive_loop line 128-130` | HttpError handler breaks the category loop on a transient error, silently skipping remaining work |
| U315 | medium | R1 | correctness | `archive_sorted.py:senders_for() callback lines 61-68; archive_loop pagination lines 92-131` | Archive pagination re-runs the same query and breaks on len(ids)<1000, so >1000 protected-heavy pages can loop or miss messages; HttpError aborts the whole category |
| U316 | medium | R1 | logic | `archive_sorted.py:archive_loop lines 90-130 (query line 90); senders_for batch.execute line 79` | Gmail query uses unescaped category in label: and batch.execute has no error handling |
| U317 | medium | R1 | error-handling | `archive_sorted.py:senders_for() lines 70-79; batch.execute() line 79` | Unhandled batch.execute() exception aborts protected-sender gate before INBOX removal |
| U318 | medium | R1 | secrets | `auth/onepassword.py:op_item_edit() line 111; gmail_auth.py:57 _op_item_edit()` | Plaintext secret passed as a command-line argument to `op` (visible via process listing) |
| U319 | medium | R1 | api-misuse | `auth/onepassword.py:op_item_edit, line 111` | op item edit assignment arg breaks when field name contains '=' or value contains '=' |
| U320 | medium | R1 | injection | `auth/onepassword.py:op_item_edit, line 111; op_item_get, line 85; op_read, line 60` | User/env-derived item names or values starting with '-' can be parsed by op as flags (argv option injection) |
| U321 | medium | R1 | correctness | `auth/onepassword.py:parse_op_ref, lines 132-137` | parse_op_ref maps op:// fields with extra '/' segments into a single slash-joined field, which op edit cannot address as a nested field |
| U322 | medium | R1 | api-misuse | `auto_drain.py:drain_loop, line 157 + extract_domain line 60-64` | Gmail `from:{domain}` query may not match the raw extracted domain, causing zero moves (and feeding the infinite-loop) |
| U323 | medium | R1 | correctness | `auto_drain.py:drain_loop() lines 159-186` | batchModify failure only sleeps 5s and continues, double-counts moves, and pagination uses a fresh search each loop causing potential infinite loop |
| U324 | medium | R1 | injection | `auto_drain.py:drain_loop line 157 (query = f"from:{domain} label:{TARGET_SOURCE}")` | Gmail search-query injection via sender-derived domain |
| U325 | medium | R1 | logic | `auto_drain.py:drain_loop lines 100-199 (outer while True), 159-187 (inner while True), callback line 121` | Potential infinite loop and dropped errors in inbox drain |
| U326 | medium | R1 | error-handling | `bulk_sweeper.py:run_sweep line 91 (`if not add_id`) vs lines 88-89, 114` | Missing 'remove' label is silently tolerated, leaving source label attached forever |
| U327 | medium | R1 | config | `bulk_sweeper.py:SWEEP_RULES lines 26-69 vs core/rules.py taxonomy` | SWEEP_RULES target label names diverge from core taxonomy ('Work/Dev/Infrastructure', 'Work/RealEstate' not in LABEL_RULES) |
| U328 | medium | R1 | money-path | `bulk_sweeper.py:SWEEP_RULES lines 26-69; query 'from:notion.so' etc.` | SWEEP_RULES route by bare 'from:<domain>' with no protected-sender gate; safe today but a one-line edit ships unprotected mutations |
| U329 | medium | R1 | config | `cli.py:default --query 'has:nouserlabels' (label_parser line 1014) used for all providers` | Gmail-specific default query passed verbatim to IMAP/Outlook/Mail.app providers |
| U330 | medium | R1 | api-misuse | `cli.py:main() lines 968-972, 1192-1195` | Global --verbose flag is defined on the top-level parser only and is shadowed/unreachable when a subcommand is given |
| U331 | medium | R1 | logic | `cli.py:cmd_pending lines 639-642, 661-677` | pending uses sender-side 'is:starred' query for gmail but 'isRead eq false' for outlook, then filters on msg.is_starred — outlook path yields zero pending items |
| U332 | medium | R1 | api-misuse | `cli.py:run_labeler, lines 172, 186-190 (page_token = state.get_token(); passed to provider.list_messages)` | Malformed page token from state is replayed unvalidated to the provider |
| U333 | medium | R3 | security/protected-gate | `cloudflare/worker.mjs:106-126 (.gov branch) vs core/rules.py:653-673 (_gov_protected terminal-label rule)` | Worker .gov protection uses endsWith('.gov') on the full From value, accepting spoofs the real API rejects |
| U334 | medium | R1 | correctness | `configure_smart_mailboxes.py:main, lines 99-124` | Overwrites live Apple Mail plist with only a single .backup that is clobbered on every run |
| U335 | medium | R1 | resource-leak | `configure_smart_mailboxes.py:main, lines 123-124 (non-atomic write)` | Non-atomic plist write can corrupt SyncedSmartMailboxes.plist on interrupt |
| U336 | medium | R1 | resource-leak | `configure_smart_mailboxes.py:main lines 98-128` | Plist read-modify-write not atomic; backup overwritten each run |
| U337 | medium | R1 | logic | `core/audit.py:record() lines 181-192` | Protected-sender disposition over-reported as protected_held even when message left the inbox (count vs violation mismatch) |
| U338 | medium | R1 | error-handling | `core/audit.py:_append() lines 226-238 (except OSError only)` | _append catches only OSError; a serialization error in json.dumps escapes into the apply path |
| U339 | medium | R1 | silent-failure | `core/audit.py:_independently_protected() lines 110-114 and record() line 178` | Audit silently downgrades to non-protected when rules import/parse fails |
| U340 | medium | R1 | silent-failure | `core/audit.py:_independently_protected() lines 110-114; _domain_of() lines 84-92` | The independent audit's protection re-derivation swallows ALL exceptions and returns False (fail-OPEN for the cross-check) |
| U341 | medium | R2 | security | `core/audit.py:summary() lines 250 -> api/receipts.py signed_body 83 / persist 94-105 -> GET /v1/audit/{run_id} 114-142 (unauthenticated)` | Receipt body schema is designed to carry raw violation message_ids to an unauthenticated endpoint; only the fail-closed assert keeps it empty |
| U342 | medium | R2 | error-handling | `core/audit.py:_independently_protected lines 110-114 and _domain_of lines 84-92 (both import core.rules and both bare-except)` | A single core.rules import failure collapses BOTH the cross-check AND the receipt's domain field at once, with the receipt still emitted as if trustworthy |
| U343 | medium | R1 | config | `core/config.py:_apply_yaml_config() lines 188-197, 250, 254-260` | No type validation of YAML values before assigning to typed config fields |
| U344 | medium | R1 | silent-failure | `core/config.py:apply_vip_senders_from_config() lines 313-322` | VIP entry missing 'pattern' is silently dropped without warning |
| U345 | medium | R1 | silent-failure | `core/config.py:load_yaml_config() lines 119-126` | Broad except Exception swallows YAML parse errors as empty config |
| U346 | medium | R1 | correctness | `core/models.py:LabelAction.merge lines 95-108 (no message_id guard)` | merge() silently merges actions for DIFFERENT message_ids; only the docstring says 'assumed' |
| U347 | medium | R1 | security | `core/models.py:LabelAction.merge line 99 (sender=self.sender or other.sender)` | merge() can resurrect a non-empty sender from `other`, weakening the fail-closed protected-sender guarantee |
| U348 | medium | R1 | api-misuse | `core/rules.py:categorize_with_tier lines 982-983 (and 1013)` | VIP tier and tier_config can disagree when VIP tier is outside 1-4, yielding wrong folder/star/inbox behavior |
| U349 | medium | R2 | datetime/timezone | `core/rules.py:lines 1176-1182 (calculate_email_age_hours: local import + replace(tzinfo=utc)) vs line 8 module-level import` | calculate_email_age_hours assumes naive provider dates are UTC, but providers populate naive LOCAL dates (e.g. email Date: header parse), inflating/deflating age by the UTC offset |
| U350 | medium | R1 | silent-failure | `core/state.py:save() lines 91-95` | Failed state save is swallowed; run continues believing progress is persisted |
| U351 | medium | R1 | none-handling | `core/state.py:_load() lines 46-56` | _load does not validate that loaded JSON is a dict with expected keys |
| U352 | medium | R1 | error-handling | `core/state.py:_load, lines 54-55 (except Exception)` | Overly broad except in _load masks non-JSON load errors and silently discards prior state |
| U353 | medium | R1 | race-condition | `final_sweep.py:lines 8-18` | RESET_STATE default 'true' wipes GmailLabeler resume state, and save(None,0,{}) may not match how run() reads token |
| U354 | medium | R1 | api-misuse | `gmail_auth.py:get_credentials() line 177; build_gmail_service 183-185` | Headless/hosted credential acquisition silently blocks on a local-server OAuth flow |
| U355 | medium | R2 | security | `gmail_auth.py:_op_item_edit 56-63 / store_token_info 144-154` | OAuth refresh-token written to 1Password via command-line argument 'field=value' — secret exposed in process args |
| U356 | medium | R1 | logic | `gmail_labeler.py:run() pagination lines 269-328; comment block 272-282` | Page-token resumption with a draining/destructive query can skip messages or resume against a shifted result set |
| U357 | medium | R1 | correctness | `gmail_labeler_legacy.py:categorize_email() lines 340-364; LABEL_RULES catch-all line 282` | Legacy categorize_email uses unguarded header['name']/['value'] and a catch-all label 'Uncategorized' that is never created elsewhere consistently |
| U358 | medium | R1 | error-handling | `icloud_triage.py:archive_uid line 72-74` | COPY failure returns False but message is left in place — but STORE/EXPUNGE results unchecked on success path |
| U359 | medium | R1 | error-handling | `icloud_triage.py:archive_uid() lines 70-77; COPY failure path` | If COPY succeeds but STORE/EXPUNGE step errors, message is duplicated or the function returns True without confirming deletion |
| U360 | medium | R1 | injection | `imap_rules.py:apply_label lines 103-110; ensure_label lines 95-100` | Folder/label names interpolated unquoted/unescaped into IMAP commands (folders with spaces or quotes break or inject) |
| U361 | medium | R1 | silent-failure | `imap_rules.py:apply_label lines 103-110; STORE +FLAGS \Seen line 110` | Messages are marked \Seen as a side effect of labeling, and STORE/COPY results are never checked |
| U362 | medium | R1 | silent-failure | `imap_rules.py:apply_label() lines 103-110; ensure_label lines 95-100` | apply_label ignores IMAP command status and force-marks \Seen on every processed message |
| U363 | medium | R4 | security | `llms.txt:line 9` | Advertises /v1/audit/{run_id} 'receipt verification' that the live worker returns unsigned |
| U364 | medium | R1 | logic | `mark_rot_read.py:mark_read_loop, lines 43-64` | Unbounded while-loop relies on each batchModify shrinking the result set; no nextPageToken and no progress guard |
| U365 | medium | R2 | correctness | `mark_rot_read.py:mark_read_loop 43-64` | Pagination loop never advances pageToken — relies on side-effect of removing UNREAD to terminate |
| U366 | medium | R2 | config | `mcp_server/server.py:_transport_security() lines 51-57` | MCP_ALLOWED_HOSTS entries with a URL scheme produce malformed origins (http://https://host) and never match |
| U367 | medium | R2 | correctness | `mcp_server/server.py:check_protected_sender line 94 (sender[:4096], subject[:4096]) vs api/schemas.py SenderCheckRequest max_length=4096` | MCP check_protected_sender truncates to 4096 chars silently rather than rejecting, diverging from the API's validation contract |
| U368 | medium | R1 | logic | `providers/base.py:288-305 (_drop_if_protected) and 349-352 (remove_labels INBOX matching)` | INBOX strip in _drop_if_protected matches only 'INBOX'/'\\INBOX' but remove path matches the same; a lowercase or aliased inbox label could leak past the gate |
| U369 | medium | R1 | api-misuse | `providers/gmail.py:315-317, 411-414 (remove_label / apply_actions remove path)` | remove_label falls back to raw label NAME as label ID on cache miss, sending an invalid removeLabelIds value |
| U370 | medium | R1 | logic | `providers/gmail.py:295-313 (apply_label) vs 449-497 (apply_actions)` | apply_label single-path and apply_actions batch-path enforce protected gate inconsistently |
| U371 | medium | R1 | api-misuse | `providers/gmail.py:remove_label(), line 317; apply_actions remove path` | remove_label falls back to using the raw label string as a label ID when not in cache, which can no-op or error silently |
| U372 | medium | R2 | error-handling | `providers/gmail.py:apply_actions 459-466 (batchModify) — partial per-id failure semantics` | Gmail batchModify is treated as all-or-nothing, but invalid ids within a chunk fail the whole call, marking valid messages in the chunk as errored |
| U373 | medium | R2 | correctness | `providers/gmail.py:apply_actions pending dict lines 434/484-487 (keyed by action.message_id)` | Gmail audit recording keyed by message_id collides on duplicate actions, dropping audit records for all but the last action on a given id |
| U374 | medium | R1 | correctness | `providers/imap.py:list_messages 184` | IMAP SEARCH query not encoded/quoted; multi-word criteria and non-ASCII break or inject extra search tokens |
| U375 | medium | R1 | correctness | `providers/imap.py:list_messages 191-206` | Pagination offset math is inconsistent between the slice and the next_token, causing skipped/overlapping pages |
| U376 | medium | R1 | correctness | `providers/imap.py:list_messages 194` | Slice stop index total-start can become negative when start>total, silently yielding wrong/empty window |
| U377 | medium | R1 | error-handling | `providers/imap.py:get_message_details 224` | fetch HEADER parsing assumes data[0] is a 2-tuple; raw/atom responses raise TypeError unhandled |
| U378 | medium | R1 | correctness | `providers/imap.py:apply_label 279 / remove_label 303` | X-GM-LABELS value not IMAP-quoted/escaped; labels with spaces, quotes, or backslashes corrupt the STORE command |
| U379 | medium | R1 | regex | `providers/imap.py:get_message_details 235-249 X-GM-LABELS regex` | X-GM-LABELS parsing regex `\(([^)]*)\)` is wrong for labels containing parentheses or quoted spaces; mis-splits labels |
| U380 | medium | R1 | injection | `providers/imap.py:apply_label line 279/288; remove_label 303; archive 319; ensure_label_exists 352; _select_mailbox 158` | IMAP command/argument injection via unescaped label and mailbox names |
| U381 | medium | R1 | logic | `providers/imap.py:list_messages lines 192-194 (pagination slice)` | IMAP pagination slice can drop/duplicate messages and mis-handle offsets |
| U382 | medium | R1 | silent-failure | `providers/imap.py:get_message_details lines 233-259, archive 312-326` | IMAP STORE/COPY return code not checked; broad except returns success/failure inconsistently |
| U383 | medium | R2 | correctness / data-integrity | `providers/imap.py:archive lines 317-326 (standard IMAP branch)` | Standard-IMAP archive sets \Deleted without EXPUNGE and reports success, leaving the message in the inbox flagged-deleted |
| U384 | medium | R2 | security | `providers/imap.py:apply_label 279/288, remove_label 303, archive 315/319, ensure_label_exists 352` | IMAP folder/label names interpolated unquoted-or-naively into IMAP commands (command injection / breakage) |
| U385 | medium | R1 | correctness | `providers/mailapp.py:get_message_details 213 vs apply_label 265` | 'first message whose id is' searches only current/default mailbox context, may target wrong or missing message |
| U386 | medium | R1 | correctness | `providers/mailapp.py:ensure_label_exists 348-356` | Mailbox marked as created even when AppleScript fails, caching a false 'exists' state |
| U387 | medium | R1 | perf | `providers/mailapp.py:list_messages 144` | Per-page O(n) message indexing causes quadratic cost and re-fetch of full message list each page |
| U388 | medium | R1 | correctness | `providers/mailapp.py:get_message_details 226 / parsing 235-239` | get_message_details TSV parse mis-handles sender/subject containing tabs (same delimiter-collision as list_messages) |
| U389 | medium | R1 | injection | `providers/mailapp.py:apply_label line 266, ensure_label_exists lines 338/342, list_messages account_filter line 133/261/332/409` | AppleScript injection: label/account/message_id interpolated unescaped into osascript |
| U390 | medium | R1 | correctness | `providers/mailapp.py:list_messages parsing lines 179-197; get_accounts/get_mailboxes 390-422` | AppleScript tab/linefeed-delimited parsing breaks on senders/subjects containing tabs or newlines |
| U391 | medium | R1 | error-handling | `providers/mailapp.py:_run_applescript 68-84; connect 86-103` | 30s osascript timeout with no recovery; TimeoutExpired loses partial output and orphan process risk |
| U392 | medium | R1 | error-handling | `providers/outlook.py:ensure_label_exists, 644-649 inner except` | Inner find-folder failure raises a misleading 'Failed to create or find folder' for the whole label, not the failing segment |
| U393 | medium | R1 | api-misuse | `providers/outlook.py:list_messages, 428 ($top: limit)` | $top passed unbounded to Graph; values >1000 are rejected/clamped, and large $top with $orderby+$filter can 400 |
| U394 | medium | R1 | correctness | `providers/outlook.py:_fetch_child_folders, 264-274 (recursion) + _init_folder_cache 257-259` | Unbounded recursive child-folder fetch with no depth limit or cycle/duplicate-name guard; deep trees risk perf/stack and name collisions overwrite cache entries |
| U395 | medium | R1 | secrets | `providers/outlook.py:_save_token_cache, 163-168 + _get_msal_app 151-154` | Token cache file written/read with default (world-readable) permissions — OAuth refresh token at rest is not protected |
| U396 | medium | R1 | api-misuse | `providers/outlook.py:_acquire_token, 177-180` | acquire_token_silent error result not surfaced; falls through to interactive prompt in headless/automated runs |
| U397 | medium | R1 | logic | `providers/outlook.py:apply_label, 521-537 + tier routing in cli.py 256-257` | tier_routing target_folder is never honored by Outlook move path — tier folder routing is effectively a no-op for the actual move |
| U398 | medium | R1 | secrets | `providers/outlook.py:_save_token_cache lines 163-168; _get_msal_app lines 151-160` | MSAL OAuth token cache written to disk with default (potentially world-readable) permissions |
| U399 | medium | R1 | injection | `providers/outlook.py:ensure_label_exists(), lines 631-651` | Folder create/find fallback can silently return the parent or raw label as the destination id, risking a move to the wrong folder |
| U400 | medium | R1 | silent-failure | `providers/outlook.py:apply_category(), lines 345-364` | apply_category swallows the read-current-categories error and proceeds with empty list, silently dropping existing categories |
| U401 | medium | R1 | secrets | `providers/outlook.py:_acquire_token() lines 170-194; _save_token_cache lines 163-168` | Token cache file written without restrictive permissions and silent failure modes around interactive auth in a server context |
| U402 | medium | R1 | error-handling | `providers/outlook.py:_fetch_child_folders lines 264-274; ensure_label_exists 631-649` | Bare/broad except: pass swallows folder-fetch and create errors silently |
| U403 | medium | R1 | secrets | `providers/outlook.py:_save_token_cache 163-168; _get_msal_app 150-160` | OAuth token cache written world-readable with no restrictive permissions |
| U404 | medium | R1 | error-handling | `providers/outlook.py:452-458 and 503-509 (receivedDateTime parsing)` | Outlook silently swallows date-parse failures, falling back to None and disabling escalation for that message |
| U405 | medium | R2 | datetime/timezone | `providers/outlook.py:lines 454-456 and 505-507 (datetime.fromisoformat(msg["receivedDateTime"].replace("Z", "+00:00")))` | datetime.fromisoformat on Graph receivedDateTime rejects 7-digit fractional seconds on Python <3.11, silently dropping the date |
| U406 | medium | R2 | api-misuse | `providers/outlook.py:_api_get/_api_post/_api_patch, lines 213-232 (response.json() unconditional)` | response.json() on 202/204 (empty body) move/patch responses raises JSONDecodeError, turning a successful move into a reported failure |
| U407 | medium | R2 | datetime | `providers/outlook.py:list_messages 451-458 and get_message_details 502-509 (datetime.fromisoformat on Z-suffix)` | datetime.fromisoformat fails on Graph timestamps with sub-second precision beyond 6 digits or fractional 'Z', silently disabling escalation |
| U408 | medium | R2 | api-misuse | `providers/outlook.py:_acquire_token 170-194 + connect 234-239 (token captured once; _get_session 196-211 caches header)` | Token bound into the requests.Session Authorization header at first use is never refreshed even though MSAL silent-refresh exists |
| U409 | medium | R2 | injection / correctness | `providers/outlook.py:ensure_label_exists line 642 (and _api_get OData $filter usage)` | Outlook folder lookup builds an OData $filter via f-string with an unescaped folder name (OData injection / breakage) |
| U410 | medium | R2 | api-misuse | `providers/outlook.py:list_messages 428-432` | $top=limit passed verbatim to Graph with no per-page cap or pagination loop |
| U411 | medium | R2 | config/dependency | `requirements-mcp.txt:line 7 (mcp>=1.2,<2) — sole declared dep` | MCP server's documented standalone HTTP run command needs uvicorn/starlette that requirements-mcp.txt does not declare |
| U412 | medium | R2 | security | `requirements.txt:line 8 (requests>=2.28.0)` | `requests>=2.28.0` floor permits known-vuln versions (CVE-2023-32681 proxy cert leak, CVE-2024-35195 verify=False persistence) |
| U413 | medium | R1 | correctness | `route_bulk_senders.applescript:lines 6-14` | `ends with dom` matching is unreliable and `contains` can over-match, risking wrong-folder moves |
| U414 | medium | R2 | correctness | `route_bulk_senders.applescript:line 2` | Default bulkDomains ships an example domain 'newsletter.yourfav.com' and runs unedited |
| U415 | medium | R1 | error-handling | `run_automation.sh:lines 5, 19-20` | set -e plus `source` of op env file aborts whole run if any `op read` fails |
| U416 | medium | R1 | test-quality | `tests/test_receipts.py:test_triage_persists_retrievable_signed_receipt, lines 30-53` | Test never exercises tamper-detection on GET, and verification only passes because sign and verify share the same in-process ephemeral key |
| U417 | medium | R1 | test-quality | `tests/test_store.py:test_credits_atomic_no_overdraw (35-43)` | No test covers negative-n on consume_credit/add_credits (overdraw-via-negative money bug uncovered) |
| U418 | medium | R2 | security | `web/index.html:lines 866-871 (previewBtn handler, live audit table)` | Live audit counts interpolated into innerHTML without escaping (DOM-XSS sink) |
| U419 | medium | R2 | security | `web/index.html:line 812 (checkBtn handler, sender-check verdict)` | categorization.tier interpolated into innerHTML unescaped; server schema does not coerce it |
| U420 | medium | R2 | security | `web/index.html:line 888 (startCheckout: window.location.href = data.url)` | Checkout redirect assigns server-supplied URL to window.location with no host validation |
| U421 | low | R1 | money-path | `acp/payment.py:StripeSPTPaymentClient.charge() lines 92-97` | Charge treats only status=='succeeded' as ok, but a PaymentIntent in 'requires_capture' or 'processing' is neither charged-final nor refunded — fulfillment is skipped while funds may be held/captured later |
| U422 | low | R3 | correctness | `acp/product_feed.json:acp/product_feed.json:13,33 (price fields) + acp/feed.py:48` | ACP product feed 'price' is emitted in cents (100 / 900) which may be misread as dollars by an ACP consumer |
| U423 | low | R1 | money-path | `acp/router.py:update_session() lines 217-232` | A session can be re-priced via update after being READY, and amount charged at /complete is recomputed from line_items — but update does not re-validate that items still map to known packs against a tampered stored session |
| U424 | low | R1 | concurrency | `acp/router.py:complete_session() lines 273-280 vs 332-337 (status persistence on failure)` | Payment-failed branch persists session as STATUS_READY but the response includes only the failure message; a concurrent successful /complete and a failed one both persist, last-write-wins can resurrect READY over COMPLETED |
| U425 | low | R1 | money-path | `acp/router.py:complete_session (257-266)` | No guard against amount <= 0 before charging / fulfilling |
| U426 | low | R2 | correctness | `acp/router.py:complete_session lines 287-290 + 337 (_persist account_id=account['id'])` | On a charge-success-but-fulfill_once-False replay, the session is re-persisted bound to whichever bearer last called /complete, rewriting account_id ownership |
| U427 | low | R1 | money-path | `api/billing.py:create_checkout() lines 119-143` | Checkout creates a brand-new free account when account_id absent but the created account_id is only returned in the JSON, not bound to any session/cookie |
| U428 | low | R1 | type-confusion | `api/billing.py:_handle_event lines 227/245/266/273 obj.get('customer'); set_subscription/get_account_by_customer` | Expanded Stripe 'customer'/'subscription' object (dict) would be used as a customer id, causing wrong lookups or a 500 |
| U429 | low | R1 | correctness | `api/receipts.py:verify() lines 71-74 and get_receipt() lines 114-142` | Receipt verification recomputes sign(body) from a body reconstructed out of the DB; type coercion on round-trip (dry_run, summary) could break signature match for some receipts |
| U430 | low | R1 | concurrency | `api/store.py:Store.__init__ / single shared connection lines 124-138, _fetch_all/execute` | Single shared sqlite3 connection with autocommit-per-statement and no transaction grouping means multi-statement money operations are not atomic if an exception occurs between statements |
| U431 | low | R1 | concurrency | `api/store.py:idempotency_complete lines 355-362` | idempotency_complete updates status='done' even if the key row was reclaimed by another request, with no compare-and-set on the original claim |
| U432 | low | R1 | correctness | `api/store.py:idempotency_begin() line 352 json.loads(existing['response_json'] or 'null')` | Replay of a key whose request completed without storing a response returns None as the replay body, which router returns as a JSON 'null' 200 response |
| U433 | low | R1 | money-path | `api/store.py:save_receipt (269-290)` | save_receipt uses INSERT OR REPLACE — an id collision silently overwrites a prior signed receipt |
| U434 | low | R2 | security | `api/well_known.py:build_agent_manifest lines 17-51 / agent_manifest line 78-80 (no Cache-Control, reflects request.base_url)` | Agent manifest/llms.txt reflect Host into absolute URLs AND set no Cache-Control, so a poisoned response can be cached and served to other agents |
| U435 | low | R2 | api-misuse | `providers/outlook.py:apply_category, lines 343-364 and remove_category 377-392 (URL = /me/messages/{id})` | apply_category/remove_category operate on /me/messages/{id} but the categorize+move pipeline may move the message first, leaving categories applied to a now-stale-folder message id |


## 🔵 Low (437)

| ID | Conf | Rounds | Category | Location | Title |
|---|---|---|---|---|---|
| U436 | high | R3 | deployment | `.github/workflows/ci.yml:test job matrix python-version [3.11, 3.12]` | CI never exercises the documented 3.9 core floor nor the stripe/mcp lower version bounds |
| U437 | high | R3 | ci/deploy-safety | `.github/workflows/ci.yml:108-119` | Smoke test runs AFTER deploy with no rollback, so a broken worker is already live before the test can fail |
| U438 | high | R3 | documentation/staleness | `CHANGELOG.md:8-24` | CHANGELOG omits all of the commerce/API/MCP/ACP/Cloudflare work — stale vs current repo state |
| U439 | high | R3 | documentation/dead-reference | `GEMINI.md:1-120` | GEMINI.md contains only auto-generated ORGANVM system boilerplate — no project-specific guidance, contradicting AGENTS.md which calls it the 'overview' |
| U440 | high | R3 | documentation/version-drift | `README.md:2 and 241 vs CLAUDE.md:278` | Inconsistent minimum Python version across docs (3.10 vs 3.9) |
| U441 | high | R2 | config / re-export drift | `acp/feed.py:line 60 ("version": "2026-04-17") vs acp/__init__.py:19 (API_VERSION = "2026-04-17")` | ACP feed hardcodes the spec version literal instead of importing API_VERSION — version drift risk |
| U442 | high | R1 | logic | `analyze_strategic_value.py:calculate_value_score line 48` | Value-score penalty keys on bare 'off' and '%' substrings, over-penalizing legitimate subjects |
| U443 | high | R2 | import-time side effect / API misuse | `api/service.py:line 28 (from cli import get_provider, run_labeler) -> cli.py:48 logging.basicConfig` | Importing the FastAPI app triggers logging.basicConfig() as an import-time side effect |
| U444 | high | R1 | resource-leak | `api/store.py:73-80 (idempotency_keys schema) + 56-60 (webhook_events schema)` | idempotency_keys and webhook_events grow unbounded — no TTL/cleanup, monotonic disk growth and ever-slower scans |
| U445 | high | R2 | dead-code | `api/store.py:add_credits (lines 223-233)` | add_credits() is dead production code — ACP fulfillment inlines its own UPDATE, nothing else credits |
| U446 | high | R1 | dead-code | `auth/onepassword.py:store_json_secret, line 233 (definition)` | store_json_secret is dead code (no callers) — write-back actually goes through gmail_auth._op_item_edit, a duplicate implementation |
| U447 | high | R1 | error-handling | `auto_drain.py:extract_domain line 61-64, classify (implicit)` | Bare `except:` swallows all errors in extract_domain |
| U448 | high | R1 | error-handling | `auto_drain.py:extract_domain lines 60-64` | Bare except swallows all errors and returns None domain |
| U449 | high | R1 | dead-code | `cli.py:_make_audit lines 365-389; cmd_label line 437 / cmd_escalate line 845` | Audit disabled silently when --dry-run, so dry-run apply previews bypass receipt unless audit object passed; _record_dry_run_intent only runs if audit is not None |
| U450 | high | R2 | security | `cli.py:cmd_summary markdown lines 696 / cmd_pending markdown lines 693-696 / cmd_vip markdown lines 797-800, 793` | Markdown table/code-span injection from unescaped sender, subject, and VIP pattern |
| U451 | high | R1 | dead-code | `cloudflare/worker.mjs:lines 1, 150-169` | PROTECTED set is dead code and protected-sender logic is duplicated/inconsistent in the fallthrough branch |
| U452 | high | R2 | correctness | `cloudflare/worker.mjs:/v1/triage handler lines 260-263 vs /v1/triage/preview lines 255-258; cross-ref api/app.py real triage semantics` | /v1/triage (the apply path) returns dry_run:true and is byte-identical to /v1/triage/preview — the worker erases the preview-vs-apply distinction the whole product is built on |
| U453 | high | R2 | correctness/regex | `cloudflare/worker.mjs:senderCheck lines 150, 155-160 marketing classification (value.includes('deal')\|\|value.includes('news'))` | Marketing classifier matches bare substrings 'deal' and 'news' anywhere in the sender — 'newsletter@irs-deals.example', 'jdealer@gmail.com' misclassified |
| U454 | high | R2 | correctness | `cloudflare/worker.mjs:senderCheck lines 154-165 fall-through tier_config color always 'amber'` | Fall-through tier_config.color is hardcoded 'amber' for BOTH Marketing (tier 3) and Misc/Other (tier 4) — Reference should be 'green' per the engine tier table |
| U455 | high | R3 | documentation/implementation-drift | `cloudflare/worker.mjs:156-164` | Worker returns wrong tier color 'amber' for Reference (tier 4) and Delegate (tier 3); README/core define green and blue |
| U456 | high | R3 | path-parsing | `cloudflare/worker.mjs:281-282` | /v1/audit (no trailing slash) does not match the audit handler and silently serves static assets |
| U457 | high | R3 | api-divergence | `cloudflare/worker.mjs:307-318 (worker llms.txt) vs api/well_known.py:54-75` | Worker /llms.txt diverges from the canonical builder and advertises non-existent worker routes |
| U458 | high | R3 | data-consistency | `cloudflare/worker.mjs:150 (triagePreview/senderCheck marketing detection) and 154-167` | Marketing categorization is a naive substring on 'deal'/'news' producing false categorizations and an always-amber tier_config color |
| U459 | high | R1 | config | `configure_smart_mailboxes.py:PLIST_PATH line 17` | Hardcoded Mail version path 'V10' will silently fail on other macOS Mail versions |
| U460 | high | R2 | correctness | `core/audit.py:record() lines 181-184 and entry build 197-210 (entry['archived']/['moved'] vs entry['disposition'])` | Violation JSONL line is internally contradictory: disposition=protected_held while archived/moved=true on the same record |
| U461 | high | R1 | api-misuse | `core/config.py:load_config docstring 146-179 and body 165-179` | Docstring claims 'CLI > env > config file' precedence but load_config never applies CLI args |
| U462 | high | R1 | api-misuse | `core/models.py:EmailMessage lines 25-53 (labels:49, categories:53)` | frozen=True gives a false immutability guarantee: mutable Set fields can be mutated in place |
| U463 | high | R1 | none-handling | `core/rules.py:line 1163 (def calculate_email_age_hours(email_date: Optional["datetime"]) -> float) with no `from __future__ import annotations` at top (line 8) and `datetime` imported only locally at line 1176` | Forward-ref annotation Optional["datetime"] is unresolvable — NameError if type hints are ever introspected |
| U464 | high | R3 | dead-code | `deploy.sh:lines 9-10, 46-60; vs com.user.gmail_labeler.plist` | com.user.gmail_labeler.plist is orphaned — committed but never installed by deploy.sh (only booted out) |
| U465 | high | R3 | documentation/accuracy | `docs/agent-commerce.md:61-70` | agent-commerce.md says 'Five endpoints' but then lists six ACP routes |
| U466 | high | R3 | dead-code | `docs/pitch/index.html:whole file vs wrangler.toml [assets].directory` | Second frontend (docs/pitch) is an orphan: not deployed and not linked from anywhere, so its stale copy will drift unnoticed |
| U467 | high | R2 | datetime/timezone | `gmail_labeler_legacy.py:lines 390 and 472 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'))` | Legacy labeler start/finish banners stamp naive local time while audit.py stamps UTC — same local-vs-UTC inconsistency as state.py |
| U468 | high | R1 | resource-leak | `imap_rules.py:main lines 131-158` | IMAP connection leaked on exception; logout only on success path |
| U469 | high | R1 | resource-leak | `imap_rules.py:main() line 158; connect_imap line 44` | IMAP connection not closed on early return / exception (resource leak) and logout-only cleanup |
| U470 | high | R1 | secrets | `labeler_state.json:whole file (git-tracked)` | Runtime state file with per-account mailbox statistics is committed to the repo |
| U471 | high | R1 | correctness | `mark_rot_read.py:module docstring line 3 vs query line 41` | Docstring says '>30 days' but the query uses older_than:7d (and inline comment says 7 days) |
| U472 | high | R2 | correctness | `providers/gmail.py:apply_actions, lines 444-446 (build loop) vs 459-472 (execution)` | Gmail label_counts recorded before batchModify runs — over-counts on batch failure or protected-suppressed actions |
| U473 | high | R2 | correctness | `providers/gmail.py:get_message_details 196-202 / _parse_message_response 278-284` | O(labels) reverse lookup per label id per message — quadratic label resolution on large mailboxes |
| U474 | high | R1 | config | `pyproject.toml:whole file (only [tool.pytest.ini_options]; no [project] / requires-python)` | No requires-python / [project] metadata — nothing authoritatively enforces the Python floor at install time |
| U475 | high | R1 | logic | `recount.py:lines 12, 41-45` | total_archived double-counts overlapping labels and miscounts because Gmail messages carry multiple labels |
| U476 | high | R3 | dependency | `requirements-api.txt:line 6 (httpx) + Dockerfile lines 9-10` | httpx is a test-only dep shipped into the production image |
| U477 | high | R1 | test-quality | `tests/test_models.py:test_immutability lines 57-63` | test_immutability asserts the wrong (overstated) guarantee and never exercises set-content mutation |
| U478 | high | R1 | test-quality | `tests/test_state.py:test_corrupted_file_returns_defaults, lines 23-29` | Test coverage gap: 'corrupt' test only exercises invalid JSON, never valid-JSON-wrong-shape |
| U479 | high | R1 | test-quality | `tests/test_store.py:6-8, 91-98 (_store() uses ':memory:' ; test_idempotency_stale_processing_is_reclaimed)` | Store tests run against ':memory:' where WAL is silently ignored — the concurrency/durability properties the store advertises are never exercised by tests |
| U480 | high | R2 | correctness | `web/index.html:lines 755-758 (localSenderCheck categorization branch)` | Offline categorization uses naive substring match ('deal'/'news') that over-matches |
| U481 | high | R2 | correctness | `web/index.html:lines 22-24 (:root --green/--green-2/--green-soft) vs prior HEAD` | Green design tokens were referenced ~13 times but never defined until this dirty diff (pre-existing broken branding) |
| U482 | medium | R1 | config | `.github/workflows/ci.yml:line 52 (`mypy . --ignore-missing-imports`) with no mypy config in repo` | mypy invoked with no config and no exclude — scans everything from repo root, advisory result is near-meaningless |
| U483 | medium | R1 | dependency | `.github/workflows/ci.yml:line 31 (`pip install pytest pytest-cov ruff mypy`) and line 30 (`pip install -r requirements*.txt`)` | Tooling (pytest/ruff/mypy) installed unpinned alongside unpinned app deps — non-reproducible toolchain |
| U484 | medium | R1 | config | `.github/workflows/ci.yml:lines 69-76 (codecov/codecov-action@v4)` | codecov-action@v4 used without CODECOV_TOKEN — coverage upload can fail/skip silently on this private-org repo |
| U485 | medium | R1 | error-handling | `.github/workflows/ci.yml:lines 108-119 (Smoke test live share demo)` | Post-deploy smoke test hits a live domain immediately after deploy with no retry/propagation wait — flaky failures and a non-blocking deploy |
| U486 | medium | R1 | config | `.gitignore:lines 1-37 (coverage gaps)` | .gitignore omits already-tracked PII artifacts (labeler_state.json, mail_export.tsv) and any *_state.json |
| U487 | medium | R2 | security | `Dockerfile:lines 9-10 (pip install -r ...) — no constraint/hash file, no pip version pin` | Docker build installs unhashed, unpinned dependencies with `pip install` and no `--require-hashes`, allowing supply-chain drift between identical source builds |
| U488 | medium | R3 | hygiene | `README.md:lines 261, 544, 556 / com.user.mail_automation.plist:14-17` | README documents the non-standard ~/System/Logs path, propagating the convention error rather than ~/Library/Logs |
| U489 | medium | R3 | documentation/command-accuracy | `README.md:288-289` | README 'First Run' Outlook/IMAP examples inherit a Gmail-only default query |
| U490 | medium | R1 | correctness | `acp/feed.py:build_feed, line 47` | Product image_url points to the dashboard HTML page (/app/), not an image |
| U491 | medium | R1 | config | `acp/payment.py:get_payment_client() lines 103-110` | Payment client is cached at module level keyed on first-call env; a STRIPE_SECRET_KEY set after first call (or rotated) is never picked up |
| U492 | medium | R1 | config | `acp/payment.py:get_payment_client, lines 103-110` | Payment client is cached process-wide on first resolution; a STRIPE_SECRET_KEY set after first call (or rotated) is never picked up |
| U493 | medium | R2 | concurrency / mutable module global | `acp/payment.py:lines 100-110 (_CLIENT module global, get_payment_client lazy init)` | Module-global payment client lazy-init has a read-check-set race under the FastAPI threadpool (no lock) |
| U494 | medium | R2 | config/consistency | `acp/product_feed.json:lines 10, 12, 30, 32 ("url" and "image_url" both "https://mail.example.com/app/")` | Static product_feed.json bakes the placeholder host mail.example.com into committed buyer-facing product/image/checkout/seller URLs |
| U495 | medium | R3 | correctness | `acp/product_feed.json:acp/product_feed.json:12,32 + acp/feed.py:47` | Feed image_url points to an HTML app page (/app/), not an image asset |
| U496 | medium | R3 | documentation/config-drift | `acp/product_feed.json:4,8,12,18,24,38,40` | Shipped ACP product feed and discovery artifacts hardcode mail.example.com placeholder URLs |
| U497 | medium | R1 | api-misuse | `acp/router.py:complete_session() lines 273-280 (payment_failed branch)` | On payment failure the failed response is stored via idempotency_complete, so a legitimate retry with the SAME Idempotency-Key replays the FAILURE instead of re-attempting payment |
| U498 | medium | R1 | auth | `acp/router.py:get_session, lines 193-197` | GET /checkout_sessions/{id} returns the stored session to ANY valid-format bearer with no ownership check |
| U499 | medium | R1 | dead-code | `acp/router.py:module / models.py` | STATUS_EXPIRED is defined but never assigned; sessions never expire and remain completable indefinitely |
| U500 | medium | R2 | money/unit arithmetic | `acp/router.py:complete_session lines 304-310 (receipt summary 'currency': CURRENCY ('usd')) vs acp/feed.py:50 / product_feed.json ('USD') and api/billing.py:102 ('usd')` | Currency casing is inconsistent across the money surfaces: charge+receipt+billing use 'usd', the product feed uses 'USD' — a consumer keying on exact case sees two currencies |
| U501 | medium | R2 | state-machine / audit-correctness | `acp/router.py:287-290 vs 316 (account['id'] used for receipt)` | Receipt account_id is the auto-provisioned bearer account, not the buyer email on the session — receipt audit trail attributes the purchase to an unidentifiable orphan |
| U502 | medium | R2 | correctness | `acp/router.py:_links lines 125-130 / _shape line 144 — terms_of_use & privacy_policy URLs point at {base}/terms and {base}/privacy which are not routed` | ACP session links advertise /terms and /privacy endpoints that the app does not serve (404) |
| U503 | medium | R1 | api-misuse | `analyze_strategic_value.py:analyze_dataset, lines 100-104` | Batch callback registered twice (on the batch AND per-request) causing each callback to fire twice — double-counting |
| U504 | medium | R1 | none-handling | `analyze_strategic_value.py:analyze_dataset lines 146,151,152` | Division by zero / statistics.mean on empty list crashes report if all batch fetches fail |
| U505 | medium | R2 | error-handling | `api/app.py:_run lines 127-129 (run_id minted + receipts.persist) — preview path via triage_preview line 88 / app calls _run(req, dry_run=True)` | triage_preview persists a durable receipt and mints a run_id for a no-op preview, polluting the audit ledger (REST preview path) |
| U506 | medium | R2 | state-machine / datetime | `api/billing.py:248-262 (subscription.* status write) + 269 (invoice.paid)` | invoice.paid sets status='active' unconditionally, but does not re-write current_period_end, so a past_due->active flip leaves a stale/expired period_end that nothing re-validates |
| U507 | medium | R2 | state-machine | `api/billing.py:248 + 260 (status=obj.get('status')) -> store.set_subscription` | subscription.created/updated with status=None writes nothing for status but still forces current_period_end and may demote plan, producing a row whose plan changed without a corresponding status change |
| U508 | medium | R2 | money/decimal/unit-arithmetic | `api/plans.py:METERED_ADDON line 133-134 ($0.01/run) vs CREDIT_PACKS line 146 (pack_1000: 1000 runs / 900 cents)` | Per-run price is inconsistent across the catalog: metered is $0.01/run but pack_1000 sells runs at $0.009/run, and neither price is ever charged |
| U509 | medium | R2 | error-handling | `api/plans.py:entitlements_for 192` | run_credits coerced with int(account.get('run_credits',0)) can raise ValueError/TypeError on a non-numeric stored value, 500-ing the entitlement check |
| U510 | medium | R1 | silent-failure | `api/receipts.py:persist(), lines 96-108` | Receipt ledger write failure swallowed (acceptable) but the API never surfaces that the run has no verifiable receipt |
| U511 | medium | R1 | security | `api/receipts.py:_signing_key, lines 47-49` | No minimum-length/strength validation on RECEIPT_SIGNING_KEY — a weak/short key is accepted silently |
| U512 | medium | R2 | maintainability / latent-correctness | `api/receipts.py:signed_body lines 77-85 vs acp/router.py order_receipt_body 297-311` | ACP order receipts are hand-built instead of reusing signed_body(), so the two receipt schemas can silently drift |
| U513 | medium | R1 | silent-failure | `api/service.py:run_triage finally block lines 120-124` | prov.disconnect() exception is silently swallowed with bare except: pass, hiding resource-cleanup failures |
| U514 | medium | R1 | silent-failure | `api/service.py:check_sender lines 63-67` | Broad 'except Exception' around categorize_with_tier silently degrades categorization to None with no logging |
| U515 | medium | R1 | error-handling | `api/service.py:run_triage() finally block, lines 120-124` | Provider disconnect failure is swallowed with bare 'except: pass', and assert_no_violations runs AFTER disconnect so a disconnect that masks state is invisible |
| U516 | medium | R1 | silent-failure | `api/service.py:check_sender(), lines 63-67` | Broad 'except Exception' silently nulls categorization, hiding rules-engine regressions on the public trust surface |
| U517 | medium | R1 | money-path | `api/store.py:current_period_end column (49); set_subscription (191-221); entitlements_for in plans.py (184-186)` | Subscription expiry (current_period_end) is stored but never checked — an expired-but-active row keeps paid limits |
| U518 | medium | R1 | money-path | `api/store.py:consume_credit (235-246)` | consume_credit always debits exactly the requested n with no cap on n and no zero/negative guard at the caller boundary |
| U519 | medium | R1 | error-handling | `api/store.py:133-136 (PRAGMA journal_mode=WAL try/except)` | WAL pragma failure is silently swallowed — store can silently run in rollback-journal mode on restricted/networked filesystems |
| U520 | medium | R1 | resource-leak | `api/store.py:127, 140-142 (connect / close), get_store 445-452` | Module-singleton Store connection is never closed in production and not coupled to FastAPI lifespan — connection/handle leak across reloads |
| U521 | medium | R2 | resource-leak/wal | `api/store.py:__init__ 134 (PRAGMA journal_mode=WAL) + close 140-142; get_store 445-452` | WAL is never checkpointed and the connection is never closed in production, so the -wal/-shm sidecar files grow unbounded |
| U522 | medium | R2 | type-confusion/error-handling | `api/store.py:add_credits 223-233; consume_credit 235-246; int(n)/int(runs)/int(limit) casts at 229,243,306,378,386` | int() coercions on caller-supplied counts can raise ValueError/TypeError mid-transaction, becoming an unhandled 500 and (with the no-rollback bug) poisoning the connection |
| U523 | medium | R2 | concurrency/transaction-isolation | `api/store.py:_fetch_one 425-427 / _fetch_one_nolock 429-432 / _fetch_all 434-437 (no explicit read transaction control)` | Reads run inside whatever transaction the shared connection currently holds, so a read can observe an uncommitted in-flight writer's data or a stale snapshot |
| U524 | medium | R2 | config/silent-failure | `api/store.py:__init__ 133-136 (PRAGMA journal_mode=WAL try/except) + return value never checked` | journal_mode=WAL return value is never verified, so on a filesystem that silently downgrades to another mode (NFS, some FUSE) the store runs without WAL while the docstring assumes WAL |
| U525 | medium | R2 | correctness | `api/store.py:get_receipt 292-298 / save_receipt 282 (INSERT OR REPLACE)` | save_receipt uses INSERT OR REPLACE on run_id, so a colliding run_id silently overwrites a prior signed receipt |
| U526 | medium | R2 | correctness / discovery | `api/well_known.py:build_agent_manifest lines 29,35-36; build_llms_txt 65-67` | Agent manifest advertises /mcp and ACP checkout unconditionally even when the MCP app failed to mount |
| U527 | medium | R2 | datetime/timezone | `archive_old_inbox.applescript:line 17` | Age cutoff uses local 'current date' with no timezone normalization; boundary off-by-one vs the Python age engine |
| U528 | medium | R1 | config | `archive_sorted.py:ARCHIVE_CATEGORIES lines 30-50; cross-ref core/rules.py LABEL_RULES` | ARCHIVE_CATEGORIES references labels that do not exist in the core taxonomy (Work/Dev/*, Work/RealEstate) |
| U529 | medium | R1 | silent-failure | `auth/onepassword.py:load_secret() lines 174-191` | 1Password read failures are swallowed to a warning and fall through to default/None |
| U530 | medium | R1 | secrets | `auth/onepassword.py:op_item_edit lines 94-117` | Secret value passed on 1Password CLI argv (visible in process list) |
| U531 | medium | R1 | secrets | `auth/onepassword.py:load_secret lines 180, 191` | Warning logs include the full RuntimeError detail, which embeds op stderr that may contain ref/item/field identifiers |
| U532 | medium | R1 | error-handling | `auth/onepassword.py:store_json_secret, lines 256-272` | store_json_secret silently prefers op_ref over item/field and silently no-ops on partial config edge cases |
| U533 | medium | R1 | silent-failure | `auto_drain.py:callback line 121-122` | Batch callback silently swallows per-message exceptions |
| U534 | medium | R1 | error-handling | `auto_drain.py:drain_loop batch.execute() line 135` | Analysis batch.execute() has no error handling; a failure aborts the whole drain with traceback and the print('\r') progress can hide errors |
| U535 | medium | R1 | silent-failure | `auto_drain.py:drain_loop() callback lines 121-129; batch.execute() line 135` | Batch callback swallows fetch exceptions silently and batch.execute has no error handling |
| U536 | medium | R1 | dead-code | `auto_drain.py:drain_loop() line 148-150` | Comment claims label auto-creation but code just `continue`s, dropping the domain when target label missing |
| U537 | medium | R1 | none-handling | `bulk_sweeper.py:get_label_id lines 74-79` | get_label_id uses results['labels'] without .get(), KeyError if no labels key |
| U538 | medium | R1 | none-handling | `bulk_sweeper.py:get_label_id() lines 74-79` | get_label_id accesses results['labels'] without .get(), KeyError if labels key absent |
| U539 | medium | R1 | api-misuse | `cli.py:cmd_report lines 478-487` | report command issues a separate API list call per label with no pagination/cost guard and swallows query into broad except |
| U540 | medium | R1 | error-handling | `cli.py:run_labeler lines 320-324` | Broad except re-raises after saving but the surrounding cmd_label has no handler — provider __exit__ runs but process exits with traceback, no exit code mapping |
| U541 | medium | R1 | logic | `cli.py:cmd_vip lines 760-772` | VIP attribution re-runs regex over all VIP patterns and attributes a message to the FIRST matching pattern only; overlapping VIPs undercounted, import re inside loop |
| U542 | medium | R1 | error-handling | `cli.py:run_labeler lines 197-201, cmd_summary 552-556, cmd_pending 655-659, cmd_vip 750-754, cmd_escalate 866-870` | batch_get_details detection via hasattr but fallback dict-comprehension calls get_message_details per id which may return None and partially populate; no error isolation |
| U543 | medium | R1 | perf | `cli.py:run_labeler line 311 time.sleep(1.0) inside while loop` | Fixed 1s throttle per batch is unconditional even in dry-run and even on the last (break) iteration |
| U544 | medium | R1 | config | `cli.py:cmd_label line 431 args.gmail_extensions` | Provider-specific flags (--host/--user/--password/--gmail-extensions/--account) accepted for every provider but only used by imap/mailapp; silently ignored otherwise |
| U545 | medium | R1 | none-handling | `cli.py:cmd_pending sort line 680 key uses x['age_hours'] which is 0 for messages with no date` | Messages with missing date get age_hours=0 (calculate_email_age_hours returns 0 for None), sorting them as 'newest' regardless of true age |
| U546 | medium | R2 | None/empty handling | `cli.py:cmd_summary 543-546, cmd_pending 646-649, cmd_vip 744-747, cmd_escalate 855-858 (limit=args.limit)` | Negative or zero --limit is passed unvalidated straight to provider.list_messages |
| U547 | medium | R2 | correctness/logic | `cli.py:cmd_report lines 480-485` | report command presents Gmail resultSizeEstimate as an authoritative label count |
| U548 | medium | R2 | error-handling/silent-failure/bad-fallback | `cli.py:cmd_vip lines 763-772 (import re inside loop) and 765 re.search(vip.pattern, ...)` | cmd_vip re-runs unvalidated user VIP regex with no try/except, crashing the command on a bad pattern |
| U549 | medium | R1 | logic | `cloudflare/worker.mjs:line 106` | `.gov` suffix match over-protects every government TLD address, not just configured senders |
| U550 | medium | R2 | correctness | `cloudflare/worker.mjs:senderCheck line 84 empty-sender branch returns protected:true with label 'Misc/Other'` | Empty/missing sender is fail-closed protected but mislabeled Misc/Other tier-4 — protected verdict paired with an archive-eligible tier_config (keep_in_inbox:false) |
| U551 | medium | R2 | api-misuse | `cloudflare/worker.mjs:fetch() dispatch lines 244-320; serveApp fall-through line 320` | Unknown POST paths and wrong-method requests fall through to serveApp/ASSETS instead of 404/405 — POST /v1/senders/check via GET, or POST to any unrouted path, silently serves static assets |
| U552 | medium | R2 | correctness | `cloudflare/worker.mjs:/v1/audit path test line 281 (url.pathname.startsWith('/v1/audit/'))` | startsWith('/v1/audit/') with split('/').pop() mis-handles trailing-slash and nested paths — '/v1/audit/' yields run_id 'demo', '/v1/audit/a/b' yields 'b' |
| U553 | medium | R2 | error-handling | `cloudflare/worker.mjs:readJson lines 216-222; used at lines 251, 256, 261` | Malformed/empty request body silently becomes {} so senderCheck/triage proceed with undefined sender — no 400 for invalid JSON |
| U554 | medium | R2 | config/divergence | `cloudflare/worker.mjs:PLANS lines 3-59 vs api/plans.py free/pro/business definitions` | Plan catalog is a hardcoded duplicate of api/plans.py with no shared source — prices/caps drift silently between the live demo and the real billing engine |
| U555 | medium | R2 | security | `cloudflare/worker.mjs:COMMON_HEADERS line 63; applied to /v1/audit, /v1/senders/check, /v1/billing/plans responses` | Wildcard CORS (access-control-allow-origin:*) lets any origin read the unsigned audit receipts and sender-classification API from the browser |
| U556 | medium | R3 | deployment | `cloudflare/worker.mjs:lines 307-318 vs root llms.txt` | Worker inlines a hand-written llms.txt that can drift from the canonical root llms.txt / gen_commerce_artifacts.py output |
| U557 | medium | R3 | deployment | `cloudflare/worker.mjs:lines 150-169 (senderCheck) vs api/service.check_sender` | Worker senderCheck is a divergent re-implementation of the Python protected-sender gate (share-demo only) |
| U558 | medium | R3 | routing | `cloudflare/worker.mjs:226-228 and 230-235 (serveApp)` | serveApp special-cases /app but lets any other path hit ASSETS, so /docs, /openapi.json, /server.json resolve to the SPA fallback or a bare 404 with no API semantics |
| U559 | medium | R3 | routing | `cloudflare/worker.mjs:226-228` | Root redirect uses 302 to /app/ and constructs the target with new URL('/app/', url), which works but the 302 (temporary) plus lost query/fragment is a minor divergence |
| U560 | medium | R3 | cors/preflight | `cloudflare/worker.mjs:61-66, 240-242` | OPTIONS preflight returns Allow-Methods GET,POST,OPTIONS for ALL paths including ones that only accept one method, and never reflects requested headers |
| U561 | medium | R3 | api-divergence | `cloudflare/worker.mjs:269-279 (billing checkout/portal/webhook)` | Worker billing webhook returns 503 JSON for POST /v1/billing/webhook, masking the fail-closed 400 'invalid signature' contract of the real webhook |
| U562 | medium | R3 | scheduling | `com.user.gmail_labeler.plist:line 25-26 (RunAtLoad true)` | RunAtLoad=true on gmail_labeler plist would trigger a full multi-provider run immediately on load/login, in addition to the 9 AM schedule |
| U563 | medium | R3 | scheduling | `com.user.mail_automation.plist:lines 7-11 (no EnvironmentVariables key)` | Plist provides no PATH/EnvironmentVariables; job depends entirely on run_automation.sh sourcing the 1Password env and on /bin/bash existing |
| U564 | medium | R1 | config | `configure_smart_mailboxes.py:SELF_NAME default line 23 + PERSONAL def lines 38-40` | Default SELF_NAME 'your-name' creates a PERSONAL smart mailbox matching the literal substring 'your-name' |
| U565 | medium | R2 | re-export drift / public API | `core/__init__.py:lines 8-40 (import block) / __all__ lines 42-78` | Public package API omits names that consumers actually use (apply_vip_senders_from_config, AuditLog, AuditInvariantError) |
| U566 | medium | R2 | correctness | `core/audit.py:receipt_line() lines 264-273 (esp. 'protected held in inbox' at 267 vs 'leave inbox' at 268)` | Human receipt_line reports a violating (protected-but-departed) message as 'protected held in inbox', misstating the breach in the headline number |
| U567 | medium | R2 | performance | `core/audit.py:record() line 178 (_independently_protected re-runs is_protected_sender per message) cross-ref providers/base.py:299/gmail.py:403 (_drop_if_protected already ran it)` | Audit re-runs the full protected-sender regex check on every recorded message, duplicating the gate's work per-message |
| U568 | medium | R2 | correctness | `core/audit.py:_domain_of 84-92 / record 206` | Audit JSONL 'domain' field uses normalize_sender (first address only), under-reporting multi-address senders |
| U569 | medium | R1 | config | `core/config.py:_apply_env_config() lines 282-285` | IMAP_HOST/IMAP_USER env vars ignore the configured env_prefix, inconsistent precedence |
| U570 | medium | R1 | correctness | `core/config.py:create_sample_config() lines 419-423` | Sample config file written without atomicity or overwrite guard |
| U571 | medium | R1 | style | `core/config.py:_apply_env_config, lines 266-297 (general pattern)` | Double os.getenv call (TOCTOU-style redundancy) on every env override |
| U572 | medium | R2 | config | `core/config.py:_apply_yaml_config custom_rules 249-250 / vip_senders 259-260` | custom_rules and vip_senders YAML are assigned wholesale with no validation, then VIP patterns are fed to re.search unguarded |
| U573 | medium | R2 | error-handling | `core/config.py:_apply_env_config 270-273` | MAIL_AUTO_BATCH_SIZE parsed with bare int() — a non-numeric env value crashes config load |
| U574 | medium | R1 | api-misuse | `core/models.py:EmailMessage dataclass lines 25-53 (frozen=True with Set/default_factory)` | Frozen EmailMessage holds mutable Set fields — frozen guarantee is shallow |
| U575 | medium | R1 | correctness | `core/models.py:LabelAction.merge lines 100-101` | merge() routes ordered List[str] label fields through set(), destroying order and any intended duplicate/sequence semantics |
| U576 | medium | R1 | logic | `core/rules.py:Finance/Banking pattern r'verizon' (line 146)` | verizon (a telecom) is in Finance/Banking, mislabeling carrier mail as a Critical financial-alert |
| U577 | medium | R1 | regex | `core/rules.py:AI/Services patterns 113-124 (r'claude', r'openai', r'anthropic', r'ollama', r'perplexity'); AI/Grok r'grok' (129)` | Bare-substring AI/brand patterns over-match unrelated mail |
| U578 | medium | R1 | regex | `core/rules.py:Shopping patterns: r'uber' (243), r'target' (247), r'square' (252), r'spirit' (Travel, 310), r'discover' (Finance/Payments, 185), r'statement'/r'invoice' (188-189), Notification r'reminder'/r'alert' (414-415), Personal r'mom'/r'dad'/r'family' (488)` | Many bare-substring keyword rules over-match common English words and brand prefixes |
| U579 | medium | R1 | logic | `core/rules.py:1147-1153 and 1184-1185 (age math)` | Negative email age (future-dated email) bypasses every escalation guard and is treated as fresh |
| U580 | medium | R2 | import-time side effect | `core/rules.py:line 616 (_local_domains, _local_selfs = _load_local_protected()) executed on import of core` | Safety-gate dataset is populated by a filesystem read executed at import of the core package |
| U581 | medium | R2 | regex | `core/rules.py:Tech/Google patterns lines 233-234 (r'workspace', r'gcp')` | Tech/Google bare substrings 'workspace'/'gcp' over-match unrelated mail |
| U582 | medium | R2 | regex | `core/rules.py:Finance/Payments r'plaid' (172); Finance/Banking r'chime' (149); Professional/Jobs r'monster' (380); Travel r'kayak' (321); Shopping r'nike'/'nordstrom'/'zara'/'macys' (250-264)` | Additional bare-brand substrings collide with common English / unrelated products |
| U583 | medium | R2 | None/empty handling | `core/rules.py:escalate_by_age lines 1091-1160 (no current_tier validation)` | escalate_by_age does not validate current_tier range/type |
| U584 | medium | R2 | correctness/logic | `core/rules.py:_find_best_label lines 1030-1037` | _find_best_label scans rules in dict order and cannot recover from any same-priority misorder |
| U585 | medium | R2 | correctness/logic | `core/rules.py:Notification patterns lines 414-422 + Tech/Storage/Notification priority interplay` | Notification catch-all keywords 'notification'/'alert'/'reminder' shadow more specific tier-1 categories below them |
| U586 | medium | R2 | config/dependency | `core/rules.py:categorize_with_tier VIP override branch lines 986-989` | VIP label_override is not validated against LABEL_RULES; a bogus override yields default time_sensitive=True silently |
| U587 | medium | R2 | correctness | `core/rules.py:_find_best_label 1030-1038` | Label selection iterates dict insertion order, so a higher-priority rule defined later than a same-text earlier rule can lose the tie incorrectly |
| U588 | medium | R2 | correctness | `core/rules.py:escalate_by_age 1131 / calculate_email_age_hours 1173-1174` | calculate_email_age_hours returns 0 for a None date, which escalate_by_age treats as a fresh (<24h) email — undated mail never escalates |
| U589 | medium | R1 | silent-failure | `core/state.py:clear, lines 122-129` | clear() resets in-memory state before removing the file, then swallows removal errors — leaves stale file |
| U590 | medium | R2 | datetime/timezone | `core/state.py:line 87 (last_run = datetime.now().isoformat()) and the absence of any reader` | state.py last_run is written as a naive-local ISO string that no code ever parses back, so the isoformat round-trip is untested and would break a naive-vs-aware comparison if a reader is added |
| U591 | medium | R2 | correctness | `core/state.py:save 91-95 (non-atomic write)` | State file written non-atomically — a crash mid-write corrupts the resume token and loses all progress |
| U592 | medium | R4 | logic | `create_smart_mailboxes.scpt:lines 10-13` | Implemented conditions do not match documented intent (no OR / no Label conditions) |
| U593 | medium | R4 | correctness | `create_smart_mailboxes.scpt:lines 10,17,23` | No idempotency — re-running duplicates smart mailboxes |
| U594 | medium | R1 | error-handling | `deploy.sh:lines 54-60` | launchctl bootstrap not idempotent / no error handling; can fail on re-deploy |
| U595 | medium | R3 | scheduling | `deploy.sh:lines 53-60` | deploy.sh boots out old jobs then bootstraps, but never reloads gmail_labeler — re-running deploy after a rename leaves only mail_automation, fine, but bootout failures are swallowed |
| U596 | medium | R3 | documentation/coverage | `docs/cloudflare-share-demo.md:16-24` | Demo doc lists /v1/triage/preview as verified but omits that POST /v1/triage is a silent no-op that always returns dry_run:true |
| U597 | medium | R3 | logic-bug | `docs/pitch/index.html:lines 257-277 (nav-dots IIFE)` | Nav-dot active-state indexing relies on data-section values being a 0-based dense sequence matching DOM order |
| U598 | medium | R2 | config/consistency | `ecosystem.yaml:lines 5-11 (delivery web_app status: not_started; revenue subscription status: planned) vs implemented api/billing.py + web/index.html + acp/router.py` | ecosystem.yaml status fields are stale — claims web_app not_started and subscription revenue merely planned while both are implemented |
| U599 | medium | R1 | resource-leak | `export_mail_snapshot.applescript:lines 2-3, 41` | File handle leaks on error: close access is outside any try and the open path may not exist |
| U600 | medium | R1 | correctness | `export_mail_snapshot.applescript:lines 28-35` | TSV delimiter/newline injection corrupts output rows |
| U601 | medium | R1 | config | `flag_important_senders.applescript:line 1` | Hardcoded placeholder sender list ships as-is (no-op or wrong matches if run unedited) |
| U602 | medium | R1 | silent-failure | `flag_important_senders.applescript:lines 11-19` | Iterating live inbox messages with bare try swallows errors; no progress/logging |
| U603 | medium | R1 | correctness | `gmail_auth.py:get_credentials() line 162` | No scope verification on loaded token; a narrower stored token is treated as valid |
| U604 | medium | R1 | secrets | `gmail_auth.py:_op_item_edit lines 56-63 (store_token_info 144-154)` | Gmail OAuth token passed as 1Password CLI argv (process-list exposure) |
| U605 | medium | R1 | error-handling | `gmail_auth.py:get_credentials lines 164-178` | Interactive run_local_server(port=0) silently triggered on a headless/automated run |
| U606 | medium | R1 | resource-leak | `gmail_auth.py / auth/onepassword.py:_run_op subprocess.run (gmail_auth:21, onepassword:33)` | No timeout on op subprocess invocation |
| U607 | medium | R1 | error-handling | `gmail_labeler.py:_init_labels lines 98-113 (no error handling around labels().create)` | Label auto-creation in _init_labels has no error handling; a create failure aborts the entire run before any processing |
| U608 | medium | R1 | silent-failure | `gmail_labeler.py:process_batch() lines 194-242; failed_ids handling lines 168-182` | Messages that fail BOTH batch-get and one-by-one retry are silently dropped from categorization (never labeled/archived) |
| U609 | medium | R1 | logic | `gmail_labeler_legacy.py:label_all_unlabeled_emails lines 415-447, max_emails check line 445` | max_emails limit is only enforced between pages, not within a page — can overshoot by up to a full batch |
| U610 | medium | R1 | error-handling | `gmail_labeler_legacy.py:execute_with_retry() lines 299-315` | execute_with_retry has two redundant except blocks and can return None on exhaustion, propagating None to .get()/['id'] callers |
| U611 | medium | R3 | data-quality | `iCloud Mail Filtering Rules - Complete Guide.md:iCloud Mail Filtering Rules - Complete Guide.md:23-24,70-71,216-217` | Committed guide has line-broken email addresses corrupting the documented rules |
| U612 | medium | R1 | error-handling | `icloud_triage.py:main() lines 161-166; per-message archive with no rate-limit/error backoff` | Apply loop has no per-message error backoff and EXPUNGEs after every message; large applies are slow and a mid-loop server error aborts the rest |
| U613 | medium | R1 | resource-leak | `imap_rules.py:main lines 131-158 (no try/finally around imap session)` | IMAP connection leaked on exception — logout only on the happy path |
| U614 | medium | R1 | error-handling | `imap_rules.py:load_password lines 71-77` | 1Password failure falls through to interactive getpass even in non-interactive/automation context, and swallows all errors |
| U615 | medium | R1 | none-handling | `inspect_remaining.py:lines 7-8, 27-28` | Unguarded dict indexing on labels list and header lookups can KeyError/crash |
| U616 | medium | R1 | secrets | `mail_export.tsv:whole file (git-tracked)` | Mail export TSV (PII sink: sender/subject/message_id columns) is committed |
| U617 | medium | R1 | error-handling | `mark_rot_read.py:mark_read_loop() lines 43-64` | No error handling on list/batchModify; pagination relies on label removal and len<1000 heuristic, can loop |
| U618 | medium | R1 | error-handling | `mark_rot_read.py:mark_read_loop lines 43-64` | No error handling on Gmail list/batchModify; service never closed |
| U619 | medium | R1 | logic | `mark_rot_read.py:mark_read_loop() lines 43-64` | Pagination re-queries first page; termination on len(ids)<1000 is unreliable, can loop or under-process |
| U620 | medium | R1 | config | `mark_rot_read.py:TARGET_CATEGORIES lines 23-31` | Marks-read targets reference label names that diverge from the core taxonomy (Work/Dev/* present, but core uses Dev/*) |
| U621 | medium | R2 | import-time side effect | `mcp_server/server.py:lines 73-80 (mcp = FastMCP(...)) and line 151 (http_app = mcp.streamable_http_app())` | Heavy MCP objects (FastMCP server + full ASGI app) are constructed at module import time, and MCP_ALLOWED_HOSTS is read at import |
| U622 | medium | R2 | security | `mcp_server/server.py:triage() provider param line 111; triage_preview() provider line 99; _triage line 132 vs api/schemas.py:45 (provider max_length=64)` | MCP provider argument is length-unbounded, bypassing the HTTP layer's documented anti-DoS max_length=64 |
| U623 | medium | R2 | api-misuse | `mcp_server/server.py:triage_preview() lines 97-107 (annotations readOnlyHint=True) vs api/schemas.py:12-16` | readOnlyHint=True on triage_preview masks a credentialed, quota-consuming scan of up to 1000 messages with a per-batch sleep |
| U624 | medium | R2 | error-handling | `mcp_server/server.py:_triage() lines 137-145 (exception mapping) vs api/app.py:108-122` | MCP error mapping collapses provider-unavailable and gate-violation to generic RuntimeError, losing the HTTP layer's status semantics and is-retriable signal |
| U625 | medium | R1 | error-handling | `providers/base.py:330-363 (apply_actions, star/category exceptions)` | base.apply_actions wraps the entire per-message body in one try/except, so a failure in apply_label aborts remove/archive/star for that message but still counts it as one processed |
| U626 | medium | R2 | correctness / policy | `providers/base.py:apply_actions lines 356-363 (star/category for protected senders on folder providers)` | Protected-sender gate suppresses label-moves but still applies star and category to protected mail |
| U627 | medium | R1 | api-misuse | `providers/gmail.py:144 (list_messages, page_size = min(limit, LIST_PAGE_SIZE))` | list_messages caps maxResults at `limit` but caller paginates expecting full pages, conflating per-page limit with total limit |
| U628 | medium | R1 | error-handling | `providers/gmail.py:97-127 (_execute_with_backoff)` | Backoff has no jitter and a high 10s base, compounding to ~310s worst case while holding the call serialized |
| U629 | medium | R1 | logic | `providers/gmail.py:196-202, 278-284 (label id -> name reverse lookup)` | O(n*m) reverse label lookup per message and silent drop of labels not in cache |
| U630 | medium | R1 | perf | `providers/gmail.py:227-249 (batch_get_details callback / fixed sleep)` | Unconditional time.sleep(2.0) after every batch of 20 makes large fetches very slow and is not configurable |
| U631 | medium | R1 | logic | `providers/gmail.py:80-90 (connect)` | connect() with injected service sets _connected but never initializes label cache, leaving _label_cache empty |
| U632 | medium | R1 | error-handling | `providers/gmail.py:_execute_with_backoff(), lines 97-127` | Rate-limit detection by string-matching the exception message is brittle and may mask non-rate-limit 403s as fatal or vice versa |
| U633 | medium | R1 | api-misuse | `providers/gmail.py:remove_label lines 315-317; apply_actions remove_ids line 413` | remove_label falls back to using raw label name as label ID when not cached |
| U634 | medium | R2 | correctness | `providers/gmail.py:apply_actions audit loop, lines 434 (pending keyed by message_id) and 482-495` | Duplicate message_ids in the action list collide in the pending dict, losing/mis-recording audit receipts |
| U635 | medium | R2 | api-misuse | `providers/gmail.py:apply_label, lines 295-313 (vs apply_actions ensure-label at 408)` | apply_label resolves a stale/missing label id and never re-validates the cache after ensure creates it |
| U636 | medium | R2 | error-handling | `providers/gmail.py:_execute_with_backoff 110-117 (rate_limit detection on e.resp.status in (403,429))` | 403 non-rate-limit errors (insufficientPermissions/forbidden) are only retried if message text matches, else immediately raised — but a 403 quota error whose body lacks the exact tag is treated as fatal |
| U637 | medium | R2 | resource-leak | `providers/gmail.py:_execute_with_backoff 104-127` | Rate-limit backoff sleeps up to 10+20+40+80+160s synchronously, blocking the request thread with no jitter or cap |
| U638 | medium | R1 | error-handling | `providers/imap.py:apply_label 286 (standard IMAP)` | COPY-to-folder does not verify ensure_label_exists succeeded; create('NO') swallowed so COPY to nonexistent folder fails silently-ish |
| U639 | medium | R1 | encoding | `providers/imap.py:_decode_header_value 26-37` | Decoded header parts joined with space can corrupt RFC2047 multi-encoded-word values and ignores decode errors silently |
| U640 | medium | R1 | correctness | `providers/imap.py:list_messages(), lines 192-194` | IMAP pagination slice math can return overlapping or out-of-order pages and uses reverse-from-end indexing that breaks when total < limit |
| U641 | medium | R1 | resource-leak | `providers/imap.py:connect lines 128-141` | IMAP connection leaked if login() fails |
| U642 | medium | R1 | none-handling | `providers/imap.py:list_messages 184-194; get_message_details 214-268; all uid() callers` | IMAP self._connection used without None-check (AttributeError if not connected) |
| U643 | medium | R1 | silent-failure | `providers/mailapp.py:ensure_label_exists(), lines 348-356` | ensure_label_exists swallows mailbox-create failure but still caches the name and returns it, so a later move silently targets a nonexistent mailbox |
| U644 | medium | R1 | api-misuse | `providers/outlook.py:list_messages, 417-434 (param construction) + 428 $top with limit` | Per-call limit not enforced when paginating via @odata.nextLink; can over-fetch beyond requested limit |
| U645 | medium | R1 | error-handling | `providers/outlook.py:ensure_category_exists, 309-321` | Category create-conflict fallback re-fetches but still raises generic RuntimeError, and masks non-conflict errors as 'race' |
| U646 | medium | R1 | none-handling | `providers/outlook.py:get_message_details, 477-478 + 493-500` | Folder-name resolution depends on a cache that is empty when connect() was skipped or folder caching failed; labels silently missing |
| U647 | medium | R1 | error-handling | `providers/outlook.py:_get_msal_app, 152-154` | Corrupt/invalid token cache file aborts auth with an unhandled exception |
| U648 | medium | R1 | correctness | `providers/outlook.py:star, 572-578` | Due-date formatting truncates time to midnight and forces UTC, mis-stating the due date across timezones |
| U649 | medium | R2 | correctness | `providers/outlook.py:list_messages, lines 417-420 (page_token path) vs 428-432 (first-page params)` | Pagination via @odata.nextLink loses $orderby/$select consistency only if server omits them, but more importantly limit/$top is silently dropped on every subsequent page |
| U650 | medium | R2 | correctness | `providers/outlook.py:ensure_category_exists 309-321 + apply_category 340-341` | ensure_category_exists ignores the requested color on the already-exists path, so tier color is silently wrong when category pre-exists |
| U651 | medium | R2 | correctness | `providers/outlook.py:_fetch_child_folders 264-274` | Unbounded recursive child-folder fetch with no depth guard or visited-set |
| U652 | medium | R2 | error-handling | `providers/outlook.py:_acquire_token 184-194 / connect 234-239` | acquire_token_interactive on a headless/hosted server blocks forever (opens a local browser) instead of failing fast |
| U653 | medium | R2 | config/dependency | `requirements-api.txt:lines 3-7 (httpx>=0.27 with comment "required by fastapi.testclient ... and for tests")` | httpx is declared as a runtime dependency but is only used by the test suite (TestClient), bloating the production image |
| U654 | medium | R2 | config/dependency | `requirements-mcp.txt:header comment lines 1-6 ("Optional, ISOLATED") vs CI/Dockerfile which always install it` | `mcp` is framed as "Optional" but is mandatory for the advertised `/mcp` product surface on the deployed (3.11) image |
| U655 | medium | R2 | config/dependency | `requirements.txt:lines 1-15 (whole file: no upper bounds on google-*/requests/pyyaml; floors as low as >=0.5.0)` | All core deps have unbounded version ceilings and very low floors (google-auth-oauthlib>=0.5.0), giving non-reproducible installs and major-version drift |
| U656 | medium | R2 | config/dependency | `requirements.txt:lines 13-15 (mypy/types-requests commented out) vs .github/workflows/ci.yml:31 (pip install ... mypy)` | requirements.txt comments out mypy/types-requests as dev deps, but CI installs an unpinned mypy and runs it with no stub packages — type-check is dependency-incomplete |
| U657 | medium | R1 | correctness | `route_bulk_senders.applescript:lines 23-31` | Move-during-iteration over live inbox messages skips messages (same Mail.app pattern) |
| U658 | medium | R1 | error-handling | `route_bulk_senders.applescript:lines 16-21` | Resolving Newsletters mailbox is unguarded and can abort the whole script |
| U659 | medium | R1 | config | `scripts/gen_commerce_artifacts.py:BASE line 28` | PUBLIC_BASE_URL is not validated; an unset/typo env var bakes a placeholder host into committed machine-readable artifacts |
| U660 | medium | R2 | money/unit arithmetic | `scripts/gen_commerce_artifacts.py:gen_pricing_md lines 61-63 (f"${pk['amount_cents'] / 100:.2f}")` | Credit-pack price rendered via float division of cents (amount_cents / 100) — float-rounding idiom on the published price page |
| U661 | medium | R1 | config | `seed.yaml:lines 1, 8` | Org name in seed.yaml (labores-profani-crux) disagrees with actual git remote (a-organvm) |
| U662 | medium | R2 | config/consistency | `seed.yaml:lines 14-17 (produces: 'Email workflow automation and scheduling' artifact; consumes: [])` | seed.yaml produces/consumes does not describe the implemented commerce product (subscriptions, ACP credit packs, MCP) |
| U663 | medium | R3 | consistency | `seed.yaml:seed.yaml:8 vs server.json:3 / git remote` | Org identifier is inconsistent across surfaces: seed.yaml says 'labores-profani-crux', remote/server.json say 'a-organvm', CLAUDE.md says 'organvm-iii-ergon' |
| U664 | medium | R1 | config | `server.json:lines 16-21` | MCP remote URL points to placeholder mail.example.com |
| U665 | medium | R1 | test-quality | `tests/conftest.py:isolated_commerce_store (20-35)` | Fixture's broad except binds _payment_mod=None and can skip payment-client reset, leaking state between tests |
| U666 | medium | R1 | test-quality | `tests/test_acp.py:_OKPay.charge (23-27); test_complete_is_idempotent_no_double_credit (141-153)` | Test fake payment client ignores idempotency_key, so the per-session charge-dedup claim is never actually exercised |
| U667 | medium | R1 | test-quality | `tests/test_audit.py:test_gmail_override_records_via_audit (271-302) and test_gmail_inbox_removal_via_aliased_cache_id_is_caught (304-344); tests/test_protected_enforcement.py TestGmailOverrideChokepoint (131-173)` | Gmail-override safety tests stub _execute_with_backoff/_drop_if_protected so the override path is partly mocked away |
| U668 | medium | R1 | test-quality | `tests/test_audit.py:test_independent_helper_matches_gate_definition (434-438)` | Test asserts _independently_protected(12345) is False, locking in 'non-str silently swallowed' as correct |
| U669 | medium | R1 | test-quality | `tests/test_config.py:TestApplyEnvConfig.test_env_overrides_batch_size 168-172 and TestLoadConfig 187-201` | Tests only exercise valid numeric/string inputs; no coverage for the int() crash or invalid provider/log_level |
| U670 | medium | R2 | test-quality | `tests/test_mailapp.py:lines 9-25 (only star+due_date test) and tests/test_rules.py:321-326` | No test exercises the one provider that actually consumes due_date (Outlook); the sole due_date star test targets Mail.app which ignores it |
| U671 | medium | R1 | test-quality | `tests/test_mcp.py:lines 11-18 (pytest.importorskip('mcp')) and assertions at 37-42` | MCP destructive/readonly hint assertions silently skip on the Python 3.9 CI floor |
| U672 | medium | R1 | test-quality | `tests/test_models.py:test_merge_deduplicates / test_merge_combines_labels lines 97-108` | merge tests normalize with set()/sorted(), so they cannot detect order loss or the List-vs-Set contract violation |
| U673 | medium | R1 | test-quality | `tests/test_models.py:missing coverage for merge() message_id / sender` | No test covers merge() mismatched message_id or the sender coalescing rule |
| U674 | medium | R1 | test-quality | `tests/test_state.py:TestStateManagerSave / test_save_creates_file (38-52), whole file` | No test for state-file write failure or concurrent/partial-write corruption |
| U675 | medium | R1 | test-quality | `tests/test_store.py:test_set_subscription_partial_update_does_not_clobber (21-32)` | Partial-update test never exercises subscription_id, leaving the stripe_subscription_id no-clobber path uncovered |
| U676 | medium | R1 | test-quality | `tests/test_store.py:test_idempotency_stale_processing_is_reclaimed (91-98)` | Stale-processing reclaim test reaches into private _conn and sets created_at=0 — brittle and only covers the extreme stale case |
| U677 | medium | R2 | security | `web/index.html:line 677 (API_BASE = window.__MAIL_AUTOMATION_API_BASE__) ; whole <script>` | No Content-Security-Policy and an overridable global API base, amplifying the innerHTML sinks |
| U678 | medium | R2 | correctness | `web/index.html:line 838 (parseInt($("limit").value, 10) \|\| 50)` | Limit input max=1000 is not enforced before sending to the unauthenticated preview endpoint |
| U679 | medium | R2 | correctness | `web/index.html:line 882 (email validation regex /.+@.+\..+/)` | Email validation regex is trivially permissive |
| U680 | medium | R2 | error-handling | `web/index.html:lines 788, 790-792 (postJSON error/JSON handling)` | postJSON collapses all transport and JSON-parse errors to a single indistinguishable {ok:false,status:0} / {data:null} |
| U681 | low | R1 | dependency | `.github/workflows/ci.yml:lines 100-106` | wranglerVersion pinned only to major "4" — non-reproducible builds, supply-chain drift |
| U682 | low | R1 | security | `.github/workflows/ci.yml:lines 19, 22, 71, 88` | Third-party actions pinned to mutable major tags instead of commit SHAs |
| U683 | low | R1 | config | `.github/workflows/ci.yml:line 25` | pip cache keyed on default lockfiles may miss requirements-api/mcp changes |
| U684 | low | R2 | config/consistency | `.well-known/agent.json:lines 16-21 (agentic_commerce.spec_version "2026-04-17") and product_feed.json line 1 ("version": "2026-04-17") vs acp/payment.py STRIPE_SPT_API_VERSION line 28 ("2026-04-22.preview")` | Advertised ACP spec_version (2026-04-17) trails the Stripe SPT preview version the charge path actually requires (2026-04-22.preview) |
| U685 | low | R2 | security/consistency | `.well-known/agent.json:lines 22-28 (api block + oauth_scopes: []) vs api/app.py triage/preview/audit endpoints which require no auth (and acp surfaces accepting any bearer)` | agent.json declares oauth_scopes [] and no auth requirement, faithfully mirroring an API that enforces no auth — the manifest normalizes the unauthenticated surface |
| U686 | low | R3 | documentation/completeness | `DEPLOY.md:28-33` | DEPLOY.md Fly.io instructions are generic and unverifiable; no fly.toml ships and secrets list is Gmail-only |
| U687 | low | R2 | config/dependency | `Dockerfile:line 19 (CMD uvicorn ...) relies on uvicorn CLI from requirements-api.txt` | Container start command `uvicorn api.app:app` has no dependency-presence guard; a requirements-api.txt install failure yields a non-obvious 'uvicorn: not found' rather than a build failure |
| U688 | low | R1 | config | `acp/feed.py:build_feed line 50 (currency 'USD') vs acp/router.py:39 CURRENCY='usd'` | Currency case mismatch between feed ('USD') and checkout/charge ('usd') |
| U689 | low | R2 | correctness / spec-conformance | `acp/feed.py:build_feed line 48 (price) and line 47 (image_url) vs ACP product-feed spec` | Product feed emits integer-cents price and a non-image image_url, likely failing strict ACP feed validation |
| U690 | low | R2 | security | `acp/feed.py:feed() line 67-69 (JSONResponse, no Cache-Control) + build_feed reflects base_url` | Product feed reflects Host and is served with no Cache-Control, enabling cached poisoning of checkout_url/seller_url |
| U691 | low | R1 | money-path | `acp/models.py:build_line_items() lines 70-97` | An update/create with an item whose id is valid but quantity drives subtotal has no per-line or grand-total overflow/sanity cap beyond Item.quantity<=1000; many distinct valid items multiply unboundedly |
| U692 | low | R1 | none-handling | `acp/models.py:build_line_items() lines 80-96, item['id'] access` | build_line_items indexes it['id'] with [] though Item guarantees id; but build_line_items is also called with raw model_dump dicts — a missing key would KeyError 500 instead of a clean invalid_items |
| U693 | low | R1 | none-handling | `acp/models.py:build_line_items, lines 80-96` | build_line_items indexes it['id'] and trusts pack['amount_cents']/['runs'] with bracket access; KeyError/TypeError on malformed input |
| U694 | low | R1 | none-handling | `acp/models.py:build_line_items (80-96)` | build_line_items reads it['id'] via dict access and it.get('quantity') without validating against the Pydantic-bounded model in the update path consistently |
| U695 | low | R2 | correctness | `acp/models.py:build_line_items 80-96` | Item quantity read via it.get('quantity',1) but Pydantic Item already bounds qty to 1..1000; raw dict path in router bypasses bound on update with current line_items reuse |
| U696 | low | R2 | correctness/money-arithmetic | `acp/models.py:build_line_items line 85 (int(it.get('quantity',1))) on create path with raw model_dump dicts` | build_line_items re-derives qty via int(it.get('quantity',1)) ignoring the pydantic-validated value, so any non-Item caller bypasses the 1..1000 bound |
| U697 | low | R1 | error-handling | `acp/payment.py:StripeSPTPaymentClient.charge, lines 67-97` | All charge exceptions are collapsed to a generic 'charge failed' that the session reports as retriable, masking permanent (non-retriable) declines |
| U698 | low | R1 | money-path | `acp/payment.py:charge / PaymentIntent.create, lines 72-88 (no amount > 0 guard)` | No guard that amount > 0 before calling Stripe; a zero/empty line-item session reaching charge would error from Stripe rather than be caught early |
| U699 | low | R2 | money/unit arithmetic | `acp/payment.py:StripeSPTPaymentClient.charge lines 72-88 (amount=int(amount), currency=currency passed verbatim)` | Charge currency is passed verbatim from CURRENCY='usd' while the feed/receipt advertise 'USD' — no normalization, and amount is trusted to already be minor units with no unit assertion |
| U700 | low | R2 | config / silent-failure | `acp/payment.py:103-110 (get_payment_client) cross-ref router 262-267` | If STRIPE_SECRET_KEY is empty-string (set but blank), NullPaymentClient is selected and every ACP completion silently fails closed with no operator signal |
| U701 | low | R2 | correctness / robustness | `acp/payment.py:StripeSPTPaymentClient.charge lines 72-88, currency param` | Charge passes currency unchanged but ACP currency constant is lowercase 'usd' while feed advertises 'USD' — no normalization before Stripe |
| U702 | low | R2 | correctness/money-arithmetic | `acp/payment.py:StripeSPTPaymentClient.charge line 74 (int(amount)) — no upper bound / no >0 guard before Stripe call` | Charge passes int(amount) to Stripe with no minimum or maximum bound, so a desynced/huge amount is sent verbatim |
| U703 | low | R1 | money-path | `acp/router.py:create_session() / _persist / save_session — session expiry` | ACP sessions are never expired; STATUS_EXPIRED is defined and checked but no code ever transitions a session to expired, so a READY session with a stale price can be completed indefinitely |
| U704 | low | R1 | money-path | `acp/router.py:update_session, lines 223-226` | On update without items, total_runs is read from row['data']['total_runs'] but line_items kept from current['line_items']; if persisted shapes ever diverge the charge amount and credited runs desynchronize |
| U705 | low | R1 | money-path | `acp/router.py:complete_session, line 289` | Auto-created account on /complete is plan='free' with no email/customer link; credited runs attach to an orphan account unreachable via billing |
| U706 | low | R1 | correctness | `acp/router.py:_begin_idempotency() / create_session etc., lines 100-117, 167-190` | Idempotency replay can return a stored response of JSON null, and gate parses body before idempotency claim allowing partial side effects |
| U707 | low | R1 | money-path | `acp/router.py:complete_session early-return when already completed (248-251)` | Idempotent already-completed return does not re-shape order/permalink and can return a session without the order on a fresh Idempotency-Key |
| U708 | low | R1 | api-misuse | `acp/router.py:_gate (79-83)` | Bearer parsing does not strip the scheme case-insensitively and ignores leading whitespace nuances; malformed-but-intended tokens slip through as opaque keys |
| U709 | low | R1 | logic | `acp/router.py:complete_session error-path persist (273-280)` | On payment failure the buyer field can be silently dropped/overwritten and the session is re-persisted as READY without re-validating items |
| U710 | low | R2 | money-correctness | `acp/router.py:257 + 262-266` | amount=0 (empty/zero-priced READY session) is charged and the response treated as fulfillable |
| U711 | low | R2 | correctness / billing | `acp/router.py:update_session lines 217-225; complete_session line 257 grand_total` | update_session with items=None keeps line_items but re-reads total_runs from stored row, while complete recomputes amount from line_items — divergence risk if persisted shapes drift |
| U712 | low | R2 | security | `acp/router.py:_persist 149-155 / get_session 193-197` | Saved ACP session 'response' embeds links built from a per-request base_url, so a replay/get returns URLs from whichever Host first created the session |
| U713 | low | R2 | correctness | `acp/router.py:complete_session lines 296-317 (order_receipt_body summary) vs api/receipts.py get_receipt lines 125-131 + store.save_receipt line 287 (json.dumps round-trip)` | ACP order-receipt summary contains an int amount/runs that round-trips through JSON; re-served signed_body may not re-verify if any value type coerces |
| U714 | low | R2 | correctness/money-arithmetic | `acp/router.py:complete_session lines 273-280 (payment-failed re-shape uses current['line_items'] but does NOT re-persist total_runs from a re-derivation) + 278 _persist(total_runs)` | Payment-failed branch re-persists the session preserving the OLD total_runs/line_items without re-validating them against CREDIT_PACKS before the next retry |
| U715 | low | R1 | error-handling | `api/billing.py:_period_end lines 294-303 and set_subscription current_period_end` | current_period_end parsed with int() but no validation it is a sane epoch; partial events can leave period_end stale |
| U716 | low | R1 | api-misuse | `api/billing.py:webhook() lines 181-185` | Broad except over stripe.error.SignatureVerificationError attribute access can itself raise AttributeError on some stripe SDK versions |
| U717 | low | R1 | money-path | `api/billing.py:_handle_event() customer.subscription.* branch, line 248-262` | status from Stripe passed straight into set_subscription; an unexpected/None status can leave a paid plan with no status update while plan stays paid |
| U718 | low | R1 | money-path | `api/billing.py:_period_end() lines 294-303 and _handle_event invoice.paid line 265-270` | invoice.paid sets status=active without re-checking subscription validity; period_end parsing swallows malformed values to None |
| U719 | low | R1 | money-path | `api/billing.py:_handle_event subscription branch (240-262)` | Subscription status written verbatim from Stripe without normalization; non-active statuses other than the canceled set leave paid plan in place |
| U720 | low | R1 | money-path | `api/billing.py:create_checkout (119-124)` | Checkout can create an orphan free account that is never linked to the resulting Stripe customer |
| U721 | low | R1 | error-handling | `api/billing.py:_handle_event 222-277; webhook try/except 197-202` | Unhandled DB exceptions from the event handler 500 and wedge the event into a permanent retry loop |
| U722 | low | R1 | resource-leak | `api/billing.py:_resolve_account 218 -> store.create_account; subsequent set_subscription 231/255` | Orphan account created by webhook may be left without its customer link if set_subscription then fails, leaking unreferenced rows |
| U723 | low | R1 | correctness | `api/billing.py:_handle_event invoice.paid 265-270` | invoice.paid sets status='active' without touching plan, producing plan='free'+status='active' on accounts created by the orphan path |
| U724 | low | R1 | error-handling | `api/billing.py:webhook handler line 187 (event['id']) and 196 (event['data']['object'])` | Webhook uses bracket indexing on the verified event without guarding malformed-but-signed payloads |
| U725 | low | R1 | correctness | `api/billing.py:_handle_event checkout.session.completed 225-238 vs subscription branch` | checkout.session.completed hard-codes status='active' regardless of actual subscription/payment state |
| U726 | low | R2 | datetime/timezone | `api/billing.py:lines 294-303 (_period_end) feeding store.current_period_end (INTEGER) at billing.py:261, store.py:49/199-211` | current_period_end stored as a bare Stripe epoch int with no semantic check; any consumer comparing it must use UTC fromtimestamp, but no such consumer/normalization exists |
| U727 | low | R2 | error-handling / config | `api/billing.py:183 (stripe.error.SignatureVerificationError) + 173-185` | construct_event ValueError on malformed JSON and SignatureVerificationError both map to 400, but a missing stripe-signature header yields empty string -> still a verification error, never a distinct 'no signature' path |
| U728 | low | R1 | config | `api/plans.py:plan_id_for_price() lines 164-172` | Reverse price->plan mapping is O(n) over plans reading env each iteration; if two plans share/misconfigure the same price env value, first match wins silently |
| U729 | low | R2 | money/unit arithmetic | `api/plans.py:list_plans/public_dict: price_cents (plans.py:56) and credit_packs amount_cents (billing.py:100) returned without a unit field; metered unit_amount_cents (plans.py:134)` | Public billing catalog returns three differently-named integer-cent fields (price_cents, unit_amount_cents, amount_cents) with no per-amount unit declaration |
| U730 | low | R1 | auth | `api/receipts.py:get_receipt route lines 114-142` | GET /v1/audit/{run_id} is unauthenticated and run_ids/order_ids enumerate the receipt ledger |
| U731 | low | R1 | silent-failure | `api/receipts.py:persist() lines 88-108` | Receipt ledger write failure is swallowed to a warning, so a Pro/Business customer paying for 'retained receipt history' can silently lose receipts |
| U732 | low | R1 | config | `api/receipts.py:_signing_key lines 44-57` | Ephemeral HMAC signing key fallback silently breaks receipt verification across restarts (integrity fallback) |
| U733 | low | R1 | none-handling | `api/receipts.py:verify, lines 71-74` | verify() treats a missing/empty signature as a normal non-match rather than distinguishing 'no signature present' |
| U734 | low | R1 | correctness | `api/receipts.py:get_receipt, lines 122-141 (with core/audit.py summary 241-251 and api/store.py save_receipt 280-290 / get_receipt 292-298)` | Stored summary round-trips through JSON (SQLite) so signed body bytes may differ from re-served body, breaking verification even without tampering |
| U735 | low | R1 | concurrency | `api/receipts.py:_signing_key + _EPHEMERAL_KEY module global, lines 41-57` | Ephemeral key lazy-init is not thread-safe (read-check-set race on _EPHEMERAL_KEY under FastAPI threadpool) |
| U736 | low | R1 | api-misuse | `api/schemas.py:TriageRequest.query Field max_length=2048 lines 46` | Provider query string is length-bounded but not otherwise validated; passed straight to provider.list_messages enabling provider-side query abuse |
| U737 | low | R1 | error-handling | `api/store.py:get_receipt lines 292-298` | get_receipt does json.loads(summary_json) and pops it, but if summary_json is somehow NULL/invalid it raises uncaught |
| U738 | low | R1 | concurrency | `api/store.py:Store.__init__ / single shared connection lines 127-138` | Single shared sqlite3 connection with check_same_thread=False relies solely on an RLock; any code path that touches self._conn outside _lock corrupts serialization, and there is no transaction isolation across multi-statement methods |
| U739 | low | R1 | concurrency | `api/store.py:idempotency_begin, lines 334-347 (stale-claim re-bind)` | Stale idempotency claim is re-bound after 60s even mid-charge, allowing a duplicate /complete to proceed concurrently with a slow-but-alive original |
| U740 | low | R1 | logic | `api/store.py:337-344 (stale reclaim UPDATE)` | Stale-claim reclaim updates created_at but never resets status or clears a prior response_json, leaving a window where a re-claimed key could already hold a response |
| U741 | low | R1 | logic | `api/store.py:337 (time arithmetic _now() - existing['created_at'])` | Stale-claim window uses wall-clock time.time(); a backward clock step (NTP correction) can make a fresh 'processing' claim appear stale or never expire |
| U742 | low | R1 | none-handling | `api/store.py:352 (json.loads(existing['response_json'] or 'null'))` | Replay of a key whose response_json is NULL silently returns response=None, which the router forwards as a JSON 'null' body with HTTP 200 |
| U743 | low | R2 | money/unit arithmetic | `api/store.py:add_credits lines 223-233 / consume_credit 235-246 (run_credits ledger) vs acp/router.py fulfill_once crediting total_runs (router 290)` | run_credits balance and the dollar amount charged are tracked in unrelated units with no linkage — a credited-runs vs amount-paid mismatch cannot be detected |
| U744 | low | R2 | error-handling/serialization | `api/store.py:save_receipt 280-290 (json.dumps(summary)); idempotency_complete 360 (json.dumps(response)); save_session 410 (json.dumps(data))` | json.dumps of caller-supplied dicts can raise TypeError on non-JSON-serializable values, raising inside the lock with no rollback |
| U745 | low | R2 | resource-leak/lifecycle | `api/store.py:close 140-142 vs get_store 445-460 (no re-init guard)` | close() leaves the singleton pointing at a closed connection; any later call raises 'Cannot operate on a closed database' on every method |
| U746 | low | R2 | concurrency / data-integrity | `api/store.py:save_session lines 392-413 (INSERT OR REPLACE) vs fulfill_once 365-389` | save_session uses INSERT OR REPLACE keyed only on session id with no status/account guard — a concurrent cancel can overwrite a completed session |
| U747 | low | R2 | race | `api/store.py:Store.__init__ 127-138 / get_account_by_api_key 170-175` | Single shared sqlite connection with check_same_thread=False relies entirely on RLock; any code path touching _conn without the lock corrupts the connection |
| U748 | low | R2 | correctness/money-arithmetic | `api/store.py:add_credits lines 223-233 + consume_credit lines 235-246 (no overflow / SQLite INTEGER semantics)` | run_credits INTEGER accumulates unbounded via add_credits/fulfill_once; a 1M-run pack repeatedly fulfilled has no ceiling and consume_credit's n is uncapped |
| U749 | low | R2 | correctness/money-arithmetic | `api/store.py:fulfill_once line 378 int(runs) — negative/huge runs accepted verbatim into balance` | fulfill_once trusts the runs argument with no >=0 guard, so a negative or oversized total_runs is credited (or debited) verbatim |
| U750 | low | R1 | correctness | `auth/onepassword.py:op_item_edit() line 111; field assignment format` | Field name with a dot is reinterpreted by `op` as section.field; unescaped assignment |
| U751 | low | R1 | security | `auth/onepassword.py:_run_op() lines 42-46 (non-sensitive branch)` | op stderr echoed into RuntimeError can leak vault/item names into error surfaces |
| U752 | low | R1 | error-handling | `auth/onepassword.py:_run_op op_read/op_item_get (sensitive defaults False), lines 60-64, 85-91` | Read paths do not set sensitive=True, so op CLI stderr is interpolated into error messages |
| U753 | low | R1 | api-misuse | `auth/onepassword.py:op_item_edit, lines 111-116 vs op_item_get lines 85-90` | Inconsistent/undocumented op CLI flag ordering for edit vs get; --vault placement after positional assignment |
| U754 | low | R1 | none-handling | `auth/onepassword.py:load_secret, lines 169-171` | Empty-string secret is treated as 'not present' and silently falls through to next source |
| U755 | low | R1 | silent-failure | `auth/onepassword.py:store_json_secret, op_item_edit success path (no logging)` | Credential write-back has no audit/success logging, so a wrong-field or wrong-vault write is undetectable |
| U756 | low | R1 | api-misuse | `auto_drain.py:callback lines 121-129; batch.execute line 135` | batch.execute() unguarded; header lookup by exact-case 'From'/'Subject' may miss |
| U757 | low | R1 | none-handling | `cli.py:cmd_summary line 564; cmd_pending line 680; cmd_summary tier_counts init line 535` | tier_counts indexed by cat_result.tier can introduce out-of-range tiers / KeyError-free silent growth |
| U758 | low | R1 | silent-failure | `cli.py:cmd_escalate lines 924-930` | escalate: when no actions built (e.g., all dry-run) result.success_count is set to escalated_count, but with dry_run escalated_count>0 and actions empty conflates 'previewed' with 'succeeded' |
| U759 | low | R1 | security | `cli.py:_make_audit line 369` | audit default path built from args.provider unsanitized; provider is choice-restricted so low risk, but audit_file custom path has no path-traversal guard |
| U760 | low | R1 | correctness | `cli.py:run_labeler lines 274-275 remove_label logic` | remove_label only removed when computed label differs from remove_label; equality check is exact-string and case-sensitive |
| U761 | low | R2 | correctness | `configure_smart_mailboxes.py:main 98-124` | Edits SyncedSmartMailboxes.plist in place while Mail may be running, with a single .backup that prior runs overwrite |
| U762 | low | R1 | resource-leak | `core/audit.py:_append() lines 215-238 (append mode, no fsync)` | Audit JSONL append is not flushed/fsynced; tail of receipt can be lost on crash |
| U763 | low | R1 | logic | `core/audit.py:_domain_of() fallback line 92` | Fallback domain parser strips '>' but not '<' / whitespace inside, and differs from canonical normalize_sender |
| U764 | low | R1 | concurrency | `core/audit.py:record() entry timestamp line 198 vs receipt; concurrency on shared path` | Concurrent AuditLog writers to same path can interleave/lose lines (no locking) |
| U765 | low | R2 | correctness | `core/audit.py:record() lines 152/184/200 (message_id typed str but accepted/stored unvalidated)` | message_id accepted and stored without type/empty validation; empty or non-str ids silently pollute the violations trail |
| U766 | low | R1 | config | `core/config.py:DEFAULT_CONFIG_PATHS lines 17-21 (module level)` | Path.expanduser() evaluated at import time freezes HOME |
| U767 | low | R1 | silent-failure | `core/config.py:_apply_env_config, lines 270-271` | DRY_RUN env var cannot be turned OFF and silently ignores invalid values |
| U768 | low | R1 | logic | `core/models.py:LabelAction.merge() lines 95-108` | merge() reorders labels via set(), losing deterministic label order |
| U769 | low | R1 | correctness | `core/models.py:combined_text property line 58` | combined_text emits a leading/trailing space for empty fields, polluting the match string (e.g. ' ' for empty sender+subject) |
| U770 | low | R1 | logic | `core/rules.py:escalate_by_age lines 1091-1160 (boundaries 1131, 1147) vs docstring 1099-1102` | Tier 2 emails in the 24-72h window never escalate, contradicting the documented 'Tier 2-4 -> Tier 1' intent and time-sensitivity |
| U771 | low | R1 | logic | `core/rules.py:escalate_by_age lines 1122, 1131, 1147; final return 1155-1160` | Negative / NaN email_age_hours mis-handled and final return is dead code |
| U772 | low | R1 | logic | `core/rules.py:_resolve_addr unprotected-relay branch lines 729-737; _self_match 777-784` | Relay senders resolve to email='' so the Gmail self-match can never fire for relayed self-mail |
| U773 | low | R1 | logic | `core/rules.py:categorize_with_tier VIP-no-override branch lines 991-995 vs normal branch 1006-1008` | VIP-without-override path re-categorizes on combined_text but defaults time_sensitive=True, diverging from non-VIP default of the rule's own value |
| U774 | low | R1 | regex | `core/rules.py:Personal rule patterns line 488 (tier 1 Critical)` | Personal rule's generic keywords (family/mom/dad) at tier 1 risk elevating marketing mail to Critical when it outranks competing rules |
| U775 | low | R1 | regex | `core/rules.py:_find_best_label() lines 1025-1038; LABEL_RULES catch-all pattern r'.*' line 502` | Catch-all regex r'.*' and broad substring patterns cause mojibake/over-matching; categorization is advisory but feeds archive decisions in tier_routing |
| U776 | low | R2 | regex | `core/rules.py:LABEL_RULES Marketing 433-437` | Duplicate/overlapping flash-sale regexes — one alternation is dead, and broad keywords mislabel transactional mail |
| U777 | low | R2 | correctness | `core/rules.py:_resolve_addr 720; _idna_decode 636-649` | appleid.com endswith check treats any '*.appleid.com' as a relay, mis-routing legitimate appleid subdomains |
| U778 | low | R2 | correctness | `core/rules.py:_load_local_protected 599-613 / module import 616-621` | Protected-sender local config loaded once at import; file is read with no size bound and merged unvalidated, and a domain line that is actually a comment-only or malformed entry is added verbatim |
| U779 | low | R1 | api-misuse | `core/state.py:save() line 87 datetime.now()` | last_run timestamp uses naive local datetime.now() (no tz) — inconsistent with audit's UTC |
| U780 | low | R1 | none-handling | `core/state.py:save, line 86 (self.state['history'] = dict(history))` | save() assumes history is mapping-like; a non-dict argument raises inside save |
| U781 | low | R1 | correctness | `core/state.py:is_resumable, lines 131-133 vs get_token usage in cli.py:172` | is_resumable only null-checks the token; an empty-string or non-string token is reported resumable |
| U782 | low | R4 | correctness | `create_smart_mailboxes.scpt:lines 19` | Date condition 'is less than value:30' is likely wrong units for a date-received filter |
| U783 | low | R4 | correctness | `create_smart_mailboxes.scpt:lines 17-26` | 'message is in mailbox does contain Finance/Dev' depends on Gmail labels existing as Mail.app mailboxes |
| U784 | low | R1 | correctness | `final_sweep.py:line 18` | Query 'label:Uncategorized' likely targets a non-existent label (taxonomy uses 'Misc/Other') |
| U785 | low | R2 | correctness | `flag_important_senders.applescript:lines 4-6` | is_important `contains s` iterates over a `text item` reference, not the string value (missing `contents of`) |
| U786 | low | R2 | correctness | `gmail_auth.py:get_credentials 164-178` | Scope upgrade silently ignored when a cached token has narrower scopes |
| U787 | low | R1 | logic | `gmail_labeler.py:process_batch retry block lines 168-182, lambda closure line 173` | Late-binding closure over loop variable in retry lambda (msg_id) — works here but fragile |
| U788 | low | R1 | logic | `gmail_labeler.py:process_batch lines 247-261, batchModify lambda body closure line 258-260` | batchModify lambda closes over loop variable 'body' (rebuilt each iteration) — relies on synchronous invocation |
| U789 | low | R1 | api-misuse | `gmail_labeler.py:_execute_with_backoff lines 78-93; batch_get.execute retry at line 164` | Batch HTTP retry re-executes an already-consumed BatchHttpRequest on rate limit, likely raising instead of retrying |
| U790 | low | R1 | race-condition | `gmail_labeler.py:run() exception handler lines 333-335 saving page_token` | On fatal mid-batch error, state is saved with the NEXT page token though the current batch was only partially modified |
| U791 | low | R1 | correctness | `gmail_labeler.py:process_batch stats line 204 vs continue at line 213` | Stats counter increments for messages that are then skipped (no label cached), over-reporting processed distribution |
| U792 | low | R1 | concurrency | `gmail_labeler.py:process_batch() lines 257-262; batchModify lambda closure over `body`` | Lambda in batch-modify retry closes over loop variable `body`; safe today but a latent closure-capture bug |
| U793 | low | R1 | error-handling | `gmail_labeler_legacy.py:execute_with_retry lines 299-316` | execute_with_retry can return None implicitly (no exception, no value) and retries non-retryable errors blindly |
| U794 | low | R1 | none-handling | `gmail_labeler_legacy.py:categorize_email lines 340-364 vs core _find_best_label` | Legacy categorize_email accesses email_data['payload']['headers'] without guards (KeyError on missing payload) |
| U795 | low | R1 | logic | `gmail_labeler_legacy.py:label_all_unlabeled_emails pagination lines 399-451 (default query 'has:nouserlabels')` | Same draining-query-with-page-token hazard as gmail_labeler.py; plus no state persistence so a crash loses all progress |
| U796 | low | R1 | api-misuse | `gmail_labeler_legacy.py:verify_labeling_complete() line 485; label_all_unlabeled_emails resultSizeEstimate usage` | resultSizeEstimate used as exact count; it is an ESTIMATE and unreliable for completion checks |
| U797 | low | R1 | logic | `icloud_triage.py:main, line 112` | `--limit` slice keeps most-recent UIDs but archives them — opposite of typical 'archive old noise' intent, and limit semantics may surprise |
| U798 | low | R1 | silent-failure | `icloud_triage.py:fetch_from_subject, lines 55-60` | IMAP fetch failure for a single message returns ('','') which then bypasses protected check via empty sender = protected (OK) but mislabels via empty domain |
| U799 | low | R1 | injection | `icloud_triage.py:connect line 49-52 / archive_uid line 67-72` | Mailbox name is wrapped in literal quotes but not escaped, breaking on names containing quotes/special chars |
| U800 | low | R1 | injection | `icloud_triage.py:archive_uid lines 67-77` | IMAP archive-mailbox name injected unescaped into UID MOVE/COPY |
| U801 | low | R1 | logic | `icloud_triage.py:archive_uid lines 67-71` | Narrow except on MOVE only catches imaplib.IMAP4.error; MOVE returning non-OK without raising falls through to COPY duplicating the message |
| U802 | low | R1 | logic | `icloud_triage.py:main() lines 104-112; UID search + slice` | data[0].split() on a failed/None search and most-recent-N slice assume sequential UID ordering |
| U803 | low | R1 | logic | `icloud_triage.py:main() line 130; normalize_sender vs is_protected_sender domain basis` | Categorization uses normalize_sender's FIRST address only while protection uses the union; a multi-address From categorizes off one address |
| U804 | low | R1 | error-handling | `imap_rules.py:ensure_label lines 95-100` | ensure_label caches label as created on IMAP error responses other than OK/NO, and treats NO as success blindly |
| U805 | low | R1 | injection | `imap_rules.py:apply_label lines 103-110; ensure_label line 95-100` | Legacy IMAP label injection (unescaped quotes in STORE/COPY) |
| U806 | low | R1 | error-handling | `imap_rules.py:load_password() lines 51-77` | load_password has unreachable final return and broad except hiding 1Password failures; can silently proceed with empty password |
| U807 | low | R4 | config | `llms.txt:lines 5-14` | Route list omits POST /v1/triage and may drift from actual api/app.py routes |
| U808 | low | R1 | api-misuse | `mark_rot_read.py:query line 41 + TARGET_CATEGORIES` | Label names with spaces/slashes are interpolated into Gmail query without quoting |
| U809 | low | R1 | error-handling | `mcp_server/server.py:_clamp_limit() line 83-84; triage limit param typed int` | _clamp_limit assumes coercible limit; int(limit) can raise on bad MCP input |
| U810 | low | R1 | config | `mcp_server/server.py:_transport_security() lines 48-58` | MCP_ALLOWED_HOSTS='*' fully disables DNS-rebinding protection with no origin checks |
| U811 | low | R1 | config | `mcp_server/server.py:_transport_security 40-58; _clamp_limit 83-84; check_protected_sender 94` | DNS-rebinding protection fully disabled when MCP_ALLOWED_HOSTS='*' |
| U812 | low | R2 | config | `mcp_server/server.py:module import time line 151 (http_app = mcp.streamable_http_app()) and lines 38-45 in api/app.py` | _transport_security() reads MCP_ALLOWED_HOSTS once at import time, freezing the host allowlist for the process |
| U813 | low | R2 | security | `mcp_server/server.py:_transport_security 48-58` | MCP_ALLOWED_HOSTS hardcodes :8000 dev hosts into the production allowlist and builds origins by string concat, admitting any scheme-host on port 8000 |
| U814 | low | R2 | security | `mcp_server/server.py:_transport_security lines 48-58 (allowed_hosts hard-appends localhost:8000 only)` | DNS-rebinding allowlist hardcodes only :8000 loopback variants; a hosted MCP on a non-8000 port loses loopback dev access and may push operators to set MCP_ALLOWED_HOSTS=* (protection off) |
| U815 | low | R1 | logic | `organize_labels.py:main lines 49-63` | Rename conflict handling updates local index incorrectly, and rename can collide with existing Gmail label causing API error mid-pass |
| U816 | low | R1 | correctness | `organize_labels.py:RENAMES line 15-25` | Hardcoded label-rename map with no dry-run mutates live Gmail label taxonomy immediately |
| U817 | low | R1 | logic | `organize_labels.py:main() lines 49-63; rename conflict / mapping update` | Label rename updates name_to_meta[new] to the SAME meta object, so chained renames and conflict detection can misbehave |
| U818 | low | R1 | error-handling | `providers/base.py:402-413 (health_check)` | health_check swallows ALL exceptions into a generic unhealthy status, masking auth vs network vs quota distinctions |
| U819 | low | R2 | correctness | `providers/base.py:_drop_if_protected 299-305` | Gate neutralizes archive + INBOX-removal but does NOT clear action.star / action.category / move-on-label for non-LABEL_IS_MOVE folder providers when archive flag is the only departure |
| U820 | low | R1 | logic | `providers/gmail.py:459-466 (apply_actions, batchModify lambda)` | batchModify body captured by late-binding closure inside loop |
| U821 | low | R1 | api-misuse | `providers/gmail.py:248-256 (batch_get_details)` | batch.execute retried wholesale on rate limit can double-process already-succeeded messages and accumulate state in closure |
| U822 | low | R1 | logic | `providers/gmail.py:432-438 (apply_actions audit inbox-form detection)` | left_inbox detection upper-cases label-cache INBOX id but real Gmail user-label ids are mixed-case opaque tokens |
| U823 | low | R1 | none-handling | `providers/gmail.py:169-184 (get_message_details)` | get_message_details bypasses 404-to-None handling when the 404 is wrapped by backoff RuntimeError, and only treats status==404 specially |
| U824 | low | R1 | logic | `providers/gmail.py:209-210, 291-292 (is_read derivation)` | is_read derived as 'UNREAD not in label_ids' — relies on UNREAD always being present in metadata labelIds |
| U825 | low | R1 | correctness | `providers/gmail.py:apply_actions() lines 459-472 with _execute_with_backoff closure` | Late-binding closure over loop variable 'body' in batchModify lambda can apply the WRONG batch on retry |
| U826 | low | R1 | api-misuse | `providers/gmail.py:batch_get_details callback, lines 227-235` | Batch callback records failures but the surrounding batch.execute via _execute_with_backoff can lose individual successes on a whole-batch retry |
| U827 | low | R2 | correctness | `providers/gmail.py:list_messages 144 + _init_label_cache 129-135 + get_message_details 196-202 label reverse-map` | Reverse label-id->name map silently drops labels created after connect() (cache populated only at connect), under-reporting message.labels |
| U828 | low | R2 | correctness / smell | `providers/gmail.py:apply_actions lines 459-466 (lambda over loop variable body)` | batchModify lambda captures loop-mutated 'body' by closure — safe today but a latent footgun if execution is ever deferred |
| U829 | low | R2 | correctness | `providers/gmail.py:apply_actions 432-438 (inbox_id resolution)` | INBOX 'left_inbox' detection upper-cases the cached INBOX id but compares against remove_ids that were built from raw label-cache ids, so a non-literal INBOX id mismatch can hide a real archive from the audit |
| U830 | low | R1 | correctness | `providers/imap.py:get_message_details 257-259` | Read/starred status via substring match '\\Seen'/'\\Flagged' in raw FLAGS string can false-positive on label/user-flag names |
| U831 | low | R1 | security | `providers/imap.py:_load_password 100-126 / connect 136` | 1Password subprocess uses check_output with broad except; password failures swallowed, and op CLI arg injection via env-controlled item name |
| U832 | low | R1 | none-handling | `providers/imap.py:_load_password 106 / connect 140` | Password potentially returned as None type leading to confusing login failure |
| U833 | low | R1 | none-handling | `providers/imap.py:_select_mailbox 155-161 / multiple methods` | Methods dereference self._connection without verifying connect() ran -> AttributeError if used outside context manager |
| U834 | low | R1 | resource-leak | `providers/imap.py:disconnect 143-153` | logout() may leave socket open on certain server errors; no close()/shutdown fallback |
| U835 | low | R1 | api-misuse | `providers/imap.py:list_messages 197-202 (uid.decode) vs get_message_details usage` | UID decoded to str for EmailMessage.id but downstream STORE/FETCH pass it back as str — fine, but no validation that data[0] split tokens are UIDs |
| U836 | low | R1 | error-handling | `providers/imap.py:_load_password lines 114-121` | Broad except Exception when loading IMAP password swallows real errors and falls through |
| U837 | low | R2 | correctness / API-misuse | `providers/imap.py:apply_label lines 277-292; archive line 312-315; _select_mailbox 155-161` | IMAP write operations assume the correct mailbox is selected, but apply_actions issues UID STOREs without re-selecting INBOX |
| U838 | low | R1 | correctness | `providers/mailapp.py:list_messages parsing 190` | is_read/is_starred parsed from raw AppleScript boolean string is fragile to localization/format |
| U839 | low | R1 | race | `providers/mailapp.py:connect 92-102` | Mail.app launch uses fixed `delay 2` race; subsequent operations may run before Mail is ready |
| U840 | low | R1 | correctness | `providers/mailapp.py:list_messages 201` | Pagination next_token off-by-one boundary when total is exactly a multiple of limit |
| U841 | low | R1 | error-handling | `providers/mailapp.py:list_messages 144` | AppleScript repeat upper bound uses string-interpolated arithmetic that breaks for non-int page_token |
| U842 | low | R1 | correctness | `providers/mailapp.py:list_messages() AppleScript repeat range, lines 144-163` | Mail.app list pagination builds an O(N) AppleScript that re-indexes 'item i of allMsgs' and uses unescaped account name |
| U843 | low | R2 | datetime/timezone | `providers/mailapp.py:lines 191-228 (list_messages/get_message_details build EmailMessage with no date) cross-ref line 293-294 star ignores due_date` | Mail.app provider returns dates in local zone semantics nowhere normalized; combined with calculate_email_age_hours assume-UTC, any future date population would be tz-wrong |
| U844 | low | R1 | api-misuse | `providers/outlook.py:archive, 544-555` | Archive uses literal destinationId 'archive'; if the well-known alias is not accepted the message stays in inbox and only logs an error |
| U845 | low | R1 | concurrency | `providers/outlook.py:remove_category, 379-392 + apply_category 346-364` | Category read-modify-write PATCH is non-atomic and can lose concurrent category changes |
| U846 | low | R1 | none-handling | `providers/outlook.py:list_messages 461 (msg['id']) and get_message_details / general` | Direct dict indexing msg['id'] in list_messages will KeyError if Graph omits id; not defensively handled like other fields |
| U847 | low | R1 | resource-leak | `providers/outlook.py:_get_session, 196-211` | requests.Session never closed on the no-connect / health-check error paths; potential socket leak across repeated provider instantiation |
| U848 | low | R1 | none-handling | `providers/outlook.py:_acquire_token, 184-191` | Interactive token result accessed without None guard; acquire_token_interactive returning None would raise TypeError instead of clean error |
| U849 | low | R1 | correctness | `providers/outlook.py:_init_folder_cache 255 / get_message_details 493-499` | Folder cache stores only displayName; well-known folders (Inbox, Archive, Sent) keyed by localized displayName can mismatch move targets |
| U850 | low | R1 | error-handling | `providers/outlook.py:ensure_category_exists(), lines 309-321` | Category create error is logged at debug and masked as 'race condition'; a real failure raises a generic RuntimeError losing the original cause |
| U851 | low | R1 | resource-leak | `providers/outlook.py:_get_session 196-211; _api_get/_api_post/_api_patch 213-232; disconnect 241-247` | requests.Session leaked on all error paths (no context manager / try-finally) |
| U852 | low | R1 | injection | `providers/outlook.py:ensure_label_exists lines 641-643 ($filter displayName eq '{part}')` | OData filter injection via folder name single-quote |
| U853 | low | R1 | security | `providers/outlook.py:list_messages lines 417-420 (page_token used as full URL)` | Pagination follows server-provided @odata.nextLink as the request URL (open-redirect / SSRF-shaped trust) |
| U854 | low | R2 | datetime/timezone | `providers/outlook.py:lines 455 and 506 (msg["receivedDateTime"].replace("Z", "+00:00"))` | Unanchored .replace("Z", ...) on the ISO timestamp corrupts any string containing a stray 'Z' |
| U855 | low | R2 | correctness | `providers/outlook.py:ensure_label_exists, lines 641-646 ($filter displayName eq '{part}' lookup) and 658-664 in __init__ folder cache by displayName` | Folder lookup by displayName eq '{part}' returns the FIRST match across the whole mailbox, ignoring parent scope when parent_id is None |
| U856 | low | R2 | correctness | `providers/outlook.py:_init_folder_cache 254-259 and ensure_label_exists 610-651 (folder name keying with '/')` | Folder names containing a literal '/' collide with the hierarchical path separator, corrupting the folder cache and routing moves to the wrong folder |
| U857 | low | R2 | correctness | `providers/outlook.py:apply_category, lines 346-356 (de-dupe is case- and whitespace-sensitive)` | Category de-dupe is exact-string; Graph treats category names case-insensitively, so repeated runs append duplicate-by-case categories |
| U858 | low | R2 | correctness | `providers/outlook.py:archive 544-555 (destinationId='archive') and apply_label 527-530 (folder move)` | Archive move and folder move share no idempotency/verification — re-running archive on an already-archived message issues a redundant move and a failed move is only logged |
| U859 | low | R2 | correctness / data-confusion | `providers/outlook.py:get_message_details lines 494-500; _init_folder_cache 254-272; _fetch_child_folders 264-272` | Folder-name attribution is ambiguous: reverse lookup of parentFolderId returns the first cache entry, mis-naming same-named child folders |
| U860 | low | R2 | error-handling | `recount.py:recount 19-28` | Gmail batch label-get with no error surfacing and no batch-size chunking — silently drops failed/over-limit entries |
| U861 | low | R2 | config/dependency | `render.yaml:lines 1-15 (whole blueprint; envVars only sets PYTHONUNBUFFERED)` | render.yaml declares no Python/runtime version and no dependency install step, fully delegating reproducibility to the unpinned Dockerfile base `python:3.11-slim` |
| U862 | low | R2 | config/dependency | `requirements-api.txt:lines 8-13 (stripe>=15.2,<16) vs acp/payment.py:30 STRIPE_SPT_API_VERSION "2026-04-22.preview"` | ACP charge path depends on a Stripe PREVIEW API surface (Shared Payment Tokens) only loosely tied to the `stripe>=15.2,<16` SDK pin |
| U863 | low | R3 | dependency | `requirements-api.txt:line 13 (stripe>=15.2,<16)` | stripe major pinned <16 — billing code uses StripeClient/v1 namespace; verify floor matches the API surface used |
| U864 | low | R1 | secrets | `run_automation.sh:lines 47-50` | iCloud credentials passed as inline env assignments to python (visible in process list and unquoted expansion) |
| U865 | low | R1 | test-quality | `tests/test_acp.py:test_create_invalid_item_not_ready (65-71)` | Invalid-item test relies on Pydantic default quantity but does not assert charge is blocked |
| U866 | low | R1 | test-quality | `tests/test_audit.py:test_append_failure_degrades_to_memory_and_still_checks_invariant (448-457) and test_apply_with_unwritable_audit_does_not_raise_or_breach (459-473)` | Unwritable-audit tests rely on directory-as-path raising, an OS/behavior-specific trigger |
| U867 | low | R1 | test-quality | `tests/test_billing.py:test_webhook_subscription_event_grants_and_dedups (52-85)` | current_period_end set in the test event is never asserted on the resulting account |
| U868 | low | R1 | test-quality | `tests/test_config.py:test_invalid_yaml_returns_empty (78-82)` | Invalid-YAML test asserts silent {} fallback as correct, masking a swallow-all error path |
| U869 | low | R1 | test-quality | `tests/test_mailapp.py:test_mailapp_star_accepts_due_date_from_base_apply_actions (9-26)` | Mail.app star test mocks _run_applescript and so never exercises AppleScript message_id interpolation/injection surface |
| U870 | low | R1 | test-quality | `tests/test_models.py:test_immutability (57-62) and tests/test_rules.py test_priority_tier_frozen (77-83)` | Frozen-dataclass tests use try/except + assert False idiom that misclassifies non-AttributeError outcomes |
| U871 | low | R1 | test-quality | `tests/test_rules.py:TestEscalation (262-304)` | Escalation boundary values (exactly 24h and exactly 72h) are untested |
| U872 | low | R2 | correctness | `web/index.html:lines 906, 936 (Number(p.monthly_run_cap).toLocaleString())` | Plan run-cap renders 'NaN' if the API returns a non-numeric monthly_run_cap |


## ⚪ Info (78)

| ID | Conf | Rounds | Category | Location | Title |
|---|---|---|---|---|---|
| U873 | high | R1 | test-quality | `.github/workflows/ci.yml:lines 33-47, 49-63` | Lint and type-check steps are advisory-only and can never fail the build (assertion-that-cannot-fail smell) |
| U874 | high | R3 | consistency | `.well-known/agent.json:.well-known/agent.json / llms.txt / acp/product_feed.json vs api/well_known.py + acp/feed.py` | Committed discovery artifacts are byte-in-sync with their generators (verified, no drift) |
| U875 | high | R1 | error-handling | `analyze_strategic_value.py:extract_domain lines 24-33 (and duplicate in auto_drain.py)` | Bare `except:` in extract_domain swallows all exceptions including KeyboardInterrupt |
| U876 | high | R3 | privacy | `config/protected_senders.local.txt:config/protected_senders.local.txt (whole file) + .gitignore:8` | Local protected-senders file with real PII exists on disk and is correctly gitignored / never committed (verified clean) |
| U877 | high | R3 | coverage | `create_smart_mailboxes.scpt:whole file` | Scope assumption wrong: create_smart_mailboxes.scpt is plain UTF-8 AppleScript source, NOT a compiled binary — it IS reviewable (and unreviewed) |
| U878 | high | R1 | style | `imap_rules.py:imports line 23 (re) and line 22 (email) unused; stats dict not defaultdict` | Minor: unused imports and re-decode of UID per fetch |
| U879 | high | R2 | documentation / import-time | `mcp_server/__init__.py:lines 6-7 (docstring: 'The heavy mcp SDK is imported lazily by mcp_server.server')` | mcp_server package docstring misstates lazy-import behavior — server.py imports the mcp SDK eagerly at module top level |
| U880 | high | R1 | dead-code | `providers/outlook.py:DEFAULT_CLIENT_ID 63 + __init__ 120` | Dead/confusing config: module-level DEFAULT_CLIENT_ID reads env but __init__ re-reads the same env, so DEFAULT_CLIENT_ID is never used |
| U881 | high | R1 | dead-code | `providers/outlook.py:GRAPH_API_MESSAGES constant, 25` | Unused module constant GRAPH_API_MESSAGES (inbox-only) — never referenced; list_messages builds its own URL |
| U882 | high | R3 | dependency | `requirements-api.txt:lines 3-13` | fastapi/uvicorn/pydantic/stripe ARE properly declared (false-positive killer) |
| U883 | high | R3 | dependency | `requirements-mcp.txt:line 6` | mcp SDK IS properly declared (false-positive killer) |
| U884 | high | R3 | dependency | `requirements.txt:lines 2-11` | Core deps (google-api-python-client, msal, requests, pyyaml) ARE declared |
| U885 | high | R2 | dead code | `web/index.html:lines 52-53 (a { color: var(--green); } a { color: var(--accent); })` | Duplicate conflicting anchor color rule (dead CSS) |
| U886 | medium | R3 | ci/test-coverage | `.github/workflows/ci.yml:112-113` | Smoke test asserts '"status":"ok"' as an exact substring, which is brittle against worker JSON.stringify spacing |
| U887 | medium | R2 | import-time side effect | `api/store.py:line 39 (DEFAULT_DB_PATH = os.environ.get('MAIL_DB_PATH', 'data/app.db'))` | DB path default read from environment at module import time |
| U888 | medium | R1 | style | `auto_drain.py:drain_loop line 180 print(...end='\r') interleaved with logging` | print with carriage-return progress interleaves badly with logging to stdout/file |
| U889 | medium | R3 | data-consistency | `cloudflare/worker.mjs:246-248 (/health) vs api/app.py:70-76` | Worker /health version is hardcoded '0.1.0' and can drift from the API's __version__ |
| U890 | medium | R1 | style | `core/rules.py:calculate_email_age_hours line 1163 signature `Optional["datetime"]`; import inside body line 1176` | datetime type annotation is an unresolved forward-ref string and import is function-local |
| U891 | medium | R4 | silent-failure | `create_smart_mailboxes.scpt:lines 3-5` | Group-creation failure silently swallowed by bare try |
| U892 | medium | R1 | dependency | `deploy.sh:line 32` | Redundant unpinned pip install of msal/requests duplicates pinned requirements.txt entries |
| U893 | medium | R1 | dead-code | `gmail_labeler_legacy.py:lines 19-26 packages_distributions shim; line 12 unused 'import re' is used; line 14 socket` | Dead/likely-unnecessary importlib_metadata shim with bare-except swallow |
| U894 | medium | R1 | api-misuse | `inspect_remaining.py:line 18` | resultSizeEstimate used as a 'Total' count is unreliable/approximate |
| U895 | medium | R1 | none-handling | `inspect_remaining.py:inspect() lines 7-12, 26-29` | Direct subscripting of results['labels'] and response['payload']['headers'] / h['name'] with no guards (read-only, low impact) |
| U896 | medium | R2 | re-export drift / public API | `providers/__init__.py:lines 16-19 (__all__) vs providers/base.py:39 (class ListMessagesResult)` | providers package __all__ omits the public DTO ListMessagesResult |
| U897 | medium | R2 | import-time / optional dependency | `providers/gmail.py:line 12 (from googleapiclient.errors import HttpError, module top level)` | providers.gmail imports googleapiclient at module top level, so direct import crashes without the optional Google dependency |
| U898 | medium | R2 | correctness | `providers/gmail.py:apply_actions, lines 419-421 and audit pending build 434-439` | Audit labels_added omits the STARRED label even though apply_actions adds it to addLabelIds |
| U899 | medium | R1 | silent-failure | `recount.py:cb line 21-23 + line 30` | Batch callback silently drops failed label fetches; report omits them with no warning |
| U900 | medium | R3 | deployment | `render.yaml:lines 3-14` | render.yaml relies entirely on the Dockerfile CMD; no PORT export and starter plan caveats are implicit |
| U901 | low | R1 | security | `Dockerfile:line 19` | uvicorn started via shell-form CMD as root with no worker/uvicorn pinning |
| U902 | low | R3 | documentation/unverified-claim | `README.md:489` | Provider capability matrix claims Gmail batch 'Yes (1000/batch)' but text elsewhere references batchModify 1000 — verify against gmail.py batch size |
| U903 | low | R1 | resource-leak | `acp/router.py:create_session lines 168-170, all POST handlers` | Idempotency-Key claimed (begin) before request body validation cost is bounded; large body is read via await request.body() with no explicit size limit at this layer |
| U904 | low | R1 | secrets | `api/billing.py:create_checkout exception handler line 140-142; create_portal line 164-166` | Stripe error logged with exc_info=True may capture sensitive request internals server-side (low risk, log-only) |
| U905 | low | R2 | money/consistency | `api/plans.py:METERED_ADDON lines 130-139 (unit_amount_cents: 1 => $0.01/run) vs CREDIT_PACKS lines 143-148 (pack_100: 100 runs/100c = $0.01/run; pack_1000: 1000 runs/900c = $0.009/run)` | Per-run pricing is internally inconsistent across the three agent pay paths (metered $0.01, pack_100 $0.01, pack_1000 $0.009) |
| U906 | low | R2 | error-handling | `api/receipts.py:verify 71-74` | verify() returns True for an empty body+empty signature edge and accepts None signature as empty string |
| U907 | low | R1 | none-handling | `archive_sorted.py:senders_for callback lines 61-68` | Header name match for 'From' is case-insensitive but value extraction takes first match only; OK, but fail-closed empty-string relies on is_protected_sender semantics |
| U908 | low | R1 | dead-code | `auth/onepassword.py:store_json_secret() lines 256-272 vs gmail_auth store_token_info` | store_json_secret ignores account override and is dead/divergent relative to gmail_auth |
| U909 | low | R1 | none-handling | `check_health.py:lines 13, 22` | Direct dict indexing on profile fields can KeyError; assumes keys always present |
| U910 | low | R1 | silent-failure | `check_health.py:cb lines 32-34` | Health-check batch callback uses parameter name 'id' shadowing builtin and drops errors silently |
| U911 | low | R1 | logic | `cli.py:_make_audit line 374-375` | in_audit_dir check uses normpath string-prefix and misses './audit' equivalence edge but flags absolute audit/ paths as outside |
| U912 | low | R1 | style | `cli.py:cmd_summary line 596/611 and cmd_pending — percentage/division and bar math` | Summary table bar uses int(pct/5) which can exceed the 20-cell width only if pct>100, but '░'*(20-int(pct/5)) goes negative-safe; verify pct cap |
| U913 | low | R1 | observability | `cli.py:cmd_label exit code lines 454-457 vs cmd_escalate 945-947` | apply error_count>1 returns generic exit 1 but partial-success runs with some errors are indistinguishable from total failure |
| U914 | low | R1 | style | `cli.py:main() line 1004 subparsers without required=True` | subparsers not marked required; no-command path returns 1 but args.func may be missing for unknown handling |
| U915 | low | R1 | security | `cloudflare/worker.mjs:lines 61-66, 240-242` | CORS allow-origin is wildcard `*` on all API responses |
| U916 | low | R1 | api-misuse | `core/config.py:GmailConfig/IMAPConfig/etc. dataclass inheritance, lines 34-72` | Subclass dataclasses redeclare 'name' with a default while base has it without — fragile field ordering |
| U917 | low | R1 | config | `core/config.py:_apply_env_config() lines 266-271` | DRY_RUN env var only togglable to True, never explicit False over a config-file True |
| U918 | low | R1 | style | `core/models.py:ProcessingResult.label_counts type annotation line 121` | label_counts annotated as bare 'dict' not Dict[str,int] |
| U919 | low | R1 | concurrency | `core/models.py:ProcessingResult.add_label_stat lines 124-126` | add_label_stat is not thread-safe (read-modify-write on shared dict) — lost counts if apply_actions is ever parallelized |
| U920 | low | R1 | dead-code | `core/rules.py:_find_best_label lines 1031-1036 (the `break`)` | Inner `break` after first matching pattern is correct but masks intent; combined with strict < it cannot pick the highest-priority within scanning |
| U921 | low | R1 | logic | `core/rules.py:_best_relay_domain line 703` | TLD heuristic for relay domain recovery uses 2<=len<=18 all-alpha terminal label, can pick a wrong real domain for categorization |
| U922 | low | R1 | regex | `core/rules.py:_load_local_protected() lines 583-613; LABEL_RULES Misc/Other pattern line 502` | Catch-all pattern r".*" combined with re.search makes the LABEL_RULES priority scan order-fragile; only priority 999 saves it |
| U923 | low | R1 | security | `core/rules.py:_relay_domain_candidates() lines 676-695; _best_relay_domain lines 698-704` | Relay local-part decoding can fabricate non-protected real domains for categorization, but never lowers protection — verify over-recovery cannot mis-skip |
| U924 | low | R1 | config | `deploy.sh:lines 50-60 (launchctl bootstrap)` | deploy.sh writes a LaunchAgent plist and bootstraps it (matches the user's hard-blocked plist/LaunchAgent rule) |
| U925 | low | R3 | security-hardening | `docs/pitch/index.html:lines 9-128 (no CSP) and overall` | No Content-Security-Policy meta tag; inline script/style only (defense-in-depth gap, currently low risk) |
| U926 | low | R3 | accessibility | `docs/pitch/index.html:lines 261-264 (a.textContent = s.id; CSS text-indent:-9999px line 45)` | Nav-dot links get their accessible name from section id, then are visually hidden via text-indent:-9999px |
| U927 | low | R1 | config | `ecosystem.yaml:lines 1-10` | ecosystem.yaml delivery/revenue status disagrees with seed.yaml metadata |
| U928 | low | R1 | style | `gmail_auth.py:store_token_info() line 151-152` | Token re-serialized via creds.to_json then re-dumped — redundant parse/dump, and full token (incl refresh_token) persisted |
| U929 | low | R1 | perf | `gmail_labeler.py:process_batch lines 149-154 callback closure over failed_ids per-chunk` | Batch callback appends to a per-chunk failed_ids but batch_results is shared across chunks (correct) — note time.sleep(2.0) fixed delay regardless of size |
| U930 | low | R1 | error-handling | `icloud_triage.py:main finally, lines 167-171` | Broad `except Exception` swallows logout errors (acceptable) but no close of select state / no NOOP error surfacing |
| U931 | low | R1 | silent-failure | `providers/base.py:248-270 (apply_category default)` | apply_category default returns False even when CATEGORIES capability is set, with comment 'Subclasses override' — silent no-op if a subclass forgets |
| U932 | low | R1 | api-misuse | `providers/base.py:151-172 (batch_get_details default) vs gmail override` | Base batch_get_details default has no throttling and could hammer the API; not an abstractmethod so a provider can silently inherit a slow/unsafe sequential path |
| U933 | low | R1 | api-misuse | `providers/gmail.py:336-338 (star signature)` | star() silently ignores due_date and does not check STAR capability before applying |
| U934 | low | R1 | api-misuse | `providers/gmail.py:129-135 (_init_label_cache pagination)` | _init_label_cache does not paginate labels().list (assumes all labels fit in one response) |
| U935 | low | R1 | dead-code | `providers/gmail.py:417, 441 (archive via INBOX in remove_ids + batch key grouping)` | Star id resolution uses cache 'STARRED' but ensure_label_exists never adds STARRED to cache, so star always appends literal 'STARRED' (benign) while add label dedup may be defeated |
| U936 | low | R1 | api-misuse | `providers/gmail.py:248 (batch.execute not wrapped to reset between backoff retries)` | On batch.execute rate-limit retry, results dict may receive duplicate parses but request_id keys dedupe — no corruption, but failed_ids not cleared |
| U937 | low | R1 | logic | `providers/gmail.py:_execute_with_backoff lines 97-127 (lambda closure over loop var in apply_actions line 460)` | Late-binding closure: batch-modify lambda captures loop variable `body` by reference |
| U938 | low | R2 | correctness | `providers/gmail.py:apply_actions 441 (batch grouping key) + 477-495 (audit)` | Star-only actions with no add/remove labels still create an empty batchModify body, and protected senders retaining star can be grouped with non-protected stars |
| U939 | low | R1 | api-misuse | `providers/imap.py:star 328 / base.star override` | IMAP star() ignores capability gating and always attempts \\Flagged even when STAR capability absent (non-gmail mode) |
| U940 | low | R1 | none-handling | `providers/imap.py:_load_password lines 100-126` | IMAP password resolved from env returns os.getenv twice (TOCTOU/None edge) — minor |
| U941 | low | R2 | correctness | `providers/imap.py:_load_password 105-106` | os.getenv('IMAP_PASS') checked then re-read, and an empty-string IMAP_PASS bypasses the 1Password fallback returning '' |
| U942 | low | R1 | concurrency | `providers/mailapp.py:connect lines 92-102` | Mail.app auto-launch + fixed 2s delay race |
| U943 | low | R1 | logic | `providers/outlook.py:remove_label, 539-542` | remove_label always returns False, so base.apply_actions never registers INBOX-removal as leaving the inbox for Outlook |
| U944 | low | R1 | dependency | `requirements.txt:lines 5-11` | Optional deps (msal/requests/pyyaml) listed as hard requirements despite being documented optional |
| U945 | low | R1 | secrets | `run_automation.sh:lines 47-50` | iCloud IMAP password passed via inline env assignment on the command (process-listing exposure) |
| U946 | low | R1 | resource-leak | `scripts/gen_commerce_artifacts.py:main lines 97-108` | Generated files written non-atomically; a crash mid-write leaves committed artifacts truncated |
| U947 | low | R1 | money-path | `scripts/gen_commerce_artifacts.py:gen_pricing_md line 62-63` | Money formatting uses float division for cents -> dollars (rounding risk) |
| U948 | low | R1 | test-quality | `tests/test_api.py:test_triage_clean_run_summary (107-134) and test_triage_fail_closed_on_violation (84-105)` | Triage tests stub run_labeler so the real audit chokepoint wiring inside run_labeler is bypassed |
| U949 | low | R1 | test-quality | `tests/test_web.py:test_root_redirects_to_dashboard (17-20)` | Redirect test accepts any 3xx and only checks Location header, not that the dashboard is actually reachable via the redirect |
| U950 | low | R2 | correctness | `web/index.html:line 807 ($("subject").value sent unbounded; line 804 sender)` | Sender/subject sent to API with no client-side length bound |


> Full descriptions for Medium/Low/Info are in [`findings.json`](./findings.json).