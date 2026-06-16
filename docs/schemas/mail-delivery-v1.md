# Mail Delivery v1

`uma.mail.delivery_ledger.v1` is the redacted post-approval delivery state for
private draft candidates. `uma.mail.delivery_receipt.v1` is the append-only local
receipt for delivery intent or operator-attested external status.

This layer does not send mail, create provider drafts, archive, label, mark
read, or mutate any mailbox. It records what is ready, requested, blocked, or
operator-attested after a draft has an approved `uma.mail.draft_approval_receipt.v1`.

Entry points:

- Core ledger: `core.mail_delivery.build_delivery_ledger(...)`
- Core receipt: `core.mail_delivery.build_delivery_receipt(...)`
- CLI ledger: `python cli.py mail-delivery-ledger --intelligence ~/System/Reports/mail-history/latest-intelligence.json --history ~/System/Reports/mail-history/latest.json --action-id action_... --ack-private`
- CLI receipt: `python cli.py mail-delivery-receipt --intelligence ~/System/Reports/mail-history/latest-intelligence.json --history ~/System/Reports/mail-history/latest.json --action-id action_... --draft-id draft_... --delivery-status provider_draft_requested --reason-code approved_for_provider_draft --ack-private`
- API ledger: `GET /v1/ops/delivery/{action_id}?ack_private=true`
- API receipt: `POST /v1/ops/delivery/{action_id}`
- MCP: `mail_delivery_ledger(...)` and `mail_delivery_receipt(...)`
- UI: `/ops` Private Draft Package delivery controls

Configure the JSONL file with `UMA_MAIL_DELIVERY_LEDGER_PATH`; if unset,
API/CLI default to user-local state.

## Receipt Shape

```json
{
  "schema": "uma.mail.delivery_receipt.v1",
  "status": "recorded",
  "receipt_id": "delivery_...",
  "draft_id": "draft_...",
  "action_id": "action_...",
  "approval_receipt_id": "draftapproval_...",
  "delivery_status": "provider_draft_requested",
  "reason_code": "approved_for_provider_draft",
  "provider": "gmail",
  "external_reference": {
    "provided": true,
    "hash": "externalref_...",
    "stored_raw": false
  },
  "safety": {
    "uma_created_provider_draft": false,
    "uma_sent_message": false,
    "mailbox_mutations_allowed": false,
    "operator_attestation_only": true,
    "requires_official_provider_receipt": false
  }
}
```

Allowed `delivery_status` values:

- `provider_draft_requested`
- `provider_draft_recorded`
- `send_requested`
- `sent_recorded`
- `blocked`
- `canceled`

Allowed `reason_code` values:

- `approved_for_provider_draft`
- `operator_confirmed_external_draft`
- `operator_confirmed_external_send`
- `final_review_required`
- `provider_unavailable`
- `portal_required`
- `not_current`
- `duplicate`
- `policy_blocked`

`provider_draft_recorded` and `sent_recorded` are local operator attestations
until a later official provider resolver writes a provider-backed proof receipt.
The raw provider reference is never stored; only a deterministic hash is kept.

## Privacy

Ledger and receipt outputs omit senders, addresses, subjects, snippets, bodies,
raw headers, full local paths, and raw external references. They include only
redacted ids, status, reason codes, provider labels, and safety flags.
