# GitHub Resolver Snapshot v1

Schema: `uma.github.resolver_snapshot.v1`
Receipt writer schema: `uma.github.resolver_receipts.v1`

## Purpose

`uma.github.resolver_snapshot.v1` is the read-only GitHub official-surface
snapshot for UMA resolver actions whose `resolver_type` is `github_reconcile`.

It answers:

- which redacted UMA action ids need GitHub reconciliation;
- whether the GitHub CLI is available and authenticated;
- which bounded official GitHub surfaces were checked;
- how many redacted notifications, assigned issues, and open PR results were
  visible;
- which resolver receipts could be recorded next;
- which provider-read or blocker candidates were durably recorded into the
  redacted resolver ledger.

It does not prove that all GitHub work is resolved, mutate GitHub, mutate mail,
create drafts, send messages, open a browser, or store raw GitHub state.

## Producers

- CLI: `python cli.py mail-github-resolver --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- CLI receipt writer: `python cli.py mail-github-resolver-receipts --intelligence ~/System/Reports/mail-history/latest-intelligence.json`
- API: `GET /v1/ops/github-resolver`
- API receipt writer: `POST /v1/ops/github-resolver-receipts`
- MCP: `mail_github_resolver(intelligence_path, include_provider_queries=True)`
- MCP receipt writer: `mail_github_resolver_receipts(intelligence_path, ledger_path, include_provider_queries=True)`
- Core: `core.github_resolver.build_github_resolver_snapshot`
- Core receipt writer: `core.github_resolver.build_github_resolver_receipts`

## Safety Boundary

The snapshot is read-only.

Required mode flags:

```json
{
  "read_only": true,
  "provider": "github",
  "official_surface": "github_cli_api",
  "provider_backed_automation": false,
  "mailbox_mutations": false,
  "sends": false,
  "portal_mutations": false
}
```

When GitHub CLI/API reads succeed, `provider_backed_read` may be `true`, but that
still does not grant mutation authority or prove external closure.

## Privacy Boundary

The snapshot must not include:

- GitHub login;
- repository full names or owners;
- notification subjects;
- issue or PR titles;
- URLs;
- body text;
- raw command output;
- raw mail fields.

Repository references are represented only as hashes:

```json
{"repo_hash": "repo_...", "record_count": 2}
```

Receipt candidates include only a hashed external reference. They do not include
raw GitHub ids, URLs, titles, or repository names.

## Shape

Top-level fields:

- `schema`: always `uma.github.resolver_snapshot.v1`
- `status`: `ok`, `planned_only`, `provider_unavailable`, `blocked_no_auth`, or
  `degraded`
- `snapshot_id`: redacted snapshot identifier
- `mode`: safety flags
- `source`: resolver-plan schema, checked timestamp, GitHub executable basename,
  query limit, and whether provider queries were included
- `privacy`: redaction contract
- `auth`: CLI/auth availability without raw command output
- `coverage`: supported and deferred GitHub surfaces
- `kpis`: aggregate counts
- `answers`: dashboard-ready summary
- `surfaces`: bounded per-surface summaries
- `actions`: redacted action rows with receipt candidates

## Supported Surfaces

Initial provider-backed read surfaces:

- `notifications`
- `assigned_issues`
- `open_pull_requests`

Deferred surfaces:

- billing;
- security alerts;
- repository-specific Dependabot alerts.

Deferred surfaces remain visible in `coverage.deferred_surfaces` so the snapshot
does not overclaim complete GitHub reconciliation.

## Receipt Candidates

Each action row may include:

```json
{
  "action_id": "action_...",
  "resolver_status": "needs_follow_up",
  "reason_code": "official_surface_checked",
  "proof_type": "github_issue_pr_billing_or_security_state",
  "provider": "github",
  "external_reference": {
    "provided": true,
    "hash": "externalref_...",
    "stored_raw": false
  },
  "provider_backed_read": true,
  "provider_backed_automation": false,
  "operator_must_record_receipt": true
}
```

The candidate is not written automatically. Durable proof state still goes
through `uma.mail.resolver_receipt.v1` in the resolver receipt ledger.

When provider queries are intentionally skipped, snapshot status is
`planned_only`, receipt candidates use `resolver_status=not_applicable` and
`reason_code=not_actionable`, and `operator_must_record_receipt=false`. That
prevents planned mappings from being mistaken for provider proof.

## Receipt Writer

`uma.github.resolver_receipts.v1` records snapshot receipt candidates into the
existing resolver ledger. It writes local JSONL proof only.

Provider-backed reads become resolver receipts with:

```json
{
  "schema": "uma.mail.resolver_receipt.v1",
  "provider": "github",
  "proof_scope": "official_surface_provider_read_snapshot",
  "source_snapshot_id": "ghsnapshot_...",
  "safety": {
    "provider_backed_read": true,
    "provider_backed_automation": false,
    "operator_attestation_only": false,
    "mailbox_mutations_allowed": false,
    "portal_mutations_allowed": false,
    "send_allowed": false
  }
}
```

CLI/auth/provider blockers become local operator-attestation receipts with
`provider_backed_read=false` and
`proof_scope=official_surface_read_blocker_snapshot`.

The writer never stores raw GitHub output, raw repository names, URLs, issue or
PR titles, raw mail fields, or raw external references.
