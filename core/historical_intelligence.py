"""Redacted historical mail intelligence and ops reconciliation."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.ops_summary import OpsReportError, build_ops_snapshot

HISTORICAL_INTELLIGENCE_SCHEMA = "uma.mail.intelligence.v1"
MAIL_ENTITY_SCHEMA = "uma.mail.entity.v1"
MAIL_EVENT_SCHEMA = "uma.mail.event.v1"
MAIL_OPPORTUNITY_SCHEMA = "uma.mail.opportunity.v1"
MAIL_RISK_SCHEMA = "uma.mail.risk.v1"
MAIL_TIMELINE_SCHEMA = "uma.mail.timeline.v1"

DEFAULT_STALE_DAYS = 14

_MAIL_TRIAGE_PREFIX = "Mail Triage/"
_PRIVACY_FIELDS = [
    "sender",
    "address",
    "subject",
    "body",
    "snippet",
    "raw_headers",
    "full_source_path",
]

_REQUEST_RE = re.compile(
    r"\b("
    r"can you|could you|would you|please|let me know|follow(?:\s|-)?up|"
    r"available|interested|open to|schedule|confirm|send|review|approve|"
    r"sign|provide|submit|reply|respond|connect|intro|introduction"
    r")\b",
    re.I,
)
_QUESTION_RE = re.compile(r"\?")

_LEAD_RE = re.compile(
    r"\b("
    r"recruiter|role|job|interview|candidate|client|customer|prospect|"
    r"partnership|partner|investor|business development|consulting|"
    r"freelance|opportunity|inmail"
    r")\b",
    re.I,
)
_LEAD_CONTEXT_RE = re.compile(r"\b(intro|introduction|demo|contract|project|linkedin|collaborat|connect)\b", re.I)
_LEGAL_RE = re.compile(r"\b(lawyer|attorney|counsel|legal|court|case|notice|filing|settlement)\b", re.I)
_FINANCE_RE = re.compile(r"\b(bank|payment|invoice|statement|tax|irs|refund|charge|card|wire|ach|bill|billing)\b", re.I)
_SECURITY_RE = re.compile(r"\b(security|sign[- ]?in|login|password|token|oauth|2fa|mfa|device|session|alert|verify)\b", re.I)
_SUBSCRIPTION_RE = re.compile(r"\b(subscription|renewal|renews|trial|plan|price|pricing|receipt|cancel|invoice)\b", re.I)
_PROVIDER_RE = re.compile(r"\b(cloudflare|google cloud|github|vercel|netlify|aws|azure|stripe|openai|provider|domain|dns)\b", re.I)
_GITHUB_RE = re.compile(r"\b(github|pull request|issue|repository|repo|dependabot|security advisory)\b", re.I)
_LINKEDIN_RE = re.compile(r"\b(linkedin|recruiter|connection request|inmail)\b", re.I)
_AUTOMATED_RE = re.compile(
    r"\b("
    r"no[-_ ]?reply|noreply|do[-_ ]?not[-_ ]?reply|donotreply|"
    r"notification|notifications|alert|alerts|digest|newsletter|"
    r"receipt|statement|invoice|billing|support|security|team"
    r")\b",
    re.I,
)
_DEADLINE_RE = re.compile(
    r"\b("
    r"due|deadline|expires?|renew(?:s|al)?|overdue|final notice|"
    r"by today|by tomorrow|within \d+ (?:hours?|days?)|asap|urgent"
    r")\b",
    re.I,
)
_PROVIDER_HINT_PATTERNS = (
    ("github", re.compile(r"\b(github|dependabot|pull request|repository|repo|security advisory)\b|github\.", re.I)),
    ("linkedin", re.compile(r"\b(linkedin|inmail|connection request)\b|linkedin\.", re.I)),
    ("cloudflare", re.compile(r"\b(cloudflare|cf pages|cloudflare pages|dns zone|zone settings)\b|cloudflare\.", re.I)),
    ("google_cloud", re.compile(r"\b(google cloud|gcp|cloud run|cloud build|google billing account)\b", re.I)),
    ("google_workspace", re.compile(r"\b(google workspace|gmail|admin console|google account)\b", re.I)),
    ("vercel", re.compile(r"\b(vercel|deployment protection|edge config)\b|vercel\.", re.I)),
    ("netlify", re.compile(r"\b(netlify|netlify deploy|netlify forms)\b|netlify\.", re.I)),
    ("aws", re.compile(r"\b(aws|amazon web services|cloudwatch|iam user|ec2|s3 bucket)\b", re.I)),
    ("azure", re.compile(r"\b(azure|microsoft entra|microsoft graph|azure portal)\b", re.I)),
    ("stripe", re.compile(r"\b(stripe|checkout session|payment intent|invoice payment)\b|stripe\.", re.I)),
    ("openai", re.compile(r"\b(openai|chatgpt|api key|platform\.openai)\b", re.I)),
    ("anthropic", re.compile(r"\b(anthropic|claude)\b|anthropic\.", re.I)),
    ("apple", re.compile(r"\b(apple id|icloud|app store connect)\b|icloud\.", re.I)),
    ("microsoft", re.compile(r"\b(microsoft account|outlook|office 365|microsoft 365)\b", re.I)),
    ("paypal", re.compile(r"\b(paypal)\b|paypal\.", re.I)),
    ("intuit", re.compile(r"\b(intuit|turbotax|quickbooks)\b|intuit\.", re.I)),
    ("onepassword", re.compile(r"\b(1password|onepassword)\b|1password\.", re.I)),
    ("slack", re.compile(r"\b(slack|slack workspace)\b|slack\.", re.I)),
    ("notion", re.compile(r"\b(notion)\b|notion\.", re.I)),
    ("dropbox", re.compile(r"\b(dropbox)\b|dropbox\.", re.I)),
)


class HistoricalIntelligenceError(ValueError):
    """Raised when a historical mail input cannot be loaded or normalized."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise HistoricalIntelligenceError("historical mail input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HistoricalIntelligenceError("historical mail input is not valid JSON") from e
    except OSError as e:
        raise HistoricalIntelligenceError(f"historical mail input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise HistoricalIntelligenceError("historical mail input has invalid shape")
    return data


def _records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = data.get("messages")
    if raw is None:
        raw = data.get("records")
    if not isinstance(raw, list):
        raise HistoricalIntelligenceError("historical mail input requires a messages array")
    return [row for row in raw if isinstance(row, dict)]


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(row: Dict[str, Any]) -> str:
    bits = [row.get("subject"), row.get("body"), row.get("snippet")]
    return "\n".join(str(bit) for bit in bits if isinstance(bit, str))


def _provider_text(row: Dict[str, Any], text: Optional[str] = None) -> str:
    bits = [
        row.get("sender"),
        row.get("address"),
        row.get("from"),
        row.get("from_address"),
        row.get("sender_email"),
        row.get("subject"),
        row.get("snippet"),
    ]
    if text is not None:
        bits.append(text)
    return "\n".join(str(bit) for bit in bits if isinstance(bit, str))


def _provider_hints(row: Dict[str, Any], text: Optional[str] = None) -> List[str]:
    haystack = _provider_text(row, text)
    return [name for name, pattern in _PROVIDER_HINT_PATTERNS if pattern.search(haystack)]


def _direction(row: Dict[str, Any]) -> str:
    raw = str(row.get("direction") or row.get("state") or "").strip().lower()
    if raw in {"sent", "out", "outbound", "from_me", "me"}:
        return "outbound"
    if raw in {"in", "inbound", "received"}:
        return "inbound"
    labels = " ".join(str(label).lower() for label in row.get("labels") or [])
    if "sent" in labels:
        return "outbound"
    return "inbound"


def _parse_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _age_days(row: Dict[str, Any], now: datetime) -> int:
    received = _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
    if received is None:
        return 0
    return max(0, int((now.astimezone(timezone.utc) - received).total_seconds() // 86400))


def _thread_key(row: Dict[str, Any]) -> str:
    return str(
        row.get("thread_id")
        or row.get("conversation_id")
        or row.get("thread")
        or row.get("message_id")
        or row.get("id")
        or "unknown"
    )


def _record_key(row: Dict[str, Any]) -> str:
    return str(row.get("message_id") or row.get("id") or row.get("rowid") or _thread_key(row))


def _evidence_id(row: Dict[str, Any]) -> str:
    return _hash(
        "ev",
        _thread_key(row),
        _record_key(row),
        row.get("received_at") or row.get("received") or row.get("date"),
        _direction(row),
    )


def evidence_id_for_row(row: Dict[str, Any]) -> str:
    """Return the stable redacted evidence id for a normalized mail row."""
    return _evidence_id(row)


def _mail_triage_labels(labels: Iterable[Any]) -> List[str]:
    return [
        label
        for label in labels or []
        if isinstance(label, str) and label.startswith(_MAIL_TRIAGE_PREFIX)
    ][:8]


def _signals(text: str) -> List[str]:
    lowered = text.lower()
    out = []
    checks = (
        ("human_ask", _REQUEST_RE),
        ("opportunity", _LEAD_RE),
        ("legal", _LEGAL_RE),
        ("finance", _FINANCE_RE),
        ("security", _SECURITY_RE),
        ("subscription", _SUBSCRIPTION_RE),
        ("provider", _PROVIDER_RE),
        ("github", _GITHUB_RE),
        ("linkedin", _LINKEDIN_RE),
        ("deadline", _DEADLINE_RE),
    )
    for name, pattern in checks:
        if pattern.search(lowered):
            out.append(name)
    if _QUESTION_RE.search(text):
        out.append("question")
    if "opportunity" not in out and _LEAD_CONTEXT_RE.search(lowered):
        out.append("opportunity_context")
    return out


def _recommended_lane(kind: str, signals: Iterable[str]) -> str:
    signal_set = set(signals)
    if kind in {"missed_lead", "stale_relationship"}:
        return "needs_reply"
    if "github" in signal_set:
        return "github_ops"
    if "security" in signal_set:
        return "security_verify"
    if "subscription" in signal_set:
        return "subscription_decision"
    if "finance" in signal_set:
        return "payment_verify" if kind == "payment_or_billing" else "finance_action"
    if "legal" in signal_set:
        return "draft_review"
    if "provider" in signal_set:
        return "provider_action"
    if "linkedin" in signal_set:
        return "needs_reply"
    return "review"


def _is_automated_noise(row: Dict[str, Any], text: str) -> bool:
    sender_bits = " ".join(
        str(row.get(key) or "")
        for key in ("sender", "address", "from", "from_address", "sender_email", "subject")
    )
    return bool(_AUTOMATED_RE.search(sender_bits) or _AUTOMATED_RE.search(text[:500]))


def _is_missed_lead_candidate(row: Dict[str, Any], text: str, signals: Iterable[str]) -> bool:
    signal_set = set(signals)
    has_core_lead = bool(_LEAD_RE.search(text))
    has_linkedin_lead = "linkedin" in signal_set and (has_core_lead or bool(_LEAD_CONTEXT_RE.search(text)))
    if not has_core_lead and not has_linkedin_lead:
        return False
    if "github" in signal_set:
        return False
    operational_signals = {"security", "finance", "subscription", "provider", "legal"} & signal_set
    if operational_signals:
        return False
    if _is_automated_noise(row, text) and "human_ask" not in signal_set:
        return False
    return True


def _kind_from_signals(signals: Iterable[str]) -> Optional[str]:
    signal_set = set(signals)
    if "github" in signal_set:
        return "github_work"
    if "security" in signal_set:
        return "security_or_account"
    if "legal" in signal_set:
        return "legal_obligation"
    if "subscription" in signal_set:
        return "subscription_or_spend"
    if "finance" in signal_set:
        return "payment_or_billing"
    if "provider" in signal_set:
        return "provider_incident"
    return None


def _event_type(signals: Iterable[str]) -> Optional[str]:
    signal_set = set(signals)
    if signal_set & {"security", "legal", "finance", "subscription", "provider", "github"}:
        return _kind_from_signals(signal_set)
    if signal_set & {"opportunity", "linkedin", "human_ask"}:
        return "relationship_or_opportunity"
    return None


def _severity(kind: str, signals: Iterable[str]) -> str:
    signal_set = set(signals)
    if kind == "github_work" and "security" in signal_set:
        return "high"
    if kind in {"security_or_account", "legal_obligation"} and "deadline" in signal_set:
        return "critical"
    if kind in {"security_or_account", "legal_obligation", "payment_or_billing"}:
        return "high"
    if kind in {"subscription_or_spend", "provider_incident", "github_work"}:
        return "medium"
    return "low"


def _risk_status(kind: str) -> str:
    if kind in {"security_or_account", "provider_incident", "payment_or_billing"}:
        return "needs_portal_verification"
    if kind == "legal_obligation":
        return "needs_human_review"
    if kind == "subscription_or_spend":
        return "decision_needed"
    return "needs_review"


def _next_action(kind: str, lane: str) -> str:
    if kind == "missed_lead":
        return "Review evidence and draft a follow-up if still relevant."
    if kind == "security_or_account":
        return "Verify directly in the official provider account before acting."
    if kind == "legal_obligation":
        return "Review with source evidence before drafting or sending anything."
    if kind == "subscription_or_spend":
        return "Decide keep, cancel, downgrade, or verify billing in the provider portal."
    if kind == "payment_or_billing":
        return "Verify payment state in the official financial or billing surface."
    if kind == "provider_incident":
        return "Open the provider's official dashboard or CLI and reconcile status."
    if lane == "github_ops":
        return "Reconcile the GitHub thread with issues, PRs, billing, or security alerts."
    return "Review the redacted evidence and assign a current ops lane."


def _entity_key(row: Dict[str, Any]) -> str:
    sender = str(row.get("address") or row.get("sender") or "unknown").strip().lower()
    if "@" in sender:
        sender = sender.split("@", 1)[1].strip(" >")
    return sender or "unknown"


def _build_entities(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = _entity_key(row)
        target = grouped.setdefault(
            key,
            {
                "schema": MAIL_ENTITY_SCHEMA,
                "id": _hash("entity", key),
                "kind": "organization" if key != "unknown" else "unknown",
                "role": "external_counterparty",
                "message_count": 0,
                "evidence_count": 0,
                "first_seen": None,
                "last_seen": None,
                "signal_counts": Counter(),
                "provider_hint_counts": Counter(),
            },
        )
        target["message_count"] += 1
        target["evidence_count"] += 1
        parsed = _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
        if parsed is not None:
            if target["first_seen"] is None or parsed < target["first_seen"]:
                target["first_seen"] = parsed
            if target["last_seen"] is None or parsed > target["last_seen"]:
                target["last_seen"] = parsed
        text = _text(row)
        for signal in _signals(text):
            target["signal_counts"][signal] += 1
        for hint in _provider_hints(row, text):
            target["provider_hint_counts"][hint] += 1

    entities = []
    for row in grouped.values():
        counts = row.pop("signal_counts")
        provider_counts = row.pop("provider_hint_counts")
        row["first_seen"] = _format_dt(row["first_seen"])
        row["last_seen"] = _format_dt(row["last_seen"])
        row["top_signals"] = [name for name, _count in counts.most_common(6)]
        row["top_provider_hints"] = [name for name, _count in provider_counts.most_common(6)]
        entities.append(row)
    return sorted(entities, key=lambda item: (-item["message_count"], item["id"]))


def _build_evidence(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        text = _text(row)
        signals = _signals(text)
        provider_hints = _provider_hints(row, text)
        out.append(
            {
                "id": _evidence_id(row),
                "thread_id": _hash("thread", _thread_key(row)),
                "occurred_at": _format_dt(
                    _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
                ),
                "direction": _direction(row),
                "scope": row.get("scope"),
                "state": row.get("state"),
                "mail_triage_labels": _mail_triage_labels(row.get("labels") or []),
                "signals": signals,
                "provider_hints": provider_hints,
            }
        )
    return out


def _build_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        text = _text(row)
        signals = _signals(text)
        event_type = _event_type(signals)
        if not event_type:
            continue
        lane = _recommended_lane(event_type, signals)
        out.append(
            {
                "schema": MAIL_EVENT_SCHEMA,
                "id": _hash("event", _thread_key(row), _record_key(row), event_type),
                "type": event_type,
                "occurred_at": _format_dt(
                    _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
                ),
                "direction": _direction(row),
                "severity": _severity(event_type, signals),
                "recommended_lane": lane,
                "signals": signals,
                "provider_hints": _provider_hints(row, text),
                "evidence_ids": [_evidence_id(row)],
            }
        )
    return sorted(out, key=lambda item: (item.get("occurred_at") or "", item["id"]))


def _thread_rows(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_thread_key(row)].append(row)
    for key in grouped:
        grouped[key].sort(
            key=lambda row: (
                _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
                or datetime.min.replace(tzinfo=timezone.utc)
            )
        )
    return grouped


def _has_later_outbound(rows: List[Dict[str, Any]], after: Dict[str, Any]) -> bool:
    after_dt = _parse_dt(after.get("received_at") or after.get("received") or after.get("date"))
    for row in rows:
        if _direction(row) != "outbound":
            continue
        row_dt = _parse_dt(row.get("received_at") or row.get("received") or row.get("date"))
        if after_dt is None or row_dt is None or row_dt >= after_dt:
            return True
    return False


def _build_opportunities(
    rows: List[Dict[str, Any]],
    *,
    now: datetime,
    stale_days: int,
) -> List[Dict[str, Any]]:
    out = []
    for thread_key, thread in _thread_rows(rows).items():
        inbound_candidates = []
        for row in thread:
            text = _text(row)
            signals = _signals(text)
            if _direction(row) != "inbound":
                continue
            if "human_ask" not in signals and "question" not in signals:
                continue
            if not _is_missed_lead_candidate(row, text, signals):
                continue
            if _has_later_outbound(thread, row):
                continue
            age = _age_days(row, now)
            if age < stale_days:
                continue
            inbound_candidates.append((row, signals, age))

        if not inbound_candidates:
            continue
        row, signals, age = max(inbound_candidates, key=lambda item: item[2])
        lane = _recommended_lane("missed_lead", signals)
        signal_set = set(signals)
        score = 55 + min(age, 90)
        if "opportunity" in signal_set:
            score += 20
        if "linkedin" in signal_set:
            score += 8
        if "question" in signal_set:
            score += 7
        confidence = "high" if score >= 95 else "medium"
        out.append(
            {
                "schema": MAIL_OPPORTUNITY_SCHEMA,
                "id": _hash("opp", thread_key, _record_key(row), "missed_lead"),
                "kind": "missed_lead",
                "status": "candidate",
                "confidence": confidence,
                "score": min(score, 100),
                "stale_days": age,
                "recommended_lane": lane,
                "signals": signals,
                "provider_hints": _provider_hints(row, _text(row)),
                "evidence_ids": [_evidence_id(row)],
                "next_action": _next_action("missed_lead", lane),
            }
        )
    return sorted(out, key=lambda item: (-item["score"], -item["stale_days"], item["id"]))


def _build_risks(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        text = _text(row)
        signals = _signals(text)
        kind = _kind_from_signals(signals)
        if kind is None:
            continue
        lane = _recommended_lane(kind, signals)
        severity = _severity(kind, signals)
        out.append(
            {
                "schema": MAIL_RISK_SCHEMA,
                "id": _hash("risk", _thread_key(row), _record_key(row), kind),
                "kind": kind,
                "status": _risk_status(kind),
                "severity": severity,
                "recommended_lane": lane,
                "needs_portal_verification": kind in {"security_or_account", "provider_incident", "payment_or_billing"},
                "signals": signals,
                "provider_hints": _provider_hints(row, text),
                "evidence_ids": [_evidence_id(row)],
                "next_action": _next_action(kind, lane),
            }
        )
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(out, key=lambda item: (severity_rank.get(item["severity"], 9), item["id"]))


def _build_timeline(events: List[Dict[str, Any]], opportunities: List[Dict[str, Any]], risks: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[str, Counter] = defaultdict(Counter)
    for event in events:
        month = (event.get("occurred_at") or "unknown")[:7] or "unknown"
        buckets[month]["events"] += 1
        buckets[month][event["type"]] += 1
    for opportunity in opportunities:
        buckets["unresolved"]["opportunities"] += 1
        buckets["unresolved"][opportunity["kind"]] += 1
    for risk in risks:
        buckets["unresolved"]["risks"] += 1
        buckets["unresolved"][risk["kind"]] += 1
    return {
        "schema": MAIL_TIMELINE_SCHEMA,
        "buckets": [
            {"period": period, **dict(counter)}
            for period, counter in sorted(buckets.items(), key=lambda item: item[0])
        ],
    }


def _provider_hint_counts(*collections: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Counter = Counter()
    for collection in collections:
        for row in collection:
            for hint in row.get("provider_hints") or []:
                if isinstance(hint, str):
                    counts[hint] += 1
    return dict(counts.most_common())


def _ops_lane_index(ops_report_path: Optional[Union[Path, str]]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    if not ops_report_path:
        return None, {}
    try:
        snapshot = build_ops_snapshot(Path(ops_report_path).expanduser())
    except OpsReportError:
        return None, {}
    lanes = {
        row.get("id"): row
        for row in snapshot.get("lanes") or []
        if isinstance(row, dict) and row.get("id")
    }
    return snapshot, lanes


def _reconcile(
    *,
    opportunities: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    ops_snapshot: Optional[Dict[str, Any]],
    ops_lanes: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    findings = []
    for item in [*opportunities, *risks]:
        lane = item.get("recommended_lane") or "review"
        ops_lane = ops_lanes.get(lane)
        if ops_snapshot is None:
            status = "ops_not_supplied"
        elif ops_lane and (_safe_int(ops_lane.get("messages")) or _safe_int(ops_lane.get("unread"))):
            status = "represented_in_ops"
        else:
            status = "not_represented_in_current_ops"
        findings.append(
            {
                "id": item["id"],
                "finding_schema": item["schema"],
                "kind": item["kind"],
                "severity": item.get("severity"),
                "recommended_lane": lane,
                "ops_lane_status": status,
                "ops_lane_messages": _safe_int((ops_lane or {}).get("messages")),
                "ops_lane_unread": _safe_int((ops_lane or {}).get("unread")),
                "next_action": item.get("next_action"),
                "evidence_ids": item.get("evidence_ids", []),
            }
        )
    represented = sum(1 for item in findings if item["ops_lane_status"] == "represented_in_ops")
    not_represented = sum(1 for item in findings if item["ops_lane_status"] == "not_represented_in_current_ops")
    return {
        "ops_source": {
            "supplied": ops_snapshot is not None,
            "schema": (ops_snapshot or {}).get("schema"),
            "freshness": (ops_snapshot or {}).get("freshness"),
            "kpis": (ops_snapshot or {}).get("kpis"),
        },
        "kpis": {
            "findings": len(findings),
            "represented_in_ops": represented,
            "not_represented_in_current_ops": not_represented,
            "ops_not_supplied": sum(1 for item in findings if item["ops_lane_status"] == "ops_not_supplied"),
        },
        "findings": findings,
    }


def _answers(
    *,
    opportunities: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    reconciliation: Dict[str, Any],
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    unresolved_by_kind = Counter(risk["kind"] for risk in risks)
    missed_by_kind = Counter(opp["kind"] for opp in opportunities)
    provider_counts = _provider_hint_counts(opportunities, risks)
    blocked = sum(
        1
        for risk in risks
        if risk.get("status") in {"needs_portal_verification", "needs_human_review", "decision_needed"}
    )
    return {
        "what_did_i_miss": {
            "missed_opportunities": len(opportunities),
            "missed_by_kind": dict(missed_by_kind),
        },
        "what_matters_now": {
            "unresolved_risks": len(risks),
            "unresolved_by_kind": dict(unresolved_by_kind),
            "high_or_critical": sum(1 for risk in risks if risk.get("severity") in {"critical", "high"}),
        },
        "what_should_happen_next": [
            {
                "kind": item["kind"],
                "recommended_lane": item["recommended_lane"],
                "next_action": item["next_action"],
            }
            for item in reconciliation.get("findings", [])[:10]
        ],
        "what_is_blocked": {
            "needs_portal_or_human_verification": blocked,
            "not_represented_in_current_ops": reconciliation.get("kpis", {}).get("not_represented_in_current_ops", 0),
            "top_provider_hints": list(provider_counts)[:10],
        },
        "what_was_safely_handled": {
            "represented_in_ops": reconciliation.get("kpis", {}).get("represented_in_ops", 0),
            "mailbox_mutations": 0,
        },
        "what_proof_exists": {
            "redacted_evidence_items": len(evidence),
            "source_backed": True,
            "privacy_redacted": True,
            "provider_hints_are_controlled_slugs": True,
        },
    }


def build_historical_intelligence(
    history_path: Union[Path, str],
    *,
    ops_report_path: Optional[Union[Path, str]] = None,
    now: Optional[datetime] = None,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> Dict[str, Any]:
    """Build a redacted historical intelligence snapshot from a mail export.

    The input may contain raw senders, addresses, subjects, snippets, and bodies.
    The returned payload intentionally omits those fields and keeps only stable
    redacted IDs, evidence IDs, normalized signals, and current-lane
    reconciliation.
    """
    path = Path(history_path).expanduser()
    data = _read_json(path)
    rows = _records(data)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    stale_threshold = max(1, int(stale_days))

    evidence = _build_evidence(rows)
    events = _build_events(rows)
    opportunities = _build_opportunities(rows, now=checked_at, stale_days=stale_threshold)
    risks = _build_risks(rows)
    entities = _build_entities(rows)
    timeline = _build_timeline(events, opportunities, risks)
    ops_snapshot, ops_lanes = _ops_lane_index(ops_report_path)
    reconciliation = _reconcile(
        opportunities=opportunities,
        risks=risks,
        ops_snapshot=ops_snapshot,
        ops_lanes=ops_lanes,
    )
    provider_hint_counts = _provider_hint_counts(evidence)

    return {
        "schema": HISTORICAL_INTELLIGENCE_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "generic_vector_store": False,
        },
        "source": {
            "filename": path.name,
            "generated_at": data.get("generated_at"),
            "since": data.get("since"),
            "until_exclusive": data.get("until_exclusive"),
            "message_count": len(rows),
            "checked_at": _format_dt(checked_at),
            "stale_days": stale_threshold,
        },
        "privacy": {
            "redacted": True,
            "omitted_fields": _PRIVACY_FIELDS,
            "private_review_required_for_raw_mail": True,
        },
        "kpis": {
            "entities": len(entities),
            "events": len(events),
            "opportunities": len(opportunities),
            "risks": len(risks),
            "evidence_items": len(evidence),
            "provider_hint_counts": provider_hint_counts,
            "provider_hint_total": sum(provider_hint_counts.values()),
            "represented_in_ops": reconciliation["kpis"]["represented_in_ops"],
            "not_represented_in_current_ops": reconciliation["kpis"]["not_represented_in_current_ops"],
        },
        "answers": _answers(
            opportunities=opportunities,
            risks=risks,
            reconciliation=reconciliation,
            evidence=evidence,
        ),
        "entities": entities,
        "events": events,
        "opportunities": opportunities,
        "risks": risks,
        "timeline": timeline,
        "reconciliation": reconciliation,
        "evidence": evidence,
    }
