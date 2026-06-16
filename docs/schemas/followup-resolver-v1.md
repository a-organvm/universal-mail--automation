# Follow-up Resolver v1

Snapshot schema: `uma.followup.resolver_snapshot.v1`
Receipt writer schema: `uma.followup.resolver_receipts.v1`

## Purpose

The follow-up resolver makes mail and LinkedIn reply work first-class in UMA.

It answers:

- which redacted action ids need mail or LinkedIn follow-up;
- whether local draft approval or delivery receipts already exist;
- which follow-up items are still waiting for private evidence review, draft
  approval, delivery intent, final send review, or external provider proof;
- which resolver receipts can be recorded from existing local proof.

It does not read LinkedIn, open a browser, create provider drafts, send mail,
archive, label, mark read, or mutate any mailbox.

## Producers

- CLI: `python cli.py mail-followup-resolver --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- CLI receipt writer: `python cli.py mail-followup-resolver-receipts --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- API: `GET /v1/ops/followup-resolver`
- API receipt writer: `POST /v1/ops/followup-resolver-receipts`
- MCP: `mail_followup_resolver(...)`
- MCP receipt writer: `mail_followup_resolver_receipts(...)`
- Core snapshot: `core.followup_resolver.build_followup_resolver_snapshot`
- Core receipt writer: `core.followup_resolver.build_followup_resolver_receipts`

## Safety Boundary

The snapshot is read-only:

```json
{
  "read_only": true,
  "provider": "mail_or_linkedin",
  "official_surface": "mail_or_linkedin_inbox",
  "provider_backed_read": false,
  "provider_backed_automation": false,
  "mailbox_mutations": false,
  "sends": false,
  "portal_mutations": false
}
```

The receipt writer appends only local redacted `uma.mail.resolver_receipt.v1`
records. It never sends, drafts, archives, labels, marks read, reads LinkedIn,
or mutates a provider.

## Privacy Boundary

The snapshot and receipt-writer result omit:

- sender;
- address;
- subject;
- snippet;
- body;
- raw headers;
- full local paths;
- private draft content;
- raw LinkedIn state;
- raw external references.

They include only redacted action ids, receipt ids, proof types, counts, status
codes, and safety flags.

## Snapshot Shape

Top-level fields:

- `schema`: always `uma.followup.resolver_snapshot.v1`
- `status`: `ok`, `needs_private_review`, or `no_followup_actions`
- `snapshot_id`: redacted snapshot identifier
- `mode`: safety flags
- `source`: resolver-plan schema, receipt filenames, and checked timestamp
- `privacy`: redaction contract
- `coverage`: supported surfaces and provider-backed coverage limits
- `kpis`: aggregate counts
- `answers`: dashboard-ready summary
- `actions`: redacted action rows with receipt candidates

Each action row includes:

```json
{
  "schema": "uma.followup.resolver_action.v1",
  "action_id": "action_...",
  "resolver_type": "reply_follow_up",
  "official_surface": "mail_or_linkedin_inbox",
  "draft_approval_receipts": 1,
  "approved_drafts": 1,
  "delivery_receipts": 1,
  "delivery_status_counts": {
    "provider_draft_requested": 1
  },
  "receipt_candidate": {
    "resolver_status": "needs_follow_up",
    "reason_code": "official_surface_checked",
    "proof_type": "delivery_receipt",
    "provider": "linkedin",
    "operator_must_record_receipt": true
  },
  "send_allowed": false,
  "mailbox_mutations_allowed": false
}
```

When there is no existing approval or delivery receipt,
`operator_must_record_receipt=false`. The resolver shows the work as open but
does not manufacture proof.

## Receipt Writer

`uma.followup.resolver_receipts.v1` records only candidates backed by existing
local proof:

- `draft_approval_receipt` candidates use
  `proof_scope=local_followup_draft_approval_state`.
- `delivery_receipt` candidates use
  `proof_scope=local_followup_delivery_state`.

The resulting resolver receipts keep:

```json
{
  "provider_backed_read": false,
  "provider_backed_automation": false,
  "mailbox_mutations_allowed": false,
  "portal_mutations_allowed": false,
  "send_allowed": false
}
```

This layer proves local workflow state, not external LinkedIn or mail-provider
delivery. Future Gmail/Mail.app/Outlook/LinkedIn provider resolvers should add
provider-backed proof without weakening this boundary.
