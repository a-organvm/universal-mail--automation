"""Tokenized, encrypted credential storage for provider authentication.

This module is the replacement path for the older environment/1Password secret
loading model. Providers can be wired to it later by persisting a returned
``uma_auth_*`` token and resolving that token only at connection time.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:  # Imported lazily enough that auth.__init__ remains importable pre-install.
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    Fernet = None  # type: ignore[assignment]
    hashes = None  # type: ignore[assignment]
    HKDF = None  # type: ignore[assignment]


DEFAULT_STORE_PATH = os.environ.get("UMA_AUTH_STORE_PATH", "data/auth_service.db")
DEFAULT_KEY_PATH = os.environ.get("UMA_AUTH_KEY_PATH", "data/auth_service.key")
MASTER_KEY_ENV = "UMA_AUTH_MASTER_KEY"
TOKEN_PREFIX = "uma_auth_"

_HKDF_SALT = b"universal-mail-auth-service-v1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_secrets (
    token           TEXT PRIMARY KEY,
    provider        TEXT NOT NULL,
    account_id      TEXT,
    kind            TEXT NOT NULL,
    ciphertext      TEXT NOT NULL,
    key_version     TEXT NOT NULL,
    metadata_json   TEXT NOT NULL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    rotated_at      REAL NOT NULL,
    rotation_due_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_secrets_provider
    ON auth_secrets (provider, account_id, kind);
"""


Jsonable = Union[None, bool, int, float, str, list, dict]
KeyInput = Union[str, bytes]


@dataclass(frozen=True)
class SecretRef:
    """Secret-free reference metadata for a stored credential.

    The token is still an access handle and should be handled with care.
    """

    token: str
    provider: str
    kind: str
    account_id: Optional[str]
    metadata: Dict[str, Any]
    key_version: str
    created_at: float
    updated_at: float
    rotated_at: float
    rotation_due_at: float


@dataclass(frozen=True)
class SecretMaterial(SecretRef):
    """Resolved credential material.

    ``secret`` is deliberately excluded from repr so accidental logging of the
    object does not print credential contents.
    """

    secret: Any = field(repr=False)  # allow-secret: runtime credential value


def generate_master_key() -> str:
    """Return a new high-entropy master key suitable for UMA_AUTH_MASTER_KEY."""

    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def connect(
    *,
    path: Optional[Union[str, os.PathLike[str]]] = None,
    master_key: Optional[KeyInput] = None,  # allow-secret: caller-supplied key
    key_path: Optional[Union[str, os.PathLike[str]]] = None,
    rotate: bool = True,
    now: Optional[Union[float, datetime]] = None,
) -> "TokenizedSecretStore":
    """Open the auth secret store and rotate any monthly-due records.

    Args:
        path: SQLite database path. Defaults to ``UMA_AUTH_STORE_PATH`` or
            ``data/auth_service.db``.
        master_key: Optional high-entropy master key. Defaults to
            ``UMA_AUTH_MASTER_KEY`` or a generated local key file.
        key_path: Local master-key file when ``master_key`` is not supplied.
        rotate: Whether to re-encrypt due records before returning.
        now: Test hook for deterministic rotation checks.
    """

    store = TokenizedSecretStore(
        path=path or DEFAULT_STORE_PATH,
        master_key=master_key,
        key_path=key_path or DEFAULT_KEY_PATH,
    )
    if rotate:
        store.rotate_due(now=now)
    return store


def resolve(
    token: str,
    *,
    path: Optional[Union[str, os.PathLike[str]]] = None,
    master_key: Optional[KeyInput] = None,  # allow-secret: caller-supplied key
    key_path: Optional[Union[str, os.PathLike[str]]] = None,
) -> SecretMaterial:
    """Resolve one token using a short-lived store connection."""

    with connect(path=path, master_key=master_key, key_path=key_path) as store:
        return store.load_secret(token)


class TokenizedSecretStore:
    """SQLite-backed token store with authenticated encryption at rest.

    The public handle is an opaque ``uma_auth_*`` token. The secret payload is
    encrypted with a data key derived from the master key and the current UTC
    month. On month rollover, ``rotate_due()`` decrypts and re-encrypts records
    under the new monthly data key without changing the token handle.
    """

    def __init__(
        self,
        path: Union[str, os.PathLike[str]] = DEFAULT_STORE_PATH,
        *,
        master_key: Optional[KeyInput] = None,  # allow-secret: caller-supplied key
        key_path: Union[str, os.PathLike[str]] = DEFAULT_KEY_PATH,
    ):
        self.path = str(path)
        self._master_material = _load_master_material(master_key, key_path)
        self._lock = threading.RLock()

        if self.path != ":memory:":
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent:
                os.makedirs(parent, exist_ok=True)

        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            try:
                self._conn.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.Error:
                pass
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def __enter__(self) -> "TokenizedSecretStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def store_secret(
        self,
        provider: str,
        secret: Jsonable,  # allow-secret: runtime credential value
        *,
        account_id: Optional[str] = None,
        kind: str = "credential",
        metadata: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        now: Optional[Union[float, datetime]] = None,
    ) -> SecretRef:
        """Create or update an encrypted secret and return its token reference.

        ``metadata`` is stored in plaintext for lookup/filtering, so callers
        should keep credential material in ``secret`` only.
        """

        provider = _clean_required("provider", provider)
        kind = _clean_required("kind", kind)
        token = token or _new_token()
        if not token.startswith(TOKEN_PREFIX):
            raise ValueError(f"token must start with {TOKEN_PREFIX!r}")

        ts = _coerce_timestamp(now)
        key_version = _month_version(ts)
        metadata_json = _json_dumps(metadata or {})
        ciphertext = self._encrypt_payload(
            token=token,
            provider=provider,
            account_id=account_id,
            kind=kind,
            secret=secret,
            key_version=key_version,
        )
        rotation_due_at = _next_month_start(ts)

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO auth_secrets (
                    token, provider, account_id, kind, ciphertext, key_version,
                    metadata_json, created_at, updated_at, rotated_at,
                    rotation_due_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    provider = excluded.provider,
                    account_id = excluded.account_id,
                    kind = excluded.kind,
                    ciphertext = excluded.ciphertext,
                    key_version = excluded.key_version,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    rotated_at = excluded.rotated_at,
                    rotation_due_at = excluded.rotation_due_at
                """,
                (
                    token,
                    provider,
                    account_id,
                    kind,
                    ciphertext,
                    key_version,
                    metadata_json,
                    ts,
                    ts,
                    ts,
                    rotation_due_at,
                ),
            )
            self._conn.commit()

        ref = self.get_ref(token)
        if ref is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("stored secret could not be read back")
        return ref

    def get_ref(self, token: str) -> Optional[SecretRef]:
        """Return secret-free metadata for a token."""

        row = self._fetch_row(token)
        if row is None:
            return None
        return _ref_from_row(row)

    def list_refs(
        self,
        *,
        provider: Optional[str] = None,
        account_id: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> list[SecretRef]:
        """List token references without decrypting or returning secrets."""

        clauses = []
        params: list[Any] = []
        if provider is not None:
            clauses.append("provider = ?")
            params.append(provider)
        if account_id is not None:
            clauses.append("account_id = ?")
            params.append(account_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM auth_secrets {where} ORDER BY updated_at DESC",
                params,
            ).fetchall()
        return [_ref_from_row(row) for row in rows]

    def get_secret(self, token: str) -> Optional[SecretMaterial]:
        """Resolve a token to secret material, or return None if it is unknown."""

        row = self._fetch_row(token)
        if row is None:
            return None
        return self._material_from_row(row)

    def load_secret(self, token: str) -> SecretMaterial:
        """Resolve a token to secret material, raising KeyError if unknown."""

        material = self.get_secret(token)
        if material is None:
            raise KeyError(f"unknown auth secret token: {token}")
        return material

    def delete_secret(self, token: str) -> bool:
        """Delete a tokenized secret."""

        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM auth_secrets WHERE token = ?",
                (token,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def needs_rotation(
        self,
        token: str,
        *,
        now: Optional[Union[float, datetime]] = None,
    ) -> bool:
        """Return True when a record is past its monthly rotation boundary."""

        ref = self.get_ref(token)
        if ref is None:
            raise KeyError(f"unknown auth secret token: {token}")
        ts = _coerce_timestamp(now)
        return ref.rotation_due_at <= ts or ref.key_version != _month_version(ts)

    def rotate_secret(
        self,
        token: str,
        *,
        now: Optional[Union[float, datetime]] = None,
    ) -> SecretRef:
        """Force re-encryption of one secret under the current monthly data key."""

        row = self._fetch_row(token)
        if row is None:
            raise KeyError(f"unknown auth secret token: {token}")
        material = self._material_from_row(row)
        return self._rewrite_secret(material, now=now)

    def rotate_due(
        self,
        *,
        now: Optional[Union[float, datetime]] = None,
    ) -> int:
        """Re-encrypt all records due for monthly rotation.

        Returns the number of records rotated.
        """

        ts = _coerce_timestamp(now)
        current_version = _month_version(ts)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM auth_secrets
                WHERE rotation_due_at <= ? OR key_version != ?
                ORDER BY updated_at ASC
                """,
                (ts, current_version),
            ).fetchall()

        count = 0
        for row in rows:
            material = self._material_from_row(row)
            self._rewrite_secret(material, now=ts)
            count += 1
        return count

    def _fetch_row(self, token: str) -> Optional[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM auth_secrets WHERE token = ?",
                (token,),
            ).fetchone()

    def _rewrite_secret(
        self,
        material: SecretMaterial,
        *,
        now: Optional[Union[float, datetime]] = None,
    ) -> SecretRef:
        ts = _coerce_timestamp(now)
        key_version = _month_version(ts)
        ciphertext = self._encrypt_payload(
            token=material.token,
            provider=material.provider,
            account_id=material.account_id,
            kind=material.kind,
            secret=material.secret,
            key_version=key_version,
        )
        rotation_due_at = _next_month_start(ts)

        with self._lock:
            self._conn.execute(
                """
                UPDATE auth_secrets
                SET ciphertext = ?, key_version = ?, updated_at = ?,
                    rotated_at = ?, rotation_due_at = ?
                WHERE token = ?
                """,
                (
                    ciphertext,
                    key_version,
                    ts,
                    ts,
                    rotation_due_at,
                    material.token,
                ),
            )
            self._conn.commit()

        ref = self.get_ref(material.token)
        if ref is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("rotated secret could not be read back")
        return ref

    def _encrypt_payload(
        self,
        *,
        token: str,
        provider: str,
        account_id: Optional[str],
        kind: str,
        secret: Jsonable,  # allow-secret: runtime credential value
        key_version: str,
    ) -> str:
        payload = _json_dumps(
            {
                "token": token,
                "provider": provider,
                "account_id": account_id,
                "kind": kind,
                "secret": secret,
            }
        ).encode("utf-8")
        return (
            self._fernet_for_version(key_version)
            .encrypt(payload)
            .decode("ascii")
        )

    def _material_from_row(self, row: sqlite3.Row) -> SecretMaterial:
        try:
            raw = self._fernet_for_version(row["key_version"]).decrypt(
                row["ciphertext"].encode("ascii")
            )
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("failed to decrypt auth secret material") from exc

        expected = {
            "token": row["token"],
            "provider": row["provider"],
            "account_id": row["account_id"],
            "kind": row["kind"],
        }
        actual = {k: payload.get(k) for k in expected}
        if actual != expected:
            raise RuntimeError("auth secret metadata does not match encrypted payload")

        return SecretMaterial(
            **_ref_kwargs_from_row(row),
            secret=payload.get("secret"),  # allow-secret: decrypted return value
        )

    def _fernet_for_version(self, key_version: str):
        if Fernet is None or HKDF is None or hashes is None:
            raise RuntimeError(
                "cryptography package is required for auth secret encryption"
            )
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_HKDF_SALT,
            info=f"auth-service:{key_version}".encode("ascii"),
        ).derive(self._master_material)
        return Fernet(base64.urlsafe_b64encode(derived))


def _new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(24)


def _clean_required(name: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    except TypeError as exc:
        raise TypeError("auth secret payloads must be JSON serializable") from exc


def _coerce_timestamp(value: Optional[Union[float, datetime]] = None) -> float:
    if value is None:
        return time.time()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    return float(value)


def _month_version(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def _next_month_start(ts: float) -> float:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if dt.month == 12:
        nxt = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        nxt = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
    return nxt.timestamp()


def _ref_from_row(row: sqlite3.Row) -> SecretRef:
    return SecretRef(**_ref_kwargs_from_row(row))


def _ref_kwargs_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "token": row["token"],
        "provider": row["provider"],
        "kind": row["kind"],
        "account_id": row["account_id"],
        "metadata": json.loads(row["metadata_json"]),
        "key_version": row["key_version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "rotated_at": row["rotated_at"],
        "rotation_due_at": row["rotation_due_at"],
    }


def _load_master_material(
    master_key: Optional[KeyInput],  # allow-secret: caller-supplied key
    key_path: Union[str, os.PathLike[str]],
) -> bytes:
    if master_key is None:
        env_key = os.environ.get(MASTER_KEY_ENV)
        if env_key:
            master_key = env_key
        else:
            master_key = _load_or_create_key_file(key_path)
    return _decode_master_key(master_key)


def _load_or_create_key_file(path: Union[str, os.PathLike[str]]) -> str:
    key_file = Path(path)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        raw = key_file.read_text(encoding="ascii").strip()
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        return raw

    key = generate_master_key()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(key_file, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            fh.write(key)
            fh.write("\n")
    except Exception:
        try:
            os.unlink(key_file)
        finally:
            raise
    return key


def _decode_master_key(master_key: KeyInput) -> bytes:  # allow-secret: key parser
    raw = master_key if isinstance(master_key, bytes) else master_key.encode("ascii")
    try:
        decoded = base64.urlsafe_b64decode(raw)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            "master key must be a base64-url encoded 32-byte key; "
            "use auth.service.generate_master_key()"
        ) from exc
    if len(decoded) != 32:
        raise ValueError(
            "master key must decode to exactly 32 bytes; "
            "use auth.service.generate_master_key()"
        )
    return decoded


__all__ = [
    "DEFAULT_KEY_PATH",
    "DEFAULT_STORE_PATH",
    "MASTER_KEY_ENV",
    "TOKEN_PREFIX",
    "SecretMaterial",
    "SecretRef",
    "TokenizedSecretStore",
    "connect",
    "generate_master_key",
    "resolve",
]
