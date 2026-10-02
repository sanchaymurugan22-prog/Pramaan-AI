"""Speech-to-text engines (Stage 8), chosen by STT_ENGINE in .env:

  onnx  offline, with onnx-asr + onnxruntime (no PyTorch):
          Hindi, Tamil  AI4Bharat IndicConformer (ONNX, weights quantised to 8 bits, MIT), models/stt/indicconformer-<code>
          English       OpenAI Whisper small (ONNX, weights quantised to 8 bits, MIT), models/stt/whisper-small
        The default.
  mock  a fixed transcript, for tests.

Used for "an audio file as a source" (e.g. a recorded briefing): the recording becomes text, and from then
on it is checked and handled like any other source. Long recordings are cut into pieces of about 25 seconds
at the quietest moment, because both models work on short pieces (Whisper reads at most 30 seconds).
"""

import threading
from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.lang import audio, languages

RATE = 16000
PIECE_SECONDS = 25           # cut long audio into pieces of about this length ...
SEARCH_SECONDS = 5           # ... at the quietest moment of the last few seconds
PAGE_SECONDS = 120           # the transcript is split into "pages" of 2 minutes, for the source trace

MODELS = {"hi": "indicconformer-hi", "ta": "indicconformer-ta", "en": "whisper-small"}
MODEL_NAMES = {"hi": "IndicConformer Hindi (AI4Bharat)", "ta": "IndicConformer Tamil (AI4Bharat)",
               "en": "Whisper small (English)"}


class STTError(Exception):
    """A friendly message when a recording cannot be turned into text."""


@dataclass
class Transcript:
    pages: list[str]      # the text, one "page" per 2 minutes of audio
    seconds: float        # length of the recording
    language: str
    model: str            # e.g. "IndicConformer Hindi (AI4Bharat)"


_loaded: dict[str, object] = {}
_lock = threading.Lock()


def languages_supported() -> list[str]:
    return list(MODELS)


def ready(language: str) -> bool:
    if settings.stt_engine == "mock":
        return language in MODELS
    folder = settings.models_dir / "stt" / MODELS.get(language, "-")
    return (folder / "config.json").exists()


def status() -> dict:
    return {"engine": settings.stt_engine, "ready": any(ready(c) for c in MODELS),
            "languages": {c: {"name": MODEL_NAMES[c], "ready": ready(c)} for c in MODELS}}


def transcribe(data: bytes, language: str, filename: str = "recording") -> Transcript:
    """Turn an audio or video file into text. language: "hi", "ta" or "en"."""
    if language not in MODELS:
        supported = ", ".join(languages.get(c).name for c in MODELS)
        raise STTError(f"Speech-to-text works for {supported}. {languages.get(language).name} is not available yet.")
    try:
        samples = audio.read_samples(data, RATE)
    except audio.AudioError as exc:
        raise STTError(f"{filename} could not be read as audio. {exc}") from exc
    seconds = len(samples) / RATE
    if seconds < 0.5:
        raise STTError(f"{filename} has no sound (it is shorter than half a second).")
    if settings.stt_engine == "mock":
        return Transcript(_pages_of([mock_text(language)], [seconds]), seconds, language, "Mock speech-to-text")
    if settings.stt_engine != "onnx":
        raise STTError(f"Unknown STT_ENGINE '{settings.stt_engine}'. Use onnx or mock.")
    if not ready(language):
        raise STTError(f"The {MODEL_NAMES[language]} model is not installed. Run "
                       "backend/.venv/bin/python scripts/download-models.py --only stt")
    model = _model(language)
    texts, lengths = [], []
    for piece in pieces(samples):
        try:
            text = model.recognize(piece, sample_rate=RATE, **({"language": "en"} if language == "en" else {}))
        except Exception as exc:
            raise STTError(f"{MODEL_NAMES[language]} could not read the recording: {exc}") from exc
        texts.append(" ".join(str(text).split()))
        lengths.append(len(piece) / RATE)
    if not any(texts):
        raise STTError(f"No speech was found in {filename}. Is it the right language ({languages.get(language).name})?")
    return Transcript(_pages_of(texts, lengths), seconds, language, MODEL_NAMES[language])


def _model(language: str):
    import onnx_asr

    with _lock:
        if language not in _loaded:
            folder = settings.models_dir / "stt" / MODELS[language]
            kind = "whisper" if language == "en" else "nemo-conformer-ctc"
            # Plain CPU: on macOS onnxruntime would try Apple's CoreML, which needs macOS 14.4+ and floods the log
            _loaded[language] = onnx_asr.load_model(kind, folder, quantization="uint8",
                                                    providers=["CPUExecutionProvider"])
        return _loaded[language]


def pieces(samples: np.ndarray) -> list[np.ndarray]:
    """Cut audio into pieces of at most PIECE_SECONDS, each cut at the quietest 0.2 s near the end."""
    out, start, n = [], 0, len(samples)
    window = int(0.2 * RATE)
    while n - start > PIECE_SECONDS * RATE:
        lo, hi = start + (PIECE_SECONDS - SEARCH_SECONDS) * RATE, start + PIECE_SECONDS * RATE
        region = samples[lo:hi]
        energy = np.convolve(region ** 2, np.ones(window), mode="valid")
        cut = lo + int(np.argmin(energy)) + window // 2
        out.append(samples[start:cut])
        start = cut
    out.append(samples[start:])
    return [p for p in out if len(p) > RATE // 10]


def _pages_of(texts: list[str], lengths: list[float]) -> list[str]:
    pages, current, used = [], [], 0.0
    for text, length in zip(texts, lengths):
        if current and used + length > PAGE_SECONDS:
            pages.append(" ".join(current))
            current, used = [], 0.0
        if text:
            current.append(text)
        used += length
    if current:
        pages.append(" ".join(current))
    return pages or [""]


def mock_text(language: str) -> str:
    """The mock transcript: a short spoken briefing with numbers and a date (in English, for the checks)."""
    return ("This is a recorded briefing. On 28 September 2026, 42 hospitals in five states reported a ransomware "
            "attack on patient-record systems. The attackers entered through an unpatched remote-access gateway. "
            "Apply the vendor patch to every gateway today and keep offline backups.")
