"""Public-release check (Stage 9A): is this text calm and safe to show to the public? No AI, rules only.

Used by the Emergency alert form (as the operator types) and the Social posts tab. It looks for:
  - panic wording: words that frighten without helping ("deadly", "catastrophic", "forward to everyone")
  - shouting: three or more words in CAPITALS in a row, or "!!"
  - private data: anything the safety scanner finds (phone numbers, Aadhaar, emails ... ) except the
    official helplines that public alerts are meant to carry (1930 cyber crime, 112 emergency ...)
Unverified claims are checked separately, by the source trace (sentences not linked to a fact).
"""

import re

from app.safety.scanner import ScanSource, scan_sources

# Lower-case words and phrases that spread panic instead of telling people what to do
PANIC_WORDS = [
    "panic", "deadly", "catastroph", "disaster is coming", "everyone will", "you will die", "nobody is safe",
    "no one is safe", "forward to everyone", "forward this to", "share before", "before it is deleted",
    "before it's deleted", "act now or", "last warning", "100% guaranteed", "guaranteed", "terrifying", "horrific",
    "apocalyp", "doomsday", "do not tell anyone",
]
# Helplines a public alert may name (not private data)
HELPLINES = {"1930", "112", "100", "101", "102", "108", "1078", "1070", "1098", "14567", "1800-11-4000"}
ACRONYMS = {"CERT-IN", "CERT", "NTRO", "SMS", "OTP", "UPI", "ATM", "PIN", "KYC", "URL", "IT", "NDMA", "IMD", "TLP",
            "CVE", "VPN", "QR", "PDF", "CEO", "RBI", "NPCI", "AI"}
CAPS_RUN = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9'-]*\s+){2,}[A-Z]{2,}[A-Z0-9'-]*\b")


def check_public_text(text: str) -> dict:
    """{ok, problems: [{kind, label, text}]} for one piece of public text."""
    problems = []
    lower = text.lower()
    for word in PANIC_WORDS:
        at = lower.find(word)
        if at >= 0:
            problems.append({"kind": "panic", "label": "Panic wording", "text": text[at:at + len(word)]})
    for run in CAPS_RUN.finditer(text):
        words = run.group(0).split()
        if sum(w.strip(".,!?") not in ACRONYMS for w in words) >= 3:
            problems.append({"kind": "shouting", "label": "Written in capitals (reads as shouting)", "text": run.group(0)})
    if "!!" in text:
        problems.append({"kind": "shouting", "label": "Many exclamation marks", "text": "!!"})

    report = scan_sources([ScanSource("S1", "alert", [text], [])])
    for finding in report["findings"]:
        if re.sub(r"[\s+]", "", finding["value"]).lstrip("91") in HELPLINES or finding["value"] in HELPLINES:
            continue
        problems.append({"kind": "private", "label": finding["label"], "text": finding["text"]})
    for item in report["suspicious"]:
        problems.append({"kind": "instruction", "label": item["label"], "text": item["text"][:80]})
    return {"ok": not problems, "problems": problems}


def check_public_outputs(outputs) -> dict:
    """The check over every public output of a job (LinkedIn post, X thread, infographic)."""
    from app.pipeline.output_types import OUTPUT_TYPES
    from app.pipeline.segments import segments
    problems = []
    for output in outputs:
        if not OUTPUT_TYPES[output.type]["public"] or not output.content_json:
            continue
        for segment in segments(output.type, output.content_json):
            if segment.checked:
                for problem in check_public_text(segment.text)["problems"]:
                    if problem["kind"] != "private":  # placeholders and the leak check cover private data
                        problems.append(problem | {"where": f"{OUTPUT_TYPES[output.type]['label']} · {segment.label}"})
    return {"ok": not problems, "problems": problems}
