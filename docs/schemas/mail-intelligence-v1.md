# UMA Mail Intelligence v1

`uma.mail.intelligence.v1` is the private, read-only historical mail
intelligence contract. It converts a historical mail export into redacted
entities, events, missed opportunities, risks, timelines, and reconciliation
against current `/ops` lanes.

It is not a mailbox mutation command, not a sender, and not a generic vector
store dump.

## Entry Points

- Core: `core.historical_intelligence.build_historical_intelligence(history_path)`
- Producer: `python cli.py mail-history-export --source ~/Library/Mail --output ~/System/Reports/mail-history/latest.json`
- CLI: `python cli.py mail-intel --history ~/System/Reports/mail-history/latest.json`
- CLI cache: `python cli.py mail-intel --history ~/System/Reports/mail-history/latest.json --output ~/System/Reports/mail-history/latest-intelligence.json`
- API: `GET /v1/ops/intelligence` with `UMA_HISTORICAL_MAIL_PATH` configured
- API cache: `UMA_HISTORICAL_INTELLIGENCE_PATH` can point to a precomputed redacted `mail-intel --output` file
- MCP: `mail_intelligence(history_path, ops_report_path=None, stale_days=14)`
- UI: `GET /ops`, which optionally fetches `/v1/ops/intelligence`

## Input

The canonical input is `uma.mail.history_export.v1`, produced by
`mail-history-export`. The builder also accepts compatible local JSON exports
with this minimum shape:

```json
{
  "generated_at": "2026-06-15T17:00:00Z",
  "since": "2026-01-01",
  "until_exclusive": "2026-06-16",
  "messages": [
    {
      "message_id": "message-1",
      "thread_id": "thread-1",
      "received_at": "2026-05-01T14:00:00Z",
      "direction": "inbound",
      "sender": "Private Person",
      "address": "person@example.test",
      "subject": "Private subject",
      "snippet": "Private snippet",
      "body": "Private body",
      "scope": "Archive",
      "state": "read",
      "labels": ["Mail Triage/Provider Security Verify 2026-06-15"]
    }
  ]
}
```

The builder accepts raw private input, but output must stay redacted.
See [mail-history-export-v1.md](mail-history-export-v1.md) for the producer
contract and receipt boundary.

## Output

Top-level fields:

| Field | Meaning |
| --- | --- |
| `schema` | Always `uma.mail.intelligence.v1` |
| `status` | `ok` when the export was loaded and normalized |
| `mode` | Read-only and no-mutation guarantees |
| `source` | Redacted filename/window/check metadata |
| `privacy` | Redaction flag and intentionally omitted raw fields |
| `kpis` | Entity, event, opportunity, risk, evidence, provider-hint, and reconciliation counts |
| `answers` | Macro answers: missed, matters now, next, blocked, safely handled, proof |
| `entities` | `uma.mail.entity.v1` records |
| `events` | `uma.mail.event.v1` records |
| `opportunities` | `uma.mail.opportunity.v1` records |
| `risks` | `uma.mail.risk.v1` records |
| `timeline` | `uma.mail.timeline.v1` buckets |
| `reconciliation` | Current `/ops` lane visibility for each finding |
| `evidence` | Redacted evidence ids and operational metadata |

## Receipt And Cache

When `mail-intel --output` is used, the CLI writes the full redacted
`uma.mail.intelligence.v1` payload to the selected cache path and prints only a
safe receipt:

```json
{
  "schema": "uma.mail.intelligence.receipt.v1",
  "status": "ok",
  "output": {
    "filename": "latest-intelligence.json",
    "schema": "uma.mail.intelligence.v1",
    "redacted": true,
    "message_count": 41415,
    "opportunities": 759,
    "risks": 31652
  },
  "privacy": {
    "receipt_redacted": true,
    "raw_mail_printed_to_stdout": false,
    "output_redacted": true
  }
}
```

`/v1/ops/intelligence` serves this cache directly when
`UMA_HISTORICAL_INTELLIGENCE_PATH` is configured. Otherwise it recomputes from
`UMA_HISTORICAL_MAIL_PATH`.

## Planned Object Schemas

The first implementation emits these schema markers:

- `uma.mail.entity.v1`
- `uma.mail.event.v1`
- `uma.mail.opportunity.v1`
- `uma.mail.risk.v1`
- `uma.mail.timeline.v1`

Objects keep redacted ids and evidence ids. Raw senders, addresses, subjects,
snippets, and bodies stay out of the contract.

Events, risks, opportunities, evidence rows, and entities may include
`provider_hints` or `top_provider_hints`. These are controlled slugs such as
`github`, `cloudflare`, `google_cloud`, `stripe`, `openai`, or `linkedin`.
They are extracted from private input only to route official-surface work; raw
domains, senders, subjects, and snippets remain omitted. A provider hint is not
proof that the official provider surface was checked.

## Reconciliation

If `ops_report_path` or `UMA_OPS_REPORT_PATH` is supplied, the builder compares
historical findings to current `/ops` lanes.

Each finding receives an `ops_lane_status`:

| Status | Meaning |
| --- | --- |
| `represented_in_ops` | The recommended current lane exists and has messages/unread work |
| `not_represented_in_current_ops` | The historical finding is not visible in the current lane summary |
| `ops_not_supplied` | No current ops report was supplied |

This does not prove closure. It proves whether a historical finding is visible in
the current cockpit.

## Privacy Boundary

The output must not expose:

- Raw sender display names
- Email addresses
- Subjects
- Snippets
- Message bodies
- Raw headers
- Full local source paths

Provider hints must stay in the controlled-slug vocabulary. Do not emit unknown
raw domains or arbitrary vendor names into `provider_hints`.

Private source review is a separate gated surface:
`uma.mail.evidence_review.v1`. The default intelligence contract remains
redacted.

## Safety Boundary

The contract is read-only:

```json
{
  "read_only": true,
  "mailbox_mutations": false,
  "sends": false,
  "archive_changes": false,
  "generic_vector_store": false
}
```

Historical intelligence may recommend drafts, portal checks, or resolver lanes,
but it must not send, archive, mark read, label, or mutate a mailbox.
