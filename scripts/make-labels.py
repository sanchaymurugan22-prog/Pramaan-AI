"""Translate the fixed words of exported files (backend/app/lang/labels.py) into the 22 languages with
IndicTrans2, and save them in backend/app/lang/labels.json (Stage 8). Run again after adding labels:

    backend/.venv/bin/python scripts/make-labels.py

{placeholders} are swapped for [V-1]-style placeholders first (the translator copies those unchanged).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.lang import languages  # noqa: E402
from app.lang.indictrans import IndicTrans2  # noqa: E402
from app.lang.labels import LABELS, REVIEWED, TABLE  # noqa: E402

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def main() -> None:
    model = IndicTrans2(ROOT / "models" / "indictrans2-en-indic-ct2")
    table = {}
    for code in languages.INDIAN:
        lang = languages.get(code)
        texts, names, keys = [], [], []
        for entry in LABELS:
            label, source = (entry, entry) if isinstance(entry, str) else entry
            keys.append(label)
            found = PLACEHOLDER.findall(source)
            names.append(found)
            masked = source
            for n, name in enumerate(found, start=1):
                masked = masked.replace("{" + name + "}", f"[VALUE-{n}]", 1)
            texts.append(masked)
        out = model.translate(texts, lang)
        result = {}
        for label, text, found in zip(keys, out, names):
            for n, name in enumerate(found, start=1):
                text = text.replace(f"[VALUE-{n}]", "{" + name + "}")
            if not label.endswith("."):  # "Thank you" -> "धन्यवाद", not "धन्यवाद।"
                text = text.rstrip(" .।۔॥᱾꯫")
            if not isinstance(entry := LABELS[keys.index(label)], str) and entry[1].startswith("1 "):
                text = text.lstrip("0123456789 ")  # a month, translated as the date "1 May"
                text = text.split()[0] if text else text
            # a placeholder lost, or letters of another script (the model sometimes mixes in an Urdu word):
            # keep the English
            if all("{" + name + "}" in text for name in found) and not languages.foreign_scripts(text, code):
                result[label] = text
        result.update(REVIEWED.get(code, {}))
        table[code] = result
        print(f"{code}: {len(result)} of {len(LABELS)} labels")
    TABLE.write_text(json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Saved {TABLE}")


if __name__ == "__main__":
    main()
