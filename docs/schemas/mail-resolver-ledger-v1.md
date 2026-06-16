# UMA Mail Resolver Ledger v1

`uma.mail.resolver_ledger.v1` is the redacted proof-state view for resolver
actions. `uma.mail.resolver_receipt.v1` is the append-only local receipt for an
official-surface check.

This layer records what an operator or future resolver verified in an official
surface. It does not open portals, send mail, create provider drafts, archive,
label, mark read, or mutate any mailbox.

## Entry Points

- Core ledger: `core.mail_resolver_receipt.build_resolver_ledger(...)`
- Core receipt: `core.mail_resolver_receipt.build_resolver_receipt(...)`
- CLI ledger: `python cli.py mail-resolver-ledger --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- CLI receipt: `python cli.py mail-resolver-receipt --intelligence ~/System/Reports/mail-history/latest-intelligence.json --action-id action_... --resolver-status verified_resolved --reason-code github_reconciled --proof-type github_issue_pr_billing_or_security_state --provider github`
- CLI GitHub receipt writer: `python cli.py mail-github-resolver-receipts --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- API ledger: `GET /v1/ops/resolver-ledger`
- API receipt: `POST /v1/ops/resolver-receipts`
- API GitHub receipt writer: `POST /v1/ops/github-resolver-receipts`
- MCP: `mail_resolver_ledger(...)`, `mail_resolver_receipt(...)`, and `mail_github_resolver_receipts(...)`
- UI: `/ops` Resolver Plan proof controls

Configure the JSONL file with `UMA_MAIL_RESOLVER_LEDGER_PATH`; if unset,
API/CLI default to user-local state.

## Ledger Shape

```json
{
  "schema": "uma.mail.resolver_ledger.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "mailbox_mutations": false,
    "sends": false,
    "portal_mutations": false,
    "local_receipts_only": true,
    "operator_attestation_supported": true,
    "provider_backed_read_supported": true,
    "provider_backed_automation": false
  },
  "kpis": {
    "resolver_groups": 11,
    "not_started": 10,
    "verified_resolved": 1,
    "receipts": 1,
    "operator_attestation_receipts": 1,
    "provider_backed_receipts": 0,
    "mailbox_mutations_allowed": 0,
    "send_allowed": 0,
    "portal_mutations_allowed": 0
  },
  "items": [],
  "receipts": []
}
```

## Receipt Shape

```json
{
  "schema": "uma.mail.resolver_receipt.v1",
  "status": "recorded",
  "receipt_id": "resolver_...",
  "action_id": "action_...",
  "resolver_status": "verified_resolved",
  "reason_code": "github_reconciled",
  "proof_type": "github_issue_pr_billing_or_security_state",
  "proof_matches_plan": true,
  "resolver_type": "github_reconcile",
  "official_surface": "github_api_cli_or_web",
  "provider": "github",
  "external_reference": {
    "provided": true,
    "hash": "externalref_...",
    "stored_raw": false
  },
  "proof_scope": "official_surface_operator_attestation",
  "source_snapshot_id": null,
  "safety": {
    "provider_backed_read": false,
    "provider_backed_automation": false,
    "operator_attestation_only": true,
    "mailbox_mutations_allowed": false,
    "portal_mutations_allowed": false,
    "send_allowed": false
  }
}
```

Allowed `resolver_status` values:

- `verified_waiting`
- `verified_blocked`
- `verified_resolved`
- `needs_follow_up`
- `not_found`
- `not_applicable`

Allowed `reason_code` values:

- `official_surface_checked`
- `external_state_matches_mail`
- `external_state_differs`
- `awaiting_provider`
- `awaiting_reply`
- `legal_review_complete`
- `billing_verified`
- `security_reviewed`
- `github_reconciled`
- `subscription_decision_recorded`
- `blocked_no_auth`
- `blocked_provider_unavailable`
- `duplicate`
- `not_actionable`

The `proof_type` must match one of the current resolver plan item's
`required_proof` values. This prevents recording generic proof against the wrong
lane.

## Safety Boundary

Resolver receipts are local proof state:

```json
{
  "provider_backed_read": false,
  "provider_backed_automation": false,
  "mailbox_mutations_allowed": 0,
  "send_allowed": 0,
  "portal_mutations_allowed": 0
}
```

They can support operator claims such as "GitHub was checked" or "billing was
verified in the official surface." They are not cryptographic provider receipts
and do not prove UMA itself changed an external system. Future provider-backed
resolvers should write separate official proof while keeping this redacted
contract.

Provider-specific read adapters may set `provider_backed_read=true` when a
bounded official API/CLI read succeeded, such as
`mail-github-resolver-receipts` recording a GitHub snapshot. That still does not
authorize or prove provider-backed automation.

## Privacy Boundary

Ledger and receipt outputs omit senders, addresses, subjects, snippets, bodies,
raw headers, full local paths, freeform private notes, raw external state, and
raw external references. External references are stored only as deterministic
hashes.
