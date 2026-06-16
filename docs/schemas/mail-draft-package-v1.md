# UMA Mail Draft Package v1

`uma.mail.draft_package.v1` is the gated private draft contract. It converts a
redacted `draft_approval` action id plus private source evidence into
approval-gated draft candidates.

It does not send mail. It does not create provider drafts. It does not archive,
label, mark read, or mutate the mailbox.

## Entry Points

- Core: `core.mail_draft_package.build_draft_package(action_plan, history_path, action_id, ack_private=True)`
- CLI: `python cli.py mail-draft-package --intelligence ~/System/Reports/mail-history/latest-intelligence.json --history ~/System/Reports/mail-history/latest.json --action-id action_... --ack-private`
- API: `GET /v1/ops/draft-package/{action_id}?ack_private=true`
- MCP: `mail_draft_package(intelligence_path, history_path, action_id, ack_private=True)`
- UI: `/ops` Private Draft Package panel

## Gate

Draft packages require explicit acknowledgement because they can contain private
recipient names, addresses, subjects, fact checklists, and draft body text.

- CLI requires `--ack-private`.
- API requires `UMA_OPS_TOKEN`, bearer auth, and `ack_private=true`.
- MCP requires `ack_private=True`.

## Output

```json
{
  "schema": "uma.mail.draft_package.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "private_review": true,
    "draft_only": true,
    "mailbox_mutations": false,
    "sends": false,
    "approval_required_before_send": true
  },
  "safety": {
    "send_allowed": false,
    "mailbox_mutations_allowed": false,
    "draft_requires_approval": true
  },
  "drafts": [
    {
      "schema": "uma.mail.draft_candidate.v1",
      "draft_id": "draft_...",
      "action_id": "action_...",
      "evidence_id": "ev_...",
      "to": {
        "name": "Private Person",
        "address": "person@example.test"
      },
      "subject": "Re: Private subject",
      "body": "Private draft body",
      "fact_checklist": [],
      "approval": {
        "required": true,
        "ready_to_send": false,
        "send_allowed": false
      }
    }
  ]
}
```

## Scope

The first implementation supports `missed_lead` action groups requiring
`draft_approval`. Legal, provider, payment, security, GitHub, and subscription
actions require their own resolver workflows and official-surface checks before
drafting or action.

## Privacy Boundary

The draft package is private, not dashboard-safe. It may include private mail
fields and draft text. Redacted dashboards should show only counts, action ids,
draft ids, and approval status unless the operator explicitly opens private
review.

## Safety Boundary

Every draft candidate is `ready_to_send=false` and `send_allowed=false`.
Approval and a later sender-specific receipt are required before any future send
workflow may claim completion.
