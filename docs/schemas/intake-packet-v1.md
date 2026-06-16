# UMA Intake Packet v1

`uma.intake.packet.v1` is the cross-surface execution envelope for UMA API/MCP/CLI/Worker
flows. It wraps request context and the raw operation result so machine consumers
can correlate runs across trust surfaces without depending on a response-specific
shape.

It is added when available to `/v1/triage` and `/v1/triage/preview` payloads as
`packet`, and may also be emitted by command surfaces.

## Top-Level Shape

```json
{
  "schema": "uma.intake.packet.v1",
  "product": "uma",
  "surface": "api|mcp|cli-label|cloudflare-worker",
  "operation": "triage|triage_receipt_lookup|...",
  "status": "ok",
  "timestamp": "2026-06-15T17:00:00Z",
  "run_id": "run_abc123",
  "request": {
    "provider": "gmail",
    "query": "has:nouserlabels",
    "limit": 100,
    "dry_run": true
  },
  "actor": {
    "type": "api_account|mcp_tool|cli",
    "id": "acct_..."
  },
  "auth": {
    "scheme": "bearer|mcp_account_api_key|none",
    "authenticated": true
  },
  "payload": {
    "surface": "api",
    "request": {
      "provider": "gmail",
      "query": "has:nouserlabels",
      "limit": 100,
      "dry_run": true
    },
    "result": {
      "dry_run": true,
      "provider": "gmail",
      "receipt": "Triage receipt...",
      "audit": {
        "total": 3,
        "protected_held": 1,
        "archived": 2,
        "moved": 0,
        "labeled": 0,
        "kept": 0,
        "violations": []
      },
      "processed": {"processed_count": 3}
    }
  }
}
```

## Safety Guidance

- `actor` and `auth` fields are metadata; avoid sensitive credentials in either.
- `payload.result` should be treated as the authoritative operational result for
  compatibility when available.
- If a surface cannot provide a packet, clients should fall back to canonical
  top-level response fields (`receipt`, `audit`, `run_id`).
