"""Tests for core.voice — learning and applying the user's speech patterns."""

import json

from core.research import ResearchDossier
from core.voice import (
    VoiceProfile,
    learn_voice_profile,
    default_voice_profile,
    load_voice_profile,
    save_voice_profile,
)

CASUAL_SAMPLES = [
    "Hey Sam, thanks for the heads up! I'll take a look and get back to you soon. Cheers, Anthony",
    "Hi Pat, sounds good to me. Let me know if you need anything. Catch you later! Cheers, Anthony",
    "Hey Jo, yeah that works for me. I'll ping you tomorrow. Cheers, Anthony",
]

FORMAL_SAMPLES = [
    "Dear Mr. Smith, Thank you for your correspondence. I will review the documents "
    "and respond accordingly. Kindly advise if anything further is required. "
    "Best regards, Anthony Padavano",
    "Dear Ms. Jones, I appreciate your patience regarding this matter. Please find "
    "the requested information enclosed. Sincerely, Anthony Padavano",
]


class TestLearning:
    def test_empty_corpus_returns_default(self):
        p = learn_voice_profile([], name="Anthony")
        assert isinstance(p, VoiceProfile)
        assert p.name == "Anthony"

    def test_casual_corpus_detected(self):
        p = learn_voice_profile(CASUAL_SAMPLES, name="Anthony")
        assert p.formality < 0.5
        assert p.uses_contractions is True
        assert "Cheers" in p.sign_off

    def test_formal_corpus_detected(self):
        p = learn_voice_profile(FORMAL_SAMPLES, name="Anthony Padavano")
        assert p.formality >= 0.5
        assert p.uses_contractions is False
        assert p.greeting.lower().startswith("dear")

    def test_greeting_templated_with_first_name_token(self):
        p = learn_voice_profile(CASUAL_SAMPLES, name="Anthony")
        assert "{first}" in p.greeting

    def test_common_phrases_collected(self):
        p = learn_voice_profile(CASUAL_SAMPLES, name="Anthony")
        assert isinstance(p.common_phrases, list)


class TestStyling:
    def test_formal_profile_expands_contractions(self):
        p = VoiceProfile(formality=0.8)
        assert "I will" in p.apply_style("I'll send it")
        assert "cannot" in p.apply_style("I can't do that")

    def test_casual_profile_keeps_contractions(self):
        p = VoiceProfile(formality=0.2)
        assert p.apply_style("I'll send it") == "I'll send it"


class TestDrafting:
    def _dossier(self, **kw):
        base = dict(sender_name="Jane Doe", questions=[], action_items=[], deadlines=[])
        base.update(kw)
        return ResearchDossier(**base)

    def test_draft_includes_greeting_and_signoff(self):
        p = learn_voice_profile(CASUAL_SAMPLES, name="Anthony")
        draft = p.draft_reply(self._dossier(questions=["Can you confirm Friday?"]))
        assert "Jane" in draft  # greeting filled with recipient first name
        assert p.sign_off in draft
        assert "Anthony" in draft

    def test_draft_addresses_questions(self):
        p = default_voice_profile(name="Anthony")
        d = self._dossier(questions=["Did you get the file?"], requires_reply=True)
        draft = p.draft_reply(d)
        assert "Did you get the file?" in draft

    def test_draft_handles_missing_recipient_name(self):
        p = default_voice_profile(name="Anthony")
        d = self._dossier(sender_name="", action_items=["Please review the doc."])
        draft = p.draft_reply(d)
        assert "{first}" not in draft  # template token must be resolved
        assert draft.strip()

    def test_draft_notes_deadline(self):
        p = default_voice_profile(name="Anthony")
        d = self._dossier(action_items=["Please sign."], deadlines=["by Friday"])
        draft = p.draft_reply(d)
        assert "Friday" in draft


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        p = learn_voice_profile(FORMAL_SAMPLES, name="Anthony Padavano")
        path = tmp_path / "voice.json"
        save_voice_profile(p, path)
        assert path.exists()
        loaded = load_voice_profile(path=path)
        assert loaded.greeting == p.greeting
        assert loaded.formality == p.formality

    def test_load_missing_falls_back_to_default(self, tmp_path):
        p = load_voice_profile(path=tmp_path / "nope.json",
                               samples_path=tmp_path / "nope.txt",
                               name="Anthony")
        assert p.name == "Anthony"

    def test_load_learns_from_samples_file(self, tmp_path):
        samples = tmp_path / "sent.txt"
        samples.write_text("\n\n".join(CASUAL_SAMPLES), encoding="utf-8")
        p = load_voice_profile(path=tmp_path / "missing.json",
                               samples_path=samples, name="Anthony")
        assert "Cheers" in p.sign_off

    def test_load_ignores_garbled_json(self, tmp_path):
        bad = tmp_path / "voice.json"
        bad.write_text("{not json", encoding="utf-8")
        p = load_voice_profile(path=bad, samples_path=tmp_path / "none.txt", name="Anthony")
        assert isinstance(p, VoiceProfile)

    def test_to_dict_is_json_serializable(self):
        p = default_voice_profile(name="Anthony")
        json.dumps(p.to_dict())  # must not raise
