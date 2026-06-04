"""
User speech-pattern modelling for triage drafts.

The automation should answer mail *the way the user writes*, not in a generic
assistant register. This module learns a lightweight :class:`VoiceProfile` from
a corpus of the user's own sent messages (or a saved JSON profile), then renders
suggested reply drafts that match the user's greeting, sign-off, formality,
cadence and pet phrases.

Everything here is offline and deterministic. There is no LLM dependency: the
profile is a small bag of measurable style signals, and drafting is template
composition steered by those signals. A model-backed renderer can later be
slotted in behind :meth:`VoiceProfile.draft_reply` without changing callers.

Public API:
    learn_voice_profile(samples, name=...) -> VoiceProfile
    default_voice_profile(name=...) -> VoiceProfile
    load_voice_profile(path=None, samples_path=None, name=...) -> VoiceProfile
    save_voice_profile(profile, path) -> Path
    VoiceProfile.draft_reply(dossier, ...) -> str
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Default location for a persisted profile / learned-from corpus.
DEFAULT_VOICE_PATH = Path("~/.config/mail_automation/voice.json").expanduser()
DEFAULT_SAMPLES_PATH = Path("~/.config/mail_automation/sent_samples.txt").expanduser()

_GREETING_RE = re.compile(
    r"^\s*(hi|hey|hello|dear|good\s+morning|good\s+afternoon|good\s+evening|"
    r"yo|hiya|greetings)\b[^\n]*",
    re.IGNORECASE,
)
_SIGNOFF_RE = re.compile(
    r"(?im)^\s*(best|best\s+regards|regards|kind\s+regards|warm\s+regards|"
    r"cheers|thanks|thank\s+you|thanks\s+so\s+much|sincerely|talk\s+soon|"
    r"all\s+the\s+best|warmly|yours)\b[,!.]*\s*$"
)
# Inline closing form: "... Cheers, Anthony" on the same line as the body. The
# trailing comma + capitalised name disambiguates it from mid-sentence uses
# (e.g. "thanks for the heads up").
_INLINE_SIGNOFF_RE = re.compile(
    r"(?i)\b(best\s+regards|kind\s+regards|warm\s+regards|all\s+the\s+best|"
    r"best|regards|cheers|thanks\s+so\s+much|thanks|thank\s+you|sincerely|"
    r"talk\s+soon|warmly|yours)\s*,\s+[A-Z][a-zA-Z'.-]+"
)
_CONTRACTION_RE = re.compile(r"\b\w+'(?:re|ve|ll|d|s|t|m)\b", re.IGNORECASE)
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
_WORD_RE = re.compile(r"[a-zA-Z']+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")

# Formality lexicon (lower => casual, higher => formal).
_CASUAL_MARKERS = {
    "hey", "yeah", "yep", "nope", "gonna", "wanna", "kinda", "cool", "thanks",
    "cheers", "lol", "haha", "btw", "fyi", "asap", "ok", "okay", "sure",
}
_FORMAL_MARKERS = {
    "regards", "sincerely", "kindly", "please", "however", "furthermore",
    "accordingly", "regarding", "pursuant", "therefore", "additionally",
    "appreciate", "respectfully",
}

# Expansion map for raising formality (drops contractions).
_EXPANSIONS = {
    "i'm": "I am", "you're": "you are", "we're": "we are", "they're": "they are",
    "it's": "it is", "that's": "that is", "i'll": "I will", "we'll": "we will",
    "i've": "I have", "we've": "we have", "don't": "do not", "doesn't": "does not",
    "didn't": "did not", "can't": "cannot", "won't": "will not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "wouldn't": "would not", "couldn't": "could not", "shouldn't": "should not",
    "let's": "let us", "i'd": "I would",
}


@dataclass
class VoiceProfile:
    """Measured style signals for one author.

    Attributes:
        name: The user's name, used to build the signature.
        greeting: Template greeting; ``{first}`` is filled with the recipient's
            first name when known (e.g. ``"Hi {first},"``).
        sign_off: Closing line before the signature (e.g. ``"Best,"``).
        signature: Name line after the sign-off.
        formality: 0.0 (very casual) – 1.0 (very formal).
        avg_sentence_len: Mean words/sentence observed in the corpus.
        uses_contractions: Whether the author tends to use contractions.
        emoji_frequency: Emoji per 100 words.
        common_phrases: Recurring multi-word phrases the author favours.
        common_openers: Sentences the author tends to start replies with.
    """

    name: str = ""
    greeting: str = "Hi {first},"
    sign_off: str = "Best,"
    signature: str = ""
    formality: float = 0.5
    avg_sentence_len: float = 15.0
    uses_contractions: bool = True
    emoji_frequency: float = 0.0
    common_phrases: List[str] = field(default_factory=list)
    common_openers: List[str] = field(default_factory=list)

    # ---- serialisation ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "greeting": self.greeting,
            "sign_off": self.sign_off,
            "signature": self.signature,
            "formality": round(self.formality, 3),
            "avg_sentence_len": round(self.avg_sentence_len, 2),
            "uses_contractions": self.uses_contractions,
            "emoji_frequency": round(self.emoji_frequency, 3),
            "common_phrases": self.common_phrases,
            "common_openers": self.common_openers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceProfile":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    # ---- styling ----------------------------------------------------------

    def apply_style(self, text: str) -> str:
        """Nudge a sentence toward the profile's formality.

        Formal voices (>=0.6) drop contractions; casual voices are left intact.
        This keeps drafts consistent regardless of how the template was phrased.
        """
        if self.formality >= 0.6:
            def _expand(m: re.Match) -> str:
                word = m.group(0)
                repl = _EXPANSIONS.get(word.lower())
                if not repl:
                    return word
                return repl.capitalize() if word[0].isupper() else repl
            return _CONTRACTION_RE.sub(_expand, text)
        return text

    # ---- drafting ---------------------------------------------------------

    def draft_reply(
        self,
        dossier,
        recipient_first: str = "",
        max_points: int = 4,
    ) -> str:
        """Compose a suggested reply in this voice answering the dossier.

        Args:
            dossier: A ``core.research.ResearchDossier`` for the message being
                answered (its questions / action items drive the body).
            recipient_first: Recipient's first name for the greeting; falls back
                to the dossier's parsed sender name, then a name-less greeting.
            max_points: Cap on questions+actions acknowledged in the body.

        Returns:
            A ready-to-edit plain-text draft (greeting, body, sign-off,
            signature).
        """
        first = recipient_first or _first_name(getattr(dossier, "sender_name", ""))
        greeting = self.greeting.format(first=first).strip()
        if not first:
            # Collapse "Hi ," style artefacts when we have no name.
            greeting = re.sub(r"\s+,", ",", greeting.replace("{first}", "")).strip()
            greeting = re.sub(r"(hi|hey|hello)\s*,", r"\1 there,", greeting, flags=re.I)

        opener = self._opener()
        body_lines: List[str] = [opener] if opener else []

        points: List[str] = []
        seen: set = set()
        for q in getattr(dossier, "questions", [])[:max_points]:
            seen.add(_truncate(q).lower())
            points.append(f"- You asked: \"{_truncate(q)}\"  [reply here]")
        remaining = max_points - len(points)
        for a in getattr(dossier, "action_items", [])[:max(remaining, 0)]:
            short = _truncate(a)
            if short.lower() in seen:
                continue
            points.append(f"- Re: {short} — I'll take care of it.")

        if points:
            body_lines.append("A few quick notes:")
            body_lines.extend(points)
        elif not opener:
            body_lines.append("Thanks for the note — I'll follow up shortly.")

        deadlines = getattr(dossier, "deadlines", [])
        if deadlines:
            body_lines.append(
                f"Noting the timing ({deadlines[0]}); I'll make sure we're on track."
            )

        body = "\n".join(self.apply_style(line) for line in body_lines)
        signature = self.signature or self.name

        parts = [greeting, "", body, "", self.sign_off]
        if signature:
            parts.append(signature)
        draft = "\n".join(parts)
        return re.sub(r"\n{3,}", "\n\n", draft).strip() + "\n"

    def _opener(self) -> str:
        # NOTE: common_openers is kept on the profile as a *style signal* for
        # transparency, but is deliberately NOT pasted verbatim into a new
        # draft — reusing old sentences risks leaking prior correspondence.
        return "Thank you for reaching out." if self.formality >= 0.6 else "Thanks for the note!"


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------

def _first_name(name: str) -> str:
    name = (name or "").strip().strip('"')
    if not name or "@" in name:
        return ""
    # Handle "Last, First" and "First Last".
    if "," in name:
        name = name.split(",", 1)[1].strip()
    return name.split()[0] if name.split() else ""


def _truncate(text: str, limit: int = 110) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _top_phrases(samples: List[str], n: int = 6) -> List[str]:
    """Most frequent 2–3 word phrases across the corpus (stop-word trimmed)."""
    stop = {
        "the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "at",
        "is", "it", "i", "you", "we", "this", "that", "with", "be", "as",
        "your", "our", "me", "my", "so", "if", "but", "by", "are", "was",
    }
    counts: dict = {}
    for sample in samples:
        words = [w.lower() for w in _WORD_RE.findall(sample)]
        for size in (3, 2):
            for i in range(len(words) - size + 1):
                gram = words[i : i + size]
                if gram[0] in stop or gram[-1] in stop:
                    continue
                phrase = " ".join(gram)
                counts[phrase] = counts.get(phrase, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [p for p, c in ranked if c >= 2][:n]


def learn_voice_profile(samples: List[str], name: str = "") -> VoiceProfile:
    """Learn a :class:`VoiceProfile` from the user's sent messages.

    Args:
        samples: Plain-text bodies of messages the user has written.
        name: The user's name for the signature (optional).

    Returns:
        A VoiceProfile. With no usable samples, a sensible neutral default is
        returned (so callers never have to special-case an empty corpus).
    """
    samples = [s for s in (samples or []) if s and s.strip()]
    if not samples:
        return default_voice_profile(name=name)

    word_total = 0
    sentence_lengths: List[int] = []
    contraction_hits = 0
    emoji_hits = 0
    casual = 0
    formal = 0
    greetings: List[str] = []
    signoffs: List[str] = []
    openers: List[str] = []

    for sample in samples:
        words = _WORD_RE.findall(sample)
        word_total += len(words)
        contraction_hits += len(_CONTRACTION_RE.findall(sample))
        emoji_hits += len(_EMOJI_RE.findall(sample))
        lower = {w.lower() for w in words}
        casual += len(lower & _CASUAL_MARKERS)
        formal += len(lower & _FORMAL_MARKERS)

        g = _GREETING_RE.match(sample.strip())
        if g:
            greetings.append(_clean_template(g.group(0)))
        for m in _SIGNOFF_RE.finditer(sample):
            signoffs.append(m.group(1).strip())
        for m in _INLINE_SIGNOFF_RE.finditer(sample):
            signoffs.append(m.group(1).strip())

        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(sample) if s.strip()]
        for s in sentences:
            sl = len(_WORD_RE.findall(s))
            if sl:
                sentence_lengths.append(sl)
        # First non-greeting sentence is a candidate opener.
        for s in sentences:
            if not _GREETING_RE.match(s):
                openers.append(_truncate(s, 90))
                break

    avg_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 15.0
    uses_contractions = contraction_hits >= max(1, len(samples) // 2)
    emoji_freq = (emoji_hits / word_total * 100) if word_total else 0.0

    # Formality: blend lexical markers with contraction/emoji signals.
    lex = 0.5
    if casual + formal:
        lex = formal / (casual + formal)
    formality = lex
    if not uses_contractions:
        formality += 0.15
    if emoji_freq > 0.5:
        formality -= 0.2
    formality = max(0.0, min(1.0, formality))

    greeting = _most_common(greetings) or ("Dear {first}," if formality >= 0.65 else "Hi {first},")
    sign_off = _normalize_signoff(_most_common(signoffs)) or (
        "Best regards," if formality >= 0.65 else "Best,"
    )

    return VoiceProfile(
        name=name,
        greeting=greeting,
        sign_off=sign_off,
        signature=name,
        formality=formality,
        avg_sentence_len=avg_len,
        uses_contractions=uses_contractions,
        emoji_frequency=emoji_freq,
        common_phrases=_top_phrases(samples),
        common_openers=_dedupe_keep_order(openers)[:3],
    )


def default_voice_profile(name: str = "") -> VoiceProfile:
    """A neutral, friendly-professional default profile."""
    return VoiceProfile(
        name=name,
        greeting="Hi {first},",
        sign_off="Best,",
        signature=name,
        formality=0.5,
        avg_sentence_len=15.0,
        uses_contractions=True,
        emoji_frequency=0.0,
    )


# ---------------------------------------------------------------------------
# Persistence / loading
# ---------------------------------------------------------------------------

def save_voice_profile(profile: VoiceProfile, path: Optional[Path] = None) -> Path:
    """Persist a profile as JSON; returns the path written."""
    path = Path(path or DEFAULT_VOICE_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    return path


def load_voice_profile(
    path: Optional[Path] = None,
    samples_path: Optional[Path] = None,
    name: str = "",
) -> VoiceProfile:
    """Resolve a VoiceProfile from the best available source.

    Resolution order:
        1. A saved JSON profile at ``path`` (default ``~/.config/mail_automation/voice.json``).
        2. A corpus of sent messages at ``samples_path`` — learned on the fly.
           Samples are split on blank-line-delimited blocks or ``---`` fences.
        3. A neutral default profile.

    Never raises on missing/garbled files — falls through to the next source.
    """
    json_path = Path(path or DEFAULT_VOICE_PATH).expanduser()
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            profile = VoiceProfile.from_dict(data)
            if name and not profile.name:
                profile.name = name
                profile.signature = profile.signature or name
            return profile
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    samples_file = Path(samples_path or DEFAULT_SAMPLES_PATH).expanduser()
    if samples_file.exists():
        try:
            raw = samples_file.read_text(encoding="utf-8")
            blocks = re.split(r"\n-{3,}\n|\n{2,}", raw)
            samples = [b.strip() for b in blocks if b.strip()]
            if samples:
                return learn_voice_profile(samples, name=name)
        except OSError:
            pass

    return default_voice_profile(name=name)


# ---------------------------------------------------------------------------
# Small internal utilities
# ---------------------------------------------------------------------------

def _clean_template(greeting: str) -> str:
    """Turn an observed greeting line into a ``{first}``-templated form."""
    greeting = re.sub(r"\s+", " ", greeting).strip()
    # Replace the name token after the salutation word with {first}.
    m = re.match(r"(?i)^(hi|hey|hello|dear|hiya|yo)\b\s+([A-Z][\w'-]*)", greeting)
    if m:
        return f"{m.group(1).capitalize()} {{first}},"
    # Greeting with no name (e.g. "Good morning,").
    return greeting.rstrip(",") + ","


def _normalize_signoff(signoff: Optional[str]) -> str:
    if not signoff:
        return ""
    return signoff.rstrip(",.! ").strip().capitalize() + ","


def _most_common(items: List[str]) -> str:
    if not items:
        return ""
    counts: dict = {}
    for it in items:
        counts[it] = counts.get(it, 0) + 1
    return max(counts.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for it in items:
        k = it.lower()
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out
