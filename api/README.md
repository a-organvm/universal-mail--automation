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
