"""Redacted operator summary contract for local mail-triage reports."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

OPS_SUMMARY_SCHEMA = "uma.ops.summary.v1"
OPS_HISTORY_SCHEMA = "uma.ops.history.v1"
OPS_REFRESH_SCHEMA = "uma.ops.refresh.v1"
DEFAULT_MAX_AGE_HOURS = 12.0

MAIL_TRIAGE_PREFIX = "Mail Triage/"
ACTION_LABEL_RULES = (
    ("GitHub Action Needed", "github_ops", "GitHub Ops", "action"),
    ("Provider Action Needed", "provider_action", "Provider Account Action", "action"),
    ("Provider Security Verify", "security_verify", "Security Verify", "verify"),
    ("Finance Action Needed", "finance_action", "Finance Action Needed", "action"),
    ("Subscription Decision Needed", "subscription_decision", "Subscription Decision Needed", "decision"),
    ("Payment Verify Needed", "payment_verify", "Payment Verify Needed", "verify"),
    ("Legal Sent", "sent_waiting", "Sent / Waiting", "waiting"),
    ("LinkedIn Sent", "sent_waiting", "Sent / Waiting", "waiting"),
    ("Business Follow-Up Sent", "sent_waiting", "Sent / Waiting", "waiting"),
    ("Provider Support Closed", "closed", "Closed", "closed"),
    ("Reviewed Closed", "closed", "Closed", "closed"),
    ("Subscription Reviewed Closed", "closed", "Closed", "closed"),
    ("Newsletter Reviewed", "closed", "Closed", "closed"),
    ("Draft Manual Review", "draft_review", "Draft Manual Review", "decision"),
    ("Draft Superseded", "closed", "Closed", "closed"),
)

BUCKET_LANES = {
    "Urgent / Action": ("urgent_action", "Urgent / Action", "action"),
    "Review": ("review", "Review", "review"),
    "Needs Reply Soon": ("needs_reply", "Needs Reply Soon", "reply"),
    "Waiting / Verify": ("sent_waiting", "Sent / Waiting", "waiting"),
    "Draft / Send Review": ("draft_review", "Draft / Send Review", "decision"),
    "FYI / Noise": ("closed", "Closed / FYI", "closed"),
}


class OpsReportError(ValueError):
    """Raised when a local operator report cannot be loaded or normalized."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_report(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise OpsReportError("operator report not found", status_code=404)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise OpsReportError("operator report is not valid JSON") from e
    if not isinstance(data, dict):
        raise OpsReportError("operator report has invalid shape")
    return data


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _hash_item(bucket: str, item: Dict[str, Any]) -> str:
    material = "|".join(
        str(item.get(k, "")) for k in ("rowid", "conversation_id", "received", "scope")
    )
    return hashlib.sha256(f"{bucket}|{material}".encode("utf-8")).hexdigest()[:16]


def _mail_triage_labels(labels: Iterable[Any]) -> List[str]:
    out = []
    for label in labels or []:
        if isinstance(label, str) and label.startswith(MAIL_TRIAGE_PREFIX):
            out.append(label)
    return out[:8]


def _lane_for_label(label: str) -> Optional[tuple[str, str, str]]:
    for needle, lane_id, title, kind in ACTION_LABEL_RULES:
        if needle in label:
            return lane_id, title, kind
    return None


def _lane_for_item(bucket: str, item: Dict[str, Any]) -> tuple[str, str, str]:
    for label in _mail_triage_labels(item.get("labels") or []):
        lane = _lane_for_label(label)
        if lane:
            return lane
    return BUCKET_LANES.get(bucket, ("other", bucket or "Other", "review"))


def _redacted_item(bucket: str, item: Dict[str, Any]) -> Dict[str, Any]:
    lane_id, lane_title, kind = _lane_for_item(bucket, item)
    return {
        "id": _hash_item(bucket, item),
        "bucket": bucket,
        "lane_id": lane_id,
        "lane": lane_title,
        "kind": kind,
        "received": item.get("received"),
        "state": item.get("state"),
        "scope": item.get("scope"),
        "group_count": _safe_int(item.get("group_count", 1)) or 1,
        "mail_triage_labels": _mail_triage_labels(item.get("labels") or []),
        "why": item.get("why"),
        "next_action": item.get("next_action"),
    }


def _bucket_summaries(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    summaries = []
    buckets = data.get("buckets") or {}
    if not isinstance(buckets, dict):
        return summaries
    for name, items in buckets.items():
        rows = items if isinstance(items, list) else []
        unread = sum(1 for item in rows if item.get("state") == "unread")
        summaries.append(
            {
                "name": name,
                "items": len(rows),
                "unread": unread,
                "sample_items": [_redacted_item(name, item) for item in rows[:5]],
            }
        )
    return summaries


def _action_sidecar(path: Path) -> Optional[Path]:
    candidate = path.with_name("latest-actions.md")
    return candidate if candidate.is_file() else None


def _labels_from_sidecar(path: Path) -> List[Dict[str, Any]]:
    sidecar = _action_sidecar(path)
    if sidecar is None:
        return []
    try:
        text = sidecar.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    pattern = re.compile(
        r"`(Mail Triage/[^`]+)`:\s+(\d+)\s+messages?,\s+(\d+)\s+unread",
        re.I,
    )
    for label, messages, unread in pattern.findall(text):
        rows.append({"label": label, "messages": int(messages), "unread": int(unread)})
    return rows


def _label_lanes(data: Dict[str, Any], path: Path) -> List[Dict[str, Any]]:
    lanes: Dict[str, Dict[str, Any]] = {}
    label_rows: Dict[str, Dict[str, Any]] = {}
    for row in ((data.get("rollups") or {}).get("top_labels") or []):
        label = row.get("label") if isinstance(row, dict) else None
        if not isinstance(label, str) or not label.startswith(MAIL_TRIAGE_PREFIX):
            continue
        label_rows[label] = row
    # The report keeps only top labels, while the action sidecar names small but
    # high-risk queues. Prefer sidecar counts when both sources name a label.
    for row in _labels_from_sidecar(path):
        label_rows[row["label"]] = row
    for row in label_rows.values():
        label = row["label"]
        lane = _lane_for_label(label)
        if not lane:
            continue
        lane_id, title, kind = lane
        target = lanes.setdefault(
            lane_id,
            {"id": lane_id, "title": title, "kind": kind, "messages": 0, "unread": 0, "labels": []},
        )
        messages = _safe_int(row.get("messages"))
        unread = _safe_int(row.get("unread"))
        target["messages"] += messages
        target["unread"] += unread
        target["labels"].append({"label": label, "messages": messages, "unread": unread})
    return sorted(
        lanes.values(),
        key=lambda x: (x["kind"] == "closed", -x["unread"], -x["messages"], x["title"]),
    )


def _coverage(data: Dict[str, Any]) -> Dict[str, Any]:
    counts = data.get("scope_counts") or {}

    def count(name: str, key: str) -> int:
        return _safe_int((counts.get(name) or {}).get(key))

    return {
        "inbox_messages": count("Inbox including Gmail label", "messages"),
        "inbox_unread": count("Inbox including Gmail label", "unread"),
        "all_mail_messages": count("Gmail All Mail", "messages"),
        "all_mail_unread": count("Gmail All Mail", "unread"),
        "archive_messages": count("Archive equivalent", "messages"),
        "archive_unread": count("Archive equivalent", "unread"),
        "scoped_messages": count("All scoped non-deleted", "messages"),
        "scoped_unread": count("All scoped non-deleted", "unread"),
    }


def _escaped_unread_from_sidecar(path: Path) -> Optional[int]:
    sidecar = _action_sidecar(path)
    if sidecar is None:
        return None
    try:
        text = sidecar.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"Escaped unread[^\n]*returned\s+(\d+)\s+messages", text, re.I)
    if not match:
        match = re.search(r"escaped-unread[^\n]*returned\s+(\d+)\s+messages", text, re.I)
    return int(match.group(1)) if match else None


def _parse_report_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    iso_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    match = re.match(
        r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\s+([A-Z]{2,4}))?$",
        text,
    )
    if not match:
        return None
    date_part, time_part, zone = match.groups()
    try:
        naive = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    zones = {
        "UTC": timezone.utc,
        "GMT": timezone.utc,
        "EDT": timezone(timedelta(hours=-4), "EDT"),
        "EST": timezone(timedelta(hours=-5), "EST"),
        "CDT": timezone(timedelta(hours=-5), "CDT"),
        "CST": timezone(timedelta(hours=-6), "CST"),
        "MDT": timezone(timedelta(hours=-6), "MDT"),
        "MST": timezone(timedelta(hours=-7), "MST"),
        "PDT": timezone(timedelta(hours=-7), "PDT"),
        "PST": timezone(timedelta(hours=-8), "PST"),
    }
    tz = zones.get(zone or "UTC")
    return naive.replace(tzinfo=tz).astimezone(timezone.utc) if tz else None


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _freshness(
    generated_at: Any,
    *,
    now: Optional[datetime],
    max_age_hours: Optional[float],
) -> Dict[str, Any]:
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    parsed = _parse_report_datetime(generated_at)
    threshold = DEFAULT_MAX_AGE_HOURS if max_age_hours is None else float(max_age_hours)
    if threshold <= 0:
        threshold = DEFAULT_MAX_AGE_HOURS

    base = {
        "checked_at": _format_utc(checked_at),
        "max_age_hours": threshold,
        "generated_at_parseable": parsed is not None,
    }
    if parsed is None:
        return {
            **base,
            "generated_at_utc": None,
            "age_seconds": None,
            "age_hours": None,
            "is_stale": True,
            "status": "unknown",
            "reason": "generated_at is missing or not parseable",
        }

    age_seconds = int((checked_at - parsed).total_seconds())
    age_hours = round(age_seconds / 3600, 2)
    is_stale = age_seconds > int(threshold * 3600)
    status = "stale" if is_stale else "fresh"
    if age_seconds < 0:
        status = "future"
        is_stale = False
    return {
        **base,
        "generated_at_utc": _format_utc(parsed),
        "age_seconds": age_seconds,
        "age_hours": age_hours,
        "is_stale": is_stale,
        "status": status,
        "reason": (
            f"report is older than {threshold:g} hours"
            if is_stale
            else "report is within freshness window"
        ),
    }


def _history_entry(snapshot: Dict[str, Any], history_file: str) -> Dict[str, Any]:
    kpis = snapshot.get("kpis") or {}
    freshness = snapshot.get("freshness") or {}
    source = snapshot.get("source") or {}
    return {
        "file": history_file,
        "generated_at": source.get("generated_at"),
        "checked_at": freshness.get("checked_at"),
        "is_stale": freshness.get("is_stale"),
        "escaped_unread": kpis.get("escaped_unread"),
        "active_unread": kpis.get("active_unread"),
        "waiting_messages": kpis.get("waiting_messages"),
        "closed_messages": kpis.get("closed_messages"),
    }


def _read_history_index(output_dir: Path) -> Dict[str, Any]:
    index_path = output_dir / "index.json"
    if not index_path.is_file():
        return {"schema": OPS_HISTORY_SCHEMA, "latest": "latest-summary.json", "entries": []}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": OPS_HISTORY_SCHEMA, "latest": "latest-summary.json", "entries": []}
    entries = data.get("entries") if isinstance(data, dict) else []
    return {
        "schema": OPS_HISTORY_SCHEMA,
        "latest": "latest-summary.json",
        "entries": entries if isinstance(entries, list) else [],
    }


def write_ops_snapshot(
    snapshot: Dict[str, Any],
    output_dir: Union[Path, str],
    *,
    history_limit: int = 100,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Persist a redacted operator snapshot and bounded history index."""
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    history_dir = out / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    latest_name = "latest-summary.json"
    latest_path = out / latest_name

    stamp_source = now or datetime.now(timezone.utc)
    if stamp_source.tzinfo is None:
        stamp_source = stamp_source.replace(tzinfo=timezone.utc)
    stamp = stamp_source.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    history_name = f"ops-summary_{stamp}.json"
    history_rel = f"history/{history_name}"
    history_path = out / history_rel

    _json_write(latest_path, snapshot)
    _json_write(history_path, snapshot)

    index = _read_history_index(out)
    existing = [row for row in index["entries"] if row.get("file") != history_rel]
    limit = max(1, int(history_limit))
    index = {
        "schema": OPS_HISTORY_SCHEMA,
        "latest": latest_name,
        "entries": [_history_entry(snapshot, history_rel), *existing][:limit],
    }
    _json_write(out / "index.json", index)

    return {
        "schema": OPS_REFRESH_SCHEMA,
        "status": "ok",
        "output_dir": str(out),
        "latest_summary": str(latest_path),
        "history_index": str(out / "index.json"),
        "history_entry": str(history_path),
        "snapshot": snapshot,
        "history": index,
    }


def load_ops_history(output_dir: Union[Path, str]) -> Dict[str, Any]:
    """Load the redacted operator history index for an output directory."""
    return _read_history_index(Path(output_dir).expanduser())


def build_ops_snapshot(
    report_path: Union[Path, str],
    *,
    now: Optional[datetime] = None,
    max_age_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the canonical redacted operator summary for a local report."""
    path = Path(report_path).expanduser()
    data = _read_report(path)
    lane_summaries = _label_lanes(data, path)
    buckets = _bucket_summaries(data)
    active_unread = sum(
        row["unread"] for row in lane_summaries if row["kind"] in {"action", "verify", "decision"}
    )
    waiting = sum(row["messages"] for row in lane_summaries if row["kind"] == "waiting")
    closed = sum(row["messages"] for row in lane_summaries if row["kind"] == "closed")

    return {
        "schema": OPS_SUMMARY_SCHEMA,
        "status": "ok",
        "source": {
            "filename": path.name,
            "generated_at": data.get("generated_at"),
            "since": data.get("since"),
            "until_exclusive": data.get("until_exclusive"),
            "apply_mode": bool(data.get("apply_mode")),
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": ["sender", "address", "subject", "body", "full_source_path"],
        },
        "freshness": _freshness(
            data.get("generated_at"),
            now=now,
            max_age_hours=max_age_hours,
        ),
        "kpis": {
            **_coverage(data),
            "escaped_unread": _escaped_unread_from_sidecar(path),
            "active_unread": active_unread,
            "waiting_messages": waiting,
            "closed_messages": closed,
        },
        "lanes": lane_summaries,
        "buckets": buckets,
    }
