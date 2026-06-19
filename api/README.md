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
auth is not yet implemented; account-level API access uses issued account API
keys (`Authorization: Bearer ...`).

## Account API keys

Account API keys live in the durable app store at `MAIL_DB_PATH` (default:
`data/app.db`, already gitignored). Operators issue keys through
`POST /v1/auth/api-keys`, which is gated by `UMA_API_KEY_ISSUER_TOKEN`. Load that
issuer token from your secret manager / 1Password-backed environment; never write
it into the repo or a checked-in `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `MAIL_DB_PATH` | SQLite account/API-key, billing, usage, and receipt store | `data/app.db` |
| `UMA_API_KEY_ISSUER_TOKEN` | Operator secret required to issue account API keys | *(required for issuance)* |

Generated account keys are returned only at issuance time or by public checkout
when it creates a new account. Verification endpoints intentionally return
account metadata and entitlements, not the key itself.

## Endpoints

| Method | Path | Purpose | Needs mailbox |
|---|---|---|---|
| GET | `/health` | Liveness | no |
| POST | `/v1/auth/api-keys` | Issue an account API key; requires issuer token | no |
| GET | `/v1/auth/verify` | Verify `Authorization: Bearer <account_api_key>` | no |
| POST | `/v1/senders/check` | Is this sender protected? + categorization | no |
| POST | `/v1/triage/preview` | Dry-run: disposition + receipt, nothing touched | yes; account key required |
| POST | `/v1/triage` | Run triage; fail-closed | yes; account key required |
| GET | `/v1/billing/plans` | Public pricing catalog | no |
| GET | `/v1/billing/usage` | Runs used this period + remaining headroom + upgrade hint | yes; account key required |

Mailbox-reading triage endpoints require
`Authorization: Bearer <account_api_key>`. Live runs (`dry_run:false`) reserve one
monthly-plan run before touching the mailbox; if the plan cap is exhausted, they
consume one prepaid run credit. Failed runs refund the reservation. Dry-runs are
authenticated and receipt-attributed, but not metered.

### Examples

```bash
curl -s localhost:8000/v1/senders/check \
  -H 'content-type: application/json' \
  -d '{"sender":"clerk@courts.ca.gov"}'
# {"sender":"clerk@courts.ca.gov","protected":true, ...}

curl -s localhost:8000/v1/auth/api-keys \
  -H 'content-type: application/json' \
  -H "x-uma-issuer-token: $UMA_API_KEY_ISSUER_TOKEN" \
  -d '{"email":"buyer@example.com","plan":"free"}'
# {"account_id":"acct_...","api_key":"uma_...","plan":"free", ...}

curl -s localhost:8000/v1/auth/verify \
  -H "authorization: Bearer $UMA_ACCOUNT_API_KEY"
# {"authenticated":true,"account_id":"acct_...","entitlements":{...}, ...}

curl -s localhost:8000/v1/billing/usage \
  -H "authorization: Bearer $UMA_ACCOUNT_API_KEY"
# {"plan":"free","live_runs_used":48,"monthly_run_cap":50,"runs_remaining":2,
#  "near_limit":true,"upgrade":{"id":"pro","price_display":"$19/mo"}, ...}

curl -s localhost:8000/v1/triage/preview \
  -H 'content-type: application/json' \
  -H "authorization: Bearer $UMA_ACCOUNT_API_KEY" \
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
