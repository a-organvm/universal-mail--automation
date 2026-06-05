# Ranked Verification Report — universal-mail--automation

**Generated:** 2026-06-04T12:03:10+00:00 · **Stage:** verified + ranked (deterministic merge)

Adversarial verification of all **950 coverage findings + 22 structural gaps** from `findings.json` against the real codebase, then uniform scoring and duplicate_of + file/line clustering. Verdicts come from two workflows (`wxr6hkjeo` primary 930/950, `whqkom9zr` recovery 20 slices + 22 gaps); ranking is pure arithmetic (reproducible via `/tmp/verify/finalize.py`).

## How to read this

- **Score** = `severityWeight × verdictFactor × corroborationBoost`. `verdictFactor` zeroes out false-positives & pure duplicates, so only *live* (confirmed / partial / needs-runtime) findings carry weight. Corroboration boost (×1.3) rewards findings independently re-discovered across rounds.
- **Clusters** collapse the same defect reported many times (the money-path bug was surfaced ~15×). Cluster score = best member + a small bonus per corroborating member.
- **Structural gaps** are whole-subsystem logic holes — per the coverage guidance these are the *highest-leverage* entries, ranked separately below.

## Verdict ledger

| | confirmed | partial | needs-runtime | false-positive | duplicate | refuted |
|---|---|---|---|---|---|---|
| **Findings (950)** | 561 | 178 | 20 | 22 | 169 | — |
| **Gaps (22)** | 10 | 11 | — | — | — | 1 |

**Live finding clusters:** 303 (deduped from 759 live findings). Severity of live findings — 🔴 4 critical, 🟠 37 high, 🟡 139 medium, 🔵 460 low, ⚪ 119 info

## ⓘ Structural gaps — ranked (highest leverage)

### G01 · 🟠 high · ✓ confirmed · score 40.0
**Entitlement / credit / plan-cap enforcement is dead code — /v1/triage and MCP triage have NO auth and NO metering**

- **Evidence:** Repo-wide grep confirms the metering primitives are dead code on every request path. `consume_credit` (api/store.py:235, the only debit: `UPDATE accounts SET run_credits = run_credits - ? WHERE id = ? AND run_credits >= ?` at 241-242) is called ONLY by tests/test_store.py:39,42 — never by api/app.py, api/service.py, mcp_server/server.py, or acp/router.py. `entitlements_for` (api/plans.py:175) has zero callers outside plans.py itself. `monthly_run_cap` appears only in api/plans.py (the dataclass/plan defs) and scripts/gen_commerce_artifacts.py:46 (marketing-copy generation). The actual triage path takes no account/credit input: api/app.py:_run (97-130) calls service.run_triage with only prov…
- **Impact:** The entire paid-tier commercial model (Free ~50 runs/mo cap, metered add-on, ACP credit packs) is structurally unenforced. No request path checks monthly_run_cap or debits run_credits, so plan caps and purchased credits are marketing-only. Blast radius is the revenue/billing integrity of the hosted service, not memory safety or mailbox safety: the triage runtime is still gated by real server-side…
- **Adjudication:** Grep proves both entitlements_for and consume_credit are uncalled by any request path (only tests/marketing reference them), and run_triage takes no account/credit argument — the dead-code claim holds exactly; severity is high (revenue integrity) rather than critical because runtime is still provider-credential-gated.
- **Fix target:** `api/app.py:_run (97-130), mcp_server/server.py:_triage (129-146), api/plans.py:entitlements_for (175-193), api/store.py:consume_credit (235-246), api/service.p…`

### G02 · 🟠 high · ✓ confirmed · score 40.0
**ACP bearer token is never validated against the store; arbitrary bearer auto-provisions an account**

- **Evidence:** acp/router.py `_gate` (72-93): only validates Authorization header `startswith("Bearer ")` and non-empty (line 80-82); the parsed string is taken verbatim as api_key (line 83) and returned in GateContext — no store lookup, no format/membership check. `complete_session` (286-289): `account = store.get_account_by_api_key(ctx.api_key)` then `if account is None: account = store.create_account(api_key=ctx.api_key, plan="free")` — mints an account from the attacker-chosen bearer. api/store.py get_account_by_api_key (170-175) is a plain SELECT; create_account (145-165) inserts with the supplied api_key. Legit keys carry the `uma_` prefix (store.py:110-112 new_api_key) but _gate enforces no such co… <!-- allow-secret false-positive: quoted source-code example -->
- **Impact:** The agent-commerce surface has no real authentication: any non-empty bearer string is accepted and, on /complete, auto-provisions a `free` account keyed to that invented token. There is no check that the bearer is a pre-issued `uma_` key. This breaks the auth model and identity boundary for ACP. Blast radius is bounded by the fact that run credits are only fulfilled after a successful SPT charge …
- **Adjudication:** Code at the cited lines exhibits exactly the defect: _gate never validates the bearer against the store, and complete_session auto-provisions an account for any unknown token.
- **Fix target:** `acp/router.py:_gate (72-93), complete_session (286-290); api/store.py:get_account_by_api_key (170-175), create_account (145-165) — assess whether unknown beare…`

### G15 · 🟠 high · ✓ confirmed · score 40.0
**cloudflare/worker.mjs (entire 322-line file) — the LIVE production demo deployed by CI to uma.4444j99.dev; never reviewed in round 1 or 2**

- **Evidence:** cloudflare/worker.mjs verified line-by-line. (1) Line 1: `const PROTECTED = new Set(["courts.ca.gov","chase.com","1password.com"])` — 3 elements only; the Python EXAMPLE_PROTECTED_SENDERS (core/rules.py:559-575) protects docusign.net/irs.gov/ssa.gov/apple.com/google.com/anthropic.com/meta.com + boundary-matched entries, none of which the worker covers. (2) Line 82-83 `senderCheck` lowercases the ENTIRE raw sender string with no address parsing; line 106 `value.includes("courts.ca.gov") || value.endsWith(".gov")` — so `x@courts.ca.gov.evil.com` includes "courts.ca.gov" => TRUE (false-positive spoof), and a display name containing ".gov" matches. Contrast core/rules.py:653-657 `_gov_protected…
- **Impact:** The live demo at uma.4444j99.dev (deployed by CI) presents a protected-sender guarantee and a "Signed receipt" that do not match the product's marketing/trust claims: most marketed protected domains are unprotected, the .gov gate is spoofable via substring/display-name and trivially false-protects attacker-controlled domains containing "courts.ca.gov", and the audit endpoint emits an unsigned, ha…
- **Adjudication:** Every concrete sub-claim (lines 1, 106, 153, 281-305, 172-198, 63, ci.yml 108-119) reproduces verbatim in current code; "third reimplementation of the safety core" slightly overstates since this is an explicit share-demo, but the divergences and fabricated signed receipt are real, so confirmed at high (not critical) because it is a demo, not the production self-hosted path.
- **Fix target:** `cloudflare/worker.mjs (lines 1, 82-170 senderCheck, 172-198 triagePreview, 281-305 audit, 61-66 CORS); cross-ref core/rules.py is_protected_sender + api/receip…`

### G16 · 🟠 high · ✓ confirmed · score 40.0
**AppleScript mail movers bypass the protected-sender gate entirely — archive_old_inbox.applescript and route_bulk_senders.applescript**

- **Evidence:** archive_old_inbox.applescript:15-21 moves EVERY inbox message older than cutoff: `repeat with msg in inboxMessages / if date received of msg < cutoffDate then / move msg to targetMailbox` — no sender check at all, so a 91-day-old lawyer/bank/government email is silently moved out of inbox. The headline guarantee lives only in Python: core/audit.py:3-5 ("a protected sender ... is NEVER archived or moved out of the inbox") enforced via core/rules.py:787 is_protected_sender. `grep -rni 'protected|audit|is_protected|gate|rules' *.applescript` returns nothing (exit 1) — the AppleScripts share NONE of the gate/audit logic. route_bulk_senders.applescript:9 `if theSender contains ("@" & dom) or the…
- **Impact:** archive_old_inbox.applescript can destructively move a protected sender's mail (legal/bank/government) out of the inbox — the exact regression the protected-sender gate + audit invariant exist to make impossible — because it runs entirely outside the Python engine. route_bulk_senders unanchored `ends with` can mis-route lookalike/subdomain senders; flag_important_senders substring match can over-…
- **Adjudication:** Cross-file claim verified verbatim: the AppleScript movers bypass the protected-sender gate and audit entirely, and the destructive archive_old_inbox path can move protected mail out of the inbox with zero sender check.
- **Fix target:** `archive_old_inbox.applescript (lines 1-22, no gate); route_bulk_senders.applescript (line 9 unanchored 'ends with'); flag_important_senders.applescript (line 5…`

### G17 · 🟠 high · ✓ confirmed · score 40.0
**ACP/billing identity model: any bearer string becomes a funded account with no API-key issuance or verification — acp/router.py complete_session lines 286-290 + tests/test_acp.py line 132**

- **Evidence:** acp/router.py:79-83 _gate only parses the bearer: `api_key = auth[len("Bearer "):].strip()` after checking it is non-empty — no lookup against the accounts table. complete_session router.py:287-289: `account = store.get_account_by_api_key(ctx.api_key); if account is None: account = store.create_account(api_key=ctx.api_key, plan="free")` — credits the runs (fulfill_once line 290, save_receipt line 313-317) to whatever raw bearer string accompanied the request. api/store.py:110-112 new_api_key() mints `uma_`-prefixed keys; grep across *.py in acp/api/tests shows its ONLY callers are store.py:110 (def) and store.py:156 (fallback default inside create_account) — nothing in the request path ever… <!-- allow-secret false-positive: quoted source-code example -->
- **Impact:** Any caller can mint/select a funded account by choosing any non-empty bearer string; two callers presenting the same bearer share one credit balance (cross-tenant collision / mutual drain), and the Stripe charge payer (delegated token) is never bound to the credited account. Billing-integrity and identity defect across the ACP completion path. Mitigant capping it below critical: credits only land…
- **Adjudication:** Current code exhibits exactly the cross-file defect claimed: a fail-open identity model where the unverified bearer becomes the credited account, with new_api_key() minted but never wired into the request path.
- **Fix target:** `acp/router.py lines 72-93 (_gate) and 286-290 (account bootstrap from raw bearer); api/store.py new_api_key line 110 (issued but never wired in); tests/test_ac…`

### G18 · 🟠 high · ✓ confirmed · score 40.0
**Paid metering / plan caps are never enforced — entitlements_for and consume_credit are dead code on every triage path**

- **Evidence:** Grep across all .py: `entitlements_for` has exactly one match — its own def at api/plans.py:175 (zero callers). `consume_credit` appears only at its def (api/store.py:235) and in tests/test_store.py:39,42 — never in api/app.py, api/service.py, acp/router.py, or mcp_server/server.py. `triage_run` meter event name appears only at its def (api/plans.py:136), never emitted. `monthly_run_cap` is referenced only in plans.py definitions/to_dict and in scripts/gen_commerce_artifacts.py:46 (doc generator) — never checked at any runtime triage path. Reading the actual triage paths confirms no gate: api/app.py:97-130 `_run` calls `service.run_triage(...)` then mints a run_id and persists a receipt wit…
- **Impact:** Paid metering and plan caps are entirely unenforced. Every /v1/triage, /v1/triage/preview, and MCP triage runs with no credit debit and no monthly_run_cap check, so the Free ~50-runs/month cap and tier gating are marketing-only — a free user can run unlimited live triage. ACP-purchased run_credits are credited but never consumed, so buyers pay for credits that are never spent. The metered Stripe …
- **Adjudication:** Cross-file claim verified verbatim: entitlements_for/consume_credit/triage-meter are dead on every triage path; the entire commercial model is structurally disconnected from the engine.
- **Fix target:** `api/plans.py entitlements_for lines 175-193 (uncalled); api/store.py consume_credit lines 235-246 (uncalled); the missing enforcement hook in api/app.py _run l…`

### G20 · 🟠 high · ✓ confirmed · score 40.0
**MCP triage tools enforce no entitlement and have a destructive default-override footgun; server.py only clamps the limit**

- **Evidence:** mcp_server/server.py verified verbatim: triage exposed with annotations={"destructiveHint": True, "idempotentHint": False} (line 109) and dry_run: bool = True default (line 117) passed straight through to _triage (line 125); triage_preview at lines 97-106. _clamp_limit (lines 83-84) clamps ONLY limit to [1, MAX_TRIAGE_LIMIT]; provider/query/remove_label/tier_routing/vip_only flow untouched into service.run_triage (_triage body lines 129-146). No api_key/account/Header/Depends/consume_credit/entitlements_for anywhere in server.py (grep). check_protected_sender truncates sender[:4096], subject[:4096] (line 94), but neither triage nor triage_preview bounds query length. Cross-file: metering ma…
- **Impact:** Any agent that can reach the hosted MCP endpoint (DNS-rebind protection is the only network guard) can drive destructive mailbox mutation with no account binding, no credit debit, and no rate limit beyond a per-call limit clamp. A prompt-injected agent flips one boolean (dry_run=False) — no confirmation step or capability gate — to mutate the mailbox, and can pass an arbitrarily long query into t…
- **Adjudication:** Every claim checks out against current code: destructive default-override is a single-boolean flip, _clamp_limit is the sole input guard, no entitlement/credit/rate-limit on the MCP surface (metering exists but is unwired across both MCP and HTTP), and query length is unbounded vs the 4096 sender/subject cap — but adjusted to high (not critical) because the protected-sender fail-closed gate still…
- **Fix target:** `mcp_server/server.py: triage dry_run default-override lines 109-126 (single-arg flip), _clamp_limit as sole guard line 83-84, no credit/entitlement check in _t…`

### G03 · 🟡 medium · ✓ confirmed · score 10.0
**Provider date field unset → escalate command silently no-ops for Gmail/IMAP/Mail.app**

- **Evidence:** core/rules.py:1173-1174 `calculate_email_age_hours` returns 0 when email_date is None. core/models.py:48 `date: Optional[datetime] = None` (default None). grep of `date=` across all four providers shows ONLY providers/outlook.py:464,515 sets it; providers/gmail.py EmailMessage at 157/204/286, providers/imap.py at 198/261, providers/mailapp.py at 191/240 all omit date= → defaults to None. cli.py:883 `age_hours = calculate_email_age_hours(msg.date)` feeds escalate_by_age (cli.py:886). core/rules.py escalate_by_age (def at 1091) returns should_escalate=False whenever email_age_hours < 24 ("Email is less than 24 hours old"). With age_hours=0 for non-Outlook messages, the >=24h and >=72h branche…
- **Impact:** `python3 cli.py escalate` is a documented feature (CLAUDE.md, escalate_parser at cli.py:1120) that silently does nothing for Gmail, IMAP, and Mail.app providers — 3 of the 4 supported backends. Users running escalate against those providers see "0 escalated" with no error, while the time-based re-triage they expect never happens. Outlook is the only provider where escalation actually fires. No cr…
- **Adjudication:** Every assertion in the gap (None-default, 0-age, single-provider date assignment, dead escalation branch) is verified verbatim against current code; it is a real provider-layer root cause the CLI-side finder missed.
- **Fix target:** `providers/gmail.py EmailMessage construction (157,204,286), providers/imap.py (198,261), providers/mailapp.py (191,240); cross-check cli.py cmd_escalate use of…`

### G14 · 🟡 medium · ✓ confirmed · score 10.0
**Tests: no dedicated coverage for cli.py, the four providers, auth/onepassword, well_known, acp/feed, or any legacy script; coverage-driven false confidence**

- **Evidence:** `ls tests/` (14 test files): test_acp, test_api, test_audit, test_billing, test_config, test_mailapp, test_mcp, test_models, test_protected_enforcement, test_receipts, test_rules, test_state, test_store, test_web. NONE of test_cli.py / test_gmail.py / test_outlook.py / test_imap.py / test_provider_base.py / test_onepassword.py / test_well_known.py / test_feed.py exist. cli.py (1205 lines) is touched only transitively: test_api.py:138 `import cli` + monkeypatch cli.time.sleep, and test_audit.py:375 `from cli import run_labeler` — no dedicated suite for its 30+ subcommands. Providers: gmail referenced only via `import providers.gmail as gmod` inside test_audit.py:273/317 and test_protected_en…
- **Impact:** The highest-risk mutation surfaces (cli.py dry-run/--limit/audit paths and the three API-backed providers performing labelModify/folder moves) ship without a unit-test backstop, so any reported CI coverage % is inflated by the well-tested api/core/rules surfaces while regressions in cli/providers/auth/well_known/feed/legacy go undetected. This is a test-coverage gap (false confidence), not itself…
- **Adjudication:** Disk enumeration confirms every named test file is absent and every named source surface (cli, gmail/outlook/imap, onepassword, well_known, feed, 5 legacy scripts) has no dedicated tests and no coverage floor; slightly overstated only in that gmail gets partial transitive exercise and mailapp has its own test, hence medium not high.
- **Fix target:** `tests/ directory (enumerate missing test_cli.py / test_gmail.py / test_outlook.py / test_imap.py / test_onepassword.py); pyproject.toml/.coveragerc for any per…`

### G07 · 🟡 medium · ◐ partial · score 5.5
**core/config.py: unguarded int() casts, no validation of provider/log_level, custom_rules/vip_senders applied verbatim, env precedence bug**

- **Evidence:** core/config.py:272-273 confirmed verbatim: `if os.getenv(f"{prefix}BATCH_SIZE"): config.batch_size = int(os.getenv(f"{prefix}BATCH_SIZE"))` — no try/except, so a non-numeric MAIL_AUTO_BATCH_SIZE raises ValueError inside load_config(), which is called unconditionally at every CLI entry (cli.py:422,523,718,828 each call load_config() then apply_vip_senders_from_config()), crashing the command. Lines 266-269 confirmed: default_provider/log_level assigned verbatim from env with zero validation against any known set (grep found no enum/allowed-set check). Lines 249-250 (custom_rules) and 259-260 (vip_senders) confirmed assigned straight from YAML with no schema check. OVERSTATEMENTS: (1) The doc…
- **Impact:** A malformed operator-supplied MAIL_AUTO_BATCH_SIZE (or bad config file value not even guarded by the int cast) crashes every CLI subcommand at startup with an unhandled ValueError. A typo'd default_provider/log_level silently mis-selects or sets an invalid logging level. Untrusted-but-operator-controlled YAML rules/VIP entries enter the engine without schema validation. Blast radius is real but l…
- **Adjudication:** Core defects (unguarded int() startup crash, no provider/log_level validation, verbatim untrusted rule ingestion) are confirmed in current code, but two supporting claims (the docstring's stated precedence and the VIP-regex crash cross-link) misread the code, so the finding is real yet overstated.
- **Fix target:** `core/config.py _apply_env_config (263-297, esp. 272-273), _apply_yaml_config custom_rules/vip_senders (248-260), load_config precedence docstring (146-179)`

### G12 · 🟡 medium · ◐ partial · score 5.5
**api/receipts.py & core/audit.py signing: ephemeral key silently rotates per process; receipt body trusts unsigned summary; no signature stored-vs-recomputed check on GET**

- **Evidence:** api/receipts.py `_signing_key` (44-57): when RECEIPT_SIGNING_KEY is unset, `_EPHEMERAL_KEY = secrets.token_bytes(32)` is generated per process with only a one-time `logger.warning`. The module docstring (16-20) itself names horizontally-scaled hosted deploys, so worker-A receipts will not verify against worker-B / post-restart — CONFIRMED, real. `get_receipt` (114-142) returns `rec["signature"]` and a body rebuilt from stored columns verbatim with NO recompute: grep shows `receipts.verify` is called only in tests/test_receipts.py (14,17,52), never on the read path — CONFIRMED, the endpoint never self-verifies stored body-vs-signature. `signed_body` (77-85) signs `triage_result.get('audit')`…
- **Impact:** Sub-claim 1 (ephemeral key): in any multi-worker/multi-restart hosted deploy, persisted receipts silently fail external HMAC verification — the product's headline "tamper-evident, independently re-derivable" trust artifact is broken at production scale, signalled only by a one-time log line. Sub-claim 2 (GET no recompute): a tampered ledger row is returned with its stale signature presented as au…
- **Adjudication:** Two of three sub-claims are genuine (ephemeral-key cross-verification break; GET returns stored signature without server-side recompute); the third (signing the gate summary) is overstated/by-design since the summary is asserted before signing and shares the violations source — hence partial, severity lowered from any safety-critical framing to medium because the real safety gate is independent a…
- **Fix target:** `api/receipts.py _signing_key (44-57), get_receipt (114-142), signed_body (77-85); core/audit.py summary/assert_no_violations interplay (241-259)`

### G21 · 🟡 medium · ◐ partial · score 5.5
**Stripe billing webhook: status from Stripe is written verbatim with no allow-list, and invoice.paid force-activates regardless of plan/period**

- **Evidence:** api/billing.py:248 `status = "canceled" if event_type.endswith("deleted") else obj.get("status")` writes Stripe's raw status verbatim into accounts via store.set_subscription (store.py:191-221, plain UPDATE, no validation). There is NO positive allow-list — only a partial negative guard at billing.py:253-254 mapping canceled/unpaid/incomplete_expired to plan="free" (but the raw status string is still stored). api/plans.py:185 `active = status in ("active", "trialing")` treats every other status (incl. a future Stripe "active-adjacent" status like "paused" or any new vocabulary) as inactive -> downgrades to PLANS[DEFAULT_PLAN_ID] (Free floor) with no log. Second defect confirmed: invoice.pai…
- **Impact:** A paying customer is silently downgraded to the Free entitlement floor if Stripe ever emits a status string outside {active,trialing} that should still grant access (e.g. a future/unknown status), with no log. Separately, invoice.paid force-activates any account by customer_id, so a paid invoice tied to an old/canceled/different subscription can re-activate an account. Both are billing-correctnes…
- **Adjudication:** Both claimed defects exist verbatim in current code, but the gap overstates by omitting the partial cancel-status mitigation (billing.py:253-254) and the intentional partial-write design (store.py:201-203) — real but bounded, hence partial / medium.
- **Fix target:** `api/billing.py _handle_event line 248 (unbounded status write), invoice.paid lines 265-270 (force-active without period/sub validation); cross-ref api/plans.py…`

### G05 · 🔵 low · ✓ confirmed · score 3.0
**core/state.py StateManager: no schema/version validation, naive last_run timestamp, silent save failures, no concurrency guard**

- **Evidence:** core/state.py read in full. All four sub-claims hold against current code: (1) No schema/version validation — _load (46-56) does `return json.load(f)` and uses whatever shape it gets; no key/type checks. (2) Silent save failure — save (91-95): `except Exception as e: logger.error(...)` then returns None normally, so a failed write is indistinguishable from success. (3) Naive timestamp — line 87 `self.state["last_run"] = datetime.now().isoformat()` (no tzinfo), while the rest of the codebase is UTC-aware: grep shows core/audit.py:198 `datetime.now(timezone.utc)` and core/rules.py:1179 `datetime.now(timezone.utc)`. (4) No concurrency guard — no file lock anywhere in the class; two runs on the…
- **Impact:** A corrupt-but-valid-JSON state file is loaded unchecked and a bad next_page_token is replayed to the provider; a failed state write silently looks like success so resume restarts from scratch; last_run is naive-local while comparisons elsewhere are UTC; concurrent runs on one state_file race. Real but bounded — state.py is used only by the single-user legacy gmail_labeler.py and the cli.py `label…
- **Adjudication:** All four defects exist verbatim in current code, but blast radius is a single-user CLI resumption helper (robustness/hygiene), not a critical path — hence low, not the implied medium/high.
- **Fix target:** `core/state.py _load (46-56), save (68-95), _default_state (58-66), last_run (87); cross-check cli.py run_labeler state.save/get_token usage`

### G04 · 🔵 low · ◐ partial · score 1.7
**Legacy/standalone scripts perform archive/move operations with little-to-no review and inconsistent or absent protected-sender gating**

- **Evidence:** Target: auto_drain.py (full), mark_rot_read.py (full), gmail_labeler_legacy.py vs gmail_labeler.py, icloud_triage.py, archive_sorted.py, bulk_sweeper.py. Two specific claims are FALSE: (1) "auto_drain.py has 4 archive-classed ops" — its only mutation (auto_drain.py:171-178) is addLabelIds:[target_id]/removeLabelIds:[source_id] where source_id is the Misc/Other label (line 93), NOT INBOX; it re-routes between category labels and never archives. Its own docstring (lines 11-14): "moves between category labels (out of Misc/Other), NOT out of INBOX... Misroute risk only, not a never-archive breach." (2) "mark_rot_read.py ... gate=1" is wrong — it has zero is_protected_sender calls (grep hit only…
- **Impact:** The destructive paths the gap fears (archive_sorted, icloud_triage — the ones that remove INBOX) DO route through is_protected_sender with fail-closed semantics, so no current never-archive breach exists. The ungated scripts (auto_drain, mark_rot_read) perform only label re-routes / read-state changes, not archives. Real residual risk is limited to: (a) misrouting Misc/Other mail into wrong categ…
- **Adjudication:** Core "whole class of unprotected destructive ops" framing is refuted — the only INBOX-archiving legacy scripts are gated, and the "ungated" ones (auto_drain/mark_rot_read) do not archive; only the no-dedicated-test observation holds, so partial at low severity.
- **Fix target:** `auto_drain.py (full), mark_rot_read.py (full), gmail_labeler_legacy.py vs gmail_labeler.py (drift), icloud_triage.py, archive_sorted.py, bulk_sweeper.py SWEEP_…`

### G06 · 🔵 low · ◐ partial · score 1.7
**core/models.py: frozen EmailMessage with mutable Set defaults; LabelAction.merge set-dedup loses order/duplicates; combined_text used for protect-matching**

- **Evidence:** core/models.py confirms every cited construct: EmailMessage is @dataclass(frozen=True) with mutable `labels: Set[str] = field(default_factory=set)` (49) and `categories` (53); `combined_text` property (55-58) does `f"{self.sender} {self.subject}".lower()`; LabelAction.merge (95-108) merges via `list(set(self.add_labels + other.add_labels))` (100-101) dropping order/dupes with only a docstring "same message_id assumed" (96) — no message_id equality guard. HOWEVER the defects are inert: `grep -rn "\.merge"` shows merge has ZERO production callers — only core/models.py:95 (def) and tests/test_models.py (100,107,113,120,126). Production action-building sites cli.py:243 and cli.py:906 construct …
- **Impact:** No active runtime impact. The merge order/dedup and missing-message_id-guard defects are real but unreachable from any production path (dead code exercised only by unit tests). The frozen-dataclass mutable-Set hazard is theoretical (no caller mutates the sets in place). combined_text on the model is not consumed by the matching logic, so the cross-link to the .gov-anchor protect-matching finding …
- **Adjudication:** All cited code constructs exist verbatim, but every asserted defect is latent (merge has no production caller; sets are never mutated in place; combined_text is unused) — real observations, overstated as defects, hence partial at low severity.
- **Fix target:** `core/models.py EmailMessage (25-58), LabelAction.merge (95-108), ProcessingResult.add_label_stat (124-126) — verify mutability and merge semantics against prov…`

### G08 · 🔵 low · ◐ partial · score 1.7
**auth/onepassword.py: subprocess argument construction and credential-in-logs surface, no test**

- **Evidence:** auth/onepassword.py verified at cited ranges. op_item_edit (94-117): `cmd = ["op","item","edit",item,f"{field}={value}"]` then `_run_op(..., sensitive=True)` — argv with no shell=True, so injection is impossible; only `op` argument-parsing ambiguity if field/value begins with '-' or field contains '='. op_read (60) `["op","read",ref]` and op_item_get (85) `["op","item","get",item,f"--field={field}"]` pass env/ref-derived values straight to argv — confirmed. load_secret logs at 180/191: `logger.warning(f"Failed to read from 1Password ref: {e}")` and `...item: {e}` — interpolates the RuntimeError (carrying the op ref/item.field via _run_op's `description`), NOT the secret value; op_item_edit …
- **Impact:** The credential boundary module has zero unit-test coverage (no test_onepassword.py), so regressions in op CLI argv construction, error handling, and JSON store/parse paths go undetected. The injection/flag-mis-parse and credentials-in-logs angles are theoretical, not exploitable: argv (not shell) bounds risk to op flag-parsing ambiguity on internally-derived strings, and the logged exception carr…
- **Adjudication:** Code-shape claims and the missing-test-file claim are accurate, but framed as a security/credential-leak finding it is overstated — the real defect is a test-coverage gap on a low-blast-radius internal module, so partial / low.
- **Fix target:** `auth/onepassword.py op_item_edit (94-117), _run_op (17-46), load_secret logging (180,191), store_json_secret (233-276); add to xcut-secrets follow-up`

### G09 · 🔵 low · ◐ partial · score 1.7
**CI tests only Python 3.11/3.12 but code claims 3.9 importability; dependency floors are unpinned (>=)**

- **Evidence:** All structural claims confirmed against current code. .github/workflows/ci.yml matrix is python-version: ["3.11","3.12"] only. The 3.9 target is real and architected-around: api/app.py:32-46 wraps `from mcp_server.server import http_app...` in try/except with the comment "the official `mcp` SDK requires Python >=3.10; the core API stays importable on 3.9. So the MCP app is imported lazily"; CLAUDE.md:278 states "Python 3.9+". So the 3.9 path is genuinely never exercised in CI. Dependency floors are lower-bound-only: requirements.txt (google-api-python-client>=2.0.0, msal>=1.25.0, requests>=2.28.0, pyyaml>=6.0), requirements-api.txt (fastapi>=0.110, uvicorn[standard]>=0.29, httpx>=0.27, pyda…
- **Impact:** A 3.10+ syntax/typing regression or an upstream minor-version dependency break could ship undetected (CI green) because: (1) no 3.9 job runs, (2) floors are unpinned with no lockfile, (3) lint/type checks are advisory. Blast radius is the 3.9 install target and reproducibility of builds. Currently latent only — no such regression exists in the code today, and the 3.9 deployment image is actually …
- **Adjudication:** All process/CI assertions verified true, but the cited active "already-flagged" 3.10 syntax slips do not exist in current code, making this a forward-looking hardening gap rather than a present defect — hence partial and low severity.
- **Fix target:** `.github/workflows/ci.yml (matrix 3.11/3.12, advisory ruff/mypy steps), requirements.txt / requirements-api.txt / requirements-mcp.txt pin policy, pyproject.tom…`

### G10 · 🔵 low · ◐ partial · score 1.7
**api/store.py concurrency & durability: single shared connection serialized by RLock kills SQLite WAL read concurrency; idempotency timeout race; no busy_timeout**

- **Evidence:** api/store.py confirms all three sub-claims literally. (1) Single connection + single lock: line 127 `self._conn = sqlite3.connect(path, check_same_thread=False)`, line 129 `self._lock = threading.RLock()`; every read funnels through `_fetch_one` (425-427) and `_fetch_all` (434-437), both wrapping `with self._lock`. So the WAL reader-concurrency the docstring advertises (line 116 "WAL reads", lines 131-132) is not realized intra-process — there is exactly one connection serialized by one lock. (2) idempotency stale re-claim: idempotency_begin lines 334-344 — if a 'processing' entry exceeds IDEMPOTENCY_PROCESSING_TIMEOUT=60.0 (line 103), a retry re-binds it and returns {"state":"new"}, so a l…
- **Impact:** Real but bounded. Sub-claim 1 is a performance/documentation mismatch, not a correctness defect: the comment at lines 124-126 explicitly states the lock serializes all access precisely because there is one shared connection (this is the intended, safe design); the only loss is the unrealized WAL read parallelism the docstring oversells. Sub-claim 3 (no busy_timeout) only bites with a second OS pr…
- **Adjudication:** All three code assertions are literally true, but the framing overstates severity: the single-lock design is intentional and safe, busy_timeout is moot under the current single-process model, and fulfill_once's exactly-once gate caps the idempotency-race blast radius — hence partial at low severity.
- **Fix target:** `api/store.py __init__ (118-138), _fetch_one/_fetch_all locking (425-437), idempotency_begin stale-claim window (334-347), IDEMPOTENCY_PROCESSING_TIMEOUT (103)`

### G11 · 🔵 low · ◐ partial · score 1.7
**api/billing.py webhook: _resolve_account can create duplicate/orphan accounts; subscription status from Stripe written without validation; _period_end/_first_price_id swallow shape errors**

- **Evidence:** api/billing.py:208-219 `_resolve_account` confirmed: when neither metadata account_id maps to an existing account (212) nor customer_id maps to one (214-217), it falls through to `store.create_account(account_id=account_id, plan="free")` (218). When account_id is None, api/store.py:155 mints `account_id = account_id or ("acct_" + secrets.token_hex(12))` — so a customer.subscription.* for an unknown customer DOES silently create a new free account (with a fresh api_key, no email). The "spoofable metadata account_id" framing is REFUTED: the webhook is signature-verified at api/billing.py:182 (`stripe.Webhook.construct_event(payload, sig, webhook_secret)`) and fails closed (line 183-185 raises…
- **Impact:** Realistic blast radius is a data-hygiene defect, not a security exposure. A legitimate Stripe subscription event for a customer with no prior account mapping (e.g., out-of-band-created customer, or a race where the subscription event precedes the checkout mapping) creates a dangling orphan account row (free plan, random id, no email, unusable api_key). No auth bypass — signature verification gate…
- **Adjudication:** Code behaviors are real as described, but the headline "spoofable/orphan-injection" severity collapses once the signature-verified, fail-closed webhook is accounted for; remaining issue is benign orphan-row creation plus two intentional, documented fallbacks.
- **Fix target:** `api/billing.py _resolve_account (208-219), _handle_event status write (248-262), _first_price_id/_checkout_plan_id/_period_end (280-303)`

### G19 · 🔵 low · ◐ partial · score 1.7
**core/audit.py independence claim is partly self-undermined: redacted receipts lose the violation evidence and a non-list message_id breaks the trail**

- **Evidence:** Target: core/audit.py + cross-ref api/app.py L117-122. CLAIM (1) — redacted receipt leaks message ids via the violations list: the specific API/web vector is REFUTED. summary().violations (audit.py:250) flows to result["audit"] -> receipts.signed_body ("summary": triage_result.get("audit"), receipts.py:83) only if the run returns a result; but api/service.py:127 calls audit.assert_no_violations() BEFORE returning (service.py:129-135), which raises AuditInvariantError whenever violations is non-empty, and api/app.py:112-122 converts it to a fixed 500 and never reaches receipts.persist (app.py:129). So a non-empty violations array can never be persisted/served by the API — app.py:117-122 is t…
- **Impact:** Low. No protected-sender bypass: the API fails closed on any violation (500, fixed message, no persist), and the gate's unguarded is_protected_sender crashes loudly on a rules-layer failure rather than silently degrading. The only confirmed defect is documentation imprecision — a redact=True JSONL receipt still embeds the raw provider message_id on every line, so the "shareable/committable" frami…
- **Adjudication:** Real but overstated: the API leak vector is refuted by the fail-closed assert_no_violations boundary and the fail-open collapse is unreachable because the gate uses the same un-guarded function; only a minor redact-keeps-message_id documentation gap survives.
- **Fix target:** `core/audit.py: violations list not redacted (lines 184, 209-210, 250 summary -> receipts/web); _independently_protected silent fail-open lines 110-114; _domain…`

### G22 · 🔵 low · ◐ partial · score 1.7
**acp/router.py update_session lets a buyer mutate line items / price after the session, and grand_total trusts stored line_items with no re-validation at charge time**

- **Evidence:** suggested_target: acp/router.py complete_session lines 246/257, update_session 216-225; acp/models.py build_line_items 85 + Item quantity le=1000.  HEADLINE (desync/no-reconciliation) REFUTED. _persist (router.py:149-155) is the SOLE session writer and ALWAYS stores response (which embeds line_items) and total_runs in one record together: data={"response": response, "total_runs": total_runs}. grep confirms no other save_session caller. All three write paths keep them in lock-step: create_session derives both from one build_line_items call (175 -> 188); update_session re-derives both together when items supplied (219) else copies both stored values unchanged (223-224 -> 230); complete_sessio…
- **Impact:** No current correctness/integrity bug from desync (the amount-vs-runs reconciliation the finding centers on cannot occur: single atomic writer, single derivation source). The only real residual is a missing high-value guardrail: one well-formed checkout can charge the buyer's own delegated token up to $9,000 / credit 1,000,000 runs with no confirmation step. Blast radius is limited — it bills the …
- **Adjudication:** The cross-file desync premise is false (single atomic writer, single derivation), but the un-capped $9k/1M-run single session is real, so the finding is partial at low severity.
- **Fix target:** `acp/router.py complete_session lines 246/257 (amount vs total_runs read from separate stored fields, no reconciliation), update_session lines 216-225; acp/mode…`

_Refuted gap: G13 (acp/models.py monetary math has no overflow/negative guard and trusts catalog i…)._

## 🔧 Top 40 live finding clusters — ranked

| # | score | sev | verdict | file | defect | corrob | dups |
|---|---|---|---|---|---|---|---|
| 1 | 166.0 | 🟠 | ✓ confirmed | `acp/router.py` | Fulfillment credits the account resolved from the request's bearer api_key, not the buyer… | ✓ | 57 |
| 2 | 148.0 | 🟠 | ✓ confirmed | `api/store.py` | consume_credit is defined and atomic but never invoked, so credit balances are decorative… | ✓ | 48 |
| 3 | 144.0 | 🟠 | ✓ confirmed | `api/billing.py` | Stripe subscription state is recorded but never enforced — plan/status writes have no run… | ✓ | 46 |
| 4 | 142.0 | 🔴 | ✓ confirmed | `api/app.py` | Triage endpoints enforce NO entitlement / quota / credit debit — paid credits are never c… | ✓ | 6 |
| 5 | 138.0 | 🔴 | ✓ confirmed | `archive_old_inbox.applescript` | Protected-sender gate completely bypassed: every inbox message >90 days is archived with … | ✓ | 4 |
| 6 | 128.0 | 🟠 | ✓ confirmed | `cloudflare/worker.mjs` | Live /v1/audit/{run_id} fabricates an UNSIGNED, hardcoded receipt — the demo's 'tamper-ev… | ✓ | 38 |
| 7 | 100.0 | 🔴 | ✓ confirmed | `api/service.py / api/app.py` | Triage execution path NEVER enforces monthly_run_cap, run_credits, or plan entitlements —… |  |  |
| 8 | 98.0 | 🟠 | ✓ confirmed | `providers/outlook.py` | Broad except swallows all errors (auth, network, 5xx) and degrades to empty/false, hiding… | ✓ | 23 |
| 9 | 90.0 | 🟠 | ✓ confirmed | `providers/imap.py` | imaplib uid(STORE/...) errors are exceptions OR ('NO', ...) tuples; success returned True… | ✓ | 19 |
| 10 | 78.0 | 🟠 | ✓ confirmed | `api/receipts.py` | ACP order-receipt save is NOT best-effort (router calls store.save_receipt directly), so … | ✓ | 13 |
| 11 | 72.0 | 🟠 | ✓ confirmed | `icloud_triage.py` | COPY+DELETE fallback expunges the ENTIRE mailbox per message, deleting any other \Deleted… | ✓ | 10 |
| 12 | 62.0 | 🟠 | ✓ confirmed | `core/rules.py` | Priority ties resolved by dict-insertion order silently misroute critical mail (gov mail … | ✓ | 5 |
| 13 | 60.0 | 🟠 | ✓ confirmed | `providers/gmail.py` | Gmail provider never populates EmailMessage.date, so escalate/pending age logic is a sile… |  | 10 |
| 14 | 58.0 | 🟠 | ✓ confirmed | `core/rules.py` | Non-UTF-8 local protected_senders config crashes the module at import time, disabling the… | ✓ | 3 |
| 15 | 55.0 | 🟡 | ✓ confirmed | `providers/gmail.py` | Gmail batchModify is treated as all-or-nothing, but invalid ids within a chunk fail the w… | ✓ | 21 |
| 16 | 52.0 | 🟠 | ✓ confirmed | `archive_sorted.py` | Pagination is broken: loops re-issue the same query and break after one full page instead… |  | 6 |
| 17 | 52.0 | 🟠 | ✓ confirmed | `cloudflare/worker.mjs` | Live demo's protected-sender set is 3 domains vs the engine's 14+ — IRS/SSA/DocuSign/Appl… | ✓ |  |
| 18 | 52.0 | 🟠 | ✓ confirmed | `core/rules.py` | irs.gov / ssa.gov / studentaid.gov never categorize as Personal/Government (Critical) bec… | ✓ |  |
| 19 | 49.0 | 🟡 | ✓ confirmed | `providers/mailapp.py` | AppleScript injection: message_id and label interpolated unescaped into osascript source | ✓ | 18 |
| 20 | 47.0 | 🟡 | ✓ confirmed | `mcp_server/server.py` | MCP triage tool has no auth/account/metering — unlimited free live triage for any connect… | ✓ | 17 |
| 21 | 46.0 | 🟡 | ✓ confirmed | `auto_drain.py` | Unbounded outer while-loop can run forever / loop indefinitely when domains keep mapping … |  | 18 |
| 22 | 45.0 | 🟡 | ✓ confirmed | `core/state.py` | Non-atomic state-file write can corrupt resume state on crash | ✓ | 16 |
| 23 | 44.0 | 🟠 | ✓ confirmed | `run_automation.sh` | set -u aborts iCloud step (and whole script) if ICLOUD_IMAP_* env vars are unset |  | 2 |
| 24 | 44.0 | 🟡 | ✓ confirmed | `auth/onepassword.py` | Secret passed as 1Password CLI argument is exposed in process listing / shell history |  | 17 |
| 25 | 42.0 | 🟠 | ✓ confirmed | `Dockerfile` | Docker build copies entire repo (no .dockerignore) — bakes data/app.db (API keys, Stripe … |  | 1 |
| 26 | 42.0 | 🟠 | ✓ confirmed | `route_bulk_senders.applescript` | Bulk-sender router moves protected mail with no protected-sender gate (and unanchored sub… |  | 1 |
| 27 | 41.0 | 🟡 | ✓ confirmed | `providers/outlook.py` | Access token never refreshed mid-run; long sweeps fail with 401 once the token expires | ✓ | 14 |
| 28 | 40.0 | 🟠 | ✓ confirmed | `acp/router.py` | Idempotency key is not namespaced by api_key (Authorization), enabling cross-account repl… |  |  |
| 29 | 40.0 | 🟠 | ✓ confirmed | `providers/imap.py` | IMAP search passes raw query string with charset=None; Gmail-style queries (label:, has:)… |  |  |
| 30 | 39.0 | 🟡 | ✓ confirmed | `core/config.py` | Unguarded int() cast on MAIL_AUTO_BATCH_SIZE crashes entire CLI/config load at startup | ✓ | 13 |
| 31 | 39.0 | 🟡 | ✓ confirmed | `core/audit.py` | Protected-sender disposition over-reported as protected_held even when message left the i… | ✓ | 13 |
| 32 | 31.0 | 🟡 | ✓ confirmed | `acp/payment.py` | Charge treats only status=='succeeded' as ok, dropping 'requires_action'/'processing' int… | ✓ | 9 |
| 33 | 30.0 | 🟡 | ✓ confirmed | `imap_rules.py` | Paging slice computes a negative end index when start > len(uids), selecting wrong (oldes… |  | 10 |
| 34 | 27.0 | 🟡 | ✓ confirmed | `providers/outlook.py` | Folder lookup fallback can silently return the label string instead of a real folder ID, … | ✓ | 7 |
| 35 | 27.0 | 🟡 | ✓ confirmed | `core/rules.py` | calculate_email_age_hours returns 0 for None date, conflating 'unknown age' with 'brand n… | ✓ | 7 |
| 36 | 27.0 | 🟡 | ✓ confirmed | `acp/feed.py` | Host header reflected into absolute feed/checkout/seller URLs (Host-header injection / ca… | ✓ | 7 |
| 37 | 21.9 | 🔵 | ✓ confirmed | `acp/models.py` | Line-item subtotal and total_runs are unbounded int*qty products with no per-session amou… | ✓ | 9 |
| 38 | 21.0 | 🟡 | ✓ confirmed | `api/plans.py` | Metered per-run billing advertised but no Stripe Meter event is ever emitted | ✓ | 4 |
| 39 | 21.0 | 🟡 | ✓ confirmed | `tests/test_acp.py` | Success-charge fake ignores the amount argument, so no test asserts the charged amount eq… | ✓ | 4 |
| 40 | 21.0 | 🟡 | ✓ confirmed | `api/well_known.py` | Manifest/llms.txt reflect the raw request base_url (Host header) — Host-header spoofing m… | ✓ | 4 |

## Detail — top live clusters

### 1. 🟠 HIGH · `acp/router.py` — Fulfillment credits the account resolved from the request's bearer api_key, not the buyer who paid / the session's orig…
score **166.0** · ✓ confirmed · cluster of 58 · corroborated · `complete_session() lines 286-290`

- **Evidence:** router.py:188 _persist(session_id, resp, total_runs) is called with no account_id (defaults None), so create_session never binds the session to a key. router.py:287-289 complete_session resolves account = store.get_account_by_api_key(ctx.api_key) and create_account(api_key=ctx.api_key) on miss; _gate (79-83) accepts any non-empty Bearer. So whoever calls /complete is credited, not the creator/payer. The body's payment_data.token (264) is charged independently. <!-- allow-secret false-positive: quoted source-code example -->
- **Adjudication:** Code exactly matches: unbound session + caller-derived credit target + unvalidated bearer. Real authorization defect.
- **Folds in:** U013, U014, U015, U016, U017, U018, U020, U021, U110, U111, U114, U252, U254, U011, U112, U019, U109, U249, U253, U256, U257, U258, U259, U263, U267, U424, U142, U250, U255, U261, U426, U497, U498, U501, U707, U709, U712, U251, U500, U502, U708, U022, U260, U265, U266, U711, U903, U713, U262, U264, U423, U705, U425, U704, U714, U706, U710

### 2. 🟠 HIGH · `api/store.py` — consume_credit is defined and atomic but never invoked, so credit balances are decorative — they are only ever added (a…
score **148.0** · ✓ confirmed · cluster of 49 · corroborated · `consume_credit lines 235-246 (and absence of any caller)`

- **Evidence:** grep -rn 'consume_credit' across repo returns only api/store.py:235 (definition) + tests/test_store.py:39,42. No caller in api/ or acp/. app.py /v1/triage (lines 91-94) → _run() never reads run_credits or debits. The atomic UPDATE...WHERE run_credits>=? is correct but dead.
- **Adjudication:** Confirmed: consume_credit is defined, atomic, and never invoked by production; the metered-credit economy adds but never spends.
- **Folds in:** U037, U124, U126, U299, U304, U305, U038, U039, U125, U297, U303, U035, U036, U153, U154, U307, U308, U309, U431, U445, U517, U518, U519, U525, U746, U444, U430, U522, U743, U744, U739, U742, U737, U748, U034, U296, U298, U300, U301, U302, U306, U432, U433, U524, U738, U740, U747, U749

### 3. 🟠 HIGH · `api/billing.py` — Stripe subscription state is recorded but never enforced — plan/status writes have no runtime effect on triage
score **144.0** · ✓ confirmed · cluster of 47 · corroborated · `_handle_event (222-277); webhook (170-204)`

- **Evidence:** grep across the entire repo: entitlements_for is defined at plans.py:175 and referenced ONLY in docs/session transcripts — zero application callers. /v1/triage (app.py:91-130) calls service.run_triage with provider/query/limit only; grep of service.py+schemas.py for get_account/api_key/entitlement returns nothing. Webhook persists plan/status via set_subscription (billing.py:231,255,269,276) but no runtime reader consumes it.
- **Adjudication:** Confirmed: billing is a recording subsystem with no authorization consumer; the docstring claim (billing.py:21-23) that subscription status is the single source of truth is unrealized for the product's core action. Severity high stands — paid vs canceled accounts get identical triage behavior.
- **Folds in:** U025, U028, U119, U122, U117, U115, U120, U145, U273, U278, U280, U282, U283, U284, U506, U715, U717, U718, U719, U721, U723, U725, U727, U427, U720, U724, U279, U285, U121, U286, U716, U726, U287, U904, U024, U026, U116, U118, U271, U276, U272, U274, U275, U277, U281, U270

### 4. 🔴 CRITICAL · `api/app.py` — Triage endpoints enforce NO entitlement / quota / credit debit — paid credits are never consumed
score **142.0** · ✓ confirmed · cluster of 7 · corroborated · `_run (97-130), triage (91-94), triage_preview (85-88)`

- **Evidence:** consume_credit only at store.py:235 (+tests); entitlements_for only at plans.py:175; monthly_run_cap is only a dataclass field (plans.py:37/74/92/111) never read at runtime; scripts/gen_commerce_artifacts.py is the only non-test consumer (artifact generation, not the run path). acp/router.py:287 credits run_credits via fulfill_once, but nothing decrements it on a triage. MCP _triage (mcp_server/server.py:129) also calls service.run_triage with no metering.
- **Adjudication:** Credits are minted (ACP) but never spent and the cap is never enforced; the metered product is dispensed free and unbounded.
- **Folds in:** U001, U144, U269, U003, U023, U505

### 5. 🔴 CRITICAL · `archive_old_inbox.applescript` — Protected-sender gate completely bypassed: every inbox message >90 days is archived with zero sender check
score **138.0** · ✓ confirmed · cluster of 5 · corroborated · `lines 15-21`

- **Evidence:** Lines 15-21 of archive_old_inbox.applescript move EVERY inbox message with `date received of msg < cutoffDate` to targetMailbox, keyed solely on age (line 17-18). There is no is_protected_sender call, no PROTECTED_SENDERS check, no audit, no dry-run. core/rules.py defines is_protected_sender (L787), _gov_protected (L652), _is_protected_domain (L666); core/audit.py docstring (verified lines 1-9) states the headline guarantee 'a protected sender ... is NEVER archived or moved out of the inbox', enforced by AuditInvariantError. CLAUDE.md L181 and AGENTS.md L17 (`osascript archive_old_inbox.applescript`) ship this script as a supported tool.
- **Adjudication:** A shipped, documented tool unconditionally archives 91-day-old mail from lawyers/banks/.gov/self, directly violating the product's stated protected-sender guarantee with no gate or audit backstop; data-loss class, critical confirmed.
- **Folds in:** U312, U156, U527, U040

### 6. 🟠 HIGH · `cloudflare/worker.mjs` — Live /v1/audit/{run_id} fabricates an UNSIGNED, hardcoded receipt — the demo's 'tamper-evident signed receipt' headline…
score **128.0** · ✓ confirmed · cluster of 39 · corroborated · `GET /v1/audit/{run_id} lines 281-305; cross-ref api/receipts.py sign(…`

- **Evidence:** worker.mjs 281-305 returns a fixed body {run_id, receipt:`Signed receipt for ${runId}`, audit:{total:3,protected_held:2,archived:1,...}} with NO signature/signed_body/algorithm. api/receipts.py get_receipt (lines 114-142) returns {signed_body, signature, algorithm:'HMAC-SHA256', verify:'...', created_at} and 404s on missing receipts (123-124); sign() (66-68) is real HMAC-SHA256. agent.json advertises 'audit_receipt: independent, HMAC-signed, re-derivable' and worker /llms.txt line 315 advertises /v1/audit/{run_id}.
- **Adjudication:** The worker's headline 'signed receipt' is a literal label string with zero cryptographic content; an auditing agent has nothing to verify. Directly contradicts the advertised trust artifact.
- **Folds in:** U056, U057, U059, U169, U170, U171, U058, U172, U175, U178, U179, U180, U181, U451, U452, U453, U454, U456, U458, U549, U552, U553, U555, U557, U173, U177, U455, U550, U551, U554, U556, U561, U176, U560, U558, U559, U889, U915

### 7. 🔴 CRITICAL · `api/service.py / api/app.py` — Triage execution path NEVER enforces monthly_run_cap, run_credits, or plan entitlements — paid limits and purchased cre…
score **100.0** · ✓ confirmed · cluster of 1 · `run_triage() (service.py 70-135) and _run() (app.py 97-130)`

- **Evidence:** service.run_triage(service.py:70-135) takes provider/query/limit/dry_run/etc and NO account_id/api_key; it builds a provider, runs the labeler, asserts no gate violations, and returns — never touching credits/caps. app._run (app.py:97-130) and mcp_server/server.py:_triage (129-146) both call service.run_triage with the same signature; neither passes nor looks up an account. grep confirms enforcement primitives have no live callers: `consume_credit` appears only at api/store.py:235 (def) and in tests/test_store.py; `entitlements_for` appears only at api/plans.py:175 (def) — zero callers in api/, mcp_server/, acp/; `monthly_run_cap` is referenced only for display (scripts/gen_commerce_artifacts.py:46, api/plans.py catalog rows 37/58/74/92/111/189) and…
- **Adjudication:** Verified: all three triage entry points lack any account lookup, credit debit, or run-cap check; consume_credit/entitlements_for have no production callers while fulfill_once does mint paid credits — the metered/credit/cap monetization model is genuinely unenforced (unlimited free triage; purchased credits never consumed).

### 8. 🟠 HIGH · `providers/outlook.py` — Broad except swallows all errors (auth, network, 5xx) and degrades to empty/false, hiding real failures
score **98.0** · ✓ confirmed · cluster of 24 · corroborated · `list_messages 436-440 (and get_message_details 480-484, apply_categor…`

- **Evidence:** list_messages (438-440) returns ListMessagesResult(messages=[]) on ANY Exception; cli.py (192-194) treats empty messages as 'No more messages found' and breaks the loop. apply_category (349-350) bare-excepts to current_cats=[]. _init_folder_cache (261) and _init_category_cache (284) log a warning and continue with empty caches. All confirmed verbatim.
- **Adjudication:** Confirmed: a mid-pagination 401/429/5xx is swallowed into an empty result that the CLI reads as successful completion — silent early termination on a bulk job. High kept.
- **Folds in:** U219, U134, U222, U404, U644, U645, U646, U650, U651, U845, U853, U849, U394, U407, U410, U405, U435, U857, U400, U402, U649, U850, U859

### 9. 🟠 HIGH · `providers/imap.py` — imaplib uid(STORE/...) errors are exceptions OR ('NO', ...) tuples; success returned True without checking response sta…
score **90.0** · ✓ confirmed · cluster of 20 · corroborated · `apply_label 279, remove_label 303, star 331, unstar 340, mark_read 36…`

- **Evidence:** Verified imaplib.IMAP4._command_complete raises self.error ONLY on typ=='BAD'; a typ=='NO' (label missing, permission, quota, invalid flag) returns ('NO',[...]) without raising. Lines 279-280/303-304/331-332/340-341/364-365/373-374 each call uid('STORE',...) then unconditionally `return True`, catching only exceptions. base.apply_actions (base.py:344-346) records applied_labels from this True return into the audit. The COPY branch (288-289) and ensure_label_exists DO check res, proving the asymmetry.
- **Adjudication:** Server NO rejections are silently reported as success; primary trust-surface defect (label add) — confirmed against real imaplib semantics.
- **Folds in:** U087, U086, U131, U376, U830, U375, U379, U642, U833, U088, U214, U215, U382, U383, U381, U640, U089, U835, U837

### 10. 🟠 HIGH · `api/receipts.py` — ACP order-receipt save is NOT best-effort (router calls store.save_receipt directly), so a receipts-table write failure…
score **78.0** · ✓ confirmed · cluster of 14 · corroborated · `88-108 (persist best-effort) cross-ref acp/router.py 312-317`

- **Evidence:** router.py complete_session: store.fulfill_once(...) commits the credit at line 290; THEN order_id minted (296), receipts.sign() (312) and store.save_receipt() (313-317) are called with NO try/except. receipts.persist() (88-108) deliberately wraps save_receipt in 'except Exception' (106) — the ACP path bypasses persist() entirely. So a receipts-table write failure after fulfill_once raises an unhandled 500 with credit already applied, receipt missing, and idempotency not yet completed (_complete_idempotency is at 338, after save_receipt).
- **Adjudication:** Confirmed and corroborated: the two receipt-write call sites have opposite error semantics, and the unprotected one is on the money path post-credit-commit. High severity stands — inconsistent committed state on a paid transaction.
- **Folds in:** U030, U294, U293, U295, U123, U429, U730, U733, U906, U510, U512, U731, U734

### 11. 🟠 HIGH · `icloud_triage.py` — COPY+DELETE fallback expunges the ENTIRE mailbox per message, deleting any other \Deleted-flagged messages
score **72.0** · ✓ confirmed · cluster of 11 · corroborated · `archive_uid, lines 63-77`

- **Evidence:** Line 76 calls `imap.expunge()`; Python's imaplib signature is `IMAP4.expunge(self)` (verified, no UID arg) -> mailbox-wide EXPUNGE that purges ALL \Deleted-flagged messages in the selected INBOX, not just this uid. Called once per archivable uid inside the apply loop (lines 161-165), so O(n) full expunges. The COPY+STORE+expunge fallback (72-77) fires only when UID MOVE returns non-OK or raises imaplib.IMAP4.error (67-71).
- **Adjudication:** Genuine unscoped-EXPUNGE data-loss path; downgraded critical->high because it only triggers when the server lacks RFC 6851 MOVE (iCloud, the primary target, supports MOVE) AND unrelated \Deleted mail already exists in INBOX.
- **Folds in:** U359, U358, U798, U799, U801, U076, U077, U128, U129, U800

### 12. 🟠 HIGH · `core/rules.py` — Priority ties resolved by dict-insertion order silently misroute critical mail (gov mail with 'unsubscribe'/'newsletter…
score **62.0** · ✓ confirmed · cluster of 6 · corroborated · `_find_best_label (lines 1025-1038) + LABEL_RULES priorities; demonstr…`

- **Evidence:** Reproduced: categorize_with_tier('Benefits <noreply@ssa.gov>','newsletter: ... unsubscribe here') -> label=Marketing, tier=4. Priority histogram confirms 17 is shared by Marketing, Tech/Storage, Personal/Government in that insertion order; _find_best_label line 1033 uses strict '<' so the first-inserted same-priority rule wins. Marketing is defined at line 429, Personal/Government at 468 (Marketing wins the tie).
- **Adjudication:** Real defect: a gov email containing any bulk-mail keyword is demoted from Critical(tier1) to Reference(tier4) by dict-insertion order alone. Sub-claim 'priority 9 Tech/Security beats Personal/Health' and 'priority 8 Finance/Payments beats Finance/Tax' confirmed by histogram (ties exist).
- **Folds in:** U775, U920, U069, U584, U587

### 13. 🟠 HIGH · `providers/gmail.py` — Gmail provider never populates EmailMessage.date, so escalate/pending age logic is a silent no-op
score **60.0** · ✓ confirmed · cluster of 11 · `157-161, 204-211, 286-293 (EmailMessage construction); 177, 243 (meta…`

- **Evidence:** All three EmailMessage constructions (gmail.py:157-161, 204-211, 286-293) omit date=, which defaults to None (core/models.py:48). The metadata fetches request metadataHeaders=["From","Subject"] (lines 177, 243) — no Date header retrieved. calculate_email_age_hours(None) returns 0 (core/rules.py: 'if email_date is None: return 0'). escalate_by_age then hits 'if email_age_hours < 24: should_escalate=False'. cli.py:883 calls calculate_email_age_hours(msg.date) and cli.py:667 builds the pending age column from msg.date.
- **Adjudication:** Confirmed end-to-end: Gmail msg.date is always None, so escalate is a silent no-op and pending age always reports 0h.
- **Folds in:** U213, U473, U629, U630, U823, U821, U934, U827, U824, U826

### 14. 🟠 HIGH · `core/rules.py` — Non-UTF-8 local protected_senders config crashes the module at import time, disabling the entire safety gate
score **58.0** · ✓ confirmed · cluster of 4 · corroborated · `_load_local_protected lines 599-612`

- **Evidence:** Reproduced: with PROTECTED_SENDERS_FILE pointing at a file containing byte 0xff, `import core.rules` raises UnicodeDecodeError ('utf-8' codec can't decode byte 0xff). Line 600 opens with encoding='utf-8'; line 611 only catches (FileNotFoundError, OSError). UnicodeDecodeError is a ValueError subclass, not caught. _load_local_protected runs at import (line 616), so the whole module fails to import.
- **Adjudication:** Docstring promises 'Never raises.' A user-supplied non-UTF-8 protected_senders config takes down the entire safety gate and every consumer at import. Fix: catch UnicodeDecodeError / errors='replace' / broaden except.
- **Folds in:** U778, U580, U922

### 15. 🟡 MEDIUM · `providers/gmail.py` — Gmail batchModify is treated as all-or-nothing, but invalid ids within a chunk fail the whole call, marking valid messa…
score **55.0** · ✓ confirmed · cluster of 22 · corroborated · `apply_actions 459-466 (batchModify) — partial per-id failure semantics`

- **Evidence:** Lines 452-472: each chunk of up to BATCH_MODIFY_SIZE=1000 ids is one batchModify call. The except at 469-472 increments error_count by len(chunk) and leaves `succeeded` unchanged for the whole chunk. There is no per-id isolation or smaller-chunk fallback. Gmail returns a single 400 for the entire batchModify if any id is invalid, so one bad id strands up to 999 valid messages as error/unapplied; audit (482-495) then records labels_added=[] for all of them.
- **Adjudication:** Confirmed poison-pill: a single invalid id fails the whole 1000-id chunk with no isolation.
- **Folds in:** U369, U472, U628, U632, U637, U373, U898, U370, U636, U828, U933, U822, U829, U938, U371, U633, U634, U635, U820, U825, U937

### 16. 🟠 HIGH · `archive_sorted.py` — Pagination is broken: loops re-issue the same query and break after one full page instead of paging through nextPageTok…
score **52.0** · ✓ confirmed · cluster of 7 · `archive_loop, lines 92-130`

- **Evidence:** Lines 92-96: `while True: results = service.users().messages().list(userId='me', q=query, maxResults=1000).execute()` with NO pageToken anywhere (grep for nextPageToken/pageToken returns nothing). Lines 112-115: `if not archivable: if len(ids) < 1000: break; continue`. When a full page of 1000 IDs is returned and every sender is_protected (archivable empty), no batchModify runs (line 122 is skipped), the INBOX label is not removed, so the next list() returns the identical 1000 messages and the loop `continue`s forever.
- **Adjudication:** The all-protected full-page path is a genuine non-terminating loop because progress depends solely on batchModify shrinking the result set, which never happens when archivable is empty.
- **Folds in:** U314, U316, U317, U907, U042, U315

### 17. 🟠 HIGH · `cloudflare/worker.mjs` — Live demo's protected-sender set is 3 domains vs the engine's 14+ — IRS/SSA/DocuSign/Apple/Google/Anthropic/1Password-e…
score **52.0** · ✓ confirmed · cluster of 1 · corroborated · `line 1 (PROTECTED set) cross-ref core/rules.py:559-573 EXAMPLE_PROTEC…`

- **Evidence:** worker.mjs line 1: PROTECTED = new Set(["courts.ca.gov","chase.com","1password.com"]) and senderCheck (82-169) only protects courts.ca.gov/.gov, chase.com, 1password.com. core/rules.py EXAMPLE_PROTECTED_SENDERS (lines 560-580) lists docusign.net, irs.gov, ssa.gov, studentaid.gov, login.gov, apple.com, appleid.com, google.com, accounts.google.com, anthropic.com, 1password.com, meta.com, facebookmail.com, chase.com + synthetic placeholders + a merged local file. web/index.html:354 promises 'court, bank, gov, account, and client mail' protection.
- **Adjudication:** The live worker's protection coverage (3 domains + bare .gov) is materially narrower than the engine's 14+ generic defaults; apple.com / accounts.google.com / docusign.net / irs.gov etc. all return 'Can move' on the shipped demo while marketing promises they are held.

### 18. 🟠 HIGH · `core/rules.py` — irs.gov / ssa.gov / studentaid.gov never categorize as Personal/Government (Critical) because lower-priority earlier ru…
score **52.0** · ✓ confirmed · cluster of 1 · corroborated · `Personal/Government rule patterns 468-479; categorize path _find_best…`

- **Evidence:** Reproduced exactly: categorize_with_tier('IRS <noreply@irs.gov>','Your tax refund status') -> label=Finance/Tax, tier=2 (NOT Personal/Government tier 1). irs.gov is listed both in Finance/Tax (priority 8, line 203) and Personal/Government (priority 17, line 476); the lower priority number (8) wins via line 1033.
- **Adjudication:** Distinct from U064: this is lower-priority-rule-wins (8<17), not a same-priority tie. Government mail from irs.gov silently downgraded from Critical to Important; the tier table promises Critical.

### 19. 🟡 MEDIUM · `providers/mailapp.py` — AppleScript injection: message_id and label interpolated unescaped into osascript source
score **49.0** · ✓ confirmed · cluster of 19 · corroborated · `apply_label/get_message_details/star/mark_read/ensure_label_exists, l…`

- **Evidence:** Every mutating method builds AppleScript via f-string with zero escaping: line 213/265/297/313/362/378 `first message whose id is {message_id}` (unquoted), line 266 `mailbox "{label}"`, line 342 `make new mailbox with properties {{name:"{label}"}}`, line 133/261/332/409 `of account "{self.account}"`. No escape helper exists anywhere in the module (full file read).
- **Adjudication:** Genuine AppleScript-injection sink; downgraded from high because all sources (message_id from Mail.app's own data, label from static rules/config, account from CLI --account) are locally-controlled, not remote/untrusted input.
- **Folds in:** U093, U216, U217, U388, U839, U843, U643, U386, U091, U092, U094, U132, U133, U389, U390, U391, U842, U942

### 20. 🟡 MEDIUM · `mcp_server/server.py` — MCP triage tool has no auth/account/metering — unlimited free live triage for any connected agent
score **47.0** · ✓ confirmed · cluster of 18 · corroborated · `_triage (129-146); triage (109-126); triage_preview (97-107)`

- **Evidence:** mcp_server/server.py imports only `api.service` (line 34) and `api.schemas` (line 35) — never `api.store`. _triage (129-146) calls service.run_triage with provider/query/limit/dry_run/remove_label/tier_routing/vip_only and NO account/api_key. grep confirms entitlements_for and consume_credit have ZERO runtime callers (only tests + the credit-pack fulfillment in acp/router.py). plans.py:130-139 advertises the metered '$0.01/triage run' add-on and Business-tier MCP access; meter_event_name='triage_run' is defined but emitted nowhere. The only guard on the surface is _transport_security() DNS-rebinding.
- **Adjudication:** Real: no auth/credit/cap/meter on the MCP triage path. But the SAME gap exists on the HTTP path (api/app.py _run never checks credits/caps either), so this is system-wide, not an MCP-unique unlimited-free-triage hole; severity downgraded from high to medium accordingly.
- **Folds in:** U081, U211, U212, U623, U810, U813, U366, U621, U622, U624, U809, U082, U814, U080, U130, U811, U812

## ⏱ Needs-runtime (20) — cannot adjudicate statically

- `providers/outlook.py` **U134** (medium): Graph rejects $orderby + $filter on different properties with HTTP 400 — the primary 'isRead eq false' pendin…
- `api/billing.py` **U286** (low): Expanded Stripe objects: obj.get('customer'/'subscription') may be a dict (when expanded), used as a string i…
- `core/rules.py` **U349** (low): calculate_email_age_hours assumes naive provider dates are UTC, but providers populate naive LOCAL dates (e.g…
- `api/billing.py` **U428** (low): Expanded Stripe 'customer'/'subscription' object (dict) would be used as a customer id, causing wrong lookups…
- `providers/outlook.py` **U435** (low): apply_category/remove_category operate on /me/messages/{id} but the categorize+move pipeline may move the mes…
- `api/billing.py` **U716** (low): Broad except over stripe.error.SignatureVerificationError attribute access can itself raise AttributeError on…
- `providers/gmail.py` **U821** (low): batch.execute retried wholesale on rate limit can double-process already-succeeded messages and accumulate st…
- `providers/outlook.py` **U844** (low): Archive uses literal destinationId 'archive'; if the well-known alias is not accepted the message stays in in…
- `providers/outlook.py` **U857** (low): Category de-dupe is exact-string; Graph treats category names case-insensitively, so repeated runs append dup…
- `requirements-api.txt` **U863** (low): stripe major pinned <16 — billing code uses StripeClient/v1 namespace; verify floor matches the API surface u…
- `providers/mailapp.py` **U385** (low): 'first message whose id is' searches only current/default mailbox context, may target wrong or missing message
- `providers/mailapp.py` **U386** (low): Mailbox marked as created even when AppleScript fails, caching a false 'exists' state
- `cloudflare/worker.mjs` **U558** (low): serveApp special-cases /app but lets any other path hit ASSETS, so /docs, /openapi.json, /server.json resolve…
- `com.user.mail_automation.plist` **U563** (low): Plist provides no PATH/EnvironmentVariables; job depends entirely on run_automation.sh sourcing the 1Password…
- `auth/onepassword.py` **U753** (low): Inconsistent/undocumented op CLI flag ordering for edit vs get; --vault placement after positional assignment
- `core/audit.py` **U764** (low): Concurrent AuditLog writers to same path can interleave/lose lines (no locking)
- `create_smart_mailboxes.scpt` **U782** (low): Date condition 'is less than value:30' is likely wrong units for a date-received filter
- `final_sweep.py` **U784** (low): Query 'label:Uncategorized' likely targets a non-existent label (taxonomy uses 'Misc/Other')
- `gmail_labeler.py` **U789** (low): Batch HTTP retry re-executes an already-consumed BatchHttpRequest on rate limit, likely raising instead of re…
- `providers/mailapp.py` **U838** (low): is_read/is_starred parsed from raw AppleScript boolean string is fragile to localization/format

## ✗ False positives (22) — surfaced by coverage, refuted on verification

- `providers/imap.py` **U089** (was high): Standard-IMAP archive expunges the whole mailbox, deleting unrelated messages — The whole-mailbox-expunge data-loss claim does not match the actual code, which never expunges.
- `requirements.txt` **U098** (was high): `requests` is mislabeled "Optional: Outlook" but is a MANDATORY runtime dependency for Gmail OAuth … — The crash scenario is impossible: requests is a hard transitive dependency of the declared Gmail deps, so it is always installed; only the comment label is imp…
- `llms.txt` **U208** (was medium): Headline trust claim ('signed audit receipt', 'never archives government/financial/legal/platform m… — Mis-attributes the demo worker's behavior to the FastAPI surface that actually emits/serves this llms.txt, where the signed-receipt and fail-closed-gate claims…
- `api/billing.py` **U270** (was medium): Webhook references stripe.error.SignatureVerificationError without guaranteeing the attribute exist… — The attribute exists on every version allowed by the pin; the except tuple (billing.py:183) evaluates fine. No AttributeError occurs. False positive for the ac…
- `bulk_sweeper.py` **U328** (was medium): SWEEP_RULES route by bare 'from:<domain>' with no protected-sender gate; safe today but a one-line … — Speculative future-edit risk on code that already documents the exact constraint; not a present bug — false positive.
- `llms.txt` **U363** (was medium): Advertises /v1/audit/{run_id} 'receipt verification' that the live worker returns unsigned — The /v1/audit/{run_id} on the FastAPI surface this file describes returns a real HMAC-signed, re-derivable receipt; the 'unsigned' claim belongs to the demo wo…
- `providers/base.py` **U368** (was medium): INBOX strip in _drop_if_protected matches only 'INBOX'/'\\INBOX' but remove path matches the same; … — Lowercase claim is refuted by the .upper() normalization; the aliased-inbox path is unreachable in current code because the one folder provider departs via arc…
- `run_automation.sh` **U415** (was medium): set -e plus `source` of op env file aborts whole run if any `op read` fails — The env file already defends against set -e abort with `|| true` on each op read; no unguarded failure path exists as described.
- `tests/test_mcp.py` **U671** (was low): MCP destructive/readonly hint assertions silently skip on the Python 3.9 CI floor — The claimed '3.9 floor that silently skips the safety assertions' does not exist in CI — the matrix is 3.11/3.12 and CI explicitly installs the mcp SDK, so the…
- `DEPLOY.md` **U686** (was low): DEPLOY.md Fly.io instructions are generic and unverifiable; no fly.toml ships and secrets list is G… — Documented intended fail-soft behavior with the secrets table in the same doc; the 'no pointer back' claim misreads the file. Not a defect.
- `acp/router.py` **U706** (was low): Idempotency replay can return a stored response of JSON null, and gate parses body before idempoten… — The harmful re-run scenario requires a state (done + null response) that no code path can produce; the benign ordering note is acknowledged as non-defect.
- `acp/router.py` **U710** (was low): amount=0 (empty/zero-priced READY session) is charged and the response treated as fulfillable — amount=0 reaching the charge is statically unreachable given the catalog and the valid=bool(items) guard.
- `api/store.py` **U747** (was low): Single shared sqlite connection with check_same_thread=False relies entirely on RLock; any code pat… — No current code path touches _conn outside the lock; this is a speculative architectural-fragility note about code that does not exist, not a defect in the rea…
- `api/store.py` **U749** (was low): fulfill_once trusts the runs argument with no >=0 guard, so a negative or oversized total_runs is c… — The negative-debit scenario is unreachable through validated input; only a manually corrupted stored session could produce it (not a code defect). Finding self…
- `providers/gmail.py` **U820** (was low): batchModify body captured by late-binding closure inside loop — Self-admitted non-bug; the synchronous execution makes the closure correct — false positive as a defect.
- `providers/gmail.py` **U826** (was low): Batch callback records failures but the surrounding batch.execute via _execute_with_backoff can los… — Read-only batch get; re-exec is idempotent overwrite and the feared whole-batch-429-mixed-with-success drop cannot corrupt results — speculative and self-rated…
- `providers/imap.py` **U835** (was low): UID decoded to str for EmailMessage.id but downstream STORE/FETCH pass it back as str — fine, but n… — The 'server chunks UIDs across data[1:]' concern does not match the IMAP SEARCH response contract — SEARCH returns one untagged response line; no real defect, …
- `providers/imap.py` **U837** (was low): IMAP write operations assume the correct mailbox is selected, but apply_actions issues UID STOREs w… — The wrong-mailbox UID scenario requires a caller to list a non-INBOX mailbox then mutate — no such call site exists; the latent risk is real only if a future c…
- `providers/outlook.py` **U859** (was low): Folder-name attribution is ambiguous: reverse lookup of parentFolderId returns the first cache entr… — The reverse id->name lookup is deterministic and correct since ids are unique; the claimed mis-attribution has no path to occur. False positive.
- `README.md` **U902** (was info): Provider capability matrix claims Gmail batch 'Yes (1000/batch)' but text elsewhere references batc… — The numeric claim flagged as unverified is verified CORRECT against the provider constant; the documentation is accurate, so there is no defect.
- `cli.py` **U912** (was info): Summary table bar uses int(pct/5) which can exceed the 20-cell width only if pct>100, but '░'*(20-i… — No defect exists in current code; the finding is an explicitly hypothetical/defensive note, and Python str*negative yields '' rather than erroring anyway.
- `web/index.html` **U950** (was info): Sender/subject sent to API with no client-side length bound — The premise that the server lacks sender/subject bounds is false — schemas.py enforces max_length=4096 on both; the client simply lacks a redundant pre-check, …

> Note: the coverage stage's `known_false_positive_class` (R2 "undeclared FastAPI/uvicorn/pydantic/stripe/mcp deps") was pre-flagged and down-weighted — those are declared in `requirements-api.txt`/`requirements-mcp.txt`.

## Methodology

1. **Coverage** (4 rounds, loop-until-census-exhausted): 950 unique findings + 22 gaps, unfiltered.
2. **Verification**: one adversarial skeptic per file-slice (read the file once, adjudicate every finding in it against real code) + one skeptic per structural gap, default-to-refute.
3. **Merge**: 930 primary + 20 recovered finding verdicts + 22 gap verdicts = full coverage (U001–U950, G01–G22; verified zero overlap / zero missing).
4. **Score & cluster**: deterministic Python — uniform formula, union-find on `duplicate_of` + same-file/line-overlap edges.

_Full machine-readable detail (all 950 findings, every verdict, evidence, cluster membership) in `verified-findings.json`._
