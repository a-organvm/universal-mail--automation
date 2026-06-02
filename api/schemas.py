"""Request/response models for the API.

Kept deliberately small and Pydantic-v1/v2 compatible (plain fields + defaults).
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

# Upper bound on messages processed in a single triage call. Without a cap a
# client could request an unbounded scan that pages through an entire mailbox
# (one provider round-trip + a 1s throttle sleep per 100-message batch), holding
# the request open and exhausting provider quota — a denial-of-service vector.
MAX_TRIAGE_LIMIT = 1000


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class SenderCheckRequest(BaseModel):
    # Bounded so a pathologically large header can't drive unbounded regex work
    # in the categorization pass (every LABEL_RULES pattern is re-scanned over
    # sender+subject). Real From/Subject headers are well under these limits.
    sender: str = Field(max_length=4096)
    subject: str = Field(default="", max_length=4096)


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
    provider: str = Field(default="gmail", max_length=64)
    query: str = Field(default="has:nouserlabels", max_length=2048)
    limit: int = Field(default=100, ge=1, le=MAX_TRIAGE_LIMIT)
    dry_run: bool = True
    remove_label: Optional[str] = Field(default=None, max_length=512)
    tier_routing: bool = False
    vip_only: bool = False


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
