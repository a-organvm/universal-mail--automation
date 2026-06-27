"""Request/response models for the API.

Kept deliberately small and Pydantic-v1/v2 compatible (plain fields + defaults).
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import field_validator as _field_validator

    def _before_validator(*fields: str):
        return _field_validator(*fields, mode="before")

except ImportError:  # pragma: no cover - Pydantic v1 compatibility
    from pydantic import validator as _validator

    def _before_validator(*fields: str):
        return _validator(*fields, pre=True)

from core.input_validation import (
    MAX_HEADER_VALUE_LENGTH,
    MAX_LABEL_LENGTH,
    MAX_PROVIDER_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_TRIAGE_LIMIT,
    validate_header_value,
    validate_mail_label,
    validate_provider_name,
    validate_search_query,
)

# Upper bound on messages processed in a single triage call. Without a cap a
# client could request an unbounded scan that pages through an entire mailbox
# (one provider round-trip + a 1s throttle sleep per 100-message batch), holding
# the request open and exhausting provider quota — a denial-of-service vector.


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class SenderCheckRequest(BaseModel):
    # Bounded so a pathologically large header can't drive unbounded regex work
    # in the categorization pass (every LABEL_RULES pattern is re-scanned over
    # sender+subject). Real From/Subject headers are well under these limits.
    sender: str = Field(max_length=MAX_HEADER_VALUE_LENGTH)
    subject: str = Field(default="", max_length=MAX_HEADER_VALUE_LENGTH)

    @_before_validator("sender")
    def _validate_sender(cls, value: Any) -> str:
        return validate_header_value(value, field="sender", allow_empty=False)

    @_before_validator("subject")
    def _validate_subject(cls, value: Any) -> str:
        return validate_header_value("" if value is None else value, field="subject")


class SenderCheckResponse(BaseModel):
    sender: str
    protected: bool
    categorization: Optional[dict] = None


class TriageRequest(BaseModel):
    # Bounded length only; the authoritative provider allowlist lives at the
    # factory boundary (cli.get_provider). An unknown provider is mapped to a
    # clean 503 in the service layer (never an unhandled 500, never echoed back
    # in an error string), and tests legitimately inject fake provider names via
    # monkeypatch, so the schema does not hard-pin the set here.
    provider: str = Field(default="gmail", max_length=MAX_PROVIDER_LENGTH)
    query: str = Field(default="has:nouserlabels", max_length=MAX_QUERY_LENGTH)
    limit: int = Field(default=100, ge=1, le=MAX_TRIAGE_LIMIT)
    dry_run: bool = True
    remove_label: Optional[str] = Field(default=None, max_length=MAX_LABEL_LENGTH)
    tier_routing: bool = False
    vip_only: bool = False

    @_before_validator("provider")
    def _validate_provider(cls, value: Any) -> str:
        return validate_provider_name(value)

    @_before_validator("query")
    def _validate_query(cls, value: Any) -> str:
        return validate_search_query("" if value is None else value)

    @_before_validator("remove_label")
    def _validate_remove_label(cls, value: Optional[Any]) -> Optional[str]:
        return validate_mail_label(value)


class AuditSummary(BaseModel):
    total: int
    protected_held: int
    archived: int
    moved: int
    labeled: int
    kept: int
    violations: List[str]


class TriageResponse(BaseModel):
    dry_run: bool
    provider: str
    receipt: str
    audit: AuditSummary
    processed: Any = None
    # Set by the API: the id under which a signed receipt was persisted, fetchable
    # at GET /v1/audit/{run_id}. Optional so the engine's own dict stays valid.
    run_id: Optional[str] = None
