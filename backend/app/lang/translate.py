"""Translation engines (Stage 8), chosen by TRANSLATE_ENGINE in .env:

  indictrans2  AI4Bharat IndicTrans2 on this computer (models/indictrans2-en-indic-ct2). The default.
  llm          the Sarvam model through app/ai/llm.py (whatever AI_MODE says). Slower; a fallback.
  mock         instant, for tests: each text gets the language's name in front, values untouched.

The rest of the app calls translate_texts(texts, "hi") and never needs to know which engine is in use.
Every text should already be MASKED by the caller (hidden values as [PHONE-1]); the engines keep such
placeholders, numbers, dates, addresses and ids exactly as they are. Helpline numbers get the words "helpline
number" in front first (v1.2, app/lang/helplines.py), so no engine reads "on 1930" as "in the year 1930".
"""

import json
import re
import threading

from app.config import settings
from app.lang import helplines, languages
from app.lang.languages import Language


class TranslateError(Exception):
    """A friendly message when translation is not possible."""


ENGINES = ("indictrans2", "llm", "mock")

# Sentence ends: ". " before a capital letter, digit, quote or bracket (the same rule as the checks)
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)]?\s+(?=[A-Z0-9\[\"“(])")

_model = None
_model_lock = threading.Lock()


def engine_name() -> str:
    return settings.translate_engine


def model_folder():
    return settings.models_dir / "indictrans2-en-indic-ct2"


def status() -> dict:
    """For the Admin "AI models" page and the language picker: is translation ready to use?"""
    name = engine_name()
    if name == "mock":
        return {"engine": "mock", "ready": True, "detail": "Test translations (TRANSLATE_ENGINE=mock)"}
    if name == "llm":
        return {"engine": "llm", "ready": True, "detail": f"Through the AI model (AI_MODE={settings.ai_mode}); slow"}
    folder = model_folder()
    ready = (folder / "model.bin").exists() and (folder / "model.SRC").exists()
    return {"engine": "indictrans2", "ready": ready,
            "detail": "IndicTrans2 on this computer" if ready else
                      "Model not installed: run backend/.venv/bin/python scripts/download-models.py --only translate"}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text.strip()) if s.strip()]


def translate_texts(texts: list[str], language: str) -> list[str]:
    """Translate English texts into `language` ("hi", "ta" ...). Empty texts stay empty."""
    lang = languages.LANGUAGES.get(language)
    if lang is None or lang.code == "en":
        raise TranslateError(f"Pramaan cannot translate into '{language}'.")
    if not any(t.strip() for t in texts):
        return list(texts)
    # "on 1930" alone reads like a year ("in 1930"): say it is a helpline number (app/lang/helplines.py)
    texts = [helplines.clarify(t) for t in texts]
    name = engine_name()
    if name == "mock":
        return [mock_translation(t, lang) if t.strip() else t for t in texts]
    if name == "llm":
        return _translate_llm(texts, lang)
    if name == "indictrans2":
        return _translate_indictrans2(texts, lang)
    raise TranslateError(f"Unknown TRANSLATE_ENGINE '{name}'. Use one of: {', '.join(ENGINES)}.")


def mock_translation(text: str, lang: Language) -> str:
    """The test 'translation': the language name in its own script, then the English text."""
    return f"{lang.native} · {text}"


# --- IndicTrans2 -----------------------------------------------------------------------------------

def _translator():
    global _model
    with _model_lock:
        if _model is None:
            folder = model_folder()
            if not (folder / "model.bin").exists():
                raise TranslateError("IndicTrans2 is not installed on this computer. Run "
                                     "backend/.venv/bin/python scripts/download-models.py --only translate, "
                                     "or set TRANSLATE_ENGINE=llm in .env.")
            from app.lang.indictrans import IndicTrans2
            _model = IndicTrans2(folder, threads=settings.translate_threads)
        return _model


def _translate_indictrans2(texts: list[str], lang: Language) -> list[str]:
    # One batch for all sentences of all texts (faster), then joined back per text.
    pieces = [split_sentences(t) for t in texts]
    flat = [s for sentences in pieces for s in sentences]
    try:
        done = iter(_translator().translate(flat, lang))
    except TranslateError:
        raise
    except Exception as exc:  # a broken model file, out of memory ...
        raise TranslateError(f"IndicTrans2 could not translate: {exc}") from exc
    return [" ".join(next(done) for _ in sentences) for sentences in pieces]


# --- through the LLM (app/ai/llm.py) -----------------------------------------------------------------

def _translate_llm(texts: list[str], lang: Language) -> list[str]:
    from app.ai import llm
    from app.ai.prompt_files import render_prompt
    from app.safety.shield import fence

    schema = {"type": "object", "required": ["translations"], "additionalProperties": False, "properties": {
        "translations": {"type": "array", "items": {"type": "string"}, "minItems": len(texts), "maxItems": len(texts)}}}
    messages = [
        {"role": "system", "content": render_prompt("translate", language=f"{lang.name} ({lang.native})", script=lang.script)},
        {"role": "user", "content": fence(json.dumps(texts, ensure_ascii=False, indent=0), "TEXTS")
                                    + f"\nTranslate every item of TEXTS into {lang.name}. Language code: {lang.code}"},
    ]
    max_tokens = min(4000, 200 + 3 * sum(len(t) for t in texts) // 2)  # Indian scripts need more tokens than English
    try:
        reply = llm.chat_json(messages, schema, kind="translate", max_tokens=max_tokens)
    except llm.LLMError as exc:
        raise TranslateError(str(exc)) from exc
    out = reply.data.get("translations") or []
    if len(out) != len(texts):
        raise TranslateError(f"The AI returned {len(out)} translations for {len(texts)} texts. Try again.")
    from app.lang.indictrans import ascii_digits
    return [ascii_digits(str(t)).strip() for t in out]
