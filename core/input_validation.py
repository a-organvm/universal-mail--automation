"""Shared validation for untrusted request/tool inputs.

The provider backends accept provider-specific query and label syntax, so this
module validates shape and bounds without trying to parse each backend language.
"""

from __future__ import annotations

import re
from typing import Any, Optional

MAX_HEADER_VALUE_LENGTH = 4096
MAX_TRIAGE_LIMIT = 1000
MAX_QUERY_LENGTH = 2048
MAX_LABEL_LENGTH = 512
MAX_PROVIDER_LENGTH = 64
MAX_TOKEN_LENGTH = 512
MAX_PLAN_ID_LENGTH = 64

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+/=-]+$")
_PLAN_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class InputValidationError(ValueError):
    """Raised when an external request/tool argument has an unsafe shape."""


def _bounded_text(
    value: Any,
    *,
    field: str,
    max_length: int,
    allow_empty: bool,
    strip: bool = True,
) -> str:
    if not isinstance(value, str):
        raise InputValidationError(f"{field} must be a string")
    text = value.strip() if strip else value
    if not text and not allow_empty:
        raise InputValidationError(f"{field} is required")
    if len(text) > max_length:
        raise InputValidationError(f"{field} exceeds {max_length} characters")
    if _CONTROL_RE.search(text):
        raise InputValidationError(f"{field} contains control characters")
    return text


def validate_header_value(
    value: Any,
    *,
    field: str,
    allow_empty: bool = True,
) -> str:
    return _bounded_text(
        value,
        field=field,
        max_length=MAX_HEADER_VALUE_LENGTH,
        allow_empty=allow_empty,
    )


def validate_provider_name(value: Any, *, field: str = "provider") -> str:
    text = _bounded_text(
        value,
        field=field,
        max_length=MAX_PROVIDER_LENGTH,
        allow_empty=False,
    ).lower()
    if not _PROVIDER_RE.fullmatch(text):
        raise InputValidationError(
            f"{field} must start with a letter and contain only lowercase letters, "
            "digits, underscores, or hyphens"
        )
    return text


def validate_search_query(value: Any, *, field: str = "query") -> str:
    return _bounded_text(
        value,
        field=field,
        max_length=MAX_QUERY_LENGTH,
        allow_empty=True,
    )


def validate_mail_label(
    value: Optional[Any],
    *,
    field: str = "remove_label",
) -> Optional[str]:
    if value is None:
        return None
    text = _bounded_text(
        value,
        field=field,
        max_length=MAX_LABEL_LENGTH,
        allow_empty=True,
    )
    return text or None


def validate_triage_limit(
    value: Any,
    *,
    field: str = "limit",
    max_limit: int = MAX_TRIAGE_LIMIT,
) -> int:
    if isinstance(value, bool):
        raise InputValidationError(f"{field} must be an integer")
    try:
        limit = int(value)
    except (TypeError, ValueError) as e:
        raise InputValidationError(f"{field} must be an integer") from e
    if limit < 1 or limit > max_limit:
        raise InputValidationError(f"{field} must be between 1 and {max_limit}")
    return limit


def validate_api_token(value: Any, *, field: str = "token") -> str:
    text = _bounded_text(
        value,
        field=field,
        max_length=MAX_TOKEN_LENGTH,
        allow_empty=False,
    )
    if not _TOKEN_RE.fullmatch(text):
        raise InputValidationError(f"{field} contains invalid characters")
    return text


def validate_plan_id(value: Any, *, field: str = "license") -> str:
    text = _bounded_text(
        value,
        field=field,
        max_length=MAX_PLAN_ID_LENGTH,
        allow_empty=False,
    ).lower()
    if not _PLAN_RE.fullmatch(text):
        raise InputValidationError(
            f"{field} must start with a letter and contain only lowercase letters, "
            "digits, underscores, or hyphens"
        )
    return text

