# UMA Ops Summary v1

`uma.ops.summary.v1` is the private operator-dashboard payload generated from a
local mail-triage report. It is intended for local control-tower views, not for
public product demos or raw mailbox export.

## Entry Points

- Core: `core.ops_summary.build_ops_snapshot(report_path)`
- CLI: `python cli.py ops-summary --report ~/System/Reports/mail-triage/latest.json`
- Refresh CLI: `python cli.py ops-refresh --report ~/System/Reports/mail-triage/latest.json`
- API: `GET /v1/ops/summary` with `UMA_OPS_REPORT_PATH` configured
- History API: `GET /v1/ops/history` with `UMA_OPS_HISTORY_DIR` configured
- UI: `GET /ops`, which fetches `/v1/ops/summary`

## Input

The input is a JSON report with this minimum shape:

```json
{
  "generated_at": "2026-06-15 12:31:01 EDT",
  "since": "2026-05-01",
  "until_exclusive": "2026-06-16",
  "apply_mode": true,
  "scope_counts": {
    "Inbox including Gmail label": {"messages": 10, "unread": 4},
    "Gmail All Mail": {"messages": 100, "unread": 8},
    "Archive equivalent": {"messages": 90, "unread": 4},
    "All scoped non-deleted": {"messages": 110, "unread": 12}
  },
  "rollups": {
    "top_labels": [
      {"label": "Mail Triage/Provider Action Needed 2026-06-15", "messages": 3, "unread": 2}
    ]
  },
  "buckets": {
    "Review": []
  }
}
```

If a sibling `latest-actions.md` exists, the summary builder parses:

- `Escaped unread ... returned N messages`
- Label count rows in the form `` `Mail Triage/...`: N messages, M unread ``

Sidecar label counts override same-label rows from `rollups.top_labels`, because
the report rollup may omit small but important action queues.

## Output

Top-level fields:

| Field | Meaning |
| --- | --- |
| `schema` | Always `uma.ops.summary.v1` |
| `status` | `ok` when the report was loaded and normalized |
| `source` | Redacted report identity: filename, generated time, window, apply mode |
| `privacy` | Redaction flag and intentionally omitted raw fields |
| `freshness` | Parse status, checked time, age, freshness threshold, and stale flag |
| `kpis` | Aggregate counts for coverage, escaped unread, active unread, waiting, closed |
| `lanes` | Aggregated triage lanes keyed from `Mail Triage/...` labels |
| `buckets` | Redacted bucket summaries with small redacted samples |

KPI fields:

| Field | Definition |
| --- | --- |
| `inbox_messages` / `inbox_unread` | `Inbox including Gmail label` counts |
| `all_mail_messages` / `all_mail_unread` | `Gmail All Mail` counts |
| `archive_messages` / `archive_unread` | `Archive equivalent` counts |
| `scoped_messages` / `scoped_unread` | `All scoped non-deleted` counts |
| `escaped_unread` | Sidecar escaped-unread check count, or `null` if unavailable |
| `active_unread` | Unread messages in `action`, `verify`, and `decision` lanes |
| `waiting_messages` | Messages in waiting lanes |
| `closed_messages` | Messages in closed/reviewed/superseded lanes |

Freshness fields:

| Field | Definition |
| --- | --- |
| `checked_at` | UTC timestamp when the summary was built |
| `generated_at_utc` | Parsed report generation timestamp, or `null` |
| `generated_at_parseable` | Whether `source.generated_at` could be parsed |
| `age_seconds` / `age_hours` | Report age at `checked_at`, or `null` |
| `max_age_hours` | Freshness threshold, default `12` |
| `is_stale` | `true` when the report age exceeds the threshold or timestamp is unparseable |
| `status` | `fresh`, `stale`, `future`, or `unknown` |
| `reason` | Reader-facing reason for the freshness status |

## Refresh And History

`python cli.py ops-refresh` builds the same redacted summary and writes:

- `latest-summary.json`
- `history/ops-summary_<UTCSTAMP>.json`
- `index.json`

The history index uses `uma.ops.history.v1`:

```json
{
  "schema": "uma.ops.history.v1",
  "latest": "latest-summary.json",
  "entries": [
    {
      "file": "history/ops-summary_20260615_180000Z.json",
      "generated_at": "2026-06-15 12:31:01 EDT",
      "checked_at": "2026-06-15T18:00:00Z",
      "is_stale": false,
      "escaped_unread": 0,
      "active_unread": 71,
      "waiting_messages": 12,
      "closed_messages": 68
    }
  ]
}
```

This history is intentionally aggregate-only and redacted. It must not be
confused with a raw mailbox archive.

`ops-refresh` can optionally run the local read-only report producer first:

```bash
python cli.py ops-refresh \
  --run-mail-triage \
  --since 2026-05-01 \
  --until 2026-06-16 \
  --report-dir ~/System/Reports/mail-triage \
  --output-dir ~/.local/state/universal-mail-automation/ops
```

The producer path defaults to `UMA_MAIL_TRIAGE_BIN` or the user-local
`mail-triage` binary. This stage refreshes raw local reports, then UMA persists
only the redacted summary/history outputs.

## Privacy Boundary

The summary must not expose:

- Raw sender display names
- Email addresses
- Subjects
- Message bodies
- Full local report paths

Bucket samples keep only operational fields: stable hashed item id, bucket, lane,
kind, received timestamp, read state, scope, group count, `Mail Triage/...`
labels, reason, and next action.

## Errors

`OpsReportError` is raised by the core builder for missing, invalid, or malformed
reports. The API maps these to HTTP errors. The CLI prints a one-line error and
exits non-zero without a traceback.
