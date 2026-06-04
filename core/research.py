"""
Content & context research for individual email messages.

For every triaged item the automation produces a :class:`ResearchDossier` — a
structured, provider-agnostic read of *what the message is actually asking for*.
The extraction is pure-Python and offline (regex + heuristics) so it runs
without network access and is fully deterministic/testable. Providers that only
expose headers still get sender/subject context; providers that supply a
``snippet`` or ``body`` get the full treatment (action items, deadlines,
questions, links, amounts, entities).

Public API:
    research_message(message, body=None, now=None) -> ResearchDossier

The dossier feeds two downstream consumers:
    * core.triage  — priority scoring (urgency, requires_reply, deadlines)
    * core.voice   — drafting a reply that answers the detected questions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from core.models import EmailMessage
from core.rules import categorize_with_tier, normalize_sender

# ---------------------------------------------------------------------------
# Extraction vocabularies & patterns
# ---------------------------------------------------------------------------

# Phrases that signal the sender wants the recipient to *do* something.
_ACTION_CUES = [
    r"please\s+(?:review|confirm|approve|sign|send|reply|respond|complete|update|"
    r"provide|submit|schedule|verify|check|fill|forward)",
    r"can\s+you\b",
    r"could\s+you\b",
    r"would\s+you\b",
    r"we\s+need\s+(?:you|your)\b",
    r"action\s+required",
    r"requires?\s+your\s+(?:attention|action|approval|signature|response)",
    r"awaiting\s+your\b",
    r"let\s+me\s+know\b",
    r"get\s+back\s+to\s+(?:me|us)\b",
    r"follow(?:\s|-)?up\b",
    r"reminder\s+to\b",
    r"don'?t\s+forget\b",
    r"kindly\b",
]

# Deadline / time-pressure language.
_DEADLINE_CUES = [
    r"\bby\s+(?:end\s+of\s+(?:day|week|month)|eo[dwm]|cob|today|tomorrow|tonight|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|next\s+week|"
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|\w+\s+\d{1,2}(?:st|nd|rd|th)?)",
    r"\bdue\s+(?:date|by|on|today|tomorrow)\b",
    r"\bdeadline\b",
    r"\bexpires?\b",
    r"\basap\b",
    r"\burgent(?:ly)?\b",
    r"\bimmediately\b",
    r"\btime[-\s]?sensitive\b",
    r"\bno\s+later\s+than\b",
    r"\bwithin\s+\d+\s+(?:hours?|days?|business\s+days?)\b",
    r"\blast\s+(?:chance|day|reminder)\b",
    r"\bact\s+now\b",
]

# Words that escalate urgency when present.
_URGENT_WORDS = {
    "urgent", "asap", "immediately", "critical", "emergency", "important",
    "overdue", "final", "expiring", "expires", "deadline", "now",
}

_URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
# Money: $1,234.56  /  USD 1000  /  1,000.00 EUR
_AMOUNT_RE = re.compile(
    r"(?:[$€£]\s?\d[\d,]*(?:\.\d{2})?)"
    r"|(?:\b(?:USD|EUR|GBP)\s?\d[\d,]*(?:\.\d{2})?)"
    r"|(?:\b\d[\d,]*(?:\.\d{2})?\s?(?:USD|EUR|GBP|dollars?))",
    re.IGNORECASE,
)
# Naive named-entity guess: runs of Capitalized Words (orgs/products/people).
_ENTITY_RE = re.compile(r"\b(?:[A-Z][a-zA-Z0-9&.\-]+)(?:\s+[A-Z][a-zA-Z0-9&.\-]+){0,3}\b")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_QUESTION_RE = re.compile(r"[^.!?\n]*\?")

# Entities that are noise rather than signal (greetings, generic openers).
_ENTITY_STOPWORDS = {
    "Hi", "Hello", "Hey", "Dear", "Thanks", "Thank", "Regards", "Best",
    "Sincerely", "Cheers", "The", "This", "That", "Please", "We", "I", "You",
    "Re", "Fwd", "Fw", "Subject", "From", "To", "Sent", "Get", "Your", "Our",
}


# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------

@dataclass
class ResearchDossier:
    """Structured context extracted from a single message.

    Attributes:
        sender_name: Display name parsed from the From header.
        sender_domain: Lower-cased sending domain (for source context).
        category: Shared-taxonomy label (e.g. ``Finance/Banking``).
        summary: One-line extractive gist of the message.
        action_items: Imperative requests directed at the recipient.
        questions: Direct questions the recipient is expected to answer.
        deadlines: Raw phrases conveying time pressure / due dates.
        links: URLs found in the content.
        amounts: Monetary amounts mentioned.
        entities: Candidate organisations / people / products referenced.
        key_phrases: Salient noun-ish phrases for a quick scan.
        urgency: 0 (none) – 3 (screaming) heuristic urgency.
        requires_reply: True when the message expects a human response.
    """

    sender_name: str = ""
    sender_domain: str = ""
    category: str = ""
    summary: str = ""
    action_items: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    deadlines: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    amounts: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    key_phrases: List[str] = field(default_factory=list)
    urgency: int = 0
    requires_reply: bool = False

    def to_dict(self) -> dict:
        return {
            "sender_name": self.sender_name,
            "sender_domain": self.sender_domain,
            "category": self.category,
            "summary": self.summary,
            "action_items": self.action_items,
            "questions": self.questions,
            "deadlines": self.deadlines,
            "links": self.links,
            "amounts": self.amounts,
            "entities": self.entities,
            "key_phrases": self.key_phrases,
            "urgency": self.urgency,
            "requires_reply": self.requires_reply,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> List[str]:
    return [_clean(s) for s in _SENTENCE_SPLIT_RE.split(text) if _clean(s)]


def _dedupe(items: List[str], limit: Optional[int] = None) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for item in items:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out


def _extract_links(text: str) -> List[str]:
    return _dedupe([m.rstrip(".,);") for m in _URL_RE.findall(text)], limit=10)


def _extract_amounts(text: str) -> List[str]:
    return _dedupe([_clean(m) for m in _AMOUNT_RE.findall(text)], limit=10)


def _extract_questions(sentences: List[str]) -> List[str]:
    out: List[str] = []
    for sentence in sentences:
        sentence = _clean(sentence)
        if "?" not in sentence:
            continue
        # A whole sentence ending in '?' is the cleanest unit — take it as-is so
        # mid-sentence punctuation (e.g. "$1,200.00") doesn't truncate it.
        if sentence.endswith("?"):
            if len(sentence) > 5:
                out.append(sentence)
            continue
        for q in _QUESTION_RE.findall(sentence):
            q = _clean(q)
            if len(q) > 5:
                out.append(q if q.endswith("?") else q + "?")
    return _dedupe(out, limit=8)


def _extract_action_items(sentences: List[str]) -> List[str]:
    cues = [re.compile(c, re.IGNORECASE) for c in _ACTION_CUES]
    out: List[str] = []
    for sentence in sentences:
        if any(c.search(sentence) for c in cues):
            out.append(sentence if len(sentence) <= 160 else sentence[:157] + "...")
    return _dedupe(out, limit=8)


def _extract_deadlines(text: str) -> List[str]:
    out: List[str] = []
    for cue in _DEADLINE_CUES:
        for m in re.finditer(cue, text, re.IGNORECASE):
            out.append(_clean(m.group(0)))
    return _dedupe(out, limit=8)


def _extract_entities(text: str) -> List[str]:
    out: List[str] = []
    for m in _ENTITY_RE.findall(text):
        phrase = _clean(m)
        first = phrase.split()[0] if phrase else ""
        if first in _ENTITY_STOPWORDS or len(phrase) < 3:
            continue
        out.append(phrase)
    return _dedupe(out, limit=8)


def _key_phrases(sentences: List[str]) -> List[str]:
    """Cheap salience: shortest informative sentences make decent scan-phrases."""
    candidates = [s for s in sentences if 12 <= len(s) <= 120]
    candidates.sort(key=len)
    return _dedupe(candidates, limit=5)


def _summarize(subject: str, sentences: List[str]) -> str:
    subject = _clean(subject)
    if sentences:
        first = sentences[0]
        if subject and subject.lower() not in first.lower():
            return f"{subject} — {first}"[:200]
        return first[:200]
    return subject[:200]


def _score_urgency(text_lower: str, deadlines: List[str]) -> int:
    score = 0
    hits = sum(1 for w in _URGENT_WORDS if w in text_lower)
    if hits:
        score += 1
    if hits >= 2:
        score += 1
    if deadlines:
        score += 1
    return min(score, 3)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def research_message(
    message: EmailMessage,
    body: Optional[str] = None,
    now: Optional[datetime] = None,  # reserved for future age-aware context
) -> ResearchDossier:
    """Build a :class:`ResearchDossier` for a message.

    Args:
        message: The message to research. Its ``content_text`` (subject plus
            body/snippet) is mined; if only headers are present, the dossier is
            still populated with sender/category context.
        body: Explicit body text. Overrides ``message.body``/``snippet`` when
            given (lets callers pass freshly fetched content without mutating
            the frozen message).
        now: Optional reference time (unused today, kept for signature
            stability with the rest of core).

    Returns:
        A populated ResearchDossier.
    """
    name, addr, domain = normalize_sender(message.sender)
    cat = categorize_with_tier(message.sender, message.subject)

    if body is not None:
        detail = body.strip()
        text = f"{message.subject}\n\n{detail}".strip() if detail else message.subject
    else:
        text = message.content_text

    sentences = _sentences(text)
    text_lower = text.lower()

    deadlines = _extract_deadlines(text)
    questions = _extract_questions(sentences)
    action_items = _extract_action_items(sentences)
    links = _extract_links(text)
    amounts = _extract_amounts(text)
    entities = _extract_entities(text)

    requires_reply = bool(questions or action_items)
    urgency = _score_urgency(text_lower, deadlines)

    return ResearchDossier(
        sender_name=name or (addr.split("@")[0] if addr else ""),
        sender_domain=domain,
        category=cat.label,
        summary=_summarize(message.subject, sentences),
        action_items=action_items,
        questions=questions,
        deadlines=deadlines,
        links=links,
        amounts=amounts,
        entities=entities,
        key_phrases=_key_phrases(sentences),
        urgency=urgency,
        requires_reply=requires_reply,
    )
