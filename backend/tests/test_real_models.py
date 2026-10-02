"""Stage 8 part 7: one real smoke test per language engine.

The other tests use the mock engines (instant, no models). These try the real ones on this computer:
IndicTrans2 (translation), the Piper voices and macOS "say" (text-to-speech), IndicConformer Hindi/Tamil
and Whisper small (speech-to-text). A test is skipped when its model is not downloaded
(backend/.venv/bin/python scripts/download-models.py), so the suite still passes on a fresh clone.
They take about a minute. Skip them all with SKIP_REAL_MODELS=1.
"""

import io
import os
import wave

import pytest

from app.config import settings
from app.lang import languages, stt, translate, tts
from app.pipeline.translation import compare_values

if os.environ.get("SKIP_REAL_MODELS") == "1":
    pytest.skip("SKIP_REAL_MODELS=1", allow_module_level=True)

ALERT = "Report fraud by calling 1930 before 28 September 2026. 42 hospitals were affected."


@pytest.fixture
def engines(monkeypatch):
    """Switch one engine from mock to real for one test (conftest.py sets them all to mock)."""
    def use(**values):
        for name, value in values.items():
            monkeypatch.setattr(settings, name, value)
    return use


def seconds(wav: bytes) -> float:
    with wave.open(io.BytesIO(wav)) as w:
        return w.getnframes() / w.getframerate()


# --- translation --------------------------------------------------------------------------------------

def test_indictrans2_translates_and_keeps_the_numbers(engines):
    engines(translate_engine="indictrans2")
    if not translate.status()["ready"]:
        pytest.skip("IndicTrans2 is not downloaded")
    for code in ("hi", "ta", "ur"):
        [text] = translate.translate_texts([ALERT], code)
        assert not languages.foreign_scripts(text, code), text  # written in the language's own script
        assert sum(languages.script_of_letter(c) == languages.get(code).script for c in text) > 20, text
        missing, extra = compare_values(ALERT, text)
        assert missing == [] and extra == [], (code, text)  # 1930, 28, 2026 and 42 survived


def test_indictrans2_keeps_a_helpline_a_phone_number(engines):
    """v1.2: "on 1930" alone became "in (the year) 1930"; with "helpline number" added it stays a phone number."""
    from app.lang import helplines
    engines(translate_engine="indictrans2")
    if not translate.status()["ready"]:
        pytest.skip("IndicTrans2 is not downloaded")
    english = "Report cyber fraud on 1930."
    for code in ("hi", "bn", "ta"):
        [text] = translate.translate_texts([english], code)
        assert helplines.not_read_as_phone(english, text) == [], (code, text)


def test_the_llm_engine_goes_through_llm_py(engines):
    """TRANSLATE_ENGINE=llm (the fallback) asks the AI of app/ai/llm.py; here the mock AI answers."""
    engines(translate_engine="llm")
    [text] = translate.translate_texts([ALERT], "hi")
    assert text and compare_values(ALERT, text) == ([], [])


# --- text-to-speech -----------------------------------------------------------------------------------

@pytest.mark.parametrize("code", sorted(tts.PIPER_VOICES))
def test_piper_voice_reads_aloud(engines, code):
    engines(tts_engine="piper", translate_engine="indictrans2")
    voice = tts.voice_for(code)
    if voice is None or voice.engine != "piper":
        pytest.skip(f"The Piper voice for {code} is not downloaded")
    # a sentence in the language itself (IndicTrans2 when it is there; else English, which the voice still reads)
    text = "Do not open unknown links. Call 1930."
    if translate.status()["ready"]:
        [text] = translate.translate_texts([text], code)
    wav, used = tts.speak(text, code)
    assert used == tts.PIPER_VOICES[code]
    assert 0.5 < seconds(wav) < 20


@pytest.mark.parametrize("code", sorted(tts.SAY_VOICES))
def test_macos_voice_reads_aloud(engines, code):
    engines(tts_engine="say")
    voice = tts.voice_for(code)
    if voice is None:
        pytest.skip(f"The macOS voice {tts.SAY_VOICES[code].model} is not on this computer")
    wav, used = tts.speak("Report fraud by calling 1930." if code == "en" else "धोखाधड़ी की सूचना 1930 पर दें।", code)
    assert used.engine == "say" and 1 < seconds(wav) < 20


def test_no_voice_means_audio_not_available(engines):
    engines(tts_engine="piper")
    assert tts.voice_for("ta") is None
    with pytest.raises(tts.TTSError, match="not available for Tamil"):
        tts.speak("வணக்கம்", "ta")


# --- speech-to-text -----------------------------------------------------------------------------------

def spoken(engines, text: str, code: str) -> bytes:
    """A real recording to listen to: made by the real voice of that language."""
    for engine in ("piper", "say"):
        engines(tts_engine=engine)
        if tts.voice_for(code):
            return tts.speak(text, code)[0]
    pytest.skip(f"No voice on this computer to make a {code} test recording")


def test_whisper_hears_english(engines):
    engines(stt_engine="onnx")
    if not stt.ready("en"):
        pytest.skip("Whisper small is not downloaded")
    recording = spoken(engines, "Forty two hospitals reported a ransomware attack. Call the cyber crime helpline.", "en")
    heard = stt.transcribe(recording, "en", "briefing.wav")
    text = " ".join(heard.pages).lower()
    assert heard.model.startswith("Whisper") and "hospital" in text and "ransomware" in text, text


def test_indicconformer_hears_hindi(engines):
    engines(stt_engine="onnx")
    if not stt.ready("hi"):
        pytest.skip("IndicConformer Hindi is not downloaded")
    recording = spoken(engines, "अस्पतालों पर साइबर हमला हुआ है। अनजान लिंक मत खोलिए।", "hi")
    heard = stt.transcribe(recording, "hi", "briefing.wav")
    text = " ".join(heard.pages)
    assert "IndicConformer" in heard.model and ("अस्पताल" in text or "लिंक" in text), text


def test_indicconformer_tamil_loads_and_runs(engines):
    """There is no Tamil voice to make a Tamil recording, so this only checks the Tamil model loads and runs."""
    engines(stt_engine="onnx")
    if not stt.ready("ta"):
        pytest.skip("IndicConformer Tamil is not downloaded")
    recording = spoken(engines, "नमस्ते, यह एक परीक्षण है।", "hi")
    try:
        heard = stt.transcribe(recording, "ta", "test.wav")
        assert "Tamil" in heard.model
    except stt.STTError as exc:  # Hindi speech may give no Tamil words at all; the model still ran
        assert "No speech was found" in str(exc)
