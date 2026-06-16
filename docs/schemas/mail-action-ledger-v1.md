# UMA Mail Action Ledger v1

`uma.mail.action_ledger.v1` is the redacted status and proof layer over
`uma.mail.action_plan.v1`. It keeps planned action groups visible until a local
operator receipt records them as waiting, blocked, resolved, ignored, or
reopened.

It is not a mailbox mutation command and not proof that an external provider,
portal, or recipient changed state. It proves that UMA recorded a local
operator outcome against a redacted action id.

## Entry Points

- Core: `core.mail_action_ledger.build_action_ledger(action_plan, receipt_path=...)`
- Receipt writer: `core.mail_action_ledger.build_action_receipt(...)`
- CLI: `python cli.py mail-action-ledger --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- CLI receipt: `python cli.py mail-action-receipt --intelligence ~/System/Reports/mail-history/latest-intelligence.json --action-id action_... --status waiting --reason-code awaiting_reply`
- API: `GET /v1/ops/action-ledger`
- API receipt: `POST /v1/ops/action-receipts`
- MCP: `mail_action_ledger(...)` and `mail_action_receipt(...)`
- UI: `/ops` Action Ledger panel

## Receipt File

The receipt ledger is JSONL. Configure it with `UMA_MAIL_ACTION_LEDGER_PATH`; if
unset, API/CLI use user-local state.

Each line is `uma.mail.action_receipt.v1`:

```json
{
  "schema": "uma.mail.action_receipt.v1",
  "status": "recorded",
  "receipt_id": "receipt_...",
  "created_at": "2026-06-15T20:00:00Z",
  "action_id": "action_...",
  "action_status": "waiting",
  "reason_code": "awaiting_reply",
  "evidence_ids": ["ev_..."],
  "proof_scope": "local_operator_receipt",
  "safety": {
    "send_allowed": false,
    "mailbox_mutations_allowed": false,
    "records_external_claim_only": true
  }
}
```

Allowed statuses are `open`, `reviewing`, `waiting`, `blocked`, `resolved`, and
`ignored`.

Allowed reason codes are `evidence_reviewed`, `draft_prepared`,
`awaiting_reply`, `portal_verified`, `legal_waiting`, `provider_blocked`,
`needs_human`, `not_actionable`, `duplicate`, and `reopened`.

## Privacy Boundary

The ledger and receipts are redacted. They must not contain raw sender names,
email addresses, subjects, snippets, bodies, raw headers, full local paths, or
freeform private notes.

## Safety Boundary

The ledger may write local proof state only. It never sends, archives, labels,
marks read, deletes, or changes provider/account state.
