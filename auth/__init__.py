"""
Authentication utilities for email providers.

Provides OAuth2 helpers and 1Password credential loading for
multi-provider authentication.
"""

from auth.onepassword import load_secret, load_json_secret
from auth.service import (
    SecretMaterial,
    SecretRef,
    TokenizedSecretStore,
    connect,
    generate_master_key,
    resolve,
)

__all__ = [
    "SecretMaterial",
    "SecretRef",
    "TokenizedSecretStore",
    "connect",
    "generate_master_key",
    "load_secret",
    "load_json_secret",
    "resolve",
]
