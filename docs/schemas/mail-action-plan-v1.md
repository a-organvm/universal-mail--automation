# UMA Mail Action Plan v1

`uma.mail.action_plan.v1` is the redacted, approval-aware next-action contract
built from `uma.mail.intelligence.v1`.

It does not read raw mail. It groups and ranks redacted findings into operator
work clusters with priority, approval type, automation boundary, lane, evidence
ids, and next action.

## Entry Points

- Core: `core.mail_action_plan.build_action_plan(intelligence)`
- CLI: `python cli.py mail-action-plan --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- API: `GET /v1/ops/action-plan`
- MCP: `mail_action_plan(intelligence_path, max_items=40)`
- UI: `/ops` Action Plan panel
- Follow-on proof layer: `uma.mail.action_ledger.v1`
- Follow-on draft layer: `uma.mail.draft_package.v1`

## Output Shape

```json
{
  "schema": "uma.mail.action_plan.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "mailbox_mutations": false,
    "sends": false,
    "archive_changes": false,
    "approval_required_before_send": true,
    "official_surface_required_for_portal_actions": true
  },
  "kpis": {
    "action_groups": 11,
    "findings": 32411,
    "p0": 8,
    "p1": 2,
    "approval_required": 32411,
    "portal_verification": 27366,
    "draft_approval": 759,
    "human_legal_review": 1391,
    "not_represented_in_current_ops": 1283,
    "provider_hint_counts": {"github": 509},
    "mailbox_mutations_allowed": 0,
    "send_allowed": 0
  },
  "lanes": [],
  "items": []
}
```

## Item Shape

Each `items[]` row is `uma.mail.action_item.v1`:

| Field | Meaning |
| --- | --- |
| `priority` | `p0`, `p1`, `p2`, or `p3` |
| `priority_score` | Deterministic score from severity, lane type, visibility, blocker, and count |
| `kind` | Finding kind, such as `missed_lead`, `legal_obligation`, or `security_or_account` |
| `action_type` | Operator workflow type |
| `recommended_lane` | Current `/ops` lane to use |
| `ops_lane_status` | Whether the finding is represented in current ops |
| `approval_type` | `draft_approval`, `human_legal_review`, `portal_verification`, `decision`, or `external_reconcile` |
| `automation_boundary` | What automation may safely do before approval |
| `finding_count` | Number of redacted findings grouped into the action |
| `sample_evidence_ids` | Redacted evidence ids only |
| `provider_hints` | Controlled provider/surface slugs inferred from grouped findings |
| `provider_hint_counts` | Counts by controlled provider/surface slug for the group |
| `next_action` | Operator-facing next step |

## Safety Boundary

The action plan never authorizes sends or mailbox mutations:

```json
{
  "mailbox_mutations_allowed": 0,
  "send_allowed": 0
}
```

Missed leads can be drafted, but not sent. Legal findings require human/legal
review. Security, provider, payment, and billing findings require official
provider/account/billing surfaces. Subscription findings require a keep/cancel/
downgrade decision.

## Privacy Boundary

The action plan is redacted. It must not include raw sender names, email
addresses, subjects, snippets, bodies, raw headers, or full local paths.
Provider hints are controlled slugs only; they must not include raw domains or
arbitrary private vendor names.

## Follow-On Ledger

Use [mail-action-ledger-v1.md](mail-action-ledger-v1.md) to track whether each
action group is open, waiting, blocked, resolved, ignored, or reopened with
local redacted receipts. The action plan ranks work; the ledger records local
status proof.

Use [mail-draft-package-v1.md](mail-draft-package-v1.md) to build private,
approval-only draft candidates for `missed_lead` groups with `draft_approval`.
