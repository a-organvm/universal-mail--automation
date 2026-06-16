# Universal Mail Automation — HTTP API

A thin FastAPI surface over the engine. It **never bypasses the protected-sender
gate**: triage runs through the engine's gate *and* an independent audit observer,
and the API asserts no-violations at the boundary before returning success
(fail-closed — a gate violation surfaces as HTTP 500, never a silent 200).

## Run

```bash
pip install -r requirements.txt -r requirements-api.txt
uvicorn api.app:app --reload            # http://127.0.0.1:8000
# interactive docs at /docs
```

Or with Docker:

```bash
docker build -t mail-api .
docker run -p 8000:8000 --env-file your.env mail-api
```

Provider credentials are supplied at runtime via environment (see the repo
`CLAUDE.md` for the 1Password-brokered variables). Broad per-customer mailbox
auth is not yet implemented; account-specific billing actions use issued account
API keys (`Authorization: Bearer ...`) and public checkout can still create a new
account.

## Endpoints

| Method | Path | Purpose | Needs mailbox |
|---|---|---|---|
| GET | `/health` | Liveness | no |
| POST | `/v1/senders/check` | Is this sender protected? + categorization | no |
| POST | `/v1/triage/preview` | Dry-run: disposition + receipt, nothing touched | yes |
| POST | `/v1/triage` | Run triage; fail-closed | yes; live runs need account key |
| GET | `/v1/ops/summary` | Redacted private operator summary | no; needs local report |
| GET | `/v1/ops/history` | Redacted operator history index | no; needs history dir |
| GET | `/v1/ops/intelligence` | Redacted historical mail intelligence, provider hints, and ops reconciliation | no; needs local historical export |
| GET | `/v1/ops/action-plan` | Redacted approval-aware action plan with provider hint counts | no; needs historical intelligence |
| GET | `/v1/ops/resolver-plan` | Redacted official-surface resolver plan with provider hints | no portal mutation; needs historical intelligence |
| GET | `/v1/ops/provider-surface-plan` | Redacted provider resolver frontier from controlled provider hints | no provider read or portal mutation; needs historical intelligence |
| GET | `/v1/ops/resolver-ledger` | Redacted resolver proof state | no portal mutation; needs historical intelligence |
| GET | `/v1/ops/github-resolver` | Redacted read-only GitHub CLI/API resolver snapshot | no GitHub mutation; needs historical intelligence |
| POST | `/v1/ops/github-resolver-receipts` | Append redacted resolver receipts from GitHub snapshot candidates | no GitHub mutation; requires `UMA_OPS_TOKEN` |
| GET | `/v1/ops/followup-resolver` | Redacted mail/LinkedIn follow-up resolver snapshot | no LinkedIn read or send; needs historical intelligence |
| POST | `/v1/ops/followup-resolver-receipts` | Append redacted resolver receipts from local follow-up proof | no send or mailbox mutation; requires `UMA_OPS_TOKEN` |
| GET | `/v1/ops/external-resolver` | Redacted provider/security/billing/subscription/legal resolver snapshot with provider hints | no provider read or portal mutation; needs historical intelligence |
| POST | `/v1/ops/external-resolver-receipts` | Append explicit local blocker attestations | no provider read or portal mutation; requires `UMA_OPS_TOKEN` |
| POST | `/v1/ops/resolver-receipts` | Append redacted resolver receipt | no portal mutation; requires `UMA_OPS_TOKEN` |
| GET | `/v1/ops/action-ledger` | Redacted action status and local proof receipts | no; needs historical intelligence |
| POST | `/v1/ops/action-receipts` | Append redacted local action receipt | no mailbox mutation; requires `UMA_OPS_TOKEN` |
| GET | `/v1/ops/draft-package/{action_id}` | Gated private draft package for approval | no send; requires `UMA_OPS_TOKEN` and `ack_private=true` |
| GET | `/v1/ops/draft-approvals/{action_id}` | Redacted draft approval status | no send; requires `UMA_OPS_TOKEN` and `ack_private=true` |
| POST | `/v1/ops/draft-approvals/{action_id}` | Append redacted draft approval receipt | no send; requires `UMA_OPS_TOKEN` and `ack_private=true` |
| GET | `/v1/ops/delivery/{action_id}` | Redacted delivery intent/status | no provider draft or send; requires `UMA_OPS_TOKEN` and `ack_private=true` |
| POST | `/v1/ops/delivery/{action_id}` | Append redacted delivery receipt | no provider draft or send; requires `UMA_OPS_TOKEN` and `ack_private=true` |
| GET | `/v1/ops/evidence/{evidence_id}` | Gated private source evidence review | no mailbox mutation; requires `UMA_OPS_TOKEN` and `ack_private=true` |
| GET | `/ops` | Private operator dashboard shell | no; fetches summary API |

Live runs (`dry_run:false`) require `Authorization: Bearer <account_api_key>`.
The API reserves one monthly-plan run before touching the mailbox; if the plan
cap is exhausted, it consumes one prepaid run credit. Failed runs refund the
reservation. Dry-runs are not metered.

### Examples

```bash
curl -s localhost:8000/v1/senders/check \
  -H 'content-type: application/json' \
  -d '{"sender":"clerk@courts.ca.gov"}'
# {"sender":"clerk@courts.ca.gov","protected":true, ...}

curl -s localhost:8000/v1/triage/preview \
  -H 'content-type: application/json' \
  -d '{"provider":"gmail","query":"has:nouserlabels","limit":50}'
# {"dry_run":true,"receipt":"Triage receipt: ...","audit":{"protected_held":N,...}}

curl -s localhost:8000/v1/triage \
  -H 'content-type: application/json' \
  -H "authorization: Bearer $UMA_ACCOUNT_API_KEY" \
  -d '{"provider":"gmail","query":"has:nouserlabels","limit":50,"dry_run":false}'
# live run: consumes one monthly allowance run or one prepaid run credit
```

The `audit` block in a triage response is the seed of the **Compliance Evidence
Pack**: per-run proof of what was protected, what moved, and that nothing
protected left the inbox.

## Operator Summary

The operator endpoint is disabled until a local report is configured:

```bash
export UMA_OPS_REPORT_PATH=~/System/Reports/mail-triage/latest.json
export UMA_OPS_HISTORY_DIR=~/.local/state/universal-mail-automation/ops
export UMA_HISTORICAL_MAIL_PATH=~/System/Reports/mail-history/latest.json
export UMA_HISTORICAL_INTELLIGENCE_PATH=~/System/Reports/mail-history/latest-intelligence.json
export UMA_MAIL_ACTION_LEDGER_PATH=~/.local/state/universal-mail-automation/mail-action-ledger.jsonl
export UMA_MAIL_RESOLVER_LEDGER_PATH=~/.local/state/universal-mail-automation/mail-resolver-ledger.jsonl
export UMA_MAIL_DRAFT_APPROVAL_PATH=~/.local/state/universal-mail-automation/mail-draft-approvals.jsonl
export UMA_MAIL_DELIVERY_LEDGER_PATH=~/.local/state/universal-mail-automation/mail-delivery-ledger.jsonl
export UMA_OPS_MAX_AGE_HOURS=12
export UMA_OPS_TOKEN="choose-a-local-token"  # optional
uvicorn api.app:app --reload
```

Generate the redacted history first:

```bash
python cli.py ops-refresh --report "$UMA_OPS_REPORT_PATH" \
  --output-dir "$UMA_OPS_HISTORY_DIR"

# Optional: run the local read-only macOS Mail report producer first.
python cli.py ops-refresh \
  --run-mail-triage \
  --since 2026-05-01 \
  --until 2026-06-16 \
  --report-dir ~/System/Reports/mail-triage \
  --output-dir "$UMA_OPS_HISTORY_DIR"
```

Generate the private historical intelligence input separately:

```bash
python cli.py mail-history-export \
  --source ~/Library/Mail \
  --output "$UMA_HISTORICAL_MAIL_PATH" \
  --since 2024-01-01 \
  --until 2026-06-16

python cli.py mail-intel \
  --history "$UMA_HISTORICAL_MAIL_PATH" \
  --ops-report "$UMA_OPS_REPORT_PATH" \
  --output "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-action-plan \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-resolver-plan \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-provider-surface-plan \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-resolver-ledger \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-github-resolver \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-followup-resolver \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"

python cli.py mail-external-resolver \
  --intelligence "$UMA_HISTORICAL_INTELLIGENCE_PATH"
```

```bash
curl -s localhost:8000/v1/ops/summary \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/history \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/intelligence \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/action-plan \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/resolver-plan \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/provider-surface-plan \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/resolver-ledger \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/github-resolver \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/followup-resolver \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/external-resolver \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/external-resolver-receipts \
  -H "authorization: Bearer $UMA_OPS_TOKEN" \
  -H "content-type: application/json" \
  -d '{"max_items":10,"max_receipts":10,"attest_blockers":true}'

curl -s localhost:8000/v1/ops/resolver-receipts \
  -H "authorization: Bearer $UMA_OPS_TOKEN" \
  -H "content-type: application/json" \
  -d '{"action_id":"action_...","resolver_status":"verified_resolved","reason_code":"github_reconciled","proof_type":"github_issue_pr_billing_or_security_state","provider":"github"}'

curl -s localhost:8000/v1/ops/action-ledger \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/action-receipts \
  -H "authorization: Bearer $UMA_OPS_TOKEN" \
  -H "content-type: application/json" \
  -d '{"action_id":"action_...","action_status":"waiting","reason_code":"awaiting_reply"}'

curl -s 'localhost:8000/v1/ops/draft-package/action_...?ack_private=true&max_drafts=1' \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s 'localhost:8000/v1/ops/draft-approvals/action_...?ack_private=true' \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/draft-approvals/action_... \
  -H "authorization: Bearer $UMA_OPS_TOKEN" \
  -H "content-type: application/json" \
  -d '{"ack_private":true,"draft_id":"draft_...","decision":"approved","reason_code":"ready_to_send"}'

curl -s 'localhost:8000/v1/ops/delivery/action_...?ack_private=true' \
  -H "authorization: Bearer $UMA_OPS_TOKEN"

curl -s localhost:8000/v1/ops/delivery/action_... \
  -H "authorization: Bearer $UMA_OPS_TOKEN" \
  -H "content-type: application/json" \
  -d '{"ack_private":true,"draft_id":"draft_...","delivery_status":"provider_draft_requested","reason_code":"approved_for_provider_draft","provider":"gmail"}'

curl -s 'localhost:8000/v1/ops/evidence/ev_...?ack_private=true' \
  -H "authorization: Bearer $UMA_OPS_TOKEN"
```

`/v1/ops/summary` returns `uma.ops.summary.v1`, the same redacted contract
emitted by `python cli.py ops-summary`. It reports aggregate coverage, escaped
unread, action lanes, waiting lanes, closed queues, and snapshot freshness. It
does not return raw senders, email addresses, subjects, bodies, or full local
report paths.

`/v1/ops/history` returns the bounded redacted index written by
`python cli.py ops-refresh`. It records aggregate KPI/freshness history only; it
does not copy raw local reports.

`/v1/ops/intelligence` returns `uma.mail.intelligence.v1`, the same redacted
contract emitted by `python cli.py mail-intel`. It mines a local historical mail
export into redacted entities, events, missed opportunities, risks, timeline
buckets, evidence ids, controlled provider/surface hint slugs, and current
`/ops` lane reconciliation. It is read-only: no sends, labels, archive changes,
mark-read changes, or mailbox mutations.
The input export is produced by `python cli.py mail-history-export`, which writes
private `uma.mail.history_export.v1` and prints only a redacted
`uma.mail.history_export.receipt.v1` receipt.
For large histories, set `UMA_HISTORICAL_INTELLIGENCE_PATH` to a precomputed
redacted `mail-intel --output` file so the endpoint serves cached intelligence
instead of recomputing it on every dashboard load.

`/v1/ops/action-plan` returns `uma.mail.action_plan.v1`, the same redacted
contract emitted by `python cli.py mail-action-plan`. It groups findings into
priority clusters with required approval type, official-surface boundary,
sample evidence ids, controlled provider hint counts, and next action. Provider
hints are routing metadata, not provider proof. The plan does not authorize
sends or mailbox mutations.

`/v1/ops/resolver-plan` returns `uma.mail.resolver_plan.v1`, the same redacted
contract emitted by `python cli.py mail-resolver-plan`. It maps action groups
to official surfaces such as mail or LinkedIn inboxes, GitHub API/CLI/web,
provider security dashboards, billing portals, and legal review. It records
safe local preparation steps, controlled provider hints, and required proof, but
does not open portals, send, create provider drafts, or mutate mail.

`/v1/ops/provider-surface-plan` returns `uma.provider.surface_plan.v1`, the same
redacted contract emitted by `python cli.py mail-provider-surface-plan`. It
ranks controlled provider/surface hint slugs into the next provider/API/CLI
resolver frontier, including existing UMA surfaces, proof goals, blockers, and
future intake detector candidates. It is plan-only: no provider reads, portal
automation, sends, provider drafts, or mailbox mutations.

`/v1/ops/resolver-ledger` returns `uma.mail.resolver_ledger.v1`, a redacted
merge of the current resolver plan and local JSONL resolver receipts.
`/v1/ops/resolver-receipts` appends `uma.mail.resolver_receipt.v1`, which
records an operator-attested official-surface check. Resolver receipts hash
external references and remain local proof state: they do not open portals,
send, create provider drafts, archive, label, mark read, or mutate mail.

`/v1/ops/followup-resolver` returns `uma.followup.resolver_snapshot.v1`, a
redacted mail/LinkedIn follow-up snapshot over local draft approval and delivery
receipts. `/v1/ops/followup-resolver-receipts` appends resolver receipts only
when existing approval or delivery receipts provide proof. It does not read
LinkedIn, create drafts, send, archive, label, mark read, or mutate mail.

`/v1/ops/external-resolver` returns `uma.external.resolver_snapshot.v1`, a
redacted planned view of provider, security, billing, subscription, and legal
official-surface lanes with controlled provider hint counts.
`/v1/ops/external-resolver-receipts` appends local blocker attestations only
when `attest_blockers` is explicitly true. Those receipts are local proof state,
not proof that a provider portal was checked. Provider hints are not provider
reads. They do not read providers, open portals, send, archive, label, mark
read, or mutate accounts.

`/v1/ops/action-ledger` returns `uma.mail.action_ledger.v1`, a redacted merge of
the current action plan and local JSONL receipts. `/v1/ops/action-receipts`
appends `uma.mail.action_receipt.v1` records for statuses such as `waiting`,
`blocked`, or `resolved`. Receipt writes require `UMA_OPS_TOKEN`; they record
local proof only and do not send, archive, label, mark read, or change provider
state.

`/v1/ops/draft-package/{action_id}` returns `uma.mail.draft_package.v1`, a gated
private package of draft candidates and source-backed fact checks for
`missed_lead` actions requiring `draft_approval`. It requires a configured
`UMA_OPS_TOKEN`, a valid bearer token, and `ack_private=true`. Draft packages are
private and still authorize no sends or mailbox mutations.

`/v1/ops/draft-approvals/{action_id}` returns
`uma.mail.draft_approval_ledger.v1`, a redacted approval status view over a
private draft package. `POST /v1/ops/draft-approvals/{action_id}` appends
`uma.mail.draft_approval_receipt.v1`. Approval receipts are local proof only:
they do not send, create provider drafts, archive, label, mark read, or mutate
mail.

`/v1/ops/delivery/{action_id}` returns `uma.mail.delivery_ledger.v1`, a
redacted post-approval delivery-intent view over approved draft candidates.
`POST /v1/ops/delivery/{action_id}` appends
`uma.mail.delivery_receipt.v1`. Delivery receipts are local operator
attestations until a later official provider resolver proves external state:
they do not send, create provider drafts, archive, label, mark read, or mutate
mail.

`/v1/ops/evidence/{evidence_id}` returns `uma.mail.evidence_review.v1`, a gated
private source-evidence view. It requires a configured `UMA_OPS_TOKEN`, a valid
bearer token, and `ack_private=true`. It can include raw sender, address,
subject, snippet, and bounded body text for fact checking; it is not public-safe
and still authorizes no sends or mailbox mutations.

`/ops` is the private control-tower UI for that payload. It is separate from
`/app`, which remains the public product/safety-proof dashboard.
