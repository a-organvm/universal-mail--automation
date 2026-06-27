"""
Mailbox triage orchestration: prioritise, research, and (optionally) draft.

This module is the spine the task calls for. For a batch of messages it:

    1. Categorises each item against the shared taxonomy (tier + VIP).
    2. Applies age-based escalation (re-prioritising stale, time-sensitive mail).
    3. Runs content & context research (core.research) to learn what each
       message is actually asking for.
    4. Computes a single composite **priority score** and sorts the mailbox by
       it — the "sort of prioritizations" the task requires.
    5. Optionally drafts a suggested reply in the user's own voice
       (core.voice) for items that expect a response.

It is provider-agnostic: callers pass already-fetched ``EmailMessage`` objects
(plus an optional ``bodies`` map), so the logic is fully unit-testable offline.

Public API:
    triage_messages(messages, bodies=None, voice=None, now=None, draft=False) -> list[TriageItem]
    render_triage(items, fmt="text") -> str
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.models import EmailMessage
from core.research import ResearchDossier, research_message
from core.rules import (
    EscalationResult,
    calculate_email_age_hours,
    categorize_with_tier,
    escalate_by_age,
    get_tier_config,
)
from core.voice import VoiceProfile

# Composite-score weights. Lower tier number == higher priority, so tiers are
# inverted into a base score; everything else stacks additively. Values are
# deliberately readable rather than tuned to a benchmark.
_TIER_BASE = {1: 60.0, 2: 40.0, 3: 22.0, 4: 10.0}
_VIP_BOOST = 25.0
_REQUIRES_REPLY_BOOST = 12.0
_URGENCY_WEIGHT = 8.0          # x dossier.urgency (0–3)
_DEADLINE_BOOST = 14.0
_QUESTION_WEIGHT = 3.0         # x min(#questions, 3)
_ESCALATION_BOOST = 18.0
_UNREAD_BOOST = 6.0
_STARRED_BOOST = 8.0
_MONEY_BOOST = 6.0


@dataclass
class TriageItem:
    """A fully-triaged message: priority, context research, and an optional draft."""

    message: EmailMessage
    label: str
    tier: int                      # effective tier (post-escalation)
    base_tier: int                 # tier before escalation
    is_vip: bool
    age_hours: float
    priority_score: float
    dossier: ResearchDossier
    escalation: Optional[EscalationResult] = None
    suggested_draft: Optional[str] = None
    rank: int = 0

    @property
    def tier_name(self) -> str:
        return get_tier_config(self.tier).name

    @property
    def needs_action(self) -> bool:
        return self.dossier.requires_reply or self.tier <= 2

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "id": self.message.id,
            "sender": self.message.sender,
            "subject": self.message.subject,
            "label": self.label,
            "tier": self.tier,
            "tier_name": self.tier_name,
            "base_tier": self.base_tier,
            "is_vip": self.is_vip,
            "age_hours": round(self.age_hours, 1),
            "priority_score": round(self.priority_score, 1),
            "escalated": bool(self.escalation and self.escalation.should_escalate),
            "needs_action": self.needs_action,
            "research": self.dossier.to_dict(),
            "suggested_draft": self.suggested_draft,
        }


def score_priority(
    *,
    tier: int,
    is_vip: bool,
    dossier: ResearchDossier,
    age_hours: float,
    escalation: Optional[EscalationResult],
    is_read: bool,
    is_starred: bool,
) -> float:
    """Combine tier, VIP status, research signals, age and flags into one score.

    Higher is more urgent. The formula is intentionally transparent so triage
    output can be explained to the user (see ``render_triage``).
    """
    score = _TIER_BASE.get(tier, 10.0)
    if is_vip:
        score += _VIP_BOOST
    if dossier.requires_reply:
        score += _REQUIRES_REPLY_BOOST
    score += _URGENCY_WEIGHT * dossier.urgency
    if dossier.deadlines:
        score += _DEADLINE_BOOST
    score += _QUESTION_WEIGHT * min(len(dossier.questions), 3)
    if dossier.amounts:
        score += _MONEY_BOOST
    if escalation and escalation.should_escalate:
        score += _ESCALATION_BOOST
    if not is_read:
        score += _UNREAD_BOOST
    if is_starred:
        score += _STARRED_BOOST
    # Gentle age pressure so equally-scored items surface oldest-first.
    score += min(age_hours / 24.0, 5.0)
    return round(score, 2)


def triage_messages(
    messages: List[EmailMessage],
    bodies: Optional[Dict[str, str]] = None,
    voice: Optional[VoiceProfile] = None,
    now: Optional[datetime] = None,
    draft: bool = False,
) -> List[TriageItem]:
    """Triage a batch of messages into a priority-sorted list.

    Args:
        messages: Messages to triage (already fetched from a provider).
        bodies: Optional ``{message_id: body_text}`` for deeper research when
            the message objects themselves don't carry a body.
        voice: User voice profile; required only when ``draft=True``.
        now: Reference time for age/escalation (defaults to ``datetime.now``).
        draft: When True, generate a suggested reply for items that expect one.

    Returns:
        TriageItems sorted by descending priority score, with ``rank`` assigned.
    """
    bodies = bodies or {}
    now = now or datetime.now(timezone.utc)
    items: List[TriageItem] = []

    for msg in messages:
        cat = categorize_with_tier(msg.sender, msg.subject)
        age_hours = calculate_email_age_hours(msg.date) if msg.date else 0.0
        escalation = escalate_by_age(cat.tier, age_hours, cat.time_sensitive)
        effective_tier = escalation.escalated_tier if escalation.should_escalate else cat.tier

        dossier = research_message(msg, body=bodies.get(msg.id), now=now)

        score = score_priority(
            tier=effective_tier,
            is_vip=cat.is_vip,
            dossier=dossier,
            age_hours=age_hours,
            escalation=escalation,
            is_read=msg.is_read,
            is_starred=msg.is_starred,
        )

        suggested = None
        if draft and dossier.requires_reply:
            profile = voice or VoiceProfile()
            suggested = profile.draft_reply(dossier)

        items.append(
            TriageItem(
                message=msg,
                label=cat.label,
                tier=effective_tier,
                base_tier=cat.tier,
                is_vip=cat.is_vip,
                age_hours=age_hours,
                priority_score=score,
                dossier=dossier,
                escalation=escalation,
                suggested_draft=suggested,
            )
        )

    items.sort(key=lambda it: (-it.priority_score, it.tier, -it.age_hours))
    for i, item in enumerate(items, start=1):
        item.rank = i
    return items


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_triage(items: List[TriageItem], fmt: str = "text") -> str:
    """Render triaged items as ``text``, ``markdown`` or ``json``."""
    if fmt == "json":
        return json.dumps([it.to_dict() for it in items], indent=2, default=str)
    if fmt == "markdown":
        return _render_markdown(items)
    return _render_text(items)


def _ctx_line(d: ResearchDossier) -> str:
    bits: List[str] = []
    if d.deadlines:
        bits.append(f"⏰ {d.deadlines[0]}")
    if d.questions:
        bits.append(f"❓{len(d.questions)}q")
    if d.action_items:
        bits.append(f"✅{len(d.action_items)} action(s)")
    if d.amounts:
        bits.append(f"💲{d.amounts[0]}")
    if d.links:
        bits.append(f"🔗{len(d.links)}")
    return "  ".join(bits)


def _render_text(items: List[TriageItem]) -> str:
    out = ["", "=" * 74, "MAILBOX TRIAGE — priority-sorted", "=" * 74,
           f"Items: {len(items)}", ""]
    for it in items:
        vip = "[VIP] " if it.is_vip else ""
        esc = " ↑escalated" if it.escalation and it.escalation.should_escalate else ""
        out.append(
            f"#{it.rank:>2} [{it.priority_score:5.1f}] Tier {it.tier} "
            f"({it.tier_name}){esc}  {vip}{it.label}"
        )
        out.append(f"      From: {it.message.sender[:60]}")
        out.append(f"      Subj: {it.message.subject[:60]}")
        if it.dossier.summary:
            out.append(f"      Gist: {it.dossier.summary[:90]}")
        ctx = _ctx_line(it.dossier)
        if ctx:
            out.append(f"      Ctx:  {ctx}")
        if it.suggested_draft:
            out.append("      Draft reply (your voice):")
            for line in it.suggested_draft.strip().splitlines():
                out.append(f"        | {line}")
        out.append("")
    out.append("=" * 74)
    return "\n".join(out)


def _render_markdown(items: List[TriageItem]) -> str:
    out = ["# Mailbox Triage", "", f"**Items:** {len(items)} (priority-sorted)", "",
           "| # | Score | Tier | VIP | Label | Sender | Subject | Context |",
           "|---|-------|------|-----|-------|--------|---------|---------|"]
    for it in items:
        vip = "⭐" if it.is_vip else ""
        ctx = _ctx_line(it.dossier).replace("|", "/")
        out.append(
            f"| {it.rank} | {it.priority_score:.1f} | {it.tier} ({it.tier_name}) "
            f"| {vip} | {it.label} | {it.message.sender[:30]} "
            f"| {it.message.subject[:40]} | {ctx} |"
        )
    drafts = [it for it in items if it.suggested_draft]
    if drafts:
        out += ["", "## Suggested replies (in your voice)", ""]
        for it in drafts:
            draft_str = it.suggested_draft or ""
            out += [f"### #{it.rank} — {it.message.subject[:60]}", "",
                    "```", draft_str.strip(), "```", ""]
    return "\n".join(out)
