"""Text-to-speech engines (Stage 8), chosen by TTS_ENGINE in .env:

  piper  Piper voices run by sherpa-onnx (8-bit, offline) for Hindi, Telugu, Malayalam and Urdu, in
         models/tts/. For a language without a Piper voice, macOS "say" is used when it has one
         (Lekha: Hindi, Rishi: Indian English). The default.
  say    macOS "say" only (Lekha, Rishi). Nothing to download; works only on a Mac.
  mock   a quiet tone of the right length, for tests.

Every other language: "Audio is not available for this language" (the text is still made).

Voice licences (see README): Hindi "priyamvada" CC BY-NC-SA 4.0 (AI4Bharat data), Telugu "padmavathi"
CC BY 4.0 (AI4Bharat IndicVoices-R), Malayalam "meera" (IIT Madras Indic TTS data, via Piper), Urdu "fasih"
MIT. sherpa-onnx is Apache-2.0; espeak-ng (inside the voice folders, for pronunciation) is GPL-3.0.
"""

import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import settings
from app.lang import audio, languages


class TTSError(Exception):
    """A friendly message, e.g. when no voice exists for a language."""


@dataclass(frozen=True)
class Voice:
    engine: str      # piper | say | mock
    name: str        # shown in the app, e.g. "Priyamvada (Piper)"
    model: str = ""  # piper: the folder in models/tts; say: the macOS voice name
    licence: str = ""


PIPER_VOICES = {
    "hi": Voice("piper", "Priyamvada", "vits-piper-hi_IN-priyamvada-medium-int8", "CC BY-NC-SA 4.0 (data: AI4Bharat)"),
    "te": Voice("piper", "Padmavathi", "vits-piper-te_IN-padmavathi-medium-int8", "CC BY 4.0 (data: AI4Bharat IndicVoices-R)"),
    "ml": Voice("piper", "Meera", "vits-piper-ml_IN-meera-medium-int8", "IIT Madras Indic TTS data"),
    "ur": Voice("piper", "Fasih", "vits-piper-ur_PK-fasih-medium-int8", "MIT"),
}
SAY_VOICES = {
    "hi": Voice("say", "Lekha (macOS)", "Lekha", "Apple macOS voice: for use on this Mac"),
    "en": Voice("say", "Rishi (macOS)", "Rishi", "Apple macOS voice: for use on this Mac"),
}

_loaded: dict[str, object] = {}
_lock = threading.Lock()


def _piper_ready(voice: Voice) -> bool:
    folder = settings.models_dir / "tts" / voice.model
    return (folder / "tokens.txt").exists() and any(folder.glob("*.onnx"))


def _say_ready(voice: Voice) -> bool:
    if sys.platform != "darwin" or not shutil.which("say"):
        return False
    try:
        listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(line.split()[0] == voice.model for line in listing.splitlines() if line.strip())


def voice_for(language: str) -> Voice | None:
    """The voice that will read this language, or None if audio is not available for it."""
    engine = settings.tts_engine
    if engine == "mock":
        return Voice("mock", "Test tone", "mock") if language in ("en", *PIPER_VOICES) else None
    if engine == "piper" and language in PIPER_VOICES and _piper_ready(PIPER_VOICES[language]):
        return PIPER_VOICES[language]
    if engine in ("piper", "say") and language in SAY_VOICES and _say_ready(SAY_VOICES[language]):
        return SAY_VOICES[language]
    return None


def status() -> dict:
    """For the Admin "AI models" page and the pickers: which languages can be spoken, and by which voice."""
    voices = {code: v for code in languages.LANGUAGES if (v := voice_for(code))}
    return {"engine": settings.tts_engine, "ready": bool(voices),
            "voices": {code: {"name": v.name, "engine": v.engine, "licence": v.licence} for code, v in voices.items()}}


def not_available(language: str) -> str:
    return f"Audio is not available for {languages.get(language).name}: there is no voice for it on this computer."


def speak(text: str, language: str) -> tuple[bytes, Voice]:
    """Read `text` aloud. Returns (WAV file, the voice used). Raises TTSError."""
    text = spoken(text)
    if not text:
        raise TTSError("There is no text to read aloud.")
    voice = voice_for(language)
    if voice is None:
        raise TTSError(not_available(language))
    try:
        if voice.engine == "mock":
            return _mock(text), voice
        if voice.engine == "piper":
            return _piper(text, voice), voice
        return _say(text, voice), voice
    except TTSError:
        raise
    except Exception as exc:
        raise TTSError(f"The voice {voice.name} could not read the text: {exc}") from exc


# The Piper voices read the Hindi full stop (।) and the Urdu one (۔) ALOUD as a word ("purnviram");
# as a full stop they become a pause, like ".".
_STOPS = str.maketrans({"।": ".", "॥": ".", "۔": "."})


def spoken(text: str) -> str:
    """Text as it should be read: sentence marks as pauses, no line breaks or double spaces."""
    return " ".join(text.translate(_STOPS).split())


def _mock(text: str) -> bytes:
    """A soft 440 Hz tone, as long as reading the text would take (2.5 words a second)."""
    rate = 16000
    seconds = max(0.5, len(text.split()) / 2.5)
    t = np.arange(int(rate * seconds)) / rate
    return audio.wav_bytes(0.05 * np.sin(2 * np.pi * 440 * t), rate)


def _piper(text: str, voice: Voice) -> bytes:
    import sherpa_onnx

    folder = settings.models_dir / "tts" / voice.model
    with _lock:
        tts = _loaded.get(voice.model)
        if tts is None:
            onnx = sorted(folder.glob("*.onnx"), key=lambda p: ("int8" not in p.name, p.name))[0]
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=str(onnx), lexicon="", tokens=str(folder / "tokens.txt"),
                        data_dir=str(folder / "espeak-ng-data")),
                    num_threads=2, provider="cpu"),
                max_num_sentences=2,
            )
            if not config.validate():
                raise TTSError(f"The voice files in {folder} are incomplete. Run scripts/download-models.py --only tts.")
            tts = _loaded[voice.model] = sherpa_onnx.OfflineTts(config)
        result = tts.generate(text, sid=0, speed=1.0)
    if not len(result.samples):
        raise TTSError(f"The voice {voice.name} made no sound for this text.")
    return audio.wav_bytes(result.samples, result.sample_rate)


def _say(text: str, voice: Voice) -> bytes:
    with tempfile.TemporaryDirectory(prefix="pramaan-say-") as folder:
        source, out = Path(folder) / "text.txt", Path(folder) / "speech.wav"
        source.write_text(text, encoding="utf-8")
        result = subprocess.run(["say", "-v", voice.model, "--file-format=WAVE", "--data-format=LEI16@22050",
                                 "-o", str(out), "-f", str(source)], capture_output=True, text=True, timeout=600)
        if result.returncode != 0 or not out.exists():
            raise TTSError(f"macOS 'say' failed: {result.stderr.strip()[:200]}")
        return out.read_bytes()
