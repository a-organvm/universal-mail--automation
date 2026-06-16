# UMA Mail Evidence Review v1

`uma.mail.evidence_review.v1` is the gated private source-evidence contract.
It opens one raw source message from a private historical export for a redacted
evidence id.

This contract is intentionally not public-safe and not dashboard-redacted. It can
contain raw sender names, email addresses, subjects, snippets, and bounded body
text. It exists so UMA can prove facts before drafts, resolver work, or closure.

## Entry Points

- Core: `core.mail_evidence_review.build_evidence_review(history_path, evidence_id, ack_private=True)`
- CLI: `python cli.py mail-evidence-review --history ~/System/Reports/mail-history/latest.json --evidence-id ev_... --ack-private`
- API: `GET /v1/ops/evidence/{evidence_id}?ack_private=true`
- MCP: `mail_evidence_review(history_path, evidence_id, ack_private=True)`
- UI: `/ops` Private Evidence Review lookup

## Gating

Private evidence review requires explicit acknowledgment:

- Core/CLI/MCP require `ack_private=True`.
- CLI requires `--ack-private`.
- API requires `UMA_OPS_TOKEN` to be configured and supplied as a bearer token.
- API also requires `ack_private=true`.

Without the acknowledgment, the request fails before any raw source fields are
returned.

## Output Shape

```json
{
  "schema": "uma.mail.evidence_review.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "private_review": true,
    "mailbox_mutations": false,
    "sends": false,
    "archive_changes": false,
    "approval_required_before_send": true
  },
  "privacy": {
    "redacted": false,
    "contains_private_mail": true,
    "public_safe": false,
    "requires_explicit_private_review": true,
    "omits_full_source_path": true,
    "body_bounded": true
  },
  "safety": {
    "send_allowed": false,
    "mailbox_mutations_allowed": false,
    "draft_allowed_only_after_fact_check": true
  },
  "message": {
    "evidence_id": "ev_...",
    "sender": "Private Person",
    "address": "person@example.test",
    "subject": "Private subject",
    "snippet": "Private snippet",
    "body": "Private bounded body"
  },
  "thread_context": []
}
```

## Safety Boundary

Evidence review never sends, labels, archives, marks read, moves, deletes, or
writes to a mailbox. It only reads the local private historical export and
returns a bounded source view for fact checking.

The response is source evidence, not approval. Drafting and resolver workflows
must still enforce their own approval gates.
