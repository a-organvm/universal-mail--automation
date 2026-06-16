# Operator Dashboard Canonicalization - 2026-06-15

## Decision

UMA now has a distinct private operator surface for mail-operations state:

- `/app` remains the public product and safety-proof dashboard.
- `/ops` is the private operator control tower.
- `/v1/ops/summary` is the redacted HTTP contract behind `/ops`.
- `python cli.py ops-summary` is the serverless/local export path.
- `python cli.py ops-refresh` is the durable local refresh path for redacted
  latest-summary and bounded history.
- `core.ops_summary.build_ops_snapshot` is the canonical normalization layer.

This avoids mixing private mailbox state into the public product demo while still
making the May 2026-to-current triage work visible as a product-grade operating
surface.

## Implemented

- Added `core/ops_summary.py` with the `uma.ops.summary.v1` redacted contract.
- Added `api/ops.py` and mounted `GET /v1/ops/summary`.
- Added `GET /v1/ops/history` for redacted bounded history.
- Added `GET /ops` to serve the private operator dashboard.
- Added `cli.py ops-summary` for local automation and Data Analytics handoff.
- Added `cli.py ops-refresh` to persist `latest-summary.json`, `history/`, and
  `index.json` under user-local state.
- Added optional `ops-refresh --run-mail-triage` support for the local read-only
  macOS Mail report producer.
- Added freshness metadata so stale reports cannot masquerade as current state.
- Added synthetic fixture tests for redaction, API auth, CLI behavior, and UI serving.
- Added `docs/schemas/ops-summary-v1.md`.

## Privacy Rules

The operator payload omits raw senders, addresses, subjects, bodies, and full
local paths. Tests use synthetic private strings to prove those fields do not
leave the core/API/CLI contract.

## Current Mail-Ops Representation

The dashboard shows:

- Escaped unread inbox count from `latest-actions.md`
- Inbox, all-mail, archive, and scoped coverage counts from `latest.json`
- Active unread action load from action/verify/decision triage labels
- Waiting and closed lane counts
- Redacted bucket samples for operator context
- Snapshot freshness and recent redacted history

The live mailbox remains the truth for current state. The report fields
`generated_at`, `since`, and `until_exclusive` must be checked before treating a
snapshot as current.

## Known Next Phases

- Fully internalize raw ops input report generation. `ops-refresh --run-mail-triage`
  now owns orchestration around the local read-only producer, but the raw report
  schema still comes from that producer.
- Add a warehouse or durable local history if trend analysis becomes required.
- Add a team-decision source if operational lane changes need Slack/Teams-style
  provenance.
- Keep `/ops` private; do not publish real mailbox summaries to the public share
  demo.
