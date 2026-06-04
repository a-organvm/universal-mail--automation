"""Tests for core.triage — prioritization scoring and orchestration."""

import json
from datetime import datetime, timezone, timedelta

from core.models import EmailMessage
from core.research import ResearchDossier
from core.triage import (
    TriageItem,
    triage_messages,
    render_triage,
    score_priority,
)
from core.voice import default_voice_profile

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


def _msg(id, sender, subject, body="", hours_old=1, **kw):
    return EmailMessage(
        id=id, sender=sender, subject=subject, body=body,
        date=NOW - timedelta(hours=hours_old), **kw,
    )


class TestScorePriority:
    def _d(self, **kw):
        return ResearchDossier(**kw)

    def test_higher_tier_scores_higher(self):
        d = self._d()
        s1 = score_priority(tier=1, is_vip=False, dossier=d, age_hours=1,
                            escalation=None, is_read=True, is_starred=False)
        s4 = score_priority(tier=4, is_vip=False, dossier=d, age_hours=1,
                            escalation=None, is_read=True, is_starred=False)
        assert s1 > s4

    def test_vip_and_reply_boost_score(self):
        plain = score_priority(tier=3, is_vip=False, dossier=self._d(), age_hours=1,
                               escalation=None, is_read=True, is_starred=False)
        boosted = score_priority(tier=3, is_vip=True,
                                 dossier=self._d(requires_reply=True, urgency=2),
                                 age_hours=1, escalation=None, is_read=False,
                                 is_starred=True)
        assert boosted > plain


class TestTriageMessages:
    def test_returns_sorted_ranked_items(self):
        msgs = [
            _msg("a", "deals@store.com", "50% off everything today",
                 body="Shop our sale now."),
            _msg("b", "alerts@chase.com",
                 "Action required: confirm wire by Friday",
                 body="Please confirm the $1,200.00 transfer by end of day Friday. Urgent.",
                 is_read=False),
        ]
        items = triage_messages(msgs, now=NOW)
        assert all(isinstance(i, TriageItem) for i in items)
        # The urgent banking item must outrank the marketing blast.
        assert items[0].message.id == "b"
        assert items[0].rank == 1
        assert items[1].rank == 2
        assert items[0].priority_score >= items[1].priority_score

    def test_escalation_applied_for_stale_time_sensitive(self):
        # A time-sensitive category aged past 72h should escalate toward tier 1.
        msg = _msg("c", "noreply@coderabbit.ai", "Review requested on PR #5",
                   hours_old=100)
        items = triage_messages([msg], now=NOW)
        item = items[0]
        assert item.tier <= item.base_tier
        assert item.escalation is not None

    def test_draft_generated_only_when_requested_and_needed(self):
        msg = _msg("d", "jane@example.com", "Quick question",
                   body="Can you confirm the meeting time?")
        voice = default_voice_profile(name="Anthony")
        no_draft = triage_messages([msg], now=NOW, draft=False)
        with_draft = triage_messages([msg], voice=voice, now=NOW, draft=True)
        assert no_draft[0].suggested_draft is None
        assert with_draft[0].suggested_draft
        assert "Anthony" in with_draft[0].suggested_draft

    def test_no_draft_for_non_reply_items(self):
        msg = _msg("e", "deals@store.com", "Newsletter",
                   body="Here are this week's deals.")
        voice = default_voice_profile(name="Anthony")
        items = triage_messages([msg], voice=voice, now=NOW, draft=True)
        assert items[0].suggested_draft is None

    def test_empty_input(self):
        assert triage_messages([], now=NOW) == []

    def test_message_without_date_handled(self):
        msg = EmailMessage(id="f", sender="a@b.com", subject="Hi", body="Hello")
        items = triage_messages([msg], now=NOW)
        assert items[0].age_hours == 0.0


class TestRendering:
    def _items(self):
        msgs = [
            _msg("b", "alerts@chase.com", "Confirm wire by Friday",
                 body="Please confirm the $1,200.00 transfer by Friday?", is_read=False),
        ]
        return triage_messages(msgs, voice=default_voice_profile(name="Anthony"),
                               now=NOW, draft=True)

    def test_text_render(self):
        out = render_triage(self._items(), fmt="text")
        assert "MAILBOX TRIAGE" in out
        assert "Tier" in out

    def test_markdown_render(self):
        out = render_triage(self._items(), fmt="markdown")
        assert out.startswith("# Mailbox Triage")
        assert "Suggested replies" in out

    def test_json_render_is_valid(self):
        out = render_triage(self._items(), fmt="json")
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["rank"] == 1
        assert "research" in data[0]
