# UMA Mail Draft Approval v1

`uma.mail.draft_approval_ledger.v1` is the redacted local approval state for
private draft packages. `uma.mail.draft_approval_receipt.v1` is the append-only
receipt for one draft decision.

This layer records operator approval. It does not send mail, create provider
drafts, archive, label, mark read, or mutate the mailbox.

## Entry Points

- Core ledger: `core.mail_draft_approval.build_draft_approval_ledger(...)`
- Core receipt: `core.mail_draft_approval.build_draft_approval_receipt(...)`
- CLI ledger: `python cli.py mail-draft-approvals --intelligence ~/System/Reports/mail-history/latest-intelligence.json --history ~/System/Reports/mail-history/latest.json --action-id action_... --ack-private`
- CLI receipt: `python cli.py mail-draft-approval --intelligence ~/System/Reports/mail-history/latest-intelligence.json --history ~/System/Reports/mail-history/latest.json --action-id action_... --draft-id draft_... --decision approved --reason-code ready_to_send --ack-private`
- API ledger: `GET /v1/ops/draft-approvals/{action_id}?ack_private=true`
- API receipt: `POST /v1/ops/draft-approvals/{action_id}`
- MCP: `mail_draft_approvals(...)` and `mail_draft_approval(...)`
- UI: `/ops` Private Draft Package approval controls

## Receipt File

Configure the JSONL file with `UMA_MAIL_DRAFT_APPROVAL_PATH`; if unset, API/CLI
use user-local state.

Each line is redacted:

```json
{
  "schema": "uma.mail.draft_approval_receipt.v1",
  "status": "recorded",
  "receipt_id": "draftapproval_...",
  "created_at": "2026-06-15T20:00:00Z",
  "draft_id": "draft_...",
  "action_id": "action_...",
  "evidence_id": "ev_...",
  "decision": "approved",
  "reason_code": "ready_to_send",
  "safety": {
    "send_allowed": false,
    "mailbox_mutations_allowed": false,
    "provider_draft_created": false,
    "approval_does_not_send": true
  }
}
```

Allowed decisions are `approved`, `rejected`, and `revise`.

Allowed reason codes are `ready_to_send`, `needs_edit`, `fact_issue`,
`wrong_recipient`, `stale_context`, `legal_review`, `duplicate`, and
`not_actionable`.

## Privacy Boundary

Approval receipts and ledgers are redacted. They must not contain recipient
names, email addresses, subjects, snippets, draft bodies, raw headers, full local
paths, or freeform private notes.

## Safety Boundary

Approval is not sending. An `approved` decision means a later, separate provider
draft or send workflow may be considered, but only after its own confirmation
and receipt.
