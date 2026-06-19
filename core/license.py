"""HMAC-signed license validation and tier entitlements."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Mapping, Optional

DEFAULT_PRODUCT_ID = "universal-mail-automation"
LICENSE_KEY_ENV = "UMAIL_LICENSE_KEY"
LICENSE_SECRET_ENV = "UMAIL_LICENSE_SECRET"
LEGACY_LICENSE_SECRET_ENV = "LICENSE_SIGNING_KEY"
KEY_PREFIX = "uma1"

FREE_TIER = "free"
PRO_TIER = "pro"
VALID_TIERS = {FREE_TIER, PRO_TIER}
FREE_DAILY_MESSAGE_CAP = 100


class LicenseError(ValueError):
    """Raised when a license key cannot be trusted."""


@dataclass(frozen=True)
class License:
    """Validated license payload plus derived CLI entitlements."""

    product_id: str
    email: str
    tier: str
    expiry: Optional[str] = None

    @property
    def is_pro(self) -> bool:
        return self.tier == PRO_TIER

    @property
    def allowed_providers(self) -> Optional[set[str]]:
        if self.is_pro:
            return None
        return {"gmail"}

    @property
    def daily_message_cap(self) -> Optional[int]:
        if self.is_pro:
            return None
        return FREE_DAILY_MESSAGE_CAP


FREE_LICENSE = License(
    product_id=DEFAULT_PRODUCT_ID,
    email="",
    tier=FREE_TIER,
    expiry=None,
)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise LicenseError("license key contains invalid base64") from exc


def _canonical_payload(
    product_id: str,
    email: str,
    tier: str,
    expiry: str,
) -> bytes:
    return "|".join((product_id, email.lower(), tier.lower(), expiry)).encode("utf-8")


def _signature(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return _b64url_encode(digest)


def _signature_matches(signature: str, payload: bytes, secret: str) -> bool:
    expected = _signature(payload, secret)
    expected_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected) or hmac.compare_digest(
        signature.lower(), expected_hex
    )


def _parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        if "T" in value:
            dt = datetime.fromisoformat(value)
        else:
            dt = datetime.combine(date.fromisoformat(value), datetime.max.time())
    except ValueError as exc:
        raise LicenseError("license expiry must be ISO-8601") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_payload(payload: Mapping[str, object]) -> tuple[str, str, str, str]:
    product_id = str(payload.get("product_id") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    tier = str(payload.get("tier") or "").strip().lower()
    expiry = str(payload.get("expiry") or payload.get("expires") or "").strip()
    if not product_id or not email or not tier or not expiry:
        raise LicenseError("license key is missing product_id, email, tier, or expiry")
    return product_id, email, tier, expiry


def _validate_fields(
    product_id: str,
    email: str,
    tier: str,
    expiry: str,
    *,
    expected_product_id: str,
    now: Optional[datetime],
) -> License:
    if product_id != expected_product_id:
        raise LicenseError("license product does not match this application")
    if tier not in VALID_TIERS:
        raise LicenseError("license tier must be free or pro")

    expiry_dt = _parse_expiry(expiry)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if expiry_dt is not None and expiry_dt < current.astimezone(timezone.utc):
        raise LicenseError("license key has expired")

    return License(product_id=product_id, email=email, tier=tier, expiry=expiry)


def validate_license_key(
    key: str,
    secret: str,
    *,
    expected_product_id: str = DEFAULT_PRODUCT_ID,
    now: Optional[datetime] = None,
) -> License:
    """Validate an HMAC license key.

    Preferred key format:
        ``uma1.<base64url-json-payload>.<base64url-hmac-sha256>``

    The signed JSON payload must contain ``product_id``, ``email``, ``tier``,
    and ``expiry``. For operational compatibility this also accepts a compact
    pipe-delimited form:
        ``product_id|email|tier|expiry|signature``

    In both formats the HMAC input is the canonical
    ``product_id|email|tier|expiry`` byte string.
    """
    if not key or not key.strip():
        raise LicenseError("license key is empty")
    if not secret:
        raise LicenseError("license signing secret is not configured")

    raw = key.strip()
    alternate_payload_bytes = None
    if raw.startswith(f"{KEY_PREFIX}."):
        parts = raw.split(".")
        if len(parts) != 3:
            raise LicenseError("license key format is invalid")
        _, payload_part, signature = parts
        try:
            payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LicenseError("license payload is invalid JSON") from exc
        product_id, email, tier, expiry = _coerce_payload(payload)
    else:
        delimiter = "|"
        parts = raw.split(delimiter)
        if len(parts) != 5:
            delimiter = "+"
            parts = raw.split(delimiter)
        if len(parts) != 5:
            raise LicenseError("license key format is invalid")
        product_id, email, tier, expiry, signature = [part.strip() for part in parts]
        product_id, email, tier, expiry = _coerce_payload(
            {
                "product_id": product_id,
                "email": email,
                "tier": tier,
                "expiry": expiry,
            }
        )
        if delimiter != "|":
            alternate_payload_bytes = delimiter.join(
                (product_id, email, tier, expiry)
            ).encode("utf-8")

    payload_bytes = _canonical_payload(product_id, email, tier, expiry)
    if not (
        _signature_matches(signature, payload_bytes, secret)
        or (
            alternate_payload_bytes is not None
            and _signature_matches(signature, alternate_payload_bytes, secret)
        )
    ):
        raise LicenseError("license signature is invalid")

    return _validate_fields(
        product_id,
        email,
        tier,
        expiry,
        expected_product_id=expected_product_id,
        now=now,
    )


def make_license_key(
    *,
    product_id: str = DEFAULT_PRODUCT_ID,
    email: str,
    tier: str,
    expiry: str,
    secret: str,
) -> str:
    """Create a signed license key for tests and operator tooling."""
    product_id, email, tier, expiry = _coerce_payload(
        {
            "product_id": product_id,
            "email": email,
            "tier": tier,
            "expiry": expiry,
        }
    )
    payload = {
        "product_id": product_id,
        "email": email,
        "tier": tier,
        "expiry": expiry,
    }
    payload_bytes = _canonical_payload(product_id, email, tier, expiry)
    payload_part = _b64url_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return f"{KEY_PREFIX}.{payload_part}.{_signature(payload_bytes, secret)}"


def load_license_from_env(
    env: Optional[Mapping[str, str]] = None,
    *,
    expected_product_id: str = DEFAULT_PRODUCT_ID,
    now: Optional[datetime] = None,
) -> License:
    """Load and validate a license from environment variables.

    No key means the CLI runs with the free entitlement. A provided key must be
    valid and signed by ``UMAIL_LICENSE_SECRET`` (or legacy
    ``LICENSE_SIGNING_KEY``) so a misconfigured paid key cannot silently elevate
    access.
    """
    source = env if env is not None else os.environ
    key = source.get(LICENSE_KEY_ENV, "").strip()
    if not key:
        return FREE_LICENSE

    secret = source.get(LICENSE_SECRET_ENV) or source.get(LEGACY_LICENSE_SECRET_ENV)
    return validate_license_key(
        key,
        secret or "",
        expected_product_id=expected_product_id,
        now=now,
    )
