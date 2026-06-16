# UMA Mail History Export v1

`uma.mail.history_export.v1` is UMA's private historical-mail intake contract.
It normalizes local JSON, JSONL/NDJSON, mbox, EML, and macOS Mail EMLX sources
into the row shape consumed by `uma.mail.intelligence.v1`.

This is not a dashboard payload. It can contain raw private subjects, snippets,
and bounded message bodies. The safe public/agent-facing output of the producer
is the receipt schema, `uma.mail.history_export.receipt.v1`.

## Entry Points

- Core: `core.mail_history_export.build_mail_history_export(source_path)`
- CLI: `python cli.py mail-history-export --source ~/Library/Mail --output ~/System/Reports/mail-history/latest.json`
- MCP: `mail_history_export(source_path, output_path, ...)`
- Consumer: `python cli.py mail-intel --history ~/System/Reports/mail-history/latest.json`

## Supported Sources

| Source type | Notes |
| --- | --- |
| `json` | Object or array containing `messages`, `records`, or `items` |
| `jsonl` / `ndjson` | One message object per line |
| `mbox` | Standard local mailbox file |
| `eml` | Single RFC 822 message file |
| `emlx` | Single macOS Mail message file |
| `emlx_dir` | Directory recursively scanned for `.emlx` and `.eml` files |

The source is read-only. Attachments are not copied.

## Output Shape

```json
{
  "schema": "uma.mail.history_export.v1",
  "status": "ok",
  "mode": {
    "read_only": true,
    "mailbox_mutations": false,
    "sends": false,
    "archive_changes": false,
    "attachments_exported": false
  },
  "source": {
    "type": "emlx_dir",
    "filename": "Mail",
    "mailbox_hint": null,
    "message_count": 10
  },
  "generated_at": "2026-06-15T19:00:00Z",
  "since": "2024-01-01",
  "until_exclusive": "2026-06-16",
  "privacy": {
    "private_raw_mail": true,
    "safe_for_dashboard": false,
    "stdout_safe": false,
    "omitted_source_fields": ["full_source_path", "attachments", "raw_headers"],
    "body_char_limit": 4000
  },
  "messages": []
}
```

Each message row uses normalized fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable redacted row id |
| `source_ref` | Stable redacted source reference |
| `source_name` | Source filename only, never a full path |
| `message_id` | Message id or generated fallback |
| `thread_id` | Thread/conversation id or generated fallback |
| `received_at` | UTC timestamp when parseable |
| `direction` | `inbound` or `outbound` |
| `scope` | Inbox, Archive, Sent, Drafts, Junk, Trash, Unknown, or supplied hint |
| `state` | read, unread, or unknown |
| `labels` | Source labels plus scope where available |
| `sender` | Raw sender display name, private |
| `address` | Raw sender address, private |
| `subject` | Raw subject, private |
| `snippet` | Bounded normalized snippet, private |
| `body` | Bounded text/plain body, private |

## Receipt Shape

`mail-history-export` prints the receipt, not the raw export:

```json
{
  "schema": "uma.mail.history_export.receipt.v1",
  "status": "ok",
  "mode": {
    "read_only_source": true,
    "mailbox_mutations": false,
    "sends": false,
    "archive_changes": false,
    "wrote_private_export": true
  },
  "output": {
    "filename": "latest.json",
    "bytes": 12345,
    "message_count": 10,
    "private_raw_mail": true,
    "safe_for_dashboard": false
  },
  "privacy": {
    "receipt_redacted": true,
    "raw_mail_printed_to_stdout": false,
    "output_contains_private_mail": true
  }
}
```

The receipt must not include raw senders, addresses, subjects, snippets, bodies,
raw headers, attachments, or full local source paths.

## Safety Boundary

The exporter never sends, labels, archives, marks read, moves, deletes, or writes
back to a mailbox. Its only write is the private local JSON export file selected
by the operator.
