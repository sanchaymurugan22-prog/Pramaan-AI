"""Stage 8: outputs in Indian languages, TRANSLATED FROM THE ENGLISH OUTPUT (not written again by the AI).

translate_content()  Every text field of the English output is translated (app/lang/translate.py) and
                     written into a copy of it, so the structure stays exactly the same: fact ids,
                     indicators, severity, layout, scene timings. Hashtags and key-number values stay as
                     they are. Hidden values are masked first (placeholders like [PHONE-1]), exactly as for
                     the AI, and put back afterwards; the translation engines copy placeholders unchanged.

check_translation()  The grounding checks, again, for the translation:
                       - every number, date, time, IP address, CVE id, hash, e-mail, link and hidden-value
                         placeholder of the English text must be in the translation, unchanged; anything
                         missing is red ("Changed in translation"), and so is a number the English does not
                         have ("Not in the English text");
                       - each field keeps the links of its English sentences (same fact ids; a sentence that
                         was "not linked" in English stays yellow), and the English "not in source" flags;
                       - the length and format rules (an X post must still fit in 280 characters).
A translation shows "Machine translated - needs a native-speaker check" until a Reviewer ticks it.
"""

import re
import time
from collections import Counter

from app.lang import languages, translate
from app.pipeline.checks import CHECKS_VERSION, _score, _warnings, format_rules, sheet_items
from app.pipeline.generate import add_timings
from app.pipeline.segments import apply_edits, segments

# The values that must survive translation, as written: placeholders and labels in square brackets,
# CVE ids, hashes, IP addresses, e-mails, links, clock times, hashtags and @names, then any other number.
_ATOM = re.compile(
    r"\[[^\[\]\n]{1,40}\]"
    r"|CVE-\d{4}-[\dX]{4,}"
    r"|\b[0-9a-fA-F]{32,128}\b"
    r"|\b\d{1,3}(?:\[?\.\]?\d{1,3}){3}\b"
    r"|[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"
    r"|https?://[^\s<>\"]+"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\b"
    r"|[#@][A-Za-z_]\w*"
    r"|\d+(?:[.,]\d+)*",
    re.IGNORECASE,
)


def _skip(path: list) -> bool:
    """Not translated: hashtags (they are tags, not sentences) and the big numbers of the infographic."""
    return path[0] == "hashtags" or (path[0] == "key_numbers" and path[-1] == "value")


def translate_content(output_type: str, content: dict, language: str, masker, public: bool) -> tuple[dict, float]:
    """The English `content` translated into `language`. Returns (new content, seconds taken)."""
    started = time.monotonic()
    fields = [s for s in segments(output_type, content) if s.editable and not _skip(s.path) and s.text.strip()]
    masked = [masker.mask(s.text) for s in fields]
    translated = translate.translate_texts(masked, language)
    edits = [(s.path, masker.restore(t, public).strip() or s.text) for s, t in zip(fields, translated)]
    new = apply_edits(output_type, content, edits)
    if output_type == "video_package":
        add_timings(new)  # the narration is now in another language: new scene times and subtitles
    return new, time.monotonic() - started


def value_atoms(text: str) -> Counter:
    return Counter(m.group(0).lower().replace("[.]", ".") for m in _ATOM.finditer(text or ""))


def compare_values(english: str, translated: str) -> tuple[list[str], list[str]]:
    """(values of the English missing from the translation, numbers in the translation not in the English)."""
    en, tr = value_atoms(english), value_atoms(translated)
    missing = sorted((en - tr).elements())
    extra = sorted((tr - en).elements())
    return missing, extra


def _key(path: list) -> str:
    return ".".join(str(p) for p in path)


def check_translation(output_type: str, translated: dict, english: dict, english_quality: dict | None,
                      sheet: dict, language: str, truncated: bool = False) -> dict:
    items = sheet_items(sheet)
    english_fields = {_key(s.path): s for s in segments(output_type, english)}
    english_sentences: dict[str, list[dict]] = {}
    for s in (english_quality or {}).get("sentences", []):
        english_sentences.setdefault(_key(s["path"]), []).append(s)

    sentences, changed, checked = [], [], 0
    for segment in segments(output_type, translated):
        if not segment.checked:
            continue
        key = _key(segment.path)
        source = english_fields.get(key)
        before = english_sentences.get(key, [])
        missing, extra = compare_values(source.text if source else "", segment.text)
        checked += sum(value_atoms(source.text if source else "").values())
        flags = [{"kind": "translation", "label": "Changed in translation", "text": m} for m in missing]
        flags += [{"kind": "translation", "label": "Not in the English text", "text": e} for e in extra]
        flags += [f for s in before for f in s.get("not_in_source", [])]  # still not in the source
        changed += [{"label": segment.label, "missing": missing, "extra": extra}] if missing or extra else []

        statuses = {s["status"] for s in before}
        if segment.fact_ids is None:
            status = "heading"
        else:
            status = next((s for s in ("unlinked", "unverified", "linked") if s in statuses), "plain")
        fact_ids = list(dict.fromkeys(i for s in before for i in s.get("fact_ids", [])))
        sentences.append({
            "id": f"s{len(sentences) + 1}", "path": segment.path, "label": segment.label,
            "text": segment.text, "start": 0, "end": len(segment.text),
            "status": status, "fact_ids": fact_ids if status in ("linked", "unverified") else [],
            "matched_by": "translation" if status == "linked" else None,
            "closest": next((s.get("closest") for s in before if s.get("closest")), None),
            "not_in_source": flags, "english": source.text if source else "",
        })

    rules = format_rules(output_type, translated, truncated)
    quality = _score(sentences, items, rules)
    quality["unknown_fact_ids"] = []
    quality["warnings"] = _warnings(quality, rules, set())
    if changed:
        shown = ", ".join(f"“{v}”" for c in changed for v in c["missing"][:2]) or ", ".join(
            f"“{v}”" for c in changed for v in c["extra"][:2])
        quality["warnings"].insert(0, f"Values changed in translation: {shown}. Compare with the English and correct it.")
    # The translator sometimes writes a word in another script (an Urdu word in a Santali text): say where
    foreign = sorted({f"{s['label']}" for s in sentences if languages.foreign_scripts(s["text"], language)})
    if foreign:
        quality["warnings"].append(f"Letters of another script in: {', '.join(foreign[:4])}. A native speaker should "
                                   "check those words.")
    quality["translation"] = {"language": language, "values_checked": checked, "changed": changed,
                              "other_script": foreign}
    quality["checks_version"] = CHECKS_VERSION
    return quality


def engine_label() -> str:
    name = translate.engine_name()
    if name == "indictrans2":
        return "IndicTrans2 (AI4Bharat)"
    if name == "llm":
        from app.ai import llm
        return f"{llm.describe().get('model', 'AI model')} (through the AI model)"
    return "Mock translation (tests)"


def language_label(code: str) -> str:
    return languages.label(code)
