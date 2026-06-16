# UMA Mail Invariant Rollup v1

`uma.mail.invariant_rollup.v1` is the operator-facing answer to the one test of
done: for every item across every mailbox surface, can it be seen as exactly one
of **closed-with-receipt**, **blocked-with-reason**, or **waiting-with-evidence**
— and trusted completely?

It is a pure read-only aggregation over resolver-ledger items. It opens no
portals, reads no providers, sends nothing, and mutates no mailbox.

## Entry Points

- Core: `core.mail_resolver_receipt.build_invariant_rollup(items)` — maps a list
  of `uma.mail.resolver_ledger_item.v1` entries to the three states.
- Embedded: `build_resolver_ledger(...)` includes `invariant_rollup` (computed
  over the full plan, before any `max_items` truncation).
- API: `GET /v1/ops/resolver-ledger` → `invariant_rollup`
- UI: `/ops` **Invariant** panel (headline view), auto-loaded on refresh.

## State Mapping

Every `resolver_status` maps to exactly one state. The mapping is intentionally
strict — only `verified_resolved` (always receipt-backed) is `closed_with_receipt`;
nothing is inflated into "closed". Anything not explicitly resolved or blocked
stays visible.

| resolver_status     | invariant state         |
|---------------------|-------------------------|
| `verified_resolved` | `closed_with_receipt`   |
| `verified_blocked`  | `blocked_with_reason`   |
| `verified_waiting`  | `waiting_with_evidence` |
| `needs_follow_up`   | `waiting_with_evidence` |
| `not_started`       | `waiting_with_evidence` |
| `not_found`         | `waiting_with_evidence` |
| `not_applicable`    | `waiting_with_evidence` |
| *(any other value)* | `unclassified`          |

`invariant_holds` is `true` iff `unclassified.groups == 0` — i.e. no item escaped
classification. An unrecognised status (future or corrupt) is surfaced in
`unclassified` and flips `invariant_holds` to `false`, never silently dropped.

## Rollup Shape

```json
{
  "schema": "uma.mail.invariant_rollup.v1",
  "states": {
    "closed_with_receipt":   {"groups": 0, "findings": 0},
    "blocked_with_reason":   {"groups": 0, "findings": 0},
    "waiting_with_evidence": {"groups": 0, "findings": 0}
  },
  "unclassified": {"groups": 0, "findings": 0, "statuses": []},
  "total": {"groups": 0, "findings": 0},
  "invariant_holds": true,
  "send_allowed": false,
  "mailbox_mutations_allowed": false,
  "portal_mutations_allowed": false
}
```

`groups` counts resolver action-groups; `findings` sums their `finding_count`.

## Why closed-with-receipt may be 0

By design UMA has no autonomous send/provider-write executor. An item only
becomes `closed_with_receipt` after an operator approves and *separately
confirms* a real provider action, which is then recorded as a receipt. A `0`
here is not a missing feature — it is the system refusing to claim closure
without proof, honoring the no-blind-send constraint.
