"""Tests for core.research — content & context extraction per message."""

from datetime import datetime, timezone

from core.models import EmailMessage
from core.research import ResearchDossier, research_message


def _msg(subject="", body="", sender="Jane Doe <jane@example.com>", **kw):
    return EmailMessage(id="x", sender=sender, subject=subject, body=body, **kw)


class TestDossierBasics:
    def test_returns_dossier(self):
        d = research_message(_msg(subject="Hello"))
        assert isinstance(d, ResearchDossier)

    def test_subject_only_message_still_categorized(self):
        d = research_message(_msg(subject="Your statement is ready", sender="alerts@chase.com"))
        assert d.category  # shared taxonomy assigns a label
        assert d.summary

    def test_sender_name_and_domain_parsed(self):
        d = research_message(_msg(sender="Jane Doe <jane@chase.com>"))
        assert d.sender_name == "Jane Doe"
        assert d.sender_domain == "chase.com"

    def test_to_dict_roundtrips_fields(self):
        d = research_message(_msg(subject="hi", body="Can you confirm?"))
        data = d.to_dict()
        assert set(data) >= {"summary", "questions", "action_items", "requires_reply"}


class TestExtraction:
    def test_questions_extracted_whole_sentence(self):
        body = "Did you receive the wire of $1,200.00 yet? Thanks."
        d = research_message(_msg(body=body))
        assert d.questions
        # The amount's period must not truncate the question.
        assert d.questions[0].startswith("Did you receive")
        assert d.questions[0].endswith("?")

    def test_action_items_detected(self):
        d = research_message(_msg(body="Please review the attached contract before Monday."))
        assert any("review" in a.lower() for a in d.action_items)

    def test_deadlines_detected(self):
        d = research_message(_msg(body="We need this back by end of day Friday, it's urgent."))
        assert d.deadlines
        assert d.urgency >= 1

    def test_links_extracted_and_trimmed(self):
        d = research_message(_msg(body="See https://example.com/path. More text."))
        assert d.links == ["https://example.com/path"]

    def test_amounts_extracted(self):
        d = research_message(_msg(body="Invoice total is $4,500.00 due soon."))
        assert any("4,500" in a for a in d.amounts)

    def test_requires_reply_true_when_question_present(self):
        d = research_message(_msg(body="Can you send me the report?"))
        assert d.requires_reply is True

    def test_requires_reply_false_for_newsletter(self):
        d = research_message(_msg(
            sender="deals@store.com",
            subject="50% off today",
            body="Shop our biggest sale of the year. Limited stock available here.",
        ))
        assert d.requires_reply is False

    def test_urgency_scales_with_signals(self):
        calm = research_message(_msg(body="Here is the monthly update."))
        loud = research_message(_msg(
            body="URGENT: this is critical and overdue, respond immediately by EOD."
        ))
        assert loud.urgency > calm.urgency

    def test_entities_skip_greeting_stopwords(self):
        d = research_message(_msg(body="Hi Anthony, the Acme Corporation invoice is ready."))
        assert "Hi" not in d.entities
        assert any("Acme" in e for e in d.entities)


class TestBodyOverride:
    def test_explicit_body_argument_overrides(self):
        msg = _msg(subject="Subj", body="old body")
        d = research_message(msg, body="Please approve the new budget?")
        assert d.requires_reply is True
        assert any("approve" in a.lower() for a in d.action_items) or d.questions

    def test_snippet_used_when_no_body(self):
        msg = EmailMessage(id="x", sender="a@b.com", subject="Subj",
                           snippet="Can you confirm the time?")
        d = research_message(msg)
        assert d.requires_reply is True


class TestDateParamAccepted:
    def test_now_param_is_accepted(self):
        d = research_message(_msg(subject="hi"), now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert isinstance(d, ResearchDossier)
