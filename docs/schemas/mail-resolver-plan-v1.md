# UMA Mail Resolver Plan v1

`uma.mail.resolver_plan.v1` is the redacted official-surface routing contract
built from `uma.mail.action_plan.v1`.

It does not read raw mail, open provider portals, send mail, create provider
drafts, or mutate any mailbox. It maps each action group to the surface that
must verify or resolve it, the safe local preparation steps, the required proof,
and the current blocker.

## Entry Points

- Core: `core.mail_resolver_plan.build_resolver_plan(action_plan)`
- CLI: `python cli.py mail-resolver-plan --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- API: `GET /v1/ops/resolver-plan`
- MCP: `mail_resolver_plan(intelligence_path, max_items=100)`
- UI: `/ops` Resolver Plan panel
- Input: `uma.mail.action_plan.v1`
- Follow-on proof layers: `uma.mail.action_ledger.v1`, `uma.mail.draft_approval_ledger.v1`, and `uma.mail.delivery_ledger.v1`

## Output Shape

```json
{
  "schema": "uma.mail.resolver_plan.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "mailbox_mutations": false,
    "sends": false,
    "portal_mutations": false,
    "official_surface_plan_only": true
  },
  "kpis": {
    "resolver_groups": 5,
    "findings": 5,
    "official_surface_required": 5,
    "can_prepare_locally": 3,
    "github_reconcile": 1,
    "mail_or_linkedin_follow_up": 1,
    "security_verify": 1,
    "legal_review": 1,
    "subscription_decision": 1,
    "provider_hint_counts": {"github": 1},
    "mailbox_mutations_allowed": 0,
    "send_allowed": 0,
    "portal_mutations_allowed": 0
  },
  "answers": {},
  "items": []
}
```

## Item Shape

Each `items[]` row is `uma.mail.resolver_item.v1`:

| Field | Meaning |
| --- | --- |
| `action_id` | Redacted action-plan id |
| `kind` | Finding kind such as `missed_lead`, `github_work`, or `security_or_account` |
| `priority` | `p0`, `p1`, `p2`, or `p3` from the action plan |
| `recommended_lane` | `/ops` lane where the item should stay visible |
| `approval_type` | Approval gate from the action plan |
| `automation_boundary` | Safe automation boundary before action |
| `resolver_type` | Lane-specific resolver family |
| `official_surface` | Machine-friendly official surface id |
| `official_surface_label` | Operator-facing surface description |
| `supported_surfaces` | Candidate official provider, CLI, API, or manual surfaces |
| `provider_hints` | Controlled provider/surface slugs carried from historical intelligence |
| `provider_hint_counts` | Counts by controlled provider/surface slug for the resolver group |
| `safe_preapproval_steps` | Local read-only or receipt steps that may happen before official resolution |
| `required_proof` | Proof types needed before closure |
| `current_blocker` | Why UMA cannot honestly call the item resolved yet |
| `next_step` | Redacted operator next action |

`max_items` limits the returned `items[]` rows for API, CLI, and MCP display.
Resolver KPIs should still be computed from the full action plan so a small
display limit does not hide lower-ranked lanes such as GitHub, subscription, or
billing work.

## Resolver Families

- `reply_follow_up`: mail provider or LinkedIn official inbox; draft and approval
  receipts can be prepared locally, but final delivery still needs proof.
- `github_reconcile`: GitHub API, CLI, issues, PRs, billing, or security state.
- `account_security_verification`: official provider security dashboard, API, or CLI.
- `payment_or_billing_verification`: bank, card, billing, or vendor portal.
- `provider_status_reconcile`: provider dashboard, status page, API, or CLI.
- `subscription_decision`: vendor subscription portal plus operator keep/cancel/
  downgrade decision.
- `legal_review`: counsel or legal review surface.
- `human_review`: fallback private evidence review and local receipt state.

## Safety Boundary

The resolver plan is a plan only:

```json
{
  "mailbox_mutations_allowed": 0,
  "send_allowed": 0,
  "portal_mutations_allowed": 0
}
```

It may say that GitHub, LinkedIn, a bank, a vendor portal, or a legal surface is
required. That is not proof that the external state changed. Closure still needs
an action receipt, draft approval receipt, delivery receipt, or future
provider-backed resolver receipt as appropriate.

## Privacy Boundary

The resolver plan is redacted. It must not include raw sender names, email
addresses, subjects, snippets, bodies, raw headers, full local paths, or raw
external provider state. Provider hints are controlled slugs only and must not
be treated as proof that a provider surface was checked.
