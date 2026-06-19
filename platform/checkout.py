"""platform/checkout.py — the ``license-issued`` webhook receiver.

Pairs with ``core/license.py``: the checkout platform (the storefront that sells
seats) POSTs a signed ``license-issued`` event here the moment a purchase clears.
This receiver verifies the signature and then writes the granted license to
``~/.config/mail_automation/license.json`` — the file ``core/license.py`` reads to
unlock paid behaviour on this host.

**No Stripe SDK.** The signature is a plain HMAC-SHA256 over the RAW request body,
keyed by the shared secret ``LICENSE_WEBHOOK_SECRET``. The posture mirrors the
Stripe webhook in ``api/billing.py`` — *fail-closed*:

  * secret unset             -> 503 (receiver not configured; nothing written)
  * missing / unverified sig -> 400, and NOTHING is written. An unverified body
                                never grants a license — same rule as the audit
                                gate: an unproven claim is denied.
  * verified but unparseable -> 400 (nothing written)
  * verified + parseable     -> license persisted at 0600, 200

The signature is read from ``X-Signature-256`` (GitHub-style ``sha256=<hex>``);
``X-License-Signature`` is accepted as an alias, and a bare hex digest (no prefix)
is tolerated. Verification is constant-time.

Mount on any FastAPI app::

    from platform import checkout
    app.include_router(checkout.router)
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["checkout"])

# Env var holding the shared secret the storefront signs each delivery with.
SECRET_ENV = "LICENSE_WEBHOOK_SECRET"  # noqa: S105 - env var name, not a secret

# Where the verified license lands. ``core/license.py`` reads this same path.
DEFAULT_LICENSE_PATH = Path("~/.config/mail_automation/license.json").expanduser()

# Signature headers we honour, in priority order.
_SIGNATURE_HEADERS = ("x-signature-256", "x-license-signature")


def _expected_signature(secret: str, body: bytes) -> str:
    """Hex HMAC-SHA256 of the RAW body under ``secret``."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _read_signature(request: Request) -> Optional[str]:
    """Pull the provided hex digest from the request, stripping any ``sha256=``
    prefix. Returns ``None`` when no signature header is present."""
    for header in _SIGNATURE_HEADERS:
        raw = request.headers.get(header)
        if raw:
            return raw.split("=", 1)[1] if raw.startswith("sha256=") else raw
    return None


def verify_signature(secret: str, body: bytes, provided: Optional[str]) -> bool:
    """Constant-time check that ``provided`` is the HMAC-SHA256 of ``body``.

    Returns ``False`` for a missing or malformed signature rather than raising —
    the caller turns a ``False`` into a 400 that grants nothing.
    """
    if not provided:
        return False
    return hmac.compare_digest(_expected_signature(secret, body), provided)


def write_license(payload: dict, path: Optional[Path] = None) -> Path:
    """Persist a verified license ``payload`` atomically at ``path`` (0600).

    The write is atomic (temp file in the same directory + ``os.replace``) so a
    concurrent reader in ``core/license.py`` never observes a half-written file,
    and the file is owner-only since a license is a credential.
    """
    target = Path(path or DEFAULT_LICENSE_PATH).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")

    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".license-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    return target


@router.post("/webhook/license-issued")
async def license_issued(request: Request) -> dict:
    """Receive a signed ``license-issued`` event and persist the license.

    Signature-verified over the RAW body, fail-closed, and never grants on an
    unverified or unparseable payload.
    """
    secret = os.environ.get(SECRET_ENV)
    if not secret:
        # Receiver isn't configured on this host — same 503 contract as billing.
        raise HTTPException(status_code=503, detail="license webhook is not configured")

    # RAW body — verifying re-serialized JSON would silently never match.
    body = await request.body()
    if not verify_signature(secret, body, _read_signature(request)):
        # Do not echo the reason; an unverified body grants nothing.
        raise HTTPException(status_code=400, detail="invalid signature")

    try:
        payload = json.loads(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="payload is not valid JSON") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    try:
        path = write_license(payload)
    except OSError as e:
        logger.error("failed to write license: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="could not persist license") from e

    logger.info("license-issued accepted; wrote %s", path)
    return {"received": True}
