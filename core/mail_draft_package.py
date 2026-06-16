"""Gated private draft packages built from verified mail evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.mail_action_plan import MAIL_ACTION_PLAN_SCHEMA
from core.mail_evidence_review import MailEvidenceReviewError, build_evidence_review

MAIL_DRAFT_PACKAGE_SCHEMA = "uma.mail.draft_package.v1"
MAIL_DRAFT_CANDIDATE_SCHEMA = "uma.mail.draft_candidate.v1"

DEFAULT_MAX_DRAFTS = 3
DEFAULT_BODY_CHAR_LIMIT = 3000


class MailDraftPackageError(ValueError):
    """Raised when a private draft package cannot be built."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(prefix: str, *parts: Any, length: int = 16) -> str:
    material = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _read_action_plan(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise MailDraftPackageError("action plan input not found", status_code=404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MailDraftPackageError("action plan input is not valid JSON") from e
    except OSError as e:
        raise MailDraftPackageError(f"action plan input could not be read: {e}") from e
    if not isinstance(data, dict):
        raise MailDraftPackageError("action plan input has invalid shape")
    return data


def _coerce_action_plan(action_plan: Union[Dict[str, Any], Path, str]) -> Dict[str, Any]:
    if isinstance(action_plan, dict):
        data = action_plan
    else:
        data = _read_action_plan(Path(action_plan).expanduser())
    if data.get("schema") != MAIL_ACTION_PLAN_SCHEMA:
        raise MailDraftPackageError(f"action plan input must be {MAIL_ACTION_PLAN_SCHEMA}")
    return data


def _action_by_id(action_plan: Dict[str, Any], action_id: str) -> Dict[str, Any]:
    for item in action_plan.get("items") or []:
        if isinstance(item, dict) and item.get("id") == action_id:
            return item
    raise MailDraftPackageError("action_id is not present in the current action plan", status_code=404)


def _first_name(sender: Any, address: Any) -> str:
    raw = str(sender or "").strip()
    if not raw:
        raw = str(address or "").split("@", 1)[0]
    raw = re.sub(r"[<\"']", "", raw).strip()
    token = raw.split()[0] if raw.split() else ""
    token = re.sub(r"[^A-Za-z0-9._-]", "", token)
    return token or "there"


def _reply_subject(subject: Any) -> str:
    raw = str(subject or "").strip()
    if not raw:
        return "Re:"
    return raw if raw.lower().startswith("re:") else f"Re: {raw}"


def _text_bits(message: Dict[str, Any]) -> str:
    bits = [message.get("subject"), message.get("snippet"), message.get("body")]
    return "\n".join(str(bit) for bit in bits if isinstance(bit, str))


def _intent_hint(message: Dict[str, Any]) -> str:
    text = _text_bits(message).lower()
    if "availability" in text or "available" in text or "schedule" in text:
        return "scheduling"
    if "interview" in text or "role" in text or "job" in text or "recruiter" in text:
        return "opportunity"
    if "partnership" in text or "partner" in text or "client" in text:
        return "business_development"
    return "follow_up"


def _draft_body(message: Dict[str, Any], *, user_name: str) -> str:
    name = _first_name(message.get("sender"), message.get("address"))
    signature = (user_name or "").strip() or "Anthony"
    intent = _intent_hint(message)
    if intent == "scheduling":
        ask = "Could you send a few current times that still work, and I can confirm from there?"
    elif intent == "opportunity":
        ask = "If this is still current, could you send the latest details and a few times that work for a quick call?"
    elif intent == "business_development":
        ask = "If this is still relevant, could you send the current context and what would be useful from me?"
    else:
        ask = "If this is still current, could you send the latest context and what you need from me?"
    return "\n\n".join(
        [
            f"Hi {name},",
            "Thanks for reaching out, and sorry for the slow reply.",
            ask,
            f"Best,\n{signature}",
        ]
    )


def _fact_checklist(review: Dict[str, Any]) -> List[Dict[str, Any]]:
    message = review.get("message") or {}
    facts = []
    for field in ("evidence_id", "occurred_at", "direction", "sender", "address", "subject"):
        value = message.get(field)
        if value:
            facts.append({"field": field, "value": value, "source": "source_message"})
    return facts


def _draft_candidate(
    action: Dict[str, Any],
    review: Dict[str, Any],
    *,
    user_name: str,
) -> Dict[str, Any]:
    message = review.get("message") or {}
    evidence_id = message.get("evidence_id")
    draft_id = _hash("draft", action.get("id"), evidence_id, message.get("address"), message.get("subject"))
    return {
        "schema": MAIL_DRAFT_CANDIDATE_SCHEMA,
        "draft_id": draft_id,
        "action_id": action.get("id"),
        "evidence_id": evidence_id,
        "to": {
            "name": message.get("sender"),
            "address": message.get("address"),
        },
        "subject": _reply_subject(message.get("subject")),
        "body": _draft_body(message, user_name=user_name),
        "source_message": {
            "occurred_at": message.get("occurred_at"),
            "direction": message.get("direction"),
            "scope": message.get("scope"),
            "state": message.get("state"),
            "subject": message.get("subject"),
        },
        "fact_checklist": _fact_checklist(review),
        "fact_warnings": [
            "Draft is template-generated from one private source message.",
            "Verify current context before approving.",
            "Approval is required before any send.",
        ],
        "approval": {
            "required": True,
            "approval_type": action.get("approval_type"),
            "ready_to_send": False,
            "send_allowed": False,
        },
    }


def build_draft_package(
    action_plan: Union[Dict[str, Any], Path, str],
    history_path: Union[Path, str],
    action_id: str,
    *,
    ack_private: bool = False,
    user_name: str = "Anthony",
    max_drafts: int = DEFAULT_MAX_DRAFTS,
    body_char_limit: int = DEFAULT_BODY_CHAR_LIMIT,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build private, approval-gated draft candidates for one action group."""
    if not ack_private:
        raise MailDraftPackageError("private draft package requires ack_private=true", status_code=403)
    if not action_id:
        raise MailDraftPackageError("action_id is required")

    plan = _coerce_action_plan(action_plan)
    action = _action_by_id(plan, action_id)
    if action.get("approval_type") != "draft_approval" or action.get("kind") != "missed_lead":
        raise MailDraftPackageError(
            "draft packages are only supported for missed_lead actions requiring draft_approval",
            status_code=409,
        )

    evidence_ids = [
        evidence_id
        for evidence_id in action.get("sample_evidence_ids") or []
        if isinstance(evidence_id, str)
    ][: max(1, int(max_drafts))]
    if not evidence_ids:
        raise MailDraftPackageError("action has no sample evidence ids", status_code=404)

    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)

    candidates = []
    for evidence_id in evidence_ids:
        try:
            review = build_evidence_review(
                history_path,
                evidence_id,
                ack_private=True,
                body_char_limit=body_char_limit,
                context_limit=2,
            )
        except MailEvidenceReviewError as e:
            raise MailDraftPackageError(e.detail, status_code=e.status_code) from e
        candidates.append(_draft_candidate(action, review, user_name=user_name))

    return {
        "schema": MAIL_DRAFT_PACKAGE_SCHEMA,
        "status": "ok",
        "mode": {
            "read_only": True,
            "private_review": True,
            "draft_only": True,
            "mailbox_mutations": False,
            "sends": False,
            "archive_changes": False,
            "approval_required_before_send": True,
        },
        "source": {
            "action_plan_schema": plan.get("schema"),
            "history_filename": Path(history_path).expanduser().name,
            "checked_at": _format_dt(checked_at),
        },
        "request": {
            "action_id": action_id,
            "ack_private": True,
            "max_drafts": max(1, int(max_drafts)),
            "body_char_limit": max(0, int(body_char_limit)),
        },
        "privacy": {
            "redacted": False,
            "contains_private_mail": True,
            "public_safe": False,
            "requires_explicit_private_review": True,
            "omits_full_source_path": True,
        },
        "safety": {
            "send_allowed": False,
            "mailbox_mutations_allowed": False,
            "draft_requires_approval": True,
            "records_external_claim_only": False,
        },
        "action": {
            "id": action.get("id"),
            "kind": action.get("kind"),
            "approval_type": action.get("approval_type"),
            "recommended_lane": action.get("recommended_lane"),
            "finding_count": action.get("finding_count"),
        },
        "drafts": candidates,
    }
