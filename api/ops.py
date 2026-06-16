"""HTTP adapter for private operator dashboard contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from api.auth import bearer_api_key
from core.historical_intelligence import (
    HISTORICAL_INTELLIGENCE_SCHEMA,
    HistoricalIntelligenceError,
    build_historical_intelligence,
)
from core.mail_action_plan import MailActionPlanError, build_action_plan
from core.mail_action_ledger import (
    MailActionLedgerError,
    build_action_ledger,
    build_action_plan_for_ledger,
    build_action_receipt,
)
from core.mail_evidence_review import MailEvidenceReviewError, build_evidence_review
from core.mail_draft_package import MailDraftPackageError, build_draft_package
from core.mail_draft_approval import (
    MailDraftApprovalError,
    build_draft_approval_ledger,
    build_draft_approval_receipt,
)
from core.mail_delivery import (
    MailDeliveryError,
    build_delivery_ledger,
    build_delivery_receipt,
)
from core.mail_resolver_plan import MailResolverPlanError, build_resolver_plan
from core.mail_resolver_receipt import (
    MailResolverReceiptError,
    build_resolver_ledger,
    build_resolver_receipt,
)
from core.github_resolver import (
    GitHubResolverError,
    build_github_resolver_receipts,
    build_github_resolver_snapshot,
)
from core.followup_resolver import (
    FollowupResolverError,
    build_followup_resolver_receipts,
    build_followup_resolver_snapshot,
)
from core.external_resolver import (
    ExternalResolverError,
    build_external_resolver_receipts,
    build_external_resolver_snapshot,
)
from core.provider_surface_plan import ProviderSurfacePlanError, build_provider_surface_plan
from core.ops_summary import DEFAULT_MAX_AGE_HOURS, OpsReportError, build_ops_snapshot, load_ops_history

OPS_REPORT_ENV = "UMA_OPS_REPORT_PATH"
OPS_TOKEN_ENV = "UMA_OPS_TOKEN"  # allow-secret: env var name only
OPS_HISTORY_ENV = "UMA_OPS_HISTORY_DIR"
OPS_MAX_AGE_ENV = "UMA_OPS_MAX_AGE_HOURS"
OPS_INTELLIGENCE_ENV = "UMA_HISTORICAL_MAIL_PATH"
OPS_INTELLIGENCE_CACHE_ENV = "UMA_HISTORICAL_INTELLIGENCE_PATH"
OPS_INTELLIGENCE_STALE_DAYS_ENV = "UMA_HISTORICAL_STALE_DAYS"
OPS_ACTION_LEDGER_ENV = "UMA_MAIL_ACTION_LEDGER_PATH"
OPS_RESOLVER_LEDGER_ENV = "UMA_MAIL_RESOLVER_LEDGER_PATH"
OPS_DRAFT_APPROVAL_ENV = "UMA_MAIL_DRAFT_APPROVAL_PATH"
OPS_DELIVERY_LEDGER_ENV = "UMA_MAIL_DELIVERY_LEDGER_PATH"

router = APIRouter(tags=["ops"])


def _configured_report_path() -> Path:
    raw = os.environ.get(OPS_REPORT_ENV, "").strip()
    if not raw:
        raise HTTPException(
            status_code=503,
            detail=f"operator report is not configured; set {OPS_REPORT_ENV}",
        )
    return Path(raw).expanduser()


def _configured_history_dir() -> Path:
    raw = os.environ.get(OPS_HISTORY_ENV, "").strip()
    if not raw:
        raise HTTPException(
            status_code=503,
            detail=f"operator history is not configured; set {OPS_HISTORY_ENV}",
        )
    return Path(raw).expanduser()


def _configured_intelligence_path() -> Path:
    raw = os.environ.get(OPS_INTELLIGENCE_ENV, "").strip()
    if not raw:
        raise HTTPException(
            status_code=503,
            detail=f"historical intelligence input is not configured; set {OPS_INTELLIGENCE_ENV}",
        )
    return Path(raw).expanduser()


def _configured_intelligence_cache_path() -> Optional[Path]:
    raw = os.environ.get(OPS_INTELLIGENCE_CACHE_ENV, "").strip()
    return Path(raw).expanduser() if raw else None


def _configured_action_ledger_path() -> Path:
    raw = os.environ.get(OPS_ACTION_LEDGER_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    history_dir = os.environ.get(OPS_HISTORY_ENV, "").strip()
    if history_dir:
        return Path(history_dir).expanduser() / "mail-action-ledger.jsonl"
    return Path("~/.local/state/universal-mail-automation/mail-action-ledger.jsonl").expanduser()


def _configured_resolver_ledger_path() -> Path:
    raw = os.environ.get(OPS_RESOLVER_LEDGER_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    history_dir = os.environ.get(OPS_HISTORY_ENV, "").strip()
    if history_dir:
        return Path(history_dir).expanduser() / "mail-resolver-ledger.jsonl"
    return Path("~/.local/state/universal-mail-automation/mail-resolver-ledger.jsonl").expanduser()


def _configured_draft_approval_path() -> Path:
    raw = os.environ.get(OPS_DRAFT_APPROVAL_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    history_dir = os.environ.get(OPS_HISTORY_ENV, "").strip()
    if history_dir:
        return Path(history_dir).expanduser() / "mail-draft-approvals.jsonl"
    return Path("~/.local/state/universal-mail-automation/mail-draft-approvals.jsonl").expanduser()


def _configured_delivery_ledger_path() -> Path:
    raw = os.environ.get(OPS_DELIVERY_LEDGER_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    history_dir = os.environ.get(OPS_HISTORY_ENV, "").strip()
    if history_dir:
        return Path(history_dir).expanduser() / "mail-delivery-ledger.jsonl"
    return Path("~/.local/state/universal-mail-automation/mail-delivery-ledger.jsonl").expanduser()


def _load_cached_intelligence(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"historical intelligence cache not found; check {OPS_INTELLIGENCE_CACHE_ENV}",
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"historical intelligence cache is invalid JSON; rebuild {OPS_INTELLIGENCE_CACHE_ENV}",
        ) from e
    except OSError as e:
        raise HTTPException(status_code=503, detail=f"historical intelligence cache could not be read: {e}") from e
    if not isinstance(data, dict) or data.get("schema") != HISTORICAL_INTELLIGENCE_SCHEMA:
        raise HTTPException(
            status_code=503,
            detail=f"historical intelligence cache must be {HISTORICAL_INTELLIGENCE_SCHEMA}",
        )
    return data


def _max_age_hours() -> float:
    raw = os.environ.get(OPS_MAX_AGE_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_AGE_HOURS
    try:
        parsed = float(raw)
    except ValueError:
        raise HTTPException(status_code=503, detail=f"{OPS_MAX_AGE_ENV} must be numeric")
    return parsed if parsed > 0 else DEFAULT_MAX_AGE_HOURS


def _stale_days() -> int:
    raw = os.environ.get(OPS_INTELLIGENCE_STALE_DAYS_ENV, "").strip()
    if not raw:
        return 14
    try:
        parsed = int(raw)
    except ValueError:
        raise HTTPException(status_code=503, detail=f"{OPS_INTELLIGENCE_STALE_DAYS_ENV} must be numeric")
    return parsed if parsed > 0 else 14


def _authorize(request: Request) -> None:
    expected = os.environ.get(OPS_TOKEN_ENV)
    if not expected:
        return
    supplied = bearer_api_key(request)
    if supplied != expected:
        raise HTTPException(status_code=401, detail="invalid bearer credentials")


def _authorize_private_review(request: Request) -> None:
    expected = os.environ.get(OPS_TOKEN_ENV)
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"private mail review requires {OPS_TOKEN_ENV}",
        )
    supplied = bearer_api_key(request)
    if supplied != expected:
        raise HTTPException(status_code=401, detail="invalid bearer credentials")


def _authorize_ops_write(request: Request) -> None:
    expected = os.environ.get(OPS_TOKEN_ENV)
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"operator write receipts require {OPS_TOKEN_ENV}",
        )
    supplied = bearer_api_key(request)
    if supplied != expected:
        raise HTTPException(status_code=401, detail="invalid bearer credentials")


def _build_current_action_plan(max_items: int = 100) -> Dict[str, Any]:
    cached = _configured_intelligence_cache_path()
    if cached is not None:
        return build_action_plan(cached, max_items=max_items)
    raw_ops_report = os.environ.get(OPS_REPORT_ENV, "").strip()
    ops_report_path = Path(raw_ops_report).expanduser() if raw_ops_report else None
    intelligence = build_historical_intelligence(
        _configured_intelligence_path(),
        ops_report_path=ops_report_path,
        stale_days=_stale_days(),
    )
    return build_action_plan_for_ledger(intelligence, max_items=max_items)


@router.get("/v1/ops/summary")
def ops_summary(request: Request) -> Dict[str, Any]:
    """Return a redacted operator summary for a configured local triage report."""
    _authorize(request)
    try:
        return build_ops_snapshot(_configured_report_path(), max_age_hours=_max_age_hours())
    except OpsReportError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/history")
def ops_history(request: Request) -> Dict[str, Any]:
    """Return the redacted operator history index for a configured output dir."""
    _authorize(request)
    return load_ops_history(_configured_history_dir())


@router.get("/v1/ops/intelligence")
def ops_intelligence(request: Request) -> Dict[str, Any]:
    """Return redacted historical mail intelligence reconciled to current ops."""
    _authorize(request)
    cached = _configured_intelligence_cache_path()
    if cached is not None:
        return _load_cached_intelligence(cached)
    raw_ops_report = os.environ.get(OPS_REPORT_ENV, "").strip()
    ops_report_path = Path(raw_ops_report).expanduser() if raw_ops_report else None
    try:
        return build_historical_intelligence(
            _configured_intelligence_path(),
            ops_report_path=ops_report_path,
            stale_days=_stale_days(),
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/action-plan")
def ops_action_plan(request: Request, max_items: int = 40) -> Dict[str, Any]:
    """Return redacted, approval-aware next-action groups."""
    _authorize(request)
    try:
        return _build_current_action_plan(max_items=max_items)
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/resolver-plan")
def ops_resolver_plan(request: Request, max_items: int = 100) -> Dict[str, Any]:
    """Return redacted lane-specific resolver plans for action groups."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        return build_resolver_plan(plan, max_items=max_items)
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/provider-surface-plan")
def ops_provider_surface_plan(request: Request, max_items: int = 20) -> Dict[str, Any]:
    """Return a redacted provider-surface resolver frontier plan."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        return build_provider_surface_plan(resolver_plan, max_items=max_items)
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except ProviderSurfacePlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/resolver-ledger")
def ops_resolver_ledger(
    request: Request,
    max_items: int = 100,
    max_receipts: int = 40,
) -> Dict[str, Any]:
    """Return redacted official-surface resolver proof state."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        return build_resolver_ledger(
            resolver_plan,
            receipt_path=_configured_resolver_ledger_path(),
            max_items=max_items,
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverReceiptError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/github-resolver")
def ops_github_resolver(
    request: Request,
    max_items: int = 100,
    query_limit: int = 50,
    include_provider_queries: bool = True,
) -> Dict[str, Any]:
    """Return a redacted read-only GitHub official-surface resolver snapshot."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        return build_github_resolver_snapshot(
            resolver_plan,
            max_items=max_items,
            query_limit=query_limit,
            include_provider_queries=include_provider_queries,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except GitHubResolverError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/github-resolver-receipts")
def ops_github_resolver_receipts(request: Request, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append redacted resolver receipts from a GitHub read-only snapshot."""
    _authorize_ops_write(request)
    body = payload or {}
    try:
        max_items = int(body.get("max_items") or 100)
        query_limit = int(body.get("query_limit") or 50)
        max_receipts = int(body.get("max_receipts") or max_items)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail="max_items, query_limit, and max_receipts must be numeric") from e
    include_provider_queries = bool(body.get("include_provider_queries", True))
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        snapshot = build_github_resolver_snapshot(
            resolver_plan,
            max_items=max_items,
            query_limit=query_limit,
            include_provider_queries=include_provider_queries,
        )
        return build_github_resolver_receipts(
            snapshot,
            resolver_plan,
            receipt_path=_configured_resolver_ledger_path(),
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except GitHubResolverError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverReceiptError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/followup-resolver")
def ops_followup_resolver(
    request: Request,
    max_items: int = 100,
) -> Dict[str, Any]:
    """Return a redacted mail/LinkedIn follow-up resolver snapshot."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        return build_followup_resolver_snapshot(
            resolver_plan,
            draft_approval_receipt_path=_configured_draft_approval_path(),
            delivery_receipt_path=_configured_delivery_ledger_path(),
            max_items=max_items,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except FollowupResolverError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/followup-resolver-receipts")
def ops_followup_resolver_receipts(request: Request, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append resolver receipts from local mail/LinkedIn follow-up proof."""
    _authorize_ops_write(request)
    body = payload or {}
    try:
        max_items = int(body.get("max_items") or 100)
        max_receipts = int(body.get("max_receipts") or max_items)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail="max_items and max_receipts must be numeric") from e
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        snapshot = build_followup_resolver_snapshot(
            resolver_plan,
            draft_approval_receipt_path=_configured_draft_approval_path(),
            delivery_receipt_path=_configured_delivery_ledger_path(),
            max_items=max_items,
        )
        return build_followup_resolver_receipts(
            snapshot,
            resolver_plan,
            receipt_path=_configured_resolver_ledger_path(),
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except FollowupResolverError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverReceiptError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/external-resolver")
def ops_external_resolver(
    request: Request,
    max_items: int = 100,
) -> Dict[str, Any]:
    """Return a redacted external-surface resolver snapshot."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        return build_external_resolver_snapshot(
            resolver_plan,
            receipt_path=_configured_resolver_ledger_path(),
            max_items=max_items,
            operator_attestation_requested=False,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except ExternalResolverError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/external-resolver-receipts")
def ops_external_resolver_receipts(request: Request, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append local external-surface resolver attestations when explicitly requested."""
    _authorize_ops_write(request)
    body = payload or {}
    try:
        max_items = int(body.get("max_items") or 100)
        max_receipts = int(body.get("max_receipts") or max_items)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail="max_items and max_receipts must be numeric") from e
    attest_blockers = bool(body.get("attest_blockers", False))
    try:
        plan = _build_current_action_plan(max_items=max(max_items, 10000))
        resolver_plan = build_resolver_plan(plan, max_items=max(max_items, 10000))
        snapshot = build_external_resolver_snapshot(
            resolver_plan,
            receipt_path=_configured_resolver_ledger_path(),
            max_items=max_items,
            operator_attestation_requested=attest_blockers,
        )
        return build_external_resolver_receipts(
            snapshot,
            resolver_plan,
            receipt_path=_configured_resolver_ledger_path(),
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except ExternalResolverError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverReceiptError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/resolver-receipts")
def ops_resolver_receipt(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append a redacted official-surface resolver receipt."""
    _authorize_ops_write(request)
    try:
        plan = _build_current_action_plan(max_items=10000)
        resolver_plan = build_resolver_plan(plan, max_items=10000)
        return build_resolver_receipt(
            resolver_plan,
            action_id=str(payload.get("action_id") or ""),
            resolver_status=str(payload.get("resolver_status") or ""),
            reason_code=str(payload.get("reason_code") or ""),
            proof_type=str(payload.get("proof_type") or ""),
            provider=str(payload.get("provider") or ""),
            external_reference=payload.get("external_reference"),
            receipt_path=_configured_resolver_ledger_path(),
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailResolverReceiptError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/action-ledger")
def ops_action_ledger(
    request: Request,
    max_items: int = 100,
    max_receipts: int = 40,
) -> Dict[str, Any]:
    """Return redacted action status and local proof receipts."""
    _authorize(request)
    try:
        plan = _build_current_action_plan(max_items=max_items)
        return build_action_ledger(
            plan,
            receipt_path=_configured_action_ledger_path(),
            max_items=max_items,
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionLedgerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/action-receipts")
def ops_action_receipt(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append a redacted local receipt for an action-plan item."""
    _authorize_ops_write(request)
    evidence_ids = payload.get("evidence_ids") or []
    if isinstance(evidence_ids, str):
        evidence_ids = [item.strip() for item in evidence_ids.split(",") if item.strip()]
    try:
        plan = _build_current_action_plan(max_items=200)
        return build_action_receipt(
            plan,
            action_id=str(payload.get("action_id") or ""),
            action_status=str(payload.get("action_status") or ""),
            reason_code=str(payload.get("reason_code") or ""),
            evidence_ids=evidence_ids,
            receipt_path=_configured_action_ledger_path(),
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionLedgerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/draft-package/{action_id}")
def ops_draft_package(
    action_id: str,
    request: Request,
    ack_private: bool = False,
    user_name: str = "Anthony",
    max_drafts: int = 3,
    body_char_limit: int = 3000,
) -> Dict[str, Any]:
    """Return private approval-gated draft candidates for an action id."""
    _authorize_private_review(request)
    try:
        plan = _build_current_action_plan(max_items=200)
        return build_draft_package(
            plan,
            _configured_intelligence_path(),
            action_id,
            ack_private=ack_private,
            user_name=user_name,
            max_drafts=max_drafts,
            body_char_limit=body_char_limit,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftPackageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/draft-approvals/{action_id}")
def ops_draft_approvals(
    action_id: str,
    request: Request,
    ack_private: bool = False,
    max_drafts: int = 3,
    max_receipts: int = 40,
) -> Dict[str, Any]:
    """Return redacted draft approval status for a private draft package."""
    _authorize_private_review(request)
    try:
        plan = _build_current_action_plan(max_items=200)
        package = build_draft_package(
            plan,
            _configured_intelligence_path(),
            action_id,
            ack_private=ack_private,
            max_drafts=max_drafts,
        )
        return build_draft_approval_ledger(
            package,
            receipt_path=_configured_draft_approval_path(),
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftPackageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftApprovalError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/draft-approvals/{action_id}")
def ops_draft_approval_receipt(
    action_id: str,
    request: Request,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Append a redacted local approval receipt for a draft candidate."""
    _authorize_ops_write(request)
    try:
        plan = _build_current_action_plan(max_items=200)
        package = build_draft_package(
            plan,
            _configured_intelligence_path(),
            action_id,
            ack_private=bool(payload.get("ack_private")),
            max_drafts=int(payload.get("max_drafts") or 3),
        )
        return build_draft_approval_receipt(
            package,
            draft_id=str(payload.get("draft_id") or ""),
            decision=str(payload.get("decision") or ""),
            reason_code=str(payload.get("reason_code") or ""),
            ack_private=bool(payload.get("ack_private")),
            receipt_path=_configured_draft_approval_path(),
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftPackageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftApprovalError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/delivery/{action_id}")
def ops_delivery_ledger(
    action_id: str,
    request: Request,
    ack_private: bool = False,
    max_drafts: int = 3,
    max_receipts: int = 40,
) -> Dict[str, Any]:
    """Return redacted delivery intent/status for approved draft candidates."""
    _authorize_private_review(request)
    try:
        plan = _build_current_action_plan(max_items=200)
        package = build_draft_package(
            plan,
            _configured_intelligence_path(),
            action_id,
            ack_private=ack_private,
            max_drafts=max_drafts,
        )
        return build_delivery_ledger(
            package,
            approval_receipt_path=_configured_draft_approval_path(),
            delivery_receipt_path=_configured_delivery_ledger_path(),
            max_receipts=max_receipts,
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftPackageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except (MailDraftApprovalError, MailDeliveryError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/v1/ops/delivery/{action_id}")
def ops_delivery_receipt(
    action_id: str,
    request: Request,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Append a redacted local delivery receipt for an approved draft candidate."""
    _authorize_ops_write(request)
    try:
        plan = _build_current_action_plan(max_items=200)
        package = build_draft_package(
            plan,
            _configured_intelligence_path(),
            action_id,
            ack_private=bool(payload.get("ack_private")),
            max_drafts=int(payload.get("max_drafts") or 3),
        )
        return build_delivery_receipt(
            package,
            draft_id=str(payload.get("draft_id") or ""),
            delivery_status=str(payload.get("delivery_status") or ""),
            reason_code=str(payload.get("reason_code") or ""),
            provider=str(payload.get("provider") or ""),
            external_reference=payload.get("external_reference"),
            ack_private=bool(payload.get("ack_private")),
            approval_receipt_path=_configured_draft_approval_path(),
            receipt_path=_configured_delivery_ledger_path(),
        )
    except HistoricalIntelligenceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailActionPlanError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except MailDraftPackageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    except (MailDraftApprovalError, MailDeliveryError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/v1/ops/evidence/{evidence_id}")
def ops_evidence_review(
    evidence_id: str,
    request: Request,
    ack_private: bool = False,
    body_char_limit: int = 6000,
    context_limit: int = 6,
) -> Dict[str, Any]:
    """Return gated private source evidence for a redacted evidence id."""
    _authorize_private_review(request)
    try:
        return build_evidence_review(
            _configured_intelligence_path(),
            evidence_id,
            ack_private=ack_private,
            body_char_limit=body_char_limit,
            context_limit=context_limit,
        )
    except MailEvidenceReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
