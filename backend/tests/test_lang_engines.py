"""Stage 8 part 1: the pluggable language engines (translation, voice, speech-to-text) with their mock
engines, the IndicTrans2 text preparation (no model needed), the audio helpers, and the mock AI fix."""

import io
import wave
from pathlib import Path

import pytest
from PIL import Image

from app.ai import mock_ai
from app.config import settings
from app.lang import audio, indictrans, languages, stt, translate, tts

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


# ---- languages ------------------------------------------------------------------------------------

def test_the_23_languages():
    assert len(languages.LANGUAGES) == 23 and len(languages.INDIAN) == 22
    assert languages.get("ta").tag == "tam_Taml" and languages.get("ur").rtl and not languages.get("hi").rtl
    assert languages.get("en").sms_limit == 160 and languages.get("hi").sms_limit == 70
    assert languages.sms_parts("a" * 160) == 1 and languages.sms_parts("a" * 161) == 2
    assert languages.sms_parts("क" * 70) == 1 and languages.sms_parts("क" * 71) == 2
    assert languages.get("xx").code == "en"


# ---- IndicTrans2 text preparation (as AI4Bharat's IndicTransToolkit) ----------------------------

def test_values_are_protected_and_put_back():
    text, found = indictrans.protect(
        "Block 203.0.113.45 and patch CVE-2026-12345 by 10:00; call [PHONE-1] or mail soc@example.org.")
    assert "203.0.113.45" not in text and "CVE-2026-12345" not in text and "[PHONE-1]" not in text
    assert set(found.values()) >= {"203.0.113.45", "CVE-2026-12345", "[PHONE-1]", "soc@example.org", "10:00"}
    # the model may write the placeholder back in another script; it is still put back
    key = next(k for k, v in found.items() if v == "203.0.113.45")
    number = key[3:-1]
    for written in (key, f"< ID{number} >", f"<আইডি{number}>", f"<آئی ڈی {number}>"):
        assert indictrans.restore(f"x {written} y", found) == "x 203.0.113.45 y"
    assert indictrans.restore("[PHONE-1] <b>2</b>", found) == "[PHONE-1] <b>2</b>"  # real text is left alone


def test_devanagari_answer_is_written_in_the_target_script():
    assert indictrans.from_devanagari("नमस्ते", "Taml") == "நமஸ்தே"
    assert indictrans.from_devanagari("पार्क", "Beng") == "পার্ক"
    assert indictrans.from_devanagari("नमस्ते", "Deva") == "नमस्ते"
    assert indictrans.from_devanagari("सलाम", "Arab") == "सलाम"  # Urdu comes out in its own script already
    assert indictrans.ascii_digits("४२ अस्पताल, ௨௮") == "42 अस्पताल, 28"
    assert indictrans.detokenize('42 अस्पताल , " पाँच " राज्य ।') == '42 अस्पताल, "पाँच" राज्य।'


# ---- translation engines --------------------------------------------------------------------------

def test_mock_translation_keeps_values():
    out = translate.translate_texts(["42 hospitals since 22 September.", ""], "hi")
    assert out == ["हिन्दी · 42 hospitals since 22 September.", ""]
    with pytest.raises(translate.TranslateError):
        translate.translate_texts(["x"], "en")


def test_translation_through_the_llm_module(monkeypatch):
    monkeypatch.setattr(settings, "translate_engine", "llm")  # AI_MODE=mock: the mock AI answers
    assert translate.translate_texts(["Block 203.0.113.45 now."], "ta") == ["தமிழ் · Block 203.0.113.45 now."]
    assert translate.status()["engine"] == "llm"


def test_indictrans2_missing_model_is_explained(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "translate_engine", "indictrans2")
    monkeypatch.setattr(settings, "models_dir", tmp_path)
    monkeypatch.setattr(translate, "_model", None)
    assert translate.status()["ready"] is False
    with pytest.raises(translate.TranslateError, match="download-models.py"):
        translate.translate_texts(["Hello."], "hi")


def test_sentences_are_split_for_the_model():
    assert translate.split_sentences("One. Two 42. [PHONE-1] three!") == ["One.", "Two 42.", "[PHONE-1] three!"]


# ---- voices -----------------------------------------------------------------------------------------

def _seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def test_mock_voice_and_languages_without_one():
    data, voice = tts.speak("Apply the patch to every gateway today.", "hi")
    assert voice.engine == "mock" and data[:4] == b"RIFF" and 2 < _seconds(data) < 4
    assert tts.voice_for("ta") is None
    with pytest.raises(tts.TTSError, match="not available for Tamil"):
        tts.speak("Hello.", "ta")
    assert set(tts.status()["voices"]) == {"en", "hi", "te", "ml", "ur"}


def test_piper_without_voice_files_falls_back_or_says_not_available(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "tts_engine", "piper")
    monkeypatch.setattr(settings, "models_dir", tmp_path)
    assert tts.voice_for("te") is None  # no Piper files, and macOS has no Telugu voice
    hindi = tts.voice_for("hi")
    assert hindi is None or hindi.engine == "say"  # Lekha on a Mac


# ---- speech to text ---------------------------------------------------------------------------------

def test_mock_speech_to_text():
    recording, _ = tts.speak("A short recorded briefing for the test.", "en")
    result = stt.transcribe(recording, "hi", "briefing.wav")
    assert "42 hospitals" in result.pages[0] and result.seconds > 2 and result.model == "Mock speech-to-text"
    with pytest.raises(stt.STTError, match="Hindi, Tamil, English"):
        stt.transcribe(recording, "bn")
    with pytest.raises(stt.STTError, match="could not be read"):
        stt.transcribe(b"not audio at all", "hi", "notes.mp3")


def test_long_recordings_are_cut_at_quiet_moments():
    import numpy as np
    rate = stt.RATE
    loud, quiet = np.ones(rate * 22, dtype=np.float32) * 0.3, np.zeros(rate, dtype=np.float32)
    samples = np.concatenate([loud, quiet, loud, quiet, loud])  # 68 s, quiet at 22-23 s and 45-46 s
    parts = stt.pieces(samples)
    assert len(parts) == 3 and all(len(p) <= stt.PIECE_SECONDS * rate for p in parts)
    assert 22 <= len(parts[0]) / rate <= 23 and sum(len(p) for p in parts) == len(samples)


# ---- audio and video ------------------------------------------------------------------------------

def _png(color) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (320, 180), color).save(buffer, "PNG")
    return buffer.getvalue()


def test_mp3_and_mp4():
    narration, _ = tts.speak("One two three four five.", "en")
    mp3 = audio.mp3_from_wav(narration)
    assert mp3[:3] == b"ID3" or mp3[:2] == b"\xff\xfb"
    joined = audio.join_wavs([narration, narration], pause=0.5)
    assert abs(audio.wav_seconds(joined) - (2 * audio.wav_seconds(narration) + 0.5)) < 0.05
    srt = "1\n00:00:00,000 --> 00:00:02,000\nहिन्दी उपशीर्षक\n"
    video = audio.make_mp4([(_png("navy"), 1.0), (_png("orange"), 1.0)], narration, srt)
    assert video[4:8] == b"ftyp" and len(video) > 1000
    assert audio.to_wav(video, 16000)[:4] == b"RIFF"  # the sound can be read back


# ---- the mock AI: a "SAMPLE - FICTIONAL" note is never a fact ------------------------------------

@pytest.mark.parametrize("name", ["sample-private-data.txt", "sample-injection.txt", "sample-ransomware-report.txt"])
def test_mock_never_uses_the_disclaimer_as_a_fact(name):
    sheet = mock_ai.fact_sheet((SAMPLES / name).read_text())
    texts = " ".join(f["text"] for f in sheet["key_facts"]) + sheet["summary"]
    assert "SAMPLE" not in texts  # the marker (a fact may still say "CVE-2026-XXXXX (sample)")
    for words in ("invented", "not real", "None of it belongs", "fictional", "on purpose"):
        assert words.lower() not in texts.lower(), (name, words)
    assert sheet["key_facts"], name
