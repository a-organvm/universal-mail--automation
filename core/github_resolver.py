"""Read-only GitHub official-surface resolver snapshots for UMA."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.mail_resolver_receipt import build_resolver_receipt
from core.mail_resolver_plan import MAIL_RESOLVER_PLAN_SCHEMA

GITHUB_RESOLVER_SNAPSHOT_SCHEMA = "uma.github.resolver_snapshot.v1"
GITHUB_RESOLVER_ACTION_SCHEMA = "uma.github.resolver_action.v1"
GITHUB_RESOLVER_RECEIPTS_SCHEMA = "uma.github.resolver_receipts.v1"

DEFAULT_GITHUB_QUERY_LIMIT = 50
DEFAULT_GITHUB_RESOLVER_MAX_ITEMS = 100
DEFAULT_GITHUB_COMMAND_TIMEOUT_SECONDS = 20

Runner = Callable[[List[str], int], Any]


class GitHubResolverError(ValueError):
    """Raised when a GitHub resolver snapshot cannot be built."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise GitHubResolverError("resolver plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise GitHubResolverError("resolver plan input is not valid JSON") from e
    except OSError as e:
        raise GitHubResolverError(f"resolver plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise GitHubResolverError("resolver plan input has invalid shape")
    return data


def _coerce_resolver_plan(resolver_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(resolver_plan, dict):
        data = resolver_plan
    else:
        data = _read_json(Path(resolver_plan).expanduser())
    if data.get("schema") != MAIL_RESOLVER_PLAN_SCHEMA:
        raise GitHubResolverError(f"resolver plan input must be {MAIL_RESOLVER_PLAN_SCHEMA}")
    return data


def _default_runner(argv: List[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _command_attempt(
    key: str,
    argv: List[str],
    *,
    runner: Runner,
    timeout_seconds: int,
) -> Dict[str, Any]:
    try:
        completed = runner(argv, timeout_seconds)
    except FileNotFoundError:
        return {"key": key, "status": "missing_executable", "returncode": None, "stdout": ""}
    except subprocess.TimeoutExpired:
        return {"key": key, "status": "timeout", "returncode": None, "stdout": ""}
    except OSError:
        return {"key": key, "status": "execution_error", "returncode": None, "stdout": ""}

    returncode = int(getattr(completed, "returncode", 1))
    stdout = getattr(completed, "stdout", "") or ""
    return {
        "key": key,
        "status": "ok" if returncode == 0 else "failed",
        "returncode": returncode,
        "stdout": stdout,
    }


def _json_records(attempt: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[int], str]:
    if attempt.get("status") != "ok":
        return [], None, str(attempt.get("status") or "failed")
    raw = str(attempt.get("stdout") or "").strip()
    if not raw:
        return [], None, "empty_json"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], None, "invalid_json"

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], None, "ok"
    if isinstance(data, dict):
        items = data.get("items")
        records = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        total = _safe_int(data.get("total_count")) if "total_count" in data else None
        return records, total, "ok"
    return [], None, "invalid_json_shape"


def _repo_from_url(raw_url: str) -> Optional[str]:
    marker = "/repos/"
    if marker not in raw_url:
        return None
    tail = raw_url.split(marker, 1)[1].strip("/")
    parts = tail.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None


def _repo_name(record: Dict[str, Any]) -> Optional[str]:
    repo = record.get("repository")
    if isinstance(repo, dict):
        raw = repo.get("full_name") or repo.get("name_with_owner")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        owner = repo.get("owner")
        name = repo.get("name")
        if isinstance(owner, dict):
            owner = owner.get("login")
        if isinstance(owner, str) and isinstance(name, str):
            return f"{owner}/{name}"
    for key in ("repository_url", "url", "html_url"):
        raw_url = record.get(key)
        if isinstance(raw_url, str):
            found = _repo_from_url(raw_url)
            if found:
                return found
    return None


def _safe_reason(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    return raw if raw.replace("_", "").replace("-", "").isalnum() and len(raw) <= 40 else "other"


def _planned_github_items(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in plan.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("resolver_type") == "github_reconcile" or "github" in str(item.get("official_surface") or ""):
            items.append(item)
    return sorted(
        items,
        key=lambda item: (
            -_safe_int(item.get("priority_score")),
            str(item.get("action_id") or ""),
        ),
    )


def _query_specs(gh_bin: str, limit: int) -> List[Tuple[str, List[str]]]:
    bounded = max(1, min(int(limit), 100))
    return [
        (
            "notifications",
            [gh_bin, "api", "notifications", "-X", "GET", "-F", f"per_page={bounded}"],
        ),
        (
            "assigned_issues",
            [gh_bin, "api", "/issues", "-X", "GET", "-F", "filter=all", "-F", "state=open", "-F", f"per_page={bounded}"],
        ),
        (
            "open_pull_requests",
            [
                gh_bin,
                "api",
                "search/issues",
                "-X",
                "GET",
                "-f",
                "q=is:pr is:open involves:@me",
                "-F",
                f"per_page={bounded}",
            ],
        ),
    ]


def _surface_summary(key: str, attempt: Dict[str, Any]) -> Dict[str, Any]:
    records, reported_total, parse_status = _json_records(attempt)
    repos = Counter(filter(None, (_repo_name(record) for record in records)))
    reason_counts = Counter(_safe_reason(record.get("reason")) for record in records if "reason" in record)

    if key == "notifications":
        unread = sum(1 for record in records if bool(record.get("unread")))
        record_count = len(records)
    elif key == "open_pull_requests":
        unread = 0
        record_count = reported_total if reported_total is not None else len(records)
    else:
        unread = 0
        record_count = len(records)

    status = "ok" if attempt.get("status") == "ok" and parse_status == "ok" else parse_status
    if attempt.get("status") != "ok":
        status = str(attempt.get("status") or "failed")

    return {
        "surface": key,
        "status": status,
        "record_count": record_count,
        "bounded_records_reviewed": len(records),
        "unread_count": unread,
        "reason_counts": dict(reason_counts),
        "repository_refs": [
            {"repo_hash": _hash("repo", repo), "record_count": count}
            for repo, count in repos.most_common(20)
        ],
        "raw_output_included": False,
    }


def _external_reference(snapshot_id: str, action_id: str) -> Dict[str, Any]:
    raw = f"github_snapshot:{snapshot_id}:{action_id}"
    return {
        "provided": True,
        "hash": _hash("externalref", raw),
        "stored_raw": False,
    }


def _candidate_status(
    *,
    provider_queries_included: bool,
    gh_available: bool,
    auth_available: bool,
    provider_read_success: bool,
    outstanding_records: int,
) -> Tuple[str, str, bool]:
    if not provider_queries_included:
        return "not_applicable", "not_actionable", False
    if not gh_available:
        return "verified_blocked", "blocked_provider_unavailable", True
    if not auth_available:
        return "verified_blocked", "blocked_no_auth", True
    if not provider_read_success:
        return "needs_follow_up", "blocked_provider_unavailable", True
    if outstanding_records > 0:
        return "needs_follow_up", "official_surface_checked", True
    return "not_found", "official_surface_checked", True


def _action_rows(
    planned_items: List[Dict[str, Any]],
    *,
    snapshot_id: str,
    provider_queries_included: bool,
    gh_available: bool,
    auth_available: bool,
    provider_read_success: bool,
    outstanding_records: int,
) -> List[Dict[str, Any]]:
    status, reason, must_record = _candidate_status(
        provider_queries_included=provider_queries_included,
        gh_available=gh_available,
        auth_available=auth_available,
        provider_read_success=provider_read_success,
        outstanding_records=outstanding_records,
    )
    rows: List[Dict[str, Any]] = []
    for item in planned_items:
        action_id = str(item.get("action_id") or "")
        rows.append(
            {
                "schema": GITHUB_RESOLVER_ACTION_SCHEMA,
                "action_id": action_id,
                "kind": item.get("kind"),
                "priority": item.get("priority"),
                "priority_score": item.get("priority_score"),
                "finding_count": _safe_int(item.get("finding_count")),
                "recommended_lane": item.get("recommended_lane"),
                "resolver_type": item.get("resolver_type"),
                "official_surface": item.get("official_surface"),
                "github_snapshot_status": status,
                "receipt_candidate": {
                    "action_id": action_id,
                    "resolver_status": status,
                    "reason_code": reason,
                    "proof_type": "github_issue_pr_billing_or_security_state",
                    "provider": "github",
                    "external_reference": _external_reference(snapshot_id, action_id),
                    "provider_backed_read": provider_read_success,
                    "provider_backed_automation": False,
                    "operator_must_record_receipt": must_record,
                },
                "mailbox_mutations_allowed": False,
                "send_allowed": False,
                "portal_mutations_allowed": False,
            }
        )
    return rows


def build_github_resolver_snapshot(
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    gh_bin: str = "gh",
    query_limit: int = DEFAULT_GITHUB_QUERY_LIMIT,
    max_items: int = DEFAULT_GITHUB_RESOLVER_MAX_ITEMS,
    include_provider_queries: bool = True,
    timeout_seconds: int = DEFAULT_GITHUB_COMMAND_TIMEOUT_SECONDS,
    runner: Optional[Runner] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a redacted read-only snapshot of GitHub official-surface state."""
    plan = _coerce_resolver_plan(resolver_plan)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    command_runner = runner or _default_runner

    planned_items = _planned_github_items(plan)
    bounded_items = planned_items[: max(1, int(max_items))]
    gh_available = False
    auth_available = False
    provider_read_success = False
    auth_status = "not_checked"
    surfaces: List[Dict[str, Any]] = []

    if include_provider_queries and planned_items:
        version_attempt = _command_attempt(
            "gh_version",
            [gh_bin, "--version"],
            runner=command_runner,
            timeout_seconds=timeout_seconds,
        )
        gh_available = version_attempt.get("status") == "ok"
        if gh_available:
            auth_attempt = _command_attempt(
                "gh_auth_status",
                [gh_bin, "auth", "status", "--hostname", "github.com"],
                runner=command_runner,
                timeout_seconds=timeout_seconds,
            )
            auth_available = auth_attempt.get("status") == "ok"
            auth_status = "ok" if auth_available else str(auth_attempt.get("status") or "failed")
        else:
            auth_status = "missing_executable"

        if gh_available and auth_available:
            for key, argv in _query_specs(gh_bin, query_limit):
                attempt = _command_attempt(key, argv, runner=command_runner, timeout_seconds=timeout_seconds)
                surfaces.append(_surface_summary(key, attempt))
            provider_read_success = any(surface.get("status") == "ok" for surface in surfaces)
    elif not include_provider_queries:
        auth_status = "provider_queries_skipped"

    notifications = next((surface for surface in surfaces if surface["surface"] == "notifications"), {})
    issues = next((surface for surface in surfaces if surface["surface"] == "assigned_issues"), {})
    prs = next((surface for surface in surfaces if surface["surface"] == "open_pull_requests"), {})
    outstanding_records = (
        _safe_int(notifications.get("unread_count"))
        + _safe_int(issues.get("record_count"))
        + _safe_int(prs.get("record_count"))
    )
    all_repo_hashes = {
        repo["repo_hash"]
        for surface in surfaces
        for repo in surface.get("repository_refs", [])
        if isinstance(repo, dict) and repo.get("repo_hash")
    }
    snapshot_id = _hash(
        "ghsnapshot",
        _format_dt(checked_at),
        ",".join(str(item.get("action_id") or "") for item in planned_items),
        outstanding_records,
        ",".join(sorted(all_repo_hashes)),
    )
    actions = _action_rows(
        bounded_items,
        snapshot_id=snapshot_id,
        provider_queries_included=include_provider_queries,
        gh_available=gh_available,
        auth_available=auth_available,
        provider_read_success=provider_read_success,
        outstanding_records=outstanding_records,
    )
    status = "ok"
    if planned_items and include_provider_queries and not gh_available:
        status = "provider_unavailable"
    elif planned_items and include_provider_queries and not auth_available:
        status = "blocked_no_auth"
    elif planned_items and include_provider_queries and not provider_read_success:
        status = "degraded"
    elif planned_items and not include_provider_queries:
        status = "planned_only"

    kpis = {
        "planned_github_actions": len(planned_items),
        "planned_github_findings": sum(_safe_int(item.get("finding_count")) for item in planned_items),
        "official_queries_attempted": len(surfaces),
        "official_queries_successful": sum(1 for surface in surfaces if surface.get("status") == "ok"),
        "notifications_reviewed": _safe_int(notifications.get("record_count")),
        "unread_notifications": _safe_int(notifications.get("unread_count")),
        "assigned_open_issues": _safe_int(issues.get("record_count")),
        "open_pull_requests": _safe_int(prs.get("record_count")),
        "outstanding_official_records": outstanding_records,
        "unique_repository_refs": len(all_repo_hashes),
        "provider_backed_read": 1 if provider_read_success else 0,
        "provider_backed_automation": 0,
        "mailbox_mutations_allowed": 0,
        "send_allowed": 0,
        "portal_mutations_allowed": 0,
    }
    recordable_receipts = sum(
        1
        for action in actions
        if bool((action.get("receipt_candidate") or {}).get("operator_must_record_receipt"))
    )

    return {
        "schema": GITHUB_RESOLVER_SNAPSHOT_SCHEMA,
        "status": status,
        "snapshot_id": snapshot_id,
        "mode": {
            "read_only": True,
            "provider": "github",
            "official_surface": "github_cli_api",
            "provider_backed_read": provider_read_success,
            "provider_backed_automation": False,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
        },
        "source": {
            "resolver_plan_schema": plan.get("schema"),
            "resolver_plan_checked_at": (plan.get("source") or {}).get("checked_at"),
            "checked_at": _format_dt(checked_at),
            "gh_bin": Path(gh_bin).name,
            "query_limit": max(1, min(int(query_limit), 100)),
            "provider_queries_included": include_provider_queries,
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": [
                "github_login",
                "repository_full_name",
                "repository_owner",
                "notification_subject",
                "issue_title",
                "pull_request_title",
                "url",
                "body",
                "raw_command_output",
            ],
            "contains_raw_external_state": False,
            "raw_command_output_included": False,
            "repository_names_hashed": True,
        },
        "auth": {
            "gh_cli_available": gh_available,
            "github_auth_available": auth_available,
            "auth_status": auth_status,
            "raw_output_included": False,
        },
        "coverage": {
            "supported_surfaces": ["notifications", "assigned_issues", "open_pull_requests"],
            "deferred_surfaces": ["billing", "security_alerts", "repository_specific_dependabot_alerts"],
            "coverage_note": "This snapshot proves bounded read-only GitHub CLI/API checks, not provider mutation or complete billing/security reconciliation.",
        },
        "kpis": kpis,
        "answers": {
            "what_matters_now": [
                {
                    "action_id": item.get("action_id"),
                    "finding_count": item.get("finding_count"),
                    "candidate_status": item.get("github_snapshot_status"),
                    "provider_backed_read": provider_read_success,
                }
                for item in actions[:10]
            ],
            "what_is_blocked": {
                "gh_cli_available": gh_available,
                "github_auth_available": auth_available,
                "deferred_surfaces": ["billing", "security_alerts", "repository_specific_dependabot_alerts"],
            },
            "what_proof_exists": {
                "snapshot_id": snapshot_id,
                "official_queries_successful": kpis["official_queries_successful"],
                "receipt_candidates": recordable_receipts,
                "raw_external_state_stored": False,
                "provider_backed_automation": False,
            },
        },
        "surfaces": surfaces,
        "actions": actions,
    }


def build_github_resolver_receipts(
    snapshot: Dict[str, Any],
    resolver_plan: Union[Dict[str, Any], Path, str],
    *,
    receipt_path: Union[Path, str],
    max_receipts: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Record redacted resolver receipts from GitHub snapshot candidates.

    This writes only the local UMA resolver ledger. It does not mutate GitHub,
    mailboxes, portals, drafts, or sends.
    """
    plan = _coerce_resolver_plan(resolver_plan)
    if not isinstance(snapshot, dict) or snapshot.get("schema") != GITHUB_RESOLVER_SNAPSHOT_SCHEMA:
        raise GitHubResolverError(f"snapshot must be {GITHUB_RESOLVER_SNAPSHOT_SCHEMA}")

    actions = [item for item in snapshot.get("actions") or [] if isinstance(item, dict)]
    limit = len(actions) if max_receipts is None else max(0, int(max_receipts))
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    receipts: List[Dict[str, Any]] = []
    candidates_seen = 0
    for action in actions:
        candidate = action.get("receipt_candidate") or {}
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("operator_must_record_receipt")):
            continue
        candidates_seen += 1
        if len(receipts) >= limit:
            continue
        external_reference = candidate.get("external_reference") or {}
        external_hash = external_reference.get("hash") if isinstance(external_reference, dict) else None
        provider_backed_read = bool(candidate.get("provider_backed_read"))
        proof_scope = (
            "official_surface_provider_read_snapshot"
            if provider_backed_read
            else "official_surface_read_blocker_snapshot"
        )
        receipts.append(
            build_resolver_receipt(
                plan,
                action_id=str(candidate.get("action_id") or ""),
                resolver_status=str(candidate.get("resolver_status") or ""),
                reason_code=str(candidate.get("reason_code") or ""),
                proof_type=str(candidate.get("proof_type") or ""),
                provider=str(candidate.get("provider") or "github"),
                external_reference_hash=str(external_hash or ""),
                proof_scope=proof_scope,
                provider_backed_read=provider_backed_read,
                source_snapshot_id=str(snapshot.get("snapshot_id") or ""),
                actor="github_resolver",
                receipt_path=receipt_path,
                now=checked_at,
            )
        )

    provider_backed = sum(1 for receipt in receipts if bool((receipt.get("safety") or {}).get("provider_backed_read")))
    return {
        "schema": GITHUB_RESOLVER_RECEIPTS_SCHEMA,
        "status": "recorded" if receipts else "no_receipts_recorded",
        "mode": {
            "local_file_write": True,
            "provider": "github",
            "read_only_provider_queries": True,
            "provider_backed_read_supported": True,
            "provider_backed_automation": False,
            "mailbox_mutations": False,
            "sends": False,
            "portal_mutations": False,
        },
        "source": {
            "snapshot_schema": snapshot.get("schema"),
            "snapshot_id": snapshot.get("snapshot_id"),
            "snapshot_status": snapshot.get("status"),
            "provider_queries_included": (snapshot.get("source") or {}).get("provider_queries_included"),
            "receipt_filename": Path(receipt_path).expanduser().name,
            "checked_at": _format_dt(checked_at),
        },
        "privacy": {
            "redacted": True,
            "raw_external_state_printed": False,
            "raw_external_state_stored": False,
            "raw_command_output_included": False,
            "repository_names_hashed": True,
            "external_reference_stored_raw": False,
        },
        "kpis": {
            "receipt_candidates": candidates_seen,
            "receipts_recorded": len(receipts),
            "provider_backed_read_receipts": provider_backed,
            "operator_attestation_receipts": len(receipts) - provider_backed,
            "provider_backed_automation": 0,
            "mailbox_mutations_allowed": 0,
            "send_allowed": 0,
            "portal_mutations_allowed": 0,
        },
        "receipts": receipts,
    }
