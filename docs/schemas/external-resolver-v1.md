# External Resolver v1

`uma.external.resolver_snapshot.v1` is a redacted operator view for external
official-surface lanes:

- `account_security_verification`
- `payment_or_billing_verification`
- `provider_status_reconcile`
- `subscription_decision`
- `legal_review`

It represents planned work and local UMA resolver receipts. It does not log into
provider portals, read bank/cloud/security/vendor systems, create drafts, send
mail, or mutate provider state.

Snapshots include `provider_hint_counts` at the KPI level and `provider_hints`
on action rows when historical intelligence can identify a controlled official
surface family such as `cloudflare`, `google_cloud`, `stripe`, `openai`, or
`linkedin`. These hints are routing context only; they are not provider-backed
proof.

`uma.external.resolver_receipts.v1` records local redacted resolver receipts only
when an operator explicitly requests blocker attestation. The CLI flag is
`--attest-blockers`; the API payload field is `attest_blockers: true`.

Safety invariants:

- `provider_backed_read` is always `false`.
- `provider_backed_automation` is always `false`.
- `mailbox_mutations_allowed`, `send_allowed`, and `portal_mutations_allowed`
  are always `0`.
- Raw mail, raw portal state, subjects, senders, addresses, snippets, bodies,
  headers, and source paths are omitted.
- Provider hints are controlled slugs only. Unknown raw domains or private
  vendor names must not be emitted.
- External references are hashed before storage.

Receipt behavior:

- Planned snapshots produce no recordable receipts by default.
- Explicit attestation records `action_receipt` proof with
  `proof_scope: external_surface_operator_attestation`.
- External resolver receipts are local blocker/status proof, not proof that the
  official provider surface was checked.
