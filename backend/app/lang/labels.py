"""The fixed words printed on exported files ("Overview", "Recommended actions", "Scan to check this is
genuine." ...), in every language (Stage 8).

A translated advisory should not have English headings. The labels below are translated once into the 22
languages by IndicTrans2 (scripts/make-labels.py) and kept in labels.json; L() looks them up. Placeholders
like {n} stay as they are. Machine translated like the outputs; the Hindi ones were read by a person.

    L("Overview", "hi")                    -> "अवलोकन"
    L("Do these {n} things now", "ta", n=4)
"""

import json
from functools import cache
from pathlib import Path

TABLE = Path(__file__).with_name("labels.json")

# Every label used by the exporters (backend/app/exporters). Add new ones here, then run
# backend/.venv/bin/python scripts/make-labels.py (needs IndicTrans2).
# An entry is the label as printed in English, or (label, clearer English for the translator) when the
# short label alone is ambiguous ("Job" would become employment, "Record" a verb).
LABELS = [
    # footers and job details (common.py, every file)
    "AI-assisted · pending human approval",
    ("Approved and signed · Record {record_no}", "Approved and signed · Record number {record_no}"),
    ("Job #{job_id}", "Task #{job_id}"),
    "Page {page}",
    "Prepared: {date}",
    "Prepared {date}",
    "Sharing label: {tlp}",
    "Check it is genuine: {url}",
    "QR code",
    "when signed",
    "Scan to check this is genuine.",
    # output names
    ("Advisory", "Security advisory"), "Executive summary", "Presentation", "Video package", "Infographic", "LinkedIn post", "X thread",
    # advisory and executive summary (blocks.py)
    "Severity: Low", "Severity: Medium", "Severity: High", "Severity: Critical", "Severity: Unknown",
    "Overview",
    "Who and what is affected",
    "How the attack works",
    "Impact",
    "Indicators found in the source",
    "Vulnerability (CVE)",
    "IP address",
    "File fingerprint",
    ("Type", "Category"),
    "Value",
    "Recommended actions",
    ("Bottom line", "In short"),
    "Key points",
    "Actions needed",
    # video package
    "Script and storyboard · {count} scenes · about {seconds} seconds",
    "Storyboard",
    "Time",
    "Visual",
    "On-screen text",
    "Narration",
    "Narration script",
    "Scene {number}",
    ("Scene", "Scene of the video"),
    # presentation (pptx.py)
    ("Presentation · Job #{job_id}", "Presentation · Task #{job_id}"),
    "Introduce the briefing: {title}. It is based on '{job_title}' and has {count} content slides. This deck is "
    "AI-assisted and pending human approval until a reviewer signs it.",
    "No speaker notes were written for this slide.",
    "Thank the audience and invite questions. Remind them that this deck is AI-assisted and pending human approval: "
    "once signed, the QR code on this slide lets anyone check it is genuine.",
    "Scan the QR code to check this deck is genuine.",
    "Scan the QR code to check this deck is genuine (added when signed).",
    "Thank you",
    "Questions and discussion",
    # infographic
    "Public alert",
    "Do these {n} things now",
    "Do this now",
    "Step {n}",
    # emergency alert (Stage 8 part 5)
    "Emergency alert",
    # dates (format_date): translated as a date ("1 May"), so "May" is the month, not the verb; the "1" is dropped
    *[(month, f"1 {month}") for month in ("January", "February", "March", "April", "May", "June", "July", "August",
                                         "September", "October", "November", "December")],
]

# Read and corrected by a person (they win over the machine translation)
REVIEWED = {
    "hi": {
        "AI-assisted · pending human approval": "एआई-सहायता प्राप्त · मानव अनुमोदन लंबित",
        "Advisory": "सुरक्षा परामर्श",
        "How the attack works": "हमला कैसे काम करता है",
        "Who and what is affected": "कौन और क्या प्रभावित है",
        "Narration": "वाचन",
        "Narration script": "वाचन स्क्रिप्ट",
        "QR code": "क्यूआर कोड",
        "Public alert": "सार्वजनिक चेतावनी",
        "Scene": "दृश्य",
        "Severity: Critical": "गंभीरता: अति गंभीर",
        "Sharing label: {tlp}": "साझाकरण लेबल: {tlp}",
        "Thank you": "धन्यवाद",
        "Type": "प्रकार",
        "Value": "मान",
        "Vulnerability (CVE)": "भेद्यता (CVE)",
        "X thread": "एक्स थ्रेड",
        "when signed": "हस्ताक्षर होने पर",
        "May": "मई",
    },
}


@cache
def _table() -> dict[str, dict[str, str]]:
    try:
        return json.loads(TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def keys() -> list[str]:
    return [entry if isinstance(entry, str) else entry[0] for entry in LABELS]


def L(text: str, language: str = "en", **values) -> str:
    """The label in `language` (English if it has no translation yet), with {placeholders} filled in."""
    out = text if language == "en" else _table().get(language, {}).get(text, text)
    return out.format(**values) if values else out
