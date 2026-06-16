# UMA Master Plan - Mail Operations OS

Date: 2026-06-15

## Endgame

The endgame is not a clean inbox. The endgame is a trusted mail-operations
system.

Universal Mail Automation should become the operating layer that watches every
mailbox-adjacent surface, separates noise from risk, protects legal, financial,
security, and business-critical mail, drafts or executes safe responses, proves
what happened, and presents the whole state in one cockpit.

The ideal system works without Chrome, without hidden manual steps, without
hallucinated sends, and without leaving quiet work behind in archive, all-mail,
drafts, social, provider, LinkedIn, GitHub, or billing queues.

The durable loop is:

```text
refresh -> classify -> reconcile -> draft/act -> verify -> receipt -> dashboard -> learn
```

For every item, UMA should either prove it is handled, show the exact blocker,
or keep it visible until it is resolved.

## Where This Started

This started as mail survival:

- too many accounts;
- too much notification noise;
- provider alerts mixed with real legal, financial, security, and work signals;
- no single trustworthy picture of what needed action.

The first layer was automation around existing mail surfaces:

- Gmail labeling;
- macOS Mail paths;
- AppleScript helpers;
- IMAP and Outlook support;
- filtering rules;
- VIP and protected sender handling;
- dry runs;
- local triage reports.

The need then sharpened from "automate email" to "avoid bad automation." UMA
therefore grew safety and proof machinery:

- protected-sender gates;
- audit receipts;
- dry-run previews;
- provider abstractions;
- billing and product surfaces;
- MCP and ACP endpoints;
- a public `/app` dashboard.

The 2026-06-15 operations pass moved the system from product demo into private
operations:

- May 2026-to-current inbox, all-mail, and archive triage;
- LinkedIn, GitHub, provider, legal, security, finance, and subscription lanes;
- no browser dependency;
- no unapproved sends;
- a private `/ops` dashboard backed by redacted API contracts.

## Current State

UMA now has three real layers.

### 1. Mailbox Triage State

Current operator state is represented by the local read-only report and the
redacted ops summary.

- Escaped unread inbox check is currently represented as clear in the latest
  verified pass.
- Remaining work is intentionally labeled rather than invisible: GitHub,
  provider action, provider security, finance, subscriptions, payments,
  legal/waiting, LinkedIn, and business follow-up.
- Legal follow-up is not lost; it is represented as sent/waiting.

These counts are point-in-time. Any current-state claim must verify report
freshness through `generated_at`, `since`, `until_exclusive`, and
`freshness.status`.

### 2. Public Product Surface

`/app` remains the public product and safety-proof surface.

It demonstrates:

- protected-sender checks;
- dry-run preview;
- receipt-style proof;
- billing;
- MCP and ACP surfaces;
- the promise of safe cleanup without exposing private mailbox state.

### 3. Private Operator Surface

`/ops` is the private cockpit.

Implemented private contracts:

- `/v1/ops/summary` returns redacted `uma.ops.summary.v1`.
- `/v1/ops/history` returns bounded redacted history.
- `python cli.py ops-summary` exports the redacted summary locally.
- `python cli.py ops-refresh` writes `latest-summary.json`, bounded `history/`,
  and `index.json`.
- `python cli.py ops-refresh --run-mail-triage` can run the local read-only
  macOS Mail report producer first, then persist redacted summary and history.
- `python cli.py mail-history-export` writes private `uma.mail.history_export.v1`
  from local JSON, JSONL, mbox, EML, or EMLX sources and prints only a redacted
  receipt.
- `python cli.py mail-intel` emits redacted `uma.mail.intelligence.v1`.
- `python cli.py mail-intel --output` writes a precomputed redacted intelligence
  cache and prints only `uma.mail.intelligence.receipt.v1`.
- `python cli.py mail-action-plan` emits redacted `uma.mail.action_plan.v1`
  groups with priority, lane, approval type, automation boundary, and sample
  evidence ids, plus controlled provider/surface hint counts.
- `python cli.py mail-resolver-plan` emits redacted
  `uma.mail.resolver_plan.v1`, mapping action groups to official surfaces,
  blockers, safe local prep steps, controlled provider hints, and required
  proof.
- `python cli.py mail-provider-surface-plan` emits redacted
  `uma.provider.surface_plan.v1`, ranking controlled provider hints into the
  next official API/CLI/manual resolver frontier, existing UMA coverage, proof
  goals, blockers, and future intake detector candidates.
- `python cli.py mail-resolver-ledger` emits redacted
  `uma.mail.resolver_ledger.v1` by merging resolver-plan groups with local
  official-surface attestation receipts.
- `python cli.py mail-github-resolver` emits redacted
  `uma.github.resolver_snapshot.v1`, a bounded read-only GitHub CLI/API snapshot
  for GitHub resolver actions. It hashes repository references, omits raw
  notification/issue/PR titles and URLs, and returns receipt candidates without
  mutating GitHub or mail.
- `python cli.py mail-github-resolver-receipts` records those provider-read or
  blocker candidates into the redacted resolver ledger. Provider-backed read is
  tracked separately from provider-backed automation, which remains false.
- `python cli.py mail-followup-resolver` emits redacted
  `uma.followup.resolver_snapshot.v1`, reconciling mail/LinkedIn follow-up
  actions against local draft approval and delivery receipts.
- `python cli.py mail-followup-resolver-receipts` records resolver proof only
  when those approval or delivery receipts already exist. It does not read
  LinkedIn, create drafts, send, or mutate mail.
- `python cli.py mail-external-resolver` emits redacted
  `uma.external.resolver_snapshot.v1`, surfacing provider, security, billing,
  subscription, and legal official-surface lanes as planned or locally
  receipted work with controlled provider/surface hint counts.
- `python cli.py mail-external-resolver-receipts --attest-blockers` records
  local blocker attestations only when explicitly requested. It does not read
  providers, open portals, send, or mutate accounts.
- Provider hints are controlled routing slugs only. They never expose raw
  senders, domains, subjects, or bodies, and they are not proof that a provider
  portal/API was checked.
- `python cli.py mail-resolver-receipt` appends redacted
  `uma.mail.resolver_receipt.v1` proof-state receipts for action ids.
- `python cli.py mail-action-ledger` emits redacted
  `uma.mail.action_ledger.v1` by merging action groups with local proof
  receipts.
- `python cli.py mail-action-receipt` appends redacted
  `uma.mail.action_receipt.v1` status receipts for action ids.
- `python cli.py mail-evidence-review --ack-private` opens gated private
  `uma.mail.evidence_review.v1` for one evidence id.
- `python cli.py mail-draft-package --ack-private` builds private
  `uma.mail.draft_package.v1` candidates for draft-approval action ids.
- `python cli.py mail-draft-approval --ack-private` records redacted
  `uma.mail.draft_approval_receipt.v1` decisions for private draft candidates.
- `python cli.py mail-delivery-receipt --ack-private` records redacted
  `uma.mail.delivery_receipt.v1` delivery intent/status for approved drafts.
- MCP exposes `mail_history_export` and `mail_intelligence` for the same
  producer/consumer loop, plus `mail_action_plan` for next-action grouping,
  `mail_resolver_plan` for official-surface routing,
  `mail_provider_surface_plan` for provider/API/CLI resolver-frontier planning,
  `mail_resolver_ledger` / `mail_resolver_receipt` for local resolver proof
  state,
  `mail_github_resolver` for bounded read-only GitHub official-surface
  snapshots,
  `mail_followup_resolver` / `mail_followup_resolver_receipts` for mail and
  LinkedIn follow-up proof state from local approval/delivery receipts,
  `mail_external_resolver` / `mail_external_resolver_receipts` for provider,
  security, billing, subscription, and legal planned/blocker proof state,
  `mail_action_ledger` / `mail_action_receipt` for local proof state, and
  `mail_evidence_review`, `mail_draft_package`, `mail_draft_approval`, and
  `mail_delivery_receipt` for explicit private source review, approval-gated
  drafting, redacted approval receipts, and post-approval delivery intent.

The verified test baseline after the provider-surface plan layer landed is
`509 passed, 1 warning`.

## Core Product Model

UMA should be represented as three complementary products inside one system.

### Future Mail Triage

The system watches new mail and routes it into safe action states.

Primary jobs:

- prevent important mail from disappearing;
- separate action from noise;
- protect legal, financial, security, and account messages;
- draft replies only from verified facts;
- require approval before sends or risky mutations.

### Current Ops Cockpit

The system shows the truth of the current operating state.

Primary jobs:

- show active unread work;
- show waiting, blocked, closed, and review lanes;
- show what changed since the last refresh;
- show stale data as stale;
- keep action queues visible until resolved.

### Historical Mail Intelligence

The system mines past mail into structured memory and analytics.

Primary jobs:

- recover missed leads;
- reconstruct relationship history;
- build obligation and risk timelines;
- surface vendor and subscription leakage;
- map provider/security incidents;
- convert archive debt into follow-up candidates and business intelligence.

This is central, not adjacent. It turns UMA from email cleanup into a memory,
opportunity, and risk intelligence system.

## Gaps

The system is coherent but not yet ideal.

The current main gaps are:

- The raw report schema still comes from an external local `mail-triage`
  producer. UMA can orchestrate it, but does not fully own it yet.
- Action lanes still require human or provider-portal work for some outcomes,
  including bank, GitHub billing/security, Cloudflare, Google Cloud,
  subscriptions, account sessions, and legal review.
- The initial resolver-plan and resolver-receipt layers can now say which
  official surface and proof type each lane needs, then record local
  official-surface attestations. A first GitHub resolver snapshot now performs
  bounded read-only GitHub CLI/API checks for notifications, assigned issues,
  and open PR search. A first external resolver snapshot now keeps provider,
  security, billing, subscription, and legal lanes visible as planned or locally
  attested blocker proof. The provider-surface plan now ranks which official
  provider/API/CLI/manual resolver families should be built next. GitHub
  billing/security, LinkedIn, Gmail, Mail.app, Outlook, finance, legal, and
  cloud-provider provider-backed resolvers still need to land.
- `/ops` shows current redacted state and bounded history, but does not yet
  provide executive-grade trends, aging, ownership, blocker state, or
  "what changed since last refresh."
- Historical mail now has an initial private export, redacted intelligence
  pipeline, private review mode, resolver-plan layer, and resolver proof ledger,
  but real full-history runs, relationship graph, and provider-backed resolver
  execution still need to land.
- Warehouse, team-communication, BI, behavior analytics, and notebook sources
  remain optional/deferred.

## Operating Principles

- No browser dependency for mail operations.
- No blind sends.
- No raw private data in public product surfaces.
- No full local paths, senders, addresses, subjects, or bodies in redacted
  dashboard contracts.
- No hidden archive debt.
- No generic vector-store dump as the first historical intelligence move.
- Deterministic extraction and redacted provenance come first; embeddings can
  become a private assistive layer later.
- Every mutation requires an audit receipt.
- Every "nothing left behind" claim requires reproducible escaped-item queries.
- Every drafted reply requires source-backed fact checks.
- Every blocker remains visible until closed, intentionally ignored, or waiting
  with evidence.

## Target Architecture

The target architecture is a layered mail-operations OS.

```text
Mailbox sources
  -> UMA-native intake
  -> normalized threads and labels
  -> redacted ops summaries
  -> historical intelligence objects
  -> lane-specific resolvers
  -> approval and receipt engine
  -> public /app, private /ops, agent tools, and analytics exports
```

Primary source surfaces:

- Gmail;
- macOS Mail;
- IMAP;
- Outlook;
- all-mail and archive-equivalent scopes;
- LinkedIn messages and jobs;
- GitHub notifications, issues, billing, and security mail;
- calendar follow-ups;
- provider CLIs/APIs where official authenticated access exists;
- optional warehouse and BI layer.

## Workstreams

### 1. Internalize Intake

Goal: UMA owns mailbox scanning end to end.

Scope:

- vendor or port the local `mail-triage` producer into UMA;
- make Gmail, macOS Mail, all-mail, and archive scans first-class UMA commands;
- preserve read-only scan mode as the default;
- make scheduled and on-demand refresh update `/ops` every time;
- define the raw report schema under UMA version control;
- keep redacted summary/history separate from raw private reports.

Definition of done:

- UMA can produce the raw report and redacted summary without an external script;
- `ops-refresh --run-mail-triage` either becomes UMA-native or formally delegates
  to a vendored producer with tests;
- escaped-unread checks are reproducible from commands documented in the repo.

### 2. Close Current Action Loops

Goal: every active lane has a resolver workflow.

Lane-specific resolvers:

- GitHub: notifications, billing, security, pull requests, issues, and account
  alerts.
- LinkedIn: messages, jobs, recruiters, business development, and stale replies.
- Finance/payment: bank notices, failed payments, invoice-like mail, renewals,
  and payment verification.
- Legal: attorney/client communications, notices, waiting states, and approved
  reply drafting.
- Provider security: Cloudflare, Google Cloud, identity, sessions, tokens,
  OAuth grants, password resets, and account changes.
- Subscriptions: renewals, price changes, unused tools, cancellation candidates,
  and receipt tracking.
- Calendar: meeting follow-ups, unanswered asks, and commitments.

Each resolver must:

- classify;
- verify facts;
- draft action;
- require approval when needed;
- execute only through official authenticated paths;
- record the outcome;
- keep the item visible if blocked.

Definition of done:

- every lane has a documented resolver state machine;
- every resolver produces audit receipts;
- risky actions cannot bypass approval.

### 3. Prove Accuracy

Goal: UMA makes correctness auditable.

Scope:

- fact-check every reply against source messages, prior sends, docs, calendar,
  and known case/project state;
- distinguish observed facts, inferred facts, and missing facts;
- show stale, partial, and conflicted evidence explicitly;
- store redacted receipts for every mutation;
- support "why is this considered handled?" drilldowns.

Definition of done:

- no reply draft can be marked ready without evidence references;
- no mutation can complete without a receipt;
- no zero-escaped-work claim can be shown without the matching query evidence.

### 4. Build Historical Mail Intelligence

Goal: convert past mail into structured memory, opportunity, and risk
intelligence.

Scope:

- read-only historical scans, starting with bounded periods and expanding after
  validation;
- deterministic extraction into schemas;
- redacted summaries with private provenance IDs;
- private review mode for opening source evidence when explicitly needed;
- no sends, archive changes, or mailbox mutations during historical scans.

Pipeline:

```text
raw mail
  -> threads
  -> entities
  -> events
  -> opportunities
  -> risks
  -> timelines
  -> dashboards
  -> recommended actions
```

Core objects:

- Person;
- Organization;
- Thread;
- Opportunity;
- Obligation;
- Risk;
- Payment;
- Subscription;
- Account;
- Provider;
- Project;
- Follow-up;
- Evidence.

Planned schema contracts:

- `uma.mail.history_export.v1`;
- `uma.mail.history_export.receipt.v1`;
- `uma.mail.entity.v1`;
- `uma.mail.event.v1`;
- `uma.mail.opportunity.v1`;
- `uma.mail.risk.v1`;
- `uma.mail.timeline.v1`.

High-value detectors:

- missed lead detector;
- stale relationship detector;
- legal/financial obligation detector;
- security/account-change detector;
- subscription leakage detector;
- provider incident detector;
- project memory extractor;
- reply/draft stall detector.

Missed-lead scoring should consider:

- human inbound ask;
- recruiting, client, partnership, investor, vendor, or business-development
  signal;
- no visible reply;
- stale for configurable days;
- explicit money, job, company, urgency, or introduction signal;
- relationship strength and recency.

Definition of done:

- historical scans produce redacted entities, events, opportunities, risks, and
  timelines;
- missed-lead candidates include evidence and confidence;
- dashboards can show value without leaking raw mail;
- private review mode can trace an object back to source evidence.

### 5. Make The Dashboard Executive-Grade

Goal: `/ops` becomes an operating cockpit, not just a snapshot viewer.

Add:

- trends;
- aging;
- owner;
- blocker state;
- severity;
- next action;
- last verified time;
- "what changed since last refresh";
- safe-to-automate versus requires portal or human approval;
- current, waiting, blocked, closed, ignored, and stale states;
- historical intelligence sections for missed leads, obligations, spend,
  security, relationships, and project memory.

Definition of done:

- an operator can tell what changed, what matters, what is blocked, and what to
  do next from one screen;
- every dashboard number maps to a schema field or documented derived metric;
- stale data cannot look current.

### 6. Productize The Ideal

Goal: keep the product promise and private operations aligned.

Public `/app`:

- sells the promise;
- shows protected inbox audit;
- demonstrates dry-run safety;
- explains receipts and restraint;
- never exposes real mailbox state.

Private `/ops`:

- operates the truth;
- tracks work until resolved;
- shows evidence, blockers, and change history;
- supports historical intelligence review.

Receipts and compliance:

- prove what happened;
- prove what did not happen;
- show why automation stopped;
- preserve restraint as a product feature.

Agent tools:

- let other agents safely query UMA;
- enforce guardrails through APIs rather than convention;
- prevent bypassing protected-sender, approval, and receipt boundaries.

Definition of done:

- product copy, dashboard behavior, API contracts, and tests all describe the
  same system;
- agents can use UMA without raw private-data leakage or unsafe mutation paths.

## Historical Intelligence Dashboard

The historical dashboard should eventually contain:

- missed leads;
- follow-up candidates;
- warm relationships gone cold;
- recurring subscriptions and renewal risks;
- failed payments and invoice-like obligations;
- legal and finance obligations;
- security/account timeline;
- provider incident history;
- project and product memory;
- unanswered asks and stalled drafts;
- relationship graph.

The dashboard should separate:

- observed facts;
- inferred opportunities;
- unresolved risks;
- safe FYI;
- needs portal verification;
- needs human approval;
- blocked by missing evidence.

## KPI Framework

Operator KPIs:

- escaped unread count;
- active unread action load;
- waiting count;
- blocked count;
- closed count;
- stale report age;
- time since last verified refresh;
- unresolved severe risks;
- action aging by lane;
- changed items since last refresh.

Historical intelligence KPIs:

- missed leads found;
- high-confidence follow-up candidates;
- stale opportunities by age;
- unresolved obligations;
- recurring spend candidates;
- renewal or cancellation candidates;
- security/account events needing review;
- cold relationships worth reviving;
- unresolved project/provider incidents.

Safety KPIs:

- drafts requiring approval;
- actions blocked by protected-sender or risk gates;
- receipts generated;
- attempted mutations without approval, which should remain zero;
- private fields leaked to redacted payloads, which should remain zero.

Product KPIs:

- audits run;
- cleanup previews generated;
- receipts viewed;
- private ops refreshes completed;
- historical intelligence scans completed;
- follow-up drafts accepted;
- opportunities recovered.

## Milestones

### Phase 0: Baseline Already Achieved

Status: implemented before this master plan.

- Public `/app` product/safety proof exists.
- Private `/ops` cockpit exists.
- `uma.ops.summary.v1` exists.
- Bounded redacted history exists.
- `ops-refresh --run-mail-triage` can orchestrate the local read-only producer.
- May 2026-to-current triage has a represented state.
- Full tests passed at the current baseline.

### Phase 1: Canonical Master Plan And Contracts

Goal: make the roadmap explicit enough to build against.

Deliverables:

- this master plan;
- historical intelligence schema docs;
- resolver state-machine docs;
- dashboard metric map;
- updated semantic layer/source inventory after new contracts land.

### Phase 2: UMA-Native Intake

Goal: remove the split between UMA and the external report producer.

Deliverables:

- UMA-owned raw report schema;
- Gmail/macOS Mail/all-mail/archive scan command;
- private historical export command for JSON, JSONL, mbox, EML, and EMLX;
- reproducible escaped-item checks;
- test fixtures for all major lane types;
- scheduled/on-demand refresh path.

### Phase 3: Historical Intelligence MVP

Goal: mine past mail into structured, redacted business value.

Deliverables:

- historical scan command;
- entity/event/opportunity/risk/timeline schemas;
- missed-lead detector;
- risk and obligation detector;
- subscription/spend detector;
- redacted historical dashboard section or private `/intel` route;
- source-backed evidence IDs.

### Phase 4: Resolver Loops

Goal: move from visibility to closure.

Deliverables:

- GitHub resolver;
- LinkedIn resolver;
- finance/payment resolver;
- legal resolver;
- provider security resolver;
- subscription resolver;
- calendar follow-up resolver;
- approval and receipt integration for every risky action.

### Phase 5: Executive-Grade Cockpit

Goal: make `/ops` the daily operating surface.

Deliverables:

- trends;
- aging;
- owners;
- blockers;
- severity;
- next action;
- changed-since-last-refresh;
- safe-to-automate versus needs-approval segmentation;
- current plus historical intelligence rollups.

### Phase 6: Expanded Analytics And Integrations

Goal: support broader product, company, and data-analytics value.

Deliverables:

- optional warehouse export;
- BI-ready tables;
- team-decision source;
- behavior analytics;
- notebook or research workflow;
- agent-safe external API contracts.

## First Build Tranche

The next large autonomous build should be:

Build UMA Historical Intelligence Layer: read-only processing of past mail into
redacted entities, events, missed opportunities, risks, and analytics-ready
dashboard data.

Initial implementation scope:

- add `uma.mail.history_export.v1` as the private intake contract and
  `uma.mail.history_export.receipt.v1` as the safe command/tool output;
- add schema docs for `uma.mail.entity.v1`, `uma.mail.event.v1`,
  `uma.mail.opportunity.v1`, `uma.mail.risk.v1`, and
  `uma.mail.timeline.v1`;
- add a read-only historical export producer for local JSON, JSONL, mbox, EML,
  and EMLX sources;
- add a core historical intelligence module using synthetic fixtures first;
- add CLI commands for private historical export and redacted historical
  intelligence;
- add missed-lead, obligation/risk, subscription/spend, and security/account
  detectors;
- add tests proving redaction and deterministic extraction;
- add a private dashboard section or `/intel` route;
- update the semantic layer after the contracts are real.

The first tranche should not require mailbox mutation, browser automation, or a
generic vector store.

Initial implementation status:

- Added `uma.mail.history_export.v1` as the private historical mail intake
  contract.
- Added `uma.mail.history_export.receipt.v1` as the safe stdout/MCP receipt.
- Added `core.mail_history_export` with JSON, JSONL, mbox, EML, and EMLX
  normalization, date filtering, outbound self-address hints, body bounds, and
  no full source-path copying.
- Added `uma.mail.intelligence.v1` as the redacted Historical Mail Intelligence
  contract.
- Added object schema markers for entities, events, opportunities, risks, and
  timelines.
- Added controlled provider/surface hint slugs across intelligence, action
  plans, resolver plans, and external resolver snapshots. These hints support
  routing and analytics only; they are not provider-backed proof.
- Added `python cli.py mail-history-export` as the private intake producer.
- Added `python cli.py mail-intel` as the redacted intelligence consumer.
- Added `python cli.py mail-intel --output` as the redacted intelligence cache
  producer for `/ops`.
- Added `python cli.py mail-action-plan` as the approval-aware next-action
  reducer.
- Added `python cli.py mail-provider-surface-plan` and
  `uma.provider.surface_plan.v1` as the redacted provider resolver frontier
  over controlled provider hints. It shows existing UMA coverage, proof goals,
  blockers, next build steps, and future intake detector candidates while
  performing 0 provider reads, 0 portal automation, 0 sends, and 0 mailbox
  mutations.
- Added `python cli.py mail-action-ledger` as the redacted status/proof merge
  over action groups and local receipts.
- Added `python cli.py mail-action-receipt` as the local redacted receipt
  writer for action statuses.
- Added `python cli.py mail-evidence-review --ack-private` as the private source
  evidence review command.
- Added `python cli.py mail-draft-package --ack-private` as the private
  approval-gated draft candidate builder.
- Added `python cli.py mail-draft-approval --ack-private` as the redacted local
  draft approval receipt writer.
- Added `python cli.py mail-delivery-ledger` and
  `python cli.py mail-delivery-receipt --ack-private` as the redacted local
  post-approval delivery intent/status layer.
- Added `python cli.py mail-github-resolver` and
  `uma.github.resolver_snapshot.v1` as the first provider-specific
  official-surface reader. It uses bounded read-only GitHub CLI/API checks,
  hashes repository references, omits raw GitHub output, and creates resolver
  receipt candidates without mutating GitHub or mail.
- Added `python cli.py mail-github-resolver-receipts`,
  `POST /v1/ops/github-resolver-receipts`, and MCP
  `mail_github_resolver_receipts` to durably record GitHub provider-read or
  blocker candidates into the resolver ledger without GitHub, mailbox, portal,
  draft, or send mutations.
- Added `python cli.py mail-followup-resolver`,
  `python cli.py mail-followup-resolver-receipts`,
  `GET/POST /v1/ops/followup-resolver[-receipts]`, and MCP
  `mail_followup_resolver` / `mail_followup_resolver_receipts` so mail/LinkedIn
  follow-up work is visible and can record resolver proof from existing local
  approval or delivery receipts without reading LinkedIn, creating drafts,
  sending, or mutating mail.
- Added `GET /v1/ops/intelligence` as the private API route.
- Added `GET /v1/ops/action-plan` as the private API route for redacted action
  clusters.
- Added `GET /v1/ops/action-ledger` as the private API route for redacted action
  status and local proof receipts.
- Added `POST /v1/ops/action-receipts` as the token-required route for appending
  local redacted proof receipts.
- Added `GET /v1/ops/evidence/{evidence_id}?ack_private=true` as the gated
  private source-evidence review route. It requires `UMA_OPS_TOKEN`.
- Added `GET /v1/ops/draft-package/{action_id}?ack_private=true` as the gated
  private draft-package route. It requires `UMA_OPS_TOKEN`.
- Added `GET/POST /v1/ops/draft-approvals/{action_id}` as the gated local draft
  approval ledger and receipt routes. They require `UMA_OPS_TOKEN`.
- Added `GET/POST /v1/ops/delivery/{action_id}` as the gated local delivery
  ledger and receipt routes. They require `UMA_OPS_TOKEN` and still perform 0
  provider draft creation and 0 sends.
- Added `UMA_HISTORICAL_INTELLIGENCE_PATH` so `/v1/ops/intelligence` can serve a
  precomputed redacted cache instead of recomputing large histories on every
  request.
- Added MCP `mail_history_export` as a non-destructive local file producer that
  returns only a redacted receipt.
- Added MCP `mail_intelligence` as a read-only agent tool.
- Added MCP `mail_action_plan` as a read-only agent tool.
- Added MCP `mail_provider_surface_plan` as a read-only provider resolver
  frontier tool.
- Added MCP `mail_action_ledger` as a read-only agent tool.
- Added MCP `mail_action_receipt` as a non-destructive local receipt writer.
- Added MCP `mail_evidence_review` as a read-only but private-data-returning
  tool that requires `ack_private=True`.
- Added MCP `mail_draft_package` as a read-only but private-data-returning tool
  that requires `ack_private=True` and still grants no send authority.
- Added MCP `mail_draft_approvals` / `mail_draft_approval` as redacted local
  approval-status and approval-receipt tools.
- Added MCP `mail_delivery_ledger` / `mail_delivery_receipt` as redacted local
  post-approval delivery-status and delivery-receipt tools.
- Added MCP `mail_github_resolver` as a read-only GitHub resolver snapshot
  tool.
- Added optional `/ops` historical intelligence cards.
- Added `/ops` action-plan cards so the cockpit shows ranked, approval-aware
  next actions rather than only candidate counts.
- Added `/ops` action-ledger cards and receipt controls so planned actions can
  remain visible as open, waiting, blocked, resolved, or ignored with local
  proof receipts.
- Added `/ops` private evidence lookup so an operator can open a bounded source
  message for a specific evidence id before drafting or resolver work.
- Added `/ops` private draft-package controls so a draft-approval action id can
  produce source-backed draft candidates for explicit approval.
- Added `/ops` draft approval controls so a draft candidate can be marked
  approved, rejected, or revise with a redacted local receipt.
- Added `/ops` delivery controls so an approved draft can be marked as provider
  draft requested, externally recorded, send requested, blocked, canceled, or
  sent recorded without UMA itself creating a provider draft or sending.
- Added `/ops` GitHub resolver cards so GitHub action groups show bounded
  official read status, receipt candidates, and zero mutation authority.
- Added synthetic fixtures and tests proving historical export normalization,
  receipt redaction, missed-lead/risk detection, intelligence redaction, API
  auth, CLI behavior, MCP registration, and `/ops` wiring.

Live local run status:

- `mail-history-export` processed 41,415 local Mail messages for the
  2024-01-01 through 2026-06-16 window into a private local export.
- `mail-intel --output` produced a redacted intelligence cache from that export.
- First-pass detector healing moved missed-lead candidates out of GitHub,
  provider, legal, finance, security, and subscription lanes so those stay risk
  findings instead of opportunity findings.
- Current redacted aggregate from the real run: 759 missed-lead candidates,
  31,652 risk candidates, 1,283 findings not represented in current ops lanes,
  and 0 mailbox mutations.
- Controlled provider/surface hints are present in the redacted real run.
  External resolver currently surfaces 8,050 planned external findings with top
  hint counts led by `google_workspace`, `paypal`, `linkedin`, `openai`,
  `apple`, `anthropic`, `stripe`, `microsoft`, `cloudflare`, and `github`.
  These remain routing hints only: provider-backed read = 0, provider-backed
  automation = 0, sends = 0, mailbox mutations = 0, portal mutations = 0.
- `mail-provider-surface-plan` currently ranks 20 provider surfaces from 30,393
  controlled provider hints. The top families are `github`, `anthropic`,
  `google_workspace`, `openai`, `linkedin`, `paypal`, `cloudflare`, `apple`,
  `stripe`, and `microsoft`. Only the GitHub family has an existing
  provider-read resolver; the remaining 19 are planned provider resolvers. The
  plan itself still performs 0 provider reads, 0 provider-backed automation, 0
  sends, 0 mailbox mutations, and 0 portal mutations.
- `mail-action-plan` now turns those candidates into redacted priority groups
  with send allowed = 0 and mailbox mutations allowed = 0.
- `mail-action-ledger` now keeps those priority groups visible until local
  receipts mark them waiting, blocked, resolved, ignored, or reopened.
- `mail-evidence-review` now provides the fact-check gate from a redacted
  evidence id back to one bounded raw source message, while still allowing 0
  sends and 0 mailbox mutations.
- `mail-draft-package` now turns a verified missed-lead action id into private
  draft candidates with source-backed fact checklists, while still allowing 0
  sends and 0 mailbox mutations.
- `mail-draft-approval` now records local approval decisions for those draft
  candidates, while still creating 0 provider drafts and 0 sends.
- `mail-delivery-receipt` now records post-approval delivery intent/status for
  approved drafts, while still creating 0 provider drafts and 0 sends from UMA.
  `provider_draft_recorded` and `sent_recorded` remain local operator
  attestations until an official provider resolver writes external proof.
- The counts are candidate-mining outputs, not final human-verified closure
  claims. Private review mode and resolver workflows are still required before
  sending replies or treating candidates as resolved.

## Completion Standard

UMA reaches the intended form when:

- future mail is triaged safely;
- current ops are visible in `/ops`;
- historical mail becomes structured memory and analytics;
- replies and actions are drafted from verified facts;
- risky operations require explicit approval;
- every mutation creates a receipt;
- every dashboard claim is source-backed;
- every "nothing left behind" claim is reproducible;
- stale or partial evidence is labeled as such;
- public product surfaces remain privacy-safe;
- agent integrations cannot bypass guardrails.

That is the endzone: not inbox zero, but a trusted mail-operations OS that
keeps work, risk, opportunity, and proof in view until each item is actually
handled.
