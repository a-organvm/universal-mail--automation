"""Durable identity + ledger store backing billing, metering, ACP, and receipts.

The triage engine has always been stateless-per-run (JSON files for crash
recovery only). The *commercial* surfaces, however, need durable, idempotent
state that survives restarts and tolerates Stripe's at-least-once webhook
redelivery:

  * which Stripe customer maps to which account, and what plan/status they hold
    (the access-grant source of truth);
  * which webhook event ids we have already processed (so a redelivery can never
    double-grant or double-credit — the replay risk the fail-closed ethos exists
    to prevent);
  * the signed audit-receipt ledger (``GET /v1/audit/{run_id}``);
  * the ACP idempotency-key replay store (the protocol *requires* dedup).

SQLite (stdlib, zero new dependencies) is the right floor: a single file with
atomic transactions and ``UNIQUE``/``PRIMARY KEY`` dedup. Every method goes
through this one class, so swapping to Postgres later is a one-file change rather
than a grep across the codebase.

The store holds exactly ONE connection guarded by a lock. That is deliberate: the
API is a single process, writes are tiny and infrequent (a checkout, a webhook, a
receipt), and a serialized writer removes every SQLite "database is locked" race
without the complexity of a pool. WAL mode keeps reads concurrent with the writer.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

# Default on-disk location. Kept under data/ which is gitignored (see .gitignore):
# this file holds customer ids and api keys and must never be committed.
DEFAULT_DB_PATH = os.environ.get("MAIL_DB_PATH", "data/app.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id                    TEXT PRIMARY KEY,
    email                 TEXT,
    stripe_customer_id    TEXT UNIQUE,
    stripe_subscription_id TEXT,
    plan                  TEXT NOT NULL DEFAULT 'free',
    status                TEXT NOT NULL DEFAULT 'active',
    current_period_end    INTEGER,
    api_key               TEXT UNIQUE,
    run_credits           INTEGER NOT NULL DEFAULT 0,
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id    TEXT PRIMARY KEY,
    type        TEXT,
    received_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    run_id       TEXT PRIMARY KEY,
    account_id   TEXT,
    provider     TEXT,
    dry_run      INTEGER NOT NULL,
    summary_json TEXT NOT NULL,
    receipt_line TEXT,
    signature    TEXT,
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key           TEXT PRIMARY KEY,
    scope         TEXT NOT NULL,
    request_hash  TEXT NOT NULL,
    response_json TEXT,
    status        TEXT NOT NULL,           -- 'processing' | 'done'
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS acp_sessions (
    id         TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    currency   TEXT,
    account_id TEXT,
    data_json  TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS acp_fulfillments (
    session_id   TEXT PRIMARY KEY,
    account_id   TEXT,
    runs         INTEGER NOT NULL,
    fulfilled_at REAL NOT NULL
);
"""

# A request that crashed while holding an idempotency key would otherwise leave it
# stuck in 'processing' and block every retry (a self-inflicted DoS). After this
# window we treat a 'processing' entry as abandoned and let a retry re-claim it.
IDEMPOTENCY_PROCESSING_TIMEOUT = 60.0  # seconds


def _now() -> float:
    return time.time()


def new_api_key() -> str:
    """A URL-safe API key. ``uma_`` prefix makes leaks greppable in logs/scanners."""
    return "uma_" + secrets.token_urlsafe(32)


class Store:
    """A thread-safe SQLite-backed store. One connection, one lock, WAL reads."""

    def __init__(self, path: str = DEFAULT_DB_PATH):
        self.path = path
        if path != ":memory:":
            parent = os.path.dirname(os.path.abspath(path))
            if parent:
                os.makedirs(parent, exist_ok=True)
        # check_same_thread=False because FastAPI/Starlette may dispatch sync
        # endpoints on a threadpool; the lock below serializes all access so this
        # is safe (a single shared connection, never touched concurrently).
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            # WAL allows readers to proceed during the single writer. Harmless on
            # :memory: (silently ignored there).
            try:
                self._conn.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.Error:
                pass
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- accounts -----------------------------------------------------------
    def create_account(
        self,
        *,
        account_id: Optional[str] = None,
        email: Optional[str] = None,
        plan: str = "free",
        status: str = "active",
        api_key: Optional[str] = None,  # allow-secret: param declaration, not a value
        run_credits: int = 0,
    ) -> Dict[str, Any]:
        account_id = account_id or ("acct_" + secrets.token_hex(12))
        api_key = api_key or new_api_key()  # allow-secret: generated, not a literal
        now = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO accounts (id, email, plan, status, api_key, "
                "run_credits, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (account_id, email, plan, status, api_key, run_credits, now, now),
            )
            self._conn.commit()
        return self.get_account(account_id)  # type: ignore[return-value]

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        return self._fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))

    def get_account_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:  # allow-secret: param name
        if not api_key:
            return None
        return self._fetch_one(
            "SELECT * FROM accounts WHERE api_key = ?", (api_key,)  # allow-secret: SQL placeholder
        )

    def get_account_by_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return self._fetch_one(
            "SELECT * FROM accounts WHERE stripe_customer_id = ?", (customer_id,)
        )

    def link_customer(self, account_id: str, customer_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET stripe_customer_id = ?, updated_at = ? "
                "WHERE id = ?",
                (customer_id, _now(), account_id),
            )
            self._conn.commit()

    def set_subscription(
        self,
        *,
        account_id: str,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        plan: Optional[str] = None,
        status: Optional[str] = None,
        current_period_end: Optional[int] = None,
    ) -> None:
        """Apply a subscription state change. Only non-None fields are written, so
        a partial event (e.g. an invoice.paid that only refreshes period_end)
        never clobbers fields it does not carry."""
        sets: List[str] = ["updated_at = ?"]
        vals: List[Any] = [_now()]
        for col, val in (
            ("stripe_customer_id", customer_id),
            ("stripe_subscription_id", subscription_id),
            ("plan", plan),
            ("status", status),
            ("current_period_end", current_period_end),
        ):
            if val is not None:
                sets.append(f"{col} = ?")
                vals.append(val)
        vals.append(account_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE accounts SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()

    def add_credits(self, account_id: str, n: int) -> int:
        """Add ``n`` run-credits (ACP credit-pack fulfillment). Returns new balance."""
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET run_credits = run_credits + ?, updated_at = ? "
                "WHERE id = ?",
                (int(n), _now(), account_id),
            )
            self._conn.commit()
        acct = self.get_account(account_id)
        return int(acct["run_credits"]) if acct else 0

    def consume_credit(self, account_id: str, n: int = 1) -> bool:
        """Atomically debit ``n`` credits iff the balance covers it. The UPDATE's
        WHERE clause makes the check-and-debit a single statement, so two
        concurrent runs can never both pass an over-the-balance check."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE accounts SET run_credits = run_credits - ?, updated_at = ? "
                "WHERE id = ? AND run_credits >= ?",
                (int(n), _now(), account_id, int(n)),
            )
            self._conn.commit()
            return cur.rowcount > 0

    # -- webhook dedup ------------------------------------------------------
    def mark_event_processed(self, event_id: str, event_type: str = "") -> bool:
        """Record a webhook event id. Returns True if this is the FIRST time we've
        seen it (caller should process), False if it's a redelivery (caller must
        skip). ``INSERT OR IGNORE`` + rowcount makes this atomic."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO webhook_events (event_id, type, received_at) "
                "VALUES (?,?,?)",
                (event_id, event_type, _now()),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def is_event_processed(self, event_id: str) -> bool:
        """Return True when a webhook event id has already completed handling."""
        return self._fetch_one(
            "SELECT event_id FROM webhook_events WHERE event_id = ?", (event_id,)
        ) is not None

    # -- receipts -----------------------------------------------------------
    def save_receipt(
        self,
        *,
        run_id: str,
        summary: Dict[str, Any],
        provider: Optional[str],
        dry_run: bool,
        receipt_line: str,
        signature: str,
        account_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO receipts (run_id, account_id, provider, "
                "dry_run, summary_json, receipt_line, signature, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    run_id, account_id, provider, 1 if dry_run else 0,
                    json.dumps(summary), receipt_line, signature, _now(),
                ),
            )
            self._conn.commit()

    def get_receipt(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetch_one("SELECT * FROM receipts WHERE run_id = ?", (run_id,))
        if row is None:
            return None
        row["summary"] = json.loads(row.pop("summary_json"))
        row["dry_run"] = bool(row["dry_run"])
        return row

    def list_receipts(
        self, account_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        rows = self._fetch_all(
            "SELECT run_id, provider, dry_run, receipt_line, created_at "
            "FROM receipts WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, int(limit)),
        )
        for r in rows:
            r["dry_run"] = bool(r["dry_run"])
        return rows

    # -- idempotency (ACP) --------------------------------------------------
    def idempotency_begin(
        self, key: str, scope: str, request_hash: str
    ) -> Dict[str, Any]:
        """Claim an idempotency key. Returns one of:
            {"state": "new"}                         -> proceed, then _complete
            {"state": "processing"}                  -> a concurrent request holds it (409)
            {"state": "conflict"}                    -> same key, different payload (422)
            {"state": "replay", "response": {...}}   -> already done, return stored response
        """
        with self._lock:
            existing = self._fetch_one_nolock(
                "SELECT * FROM idempotency_keys WHERE key = ?", (key,)
            )
            if existing is None:
                self._conn.execute(
                    "INSERT INTO idempotency_keys (key, scope, request_hash, "
                    "status, created_at) VALUES (?,?,?,?,?)",
                    (key, scope, request_hash, "processing", _now()),
                )
                self._conn.commit()
                return {"state": "new"}
            if existing["status"] == "processing":
                # Stale (crashed) claim -> let this request re-claim it, rebinding
                # to the current payload. Prevents a permanent 409 lockout.
                if _now() - existing["created_at"] > IDEMPOTENCY_PROCESSING_TIMEOUT:
                    self._conn.execute(
                        "UPDATE idempotency_keys SET request_hash = ?, "
                        "created_at = ? WHERE key = ?",
                        (request_hash, _now(), key),
                    )
                    self._conn.commit()
                    return {"state": "new"}
                if existing["request_hash"] != request_hash:
                    return {"state": "conflict"}
                return {"state": "processing"}
            if existing["request_hash"] != request_hash:
                return {"state": "conflict"}
            return {
                "state": "replay",
                "response": json.loads(existing["response_json"] or "null"),
            }

    def idempotency_complete(self, key: str, response: Any) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE idempotency_keys SET status = 'done', response_json = ? "
                "WHERE key = ?",
                (json.dumps(response), key),
            )
            self._conn.commit()

    # -- ACP fulfillment (exactly-once credit per session) ------------------
    def fulfill_once(self, session_id: str, account_id: str, runs: int) -> bool:
        """Credit ``runs`` to ``account_id`` for ``session_id`` AT MOST ONCE.

        The INSERT-or-IGNORE on the session id and the balance UPDATE run in one
        locked transaction, so two concurrent completions of the same checkout
        session credit the buyer exactly once. Returns True if this call applied
        the credit, False if the session was already fulfilled (idempotent replay).
        Combined with a per-session Stripe charge key, ``/complete`` is fully
        retry-safe: a crash mid-flight is recovered by simply retrying."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO acp_fulfillments (session_id, account_id, "
                "runs, fulfilled_at) VALUES (?,?,?,?)",
                (session_id, account_id, int(runs), _now()),
            )
            if cur.rowcount == 0:
                self._conn.commit()
                return False  # already fulfilled
            self._conn.execute(
                "UPDATE accounts SET run_credits = run_credits + ?, updated_at = ? "
                "WHERE id = ?",
                (int(runs), _now(), account_id),
            )
            self._conn.commit()
            return True

    def get_fulfillment(self, session_id: str) -> Optional[Dict[str, Any]]:
        """The fulfillment row for ``session_id``, or None if never fulfilled.

        Existence means the credit was committed: the session's money state is
        no longer mutable (update/cancel are refused by the ACP router)."""
        return self._fetch_one(
            "SELECT * FROM acp_fulfillments WHERE session_id = ?", (session_id,))

    # -- ACP sessions -------------------------------------------------------
    def save_session(
        self,
        *,
        session_id: str,
        status: str,
        currency: Optional[str],
        data: Dict[str, Any],
        account_id: Optional[str] = None,
    ) -> None:
        now = _now()
        with self._lock:
            existing = self._fetch_one_nolock(
                "SELECT created_at FROM acp_sessions WHERE id = ?", (session_id,)
            )
            created = existing["created_at"] if existing else now
            self._conn.execute(
                "INSERT OR REPLACE INTO acp_sessions (id, status, currency, "
                "account_id, data_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (session_id, status, currency, account_id, json.dumps(data),
                 created, now),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetch_one(
            "SELECT * FROM acp_sessions WHERE id = ?", (session_id,)
        )
        if row is None:
            return None
        row["data"] = json.loads(row.pop("data_json"))
        return row

    # -- helpers ------------------------------------------------------------
    def _fetch_one(self, sql: str, params: tuple) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._fetch_one_nolock(sql, params)

    def _fetch_one_nolock(self, sql: str, params: tuple) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def _fetch_all(self, sql: str, params: tuple) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


# -- module singleton (injectable for tests) --------------------------------
_STORE: Optional[Store] = None
_STORE_LOCK = threading.Lock()


def get_store() -> Store:
    """Return the process-wide store, creating it on first use from MAIL_DB_PATH."""
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = Store(os.environ.get("MAIL_DB_PATH", DEFAULT_DB_PATH))
    return _STORE


def set_store(store: Optional[Store]) -> None:
    """Inject a store (tests) or clear it (pass None) so the next get_store()
    rebuilds from the current MAIL_DB_PATH."""
    global _STORE
    with _STORE_LOCK:
        _STORE = store
