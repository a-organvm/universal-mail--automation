# Universal Mail Automation API Documentation

Welcome to the Universal Mail Automation API! This API allows you to safely triage your mailbox, check sender statuses, and retrieve audit receipts of the actions performed. Our core promise is **provable restraint**: the API never bypasses our protected-sender gate, ensuring important emails are never accidentally archived or moved out of your inbox.

## Base URL

All API requests should be made to your instance URL (e.g. `http://127.0.0.1:8000` locally, or your deployed URL).

## Authentication

Live runs that modify your mailbox require authentication. You must provide your account API key in the `Authorization` header.

```http
Authorization: Bearer <your_account_api_key>
```

Dry-runs (`/v1/triage/preview` or `/v1/triage` with `dry_run: true`), health checks, checking sender status, and listing billing plans do not require an API key.

## Endpoints

### Health Check

Check the liveness of the API.

**Endpoint:** `GET /health`

**Authentication:** None

**Example Request:**
```bash
curl -s http://127.0.0.1:8000/health
```

**Example Response:**
```json
{
  "status": "ok",
  "service": "universal-mail-automation",
  "version": "1.0.0"
}
```

---

### Check Sender Status

Determine if a specific sender is protected (meaning they will never be archived by the automation) and see how they are categorized.

**Endpoint:** `POST /v1/senders/check`

**Authentication:** None

**Request Body:**
```json
{
  "sender": "clerk@courts.ca.gov",
  "subject": "Notice of Hearing"
}
```

**Example Request:**
```bash
curl -s http://127.0.0.1:8000/v1/senders/check \
  -H 'Content-Type: application/json' \
  -d '{"sender":"clerk@courts.ca.gov","subject":"Notice of Hearing"}'
```

**Example Response:**
```json
{
  "sender": "clerk@courts.ca.gov",
  "protected": true,
  "categorization": {
    "tier": 1,
    "label": "T1-Important",
    "reason": "Known court domain"
  }
}
```

---

### Triage Preview (Dry-Run)

Simulate a triage run to see what *would* happen without actually touching your mailbox. It shows the planned disposition and provides an audit receipt.

**Endpoint:** `POST /v1/triage/preview`

**Authentication:** None

**Request Body:**
```json
{
  "provider": "gmail",
  "query": "has:nouserlabels",
  "limit": 50
}
```

- `provider`: (e.g. `"gmail"`, `"imap"`)
- `query`: The search query for emails to process.
- `limit`: Number of emails to process (1-1000).
- `remove_label`: Optional label to remove when processing.
- `tier_routing`: Optional boolean.
- `vip_only`: Optional boolean.

**Example Request:**
```bash
curl -s http://127.0.0.1:8000/v1/triage/preview \
  -H 'Content-Type: application/json' \
  -d '{"provider":"gmail","query":"has:nouserlabels","limit":50}'
```

**Example Response:**
```json
{
  "dry_run": true,
  "provider": "gmail",
  "receipt": "Triage preview receipt...",
  "audit": {
    "total": 50,
    "protected_held": 2,
    "archived": 48,
    "moved": 0,
    "labeled": 0,
    "kept": 2,
    "violations": []
  },
  "processed": null,
  "run_id": null
}
```

---

### Run Triage

Execute a triage run to organize and archive emails based on rules. The API guarantees safety by running through the protected-sender gate. If a protected sender is somehow scheduled to be moved out of the inbox, the run will fail-closed and return an HTTP 500.

**Endpoint:** `POST /v1/triage`

**Authentication:** Required for live runs (`Bearer <your_account_api_key>`).

**Billing:** Live runs consume one monthly-plan run. If the plan cap is exhausted, it consumes one prepaid run credit. Failed runs are not charged.

**Request Body:** Same as `/v1/triage/preview`, but with `dry_run: false`.
```json
{
  "provider": "gmail",
  "query": "has:nouserlabels",
  "limit": 50,
  "dry_run": false
}
```

**Example Request:**
```bash
curl -s http://127.0.0.1:8000/v1/triage \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer YOUR_ACCOUNT_API_KEY" \
  -d '{"provider":"gmail","query":"has:nouserlabels","limit":50,"dry_run":false}'
```

**Example Response:**
```json
{
  "dry_run": false,
  "provider": "gmail",
  "receipt": "Triage run completed successfully...",
  "audit": {
    "total": 50,
    "protected_held": 2,
    "archived": 48,
    "moved": 0,
    "labeled": 0,
    "kept": 2,
    "violations": []
  },
  "processed": [...],
  "run_id": "run_abc123"
}
```

*Note: In the event of a safety gate violation (a protected sender being moved out of the inbox), the API will return an HTTP 500 Error with the message "SAFETY GATE VIOLATION: a protected sender was moved out of the inbox; the run was rejected."*

---

### Audit Receipt

Fetch the signed, re-derivable audit receipt for a given run. The audit block is the seed of the **Compliance Evidence Pack**, providing proof of what was protected and what was moved. Receipts are signed with HMAC-SHA256 to be tamper-evident.

**Endpoint:** `GET /v1/audit/{run_id}`

**Authentication:** None (Wait, or is it required? Publicly readable or not? Read endpoints are currently just `get_store().get_receipt(run_id)`. The code doesn't enforce auth).

**Example Request:**
```bash
curl -s http://127.0.0.1:8000/v1/audit/run_abc123
```

**Example Response:**
```json
{
  "run_id": "run_abc123",
  "signed_body": {
    "run_id": "run_abc123",
    "provider": "gmail",
    "dry_run": false,
    "summary": {
      "total": 50,
      "protected_held": 2,
      "archived": 48,
      "moved": 0,
      "labeled": 0,
      "kept": 2,
      "violations": []
    },
    "receipt_line": "Triage run completed successfully..."
  },
  "signature": "abcdef123456...",
  "algorithm": "HMAC-SHA256",
  "verify": "HMAC-SHA256 over JSON.dumps(signed_body, sort_keys=True, separators=(',',':')) with the server's RECEIPT_SIGNING_KEY.",
  "created_at": "2024-01-01T12:00:00Z"
}
```

---

### Billing and Subscriptions

Manage your subscription and plans.

#### Get Available Plans
Returns the public pricing catalog. No credentials needed.

**Endpoint:** `GET /v1/billing/plans`

**Authentication:** None

**Example Request:**
```bash
curl -s http://127.0.0.1:8000/v1/billing/plans
```

#### Checkout Session
Initiate a Stripe checkout session to purchase a plan (e.g., `pro` or `business`). Returns the redirect URL to complete checkout.

**Endpoint:** `POST /v1/billing/checkout`

**Authentication:** If `account_id` is provided, you must provide your `Authorization: Bearer` key matching that account. Otherwise, a new account will be created automatically.

**Request Body:**
```json
{
  "plan": "pro",
  "email": "user@example.com",
  "success_url": "https://myapp.com/success",
  "cancel_url": "https://myapp.com/cancel"
}
```

**Example Request:**
```bash
curl -X POST http://127.0.0.1:8000/v1/billing/checkout \
  -H 'Content-Type: application/json' \
  -d '{"plan":"pro","email":"user@example.com"}'
```

#### Billing Portal
Generate a link to the Stripe customer billing portal to manage your subscription.

**Endpoint:** `POST /v1/billing/portal`

**Authentication:** Required (`Bearer <your_account_api_key>`).

**Request Body:**
```json
{
  "return_url": "https://myapp.com/dashboard"
}
```

**Example Request:**
```bash
curl -X POST http://127.0.0.1:8000/v1/billing/portal \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer YOUR_ACCOUNT_API_KEY" \
  -d '{}'
```

## Limits and Constraints
- The `limit` parameter in triage requests determines the maximum number of emails to process in that run (max `1000`).
- If you exhaust your entitlement (monthly run limit without prepaid credits), the API returns HTTP 402 Payment Required.
- If the mailbox provider is unavailable or fails, the API returns HTTP 503.
- Unauthenticated live runs return HTTP 401.
