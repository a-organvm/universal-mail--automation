"""Signed, re-derivable audit receipts — the product's headline trust artifact.

``core.audit`` already produces an INDEPENDENT receipt: it re-derives protection
from a separate code path and refuses to report success if a protected sender left
the inbox. This module makes that receipt:

  * **addressable** — every triage run gets a ``run_id`` and its receipt is
    persisted to the ledger, retrievable at ``GET /v1/audit/{run_id}``;
  * **tamper-evident** — the receipt body is signed with HMAC-SHA256 so a third
    party (or an auditing agent) can verify it was issued by this server and not
    altered after the fact. The verifier (:func:`verify`) is exported so it can
    run standalone / open-source, which is the whole point of an *independent*
    receipt.

No PII crosses this boundary: the signed body carries only counts + the one-line
human receipt + provider/dry_run (the engine's ``summary()`` already excludes
sender addresses). The signing KEY comes from ``RECEIPT_SIGNING_KEY`` (a deploy
secret); if unset we generate an ephemeral per-process key so dev/test always
work, and warn once that cross-restart verification needs the env key. The key is
never returned to a client — only the signature is.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from api.store import get_store

logger = logging.getLogger(__name__)

SIGNATURE_ALGORITHM = "HMAC-SHA256"

_EPHEMERAL_KEY: Optional[bytes] = None


def _signing_key() -> bytes:
    """The HMAC key from RECEIPT_SIGNING_KEY, or a stable ephemeral process key."""
    global _EPHEMERAL_KEY
    env = os.environ.get("RECEIPT_SIGNING_KEY")
    if env:
        return env.encode("utf-8")
    if _EPHEMERAL_KEY is None:
        _EPHEMERAL_KEY = secrets.token_bytes(32)
        logger.warning(
            "RECEIPT_SIGNING_KEY is not set; using an ephemeral signing key. "
            "Receipts signed now will not verify after a restart — set "
            "RECEIPT_SIGNING_KEY as a deploy secret for durable verification."
        )
    return _EPHEMERAL_KEY


def _canonical(body: Dict[str, Any]) -> bytes:
    """Deterministic JSON encoding so the signature is reproducible regardless of
    key ordering (sort_keys) or incidental whitespace."""
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(body: Dict[str, Any]) -> str:
    """HMAC-SHA256 signature (hex) over the canonical receipt body."""
    return hmac.new(_signing_key(), _canonical(body), hashlib.sha256).hexdigest()


def verify(body: Dict[str, Any], signature: str) -> bool:
    """Constant-time verification that ``signature`` matches ``body``."""
    expected = sign(body)
    return hmac.compare_digest(expected, signature or "")


def signed_body(run_id: str, triage_result: Dict[str, Any]) -> Dict[str, Any]:
    """Build the canonical, PII-free receipt body that gets signed + stored."""
    return {
        "run_id": run_id,
        "provider": triage_result.get("provider"),
        "dry_run": bool(triage_result.get("dry_run")),
        "summary": triage_result.get("audit"),  # counts only, no senders
        "receipt_line": triage_result.get("receipt"),
    }


def persist(
    run_id: str, triage_result: Dict[str, Any], account_id: Optional[str] = None
) -> str:
    """Sign + persist the receipt for a completed triage run. Best-effort: a ledger
    write failure must never turn a safe, gate-respecting run into an error
    (the safety invariant was already asserted upstream), so we log and move on."""
    body = signed_body(run_id, triage_result)
    signature = sign(body)
    try:
        get_store().save_receipt(
            run_id=run_id,
            summary=body["summary"] or {},
            provider=body["provider"],
            dry_run=body["dry_run"],
            receipt_line=body["receipt_line"] or "",
            signature=signature,
            account_id=account_id,
        )
    except Exception as e:  # ledger is a convenience, not the safety boundary
        logger.warning("receipt ledger write failed for %s: %s", run_id, e)
    return signature


router = APIRouter(tags=["receipts"])


@router.get("/v1/audit/{run_id}")
def get_receipt(run_id: str) -> dict:
    """Fetch a signed, re-derivable audit receipt by run id.

    The response is everything a third party needs to verify independently: the
    exact signed body, the signature, and the algorithm. Recompute
    HMAC-SHA256(canonical_json(body), RECEIPT_SIGNING_KEY) and compare.
    """
    rec = get_store().get_receipt(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="receipt not found")
    body = {
        "run_id": rec["run_id"],
        "provider": rec["provider"],
        "dry_run": rec["dry_run"],
        "summary": rec["summary"],
        "receipt_line": rec["receipt_line"],
    }
    return {
        "run_id": rec["run_id"],
        "signed_body": body,
        "signature": rec["signature"],
        "algorithm": SIGNATURE_ALGORITHM,
        "verify": (
            "HMAC-SHA256 over JSON.dumps(signed_body, sort_keys=True, "
            "separators=(',',':')) with the server's RECEIPT_SIGNING_KEY."
        ),
        "created_at": rec["created_at"],
    }
