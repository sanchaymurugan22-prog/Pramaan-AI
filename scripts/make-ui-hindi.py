"""Make the Hindi interface words of the web app (Stage 8): frontend/src/i18n/hi.json.

    backend/.venv/bin/python scripts/make-ui-hindi.py

1. Writes frontend/src/i18n/backend-keys.json: the fixed labels the backend sends (output names, setting
   choices, finding types, roles), so the screens can show them in Hindi too.
2. Runs frontend/scripts/i18n-keys.cjs, which collects every t("...") text of the app (keys.json).
3. Translates the texts that hi.json does not have yet with IndicTrans2 (on this computer). {placeholders}
   are kept. Texts in REVIEWED (menus, buttons, statuses: the words seen most) were written by a person and
   always win. Existing entries are kept, so corrections made by hand in hi.json stay.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.auth.accounts import ROLE_LABELS  # noqa: E402
from app.lang import languages  # noqa: E402
from app.lang.indictrans import IndicTrans2  # noqa: E402
from app.pipeline.versions import ORIGIN_LABELS  # noqa: E402
from app.pipeline.output_types import OUTPUT_TYPES, SETTING_OPTIONS  # noqa: E402
from app.routes.alerts import ALERT_TYPES, SEVERITIES  # noqa: E402
from app.safety.scanner import KINDS  # noqa: E402

I18N = ROOT / "frontend" / "src" / "i18n"
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# Code-like words (AI_MODE, .env, scripts/start.sh, PRM-2026-000001) are kept exactly as they are
CODE = re.compile(r"(?<![\w])(?:\.?[\w-]+(?:[._/][\w.-]+)+|[A-Z]{2,}_[A-Z_]+|\.[a-z]{2,5})(?![\w])")
# "job" is translated as employment (नौकरी); the translator gets "task" instead (कार्य)
JOB = re.compile(r"\b([Jj])obs?\b")

# Written by a person: the words on every screen
REVIEWED = {
    # menu
    "Dashboard": "डैशबोर्ड", "New transformation": "नया रूपांतरण", "My jobs": "मेरे कार्य",
    "Emergency alert": "आपातकालीन चेतावनी", "Watch folder": "निगरानी फ़ोल्डर", "Is this real?": "क्या यह असली है?",
    "Review queue": "समीक्षा कतार", "Signed records": "हस्ताक्षरित रिकॉर्ड", "Overview": "अवलोकन",
    "Users & access": "उपयोगकर्ता और पहुँच", "Audit trail": "ऑडिट ट्रेल", "AI models": "एआई मॉडल",
    "Templates": "टेम्पलेट", "Security & policies": "सुरक्षा और नीतियाँ", "Record book": "रिकॉर्ड बुक",
    "Public verify page": "सार्वजनिक सत्यापन पृष्ठ", "Updates & backup": "अपडेट और बैकअप",
    "Notifications": "सूचनाएँ", "Profile & settings": "प्रोफ़ाइल और सेटिंग्स", "Help": "सहायता",
    "Sign out": "साइन आउट", "Skip to main content": "मुख्य सामग्री पर जाएँ", "Menu": "मेनू",
    "Fully offline": "पूरी तरह ऑफ़लाइन", "Nothing leaves this computer": "कुछ भी इस कंप्यूटर से बाहर नहीं जाता",
    "Operator workspace": "ऑपरेटर कार्यक्षेत्र", "Reviewer workspace": "समीक्षक कार्यक्षेत्र",
    "Admin workspace": "एडमिन कार्यक्षेत्र", "Language of the app": "ऐप की भाषा",
    # statuses and roles
    "Approved": "स्वीकृत", "Ready": "तैयार", "Failed": "विफल", "In review": "समीक्षा में", "Sent back": "वापस भेजा गया",
    "Generating": "बन रहा है", "Draft": "मसौदा", "Operator": "ऑपरेटर", "Reviewer": "समीक्षक", "Admin": "एडमिन",
    "Waiting": "प्रतीक्षा में", "Done": "पूर्ण", "Job": "कार्य", "Jobs": "कार्य",
    # steps of a new transformation
    "Add sources": "स्रोत जोड़ें", "Safety check": "सुरक्षा जाँच", "Outputs & settings": "आउटपुट और सेटिंग्स",
    "Outputs and settings": "आउटपुट और सेटिंग्स", "Generate": "बनाएँ",
    # buttons
    "Cancel": "रद्द करें", "Save": "सहेजें", "Edit": "संपादित करें", "Delete": "हटाएँ", "Close": "बंद करें",
    "Back": "वापस", "Next": "आगे", "Download": "डाउनलोड", "Open": "खोलें", "Search": "खोजें", "Sign in": "साइन इन",
    "Submit for review": "समीक्षा के लिए भेजें", "Send back": "वापस भेजें", "Approve & sign": "स्वीकृत करें और हस्ताक्षर करें",
    "Regenerate": "फिर से लिखें", "Versions": "संस्करण", "Try again": "फिर कोशिश करें", "Campaign kit": "अभियान किट",
    "Compare versions": "संस्करणों की तुलना करें", "Mark all as read": "सभी को पढ़ा हुआ चिह्नित करें",
    "Next: safety check": "आगे: सुरक्षा जाँच", "Choose files": "फ़ाइलें चुनें", "Select all": "सभी चुनें",
    "Clear all": "सभी हटाएँ", "Listen": "सुनें", "Stop": "रोकें", "Translate again": "फिर से अनुवाद करें",
    "Add language": "भाषा जोड़ें", "Show the English next to it": "साथ में अंग्रेज़ी दिखाएँ",
    "Hide the English": "अंग्रेज़ी छिपाएँ", "Send for fast-track approval": "त्वरित स्वीकृति के लिए भेजें",
    # common words
    "Settings": "सेटिंग्स", "Outputs": "आउटपुट", "Languages": "भाषाएँ", "Source": "स्रोत", "Sources": "स्रोत",
    "Source trace": "स्रोत अनुरेखण", "Fact sheet": "तथ्य पत्र", "Quality score": "गुणवत्ता स्कोर",
    "Severity": "गंभीरता", "Audience": "पाठक वर्ग", "Tone": "लहजा", "Objective": "उद्देश्य", "Style": "शैली",
    "Level of detail": "विवरण का स्तर", "Short": "संक्षिप्त", "Medium": "मध्यम", "Detailed": "विस्तृत",
    "All": "सभी", "Unread": "अपठित", "Mentions": "उल्लेख", "Today": "आज", "Yesterday": "कल", "Public": "सार्वजनिक",
    "Machine translated - needs a native-speaker check.": "मशीन अनुवाद - मूल भाषी द्वारा जाँच आवश्यक।",
    "Checked by a native speaker": "मूल भाषी द्वारा जाँचा गया",
    # output names and labels the backend sends
    "Advisory": "सुरक्षा परामर्श", "Social posts": "सोशल पोस्ट", "X thread": "एक्स थ्रेड", "SMS alert": "एसएमएस चेतावनी",
    "Records": "रिकॉर्ड", "Critical": "अति गंभीर", "High": "उच्च", "Low": "निम्न", "Narration": "वर्णन",
    "Written by AI": "एआई द्वारा लिखा गया", "Edited by human": "व्यक्ति द्वारा संपादित",
    "Regenerated by AI": "एआई द्वारा फिर से लिखा गया", "Machine translated": "मशीन अनुवाद",
    "Translated again": "फिर से अनुवादित", "Submitted for review.": "समीक्षा के लिए भेजा गया।",
    "Submitted for review by {by} · {n}.": "{by} द्वारा समीक्षा के लिए भेजा गया · {n}।", "Written by the Operator": "ऑपरेटर द्वारा लिखा गया",
}


def backend_keys() -> list[str]:
    keys = set(ROLE_LABELS.values())
    for spec in OUTPUT_TYPES.values():
        keys |= {spec["label"], spec["description"]}
    for options in SETTING_OPTIONS.values():
        keys |= {o for o in options if re.search(r"[A-Za-z]{2}", o)}
    keys |= {kind.label for kind in KINDS.values()}
    keys |= set(ALERT_TYPES) | set(SEVERITIES) | set(ORIGIN_LABELS.values())
    keys |= {"Critical", "High", "Medium", "Low"}  # severity of a fact sheet
    return sorted(keys)


def main() -> None:
    (I18N / "backend-keys.json").write_text(json.dumps(backend_keys(), indent=1) + "\n", encoding="utf-8")
    subprocess.run(["node", str(ROOT / "frontend" / "scripts" / "i18n-keys.cjs")], check=True, cwd=ROOT / "frontend")
    keys = json.loads((I18N / "keys.json").read_text(encoding="utf-8"))
    hi_path = I18N / "hi.json"
    table = json.loads(hi_path.read_text(encoding="utf-8")) if hi_path.exists() else {}
    # entries from an earlier run with the problems above are made again
    for key in list(table):
        if ("नौकर" in table[key] or any(code not in table[key] for code in CODE.findall(key))
                or (key.endswith("…") and not table[key].endswith("…"))):
            del table[key]
    todo = [k for k in keys if k not in table and k not in REVIEWED]
    print(f"{len(keys)} texts; {len(todo)} to translate")
    if todo:
        model = IndicTrans2(ROOT / "models" / "indictrans2-en-indic-ct2")
        hindi = languages.get("hi")
        masked, names = [], []
        for key in todo:
            found = PLACEHOLDER.findall(key)
            names.append(found)
            text = key
            for n, name in enumerate(found, start=1):
                text = text.replace("{" + name + "}", f"[VALUE-{n}]", 1)
            codes = CODE.findall(text)
            for n, code in enumerate(codes, start=len(found) + 1):
                text = text.replace(code, f"[VALUE-{n}]", 1)
            names[-1] = found + [("code", c) for c in codes]
            text = JOB.sub(lambda m: ("T" if m.group(1) == "J" else "t") + ("asks" if m.group(0).endswith("s") else "ask"), text)
            masked.append(text)
        for start in range(0, len(todo), 64):  # in batches, with progress
            out = model.translate(masked[start:start + 64], hindi)
            for key, text, found in zip(todo[start:start + 64], out, names[start:start + 64]):
                for n, name in enumerate(found, start=1):
                    text = text.replace(f"[VALUE-{n}]", name[1] if isinstance(name, tuple) else "{" + name + "}")
                if not key.rstrip().endswith((".", "?", "!", "…")):
                    text = text.rstrip(" ।.")
                elif key.rstrip().endswith("…") and not text.endswith("…"):
                    text = text.rstrip(" ।.") + "…"
                placeholders = [name for name in found if not isinstance(name, tuple)]
                ok = (all("{" + name + "}" in text for name in placeholders) and not languages.foreign_scripts(text, "hi")
                      and all(name[1] in text for name in found if isinstance(name, tuple)))
                table[key] = text if ok else key  # a lost placeholder or another script: kept in English
            print(f"  {min(start + 64, len(todo))} of {len(todo)}")
    table.update(REVIEWED)
    table = {k: table[k] for k in sorted(table) if k in keys or k in REVIEWED}
    hi_path.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missing = [k for k in keys if k not in table]
    print(f"Saved {hi_path} ({len(table)} texts; {len(missing)} left in English: {missing[:5]})")


if __name__ == "__main__":
    main()
