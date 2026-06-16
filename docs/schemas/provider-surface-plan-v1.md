# Provider Surface Plan v1

`uma.provider.surface_plan.v1` ranks controlled provider/surface hint slugs from
the resolver plan into a provider resolver frontier.

It answers:

- which official provider surfaces appear most often in historical/current work;
- which UMA resolver already exists;
- which resolver should be built next;
- what proof each provider resolver must eventually produce;
- what remains blocked by official auth, API, CLI, or manual review.

## Producers

- CLI: `python cli.py mail-provider-surface-plan --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- API: `GET /v1/ops/provider-surface-plan`
- MCP: `mail_provider_surface_plan(intelligence_path, max_items=20)`

## Safety

This is a plan-only redacted contract.

- No provider reads.
- No provider-backed automation.
- No portal/account mutations.
- No mailbox mutations.
- No sends.
- No raw provider state.
- No raw senders, addresses, subjects, bodies, snippets, raw headers, or full
  local paths.

Provider names are controlled slugs carried from `provider_hints`; they are not
raw domains and not proof that the provider was checked.

## Top-Level Shape

```json
{
  "schema": "uma.provider.surface_plan.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "provider_backed_read": false,
    "provider_backed_automation": false,
    "mailbox_mutations": false,
    "sends": false,
    "portal_mutations": false,
    "plan_only": true
  },
  "kpis": {
    "provider_surfaces": 3,
    "provider_hint_total": 12,
    "provider_backed_read_resolvers_available": 1,
    "planned_provider_resolvers": 2,
    "future_intake_detector_candidates": 3,
    "provider_backed_automation": 0,
    "mailbox_mutations_allowed": 0,
    "send_allowed": 0,
    "portal_mutations_allowed": 0
  },
  "items": []
}
```

## Item Shape

Each `uma.provider.surface_item.v1` item includes:

| Field | Meaning |
| --- | --- |
| `provider` | Controlled provider/surface slug |
| `title` | Operator-facing provider label |
| `priority_score` | Ranking score from hint count, related findings, p0 presence, and existing provider-read support |
| `hint_count` | Count of controlled provider hints across resolver groups |
| `related_findings` | Resolver-group finding count; overlap is allowed because one group can contain multiple provider hints |
| `resolver_type_counts` | Resolver families associated with this provider slug |
| `official_surfaces` | Official API/CLI/manual surfaces that may verify the provider state |
| `required_proof` | Proof types inherited from resolver groups |
| `existing_uma_surfaces` | UMA commands/tools already relevant to this provider |
| `coverage_state` | Current support level, such as `partial_provider_read_available` or `planned_only` |
| `resolver_candidate` | Candidate resolver family to build next |
| `next_build_step` | Specific next build step |
| `proof_goal` | Proof type the future resolver should produce |
| `blocked_by` | Why UMA cannot yet claim provider proof |

## Interpretation

Use this contract to prioritize future resolver work and future intake
detectors. Do not use it as closure evidence. Closure still requires resolver
receipts, provider-backed read proof where implemented, delivery receipts, or
human/operator attestations depending on the lane.
