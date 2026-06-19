"""Tests for the tokenized auth secret service."""

from datetime import datetime, timezone

import pytest

from auth.service import TokenizedSecretStore, connect, generate_master_key


def _dt(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


def _store(tmp_path):
    return TokenizedSecretStore(
        tmp_path / "auth.db",
        master_key=generate_master_key(),
        key_path=tmp_path / "auth.key",
    )


def test_secret_round_trip_uses_token_and_encrypts_at_rest(tmp_path):
    store = _store(tmp_path)
    secret = {  # allow-secret: synthetic test credential
        "access_token": "access-token-123",
        "refresh_token": "refresh-token-456",
    }

    ref = store.store_secret(
        "gmail",
        secret,
        account_id="me",
        kind="oauth_token",
        metadata={"scopes": ["gmail.modify"]},
        now=_dt(2026, 6, 19),
    )
    resolved = store.load_secret(ref.token)

    assert ref.token.startswith("uma_auth_")
    assert resolved.secret == secret
    assert resolved.provider == "gmail"
    assert resolved.metadata == {"scopes": ["gmail.modify"]}

    for path in tmp_path.glob("auth.db*"):
        raw = path.read_bytes()
        assert b"access-token-123" not in raw
        assert b"refresh-token-456" not in raw
        assert b"access_token" not in raw
        assert b"refresh_token" not in raw


def test_list_refs_does_not_expose_secret_material(tmp_path):
    store = _store(tmp_path)
    ref = store.store_secret(
        "imap",
        "app-password",
        account_id="user@example.com",
        kind="password",
    )

    refs = store.list_refs(provider="imap", kind="password")

    assert refs == [store.get_ref(ref.token)]
    assert not hasattr(refs[0], "secret")


def test_monthly_rotation_reencrypts_without_changing_token(tmp_path):
    store = _store(tmp_path)
    ref = store.store_secret(
        "gmail",
        {"refresh_token": "refresh-token-456"},  # allow-secret: synthetic
        kind="oauth_token",
        now=_dt(2026, 1, 15),
    )

    before = store._fetch_row(ref.token)["ciphertext"]
    assert ref.key_version == "2026-01"
    assert store.needs_rotation(ref.token, now=_dt(2026, 1, 31)) is False
    assert store.rotate_due(now=_dt(2026, 1, 31)) == 0

    assert store.needs_rotation(ref.token, now=_dt(2026, 2, 1)) is True
    assert store.rotate_due(now=_dt(2026, 2, 1)) == 1

    rotated = store.load_secret(ref.token)
    after = store._fetch_row(ref.token)["ciphertext"]
    assert rotated.token == ref.token
    assert rotated.key_version == "2026-02"
    assert rotated.secret == {"refresh_token": "refresh-token-456"}
    assert after != before


def test_connect_helper_rotates_due_records(tmp_path):
    key = generate_master_key()
    path = tmp_path / "auth.db"
    with connect(path=path, master_key=key, rotate=False) as store:
        ref = store.store_secret(
            "gmail",
            {"refresh_token": "refresh-token-456"},  # allow-secret: synthetic
            kind="oauth_token",
            now=_dt(2026, 1, 15),
        )

    with connect(path=path, master_key=key, now=_dt(2026, 2, 1)) as store:
        assert store.load_secret(ref.token).key_version == "2026-02"


def test_delete_secret_removes_token(tmp_path):
    store = _store(tmp_path)
    ref = store.store_secret("imap", "app-password", kind="password")

    assert store.delete_secret(ref.token) is True
    assert store.get_secret(ref.token) is None
    with pytest.raises(KeyError):
        store.load_secret(ref.token)
