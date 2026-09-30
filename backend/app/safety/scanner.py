"""The sensitivity scanner: finds private data and attack indicators in every source (no AI).

Private data (each one is a "finding" the operator makes a choice for):
  personal   Aadhaar (12 digits, checked with the Verhoeff checksum), PAN, Indian mobile numbers,
             email addresses, bank account numbers, IFSC codes, passport numbers, vehicle numbers
  location   GPS coordinates
  network    private IP addresses (10.x, 172.16-31.x, 192.168.x) and internal host names (.local, .corp ...)
  secret     passwords, API keys, tokens, private keys
  marking    classification words: TOP SECRET, SECRET, CONFIDENTIAL, RESTRICTED, "For official use only"

Attack indicators (public attacker IPs, CVE ids, file hashes) are NOT private data. They are listed
separately as "Indicator": kept in the advisory, left out of public posts by default.

The same value found several times is ONE finding (one phone number on pages 1 and 4), so the operator
makes one choice for it. Each place it was found is an "occurrence": source id, page, and character
positions (start, end) in that page's text, so the Safety check page can highlight it.

The operator's choice for each finding:
  hide_public  hidden in public outputs, kept in internal ones (the default for personal data)
  hide_all     hidden in every output (the default for passwords and keys)
  keep         not hidden
"""

import re
from dataclasses import dataclass

from app.pipeline.factsheet import CVE_PATTERN, HASH_PATTERN, IP_PATTERN, is_private_ip

CHOICES = {"hide_public": "Hide in public outputs", "hide_all": "Hide everywhere", "keep": "Keep"}
RISK_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class Kind:
    label: str          # shown on the page: "Phone number"
    group: str          # personal | location | network | secret | marking | indicator
    risk: str           # high | medium | low (classification words set their own)
    prefix: str         # placeholder sent to the AI: [PHONE-1]
    redaction: str      # what readers see where a value was hidden: [phone number]
    default: str        # the choice made for the operator until they change it
    compact: bool = False  # compared without spaces and dashes ("98765 43210" = "9876543210")


KINDS: dict[str, Kind] = {
    "aadhaar": Kind("Aadhaar number", "personal", "high", "AADHAAR", "[Aadhaar number]", "hide_public", True),
    "pan": Kind("PAN", "personal", "high", "PAN", "[PAN]", "hide_public", True),
    "phone": Kind("Phone number", "personal", "medium", "PHONE", "[phone number]", "hide_public", True),
    "email": Kind("Email address", "personal", "medium", "EMAIL", "[email address]", "hide_public"),
    "bank_account": Kind("Bank account number", "personal", "high", "BANK-ACCOUNT", "[bank account]", "hide_public", True),
    "ifsc": Kind("IFSC code", "personal", "low", "IFSC", "[IFSC code]", "hide_public", True),
    "passport": Kind("Passport number", "personal", "high", "PASSPORT", "[passport number]", "hide_public", True),
    "vehicle": Kind("Vehicle number", "personal", "medium", "VEHICLE", "[vehicle number]", "hide_public", True),
    "gps": Kind("GPS location", "location", "medium", "GPS", "[location]", "hide_public"),
    "private_ip": Kind("Internal IP address", "network", "medium", "INTERNAL-IP", "[internal address]", "hide_public"),
    "internal_host": Kind("Internal host name", "network", "medium", "INTERNAL-HOST", "[internal host]", "hide_public"),
    "password": Kind("Password", "secret", "high", "PASSWORD", "[password]", "hide_all"),
    "api_key": Kind("API or access key", "secret", "high", "API-KEY", "[access key]", "hide_all"),
    "token": Kind("Access token", "secret", "high", "TOKEN", "[token]", "hide_all"),
    "private_key": Kind("Private key", "secret", "high", "PRIVATE-KEY", "[private key]", "hide_all"),
    "classification": Kind("Classification marking", "marking", "medium", "MARKING", "[marking]", "hide_public"),
    # attack indicators: not private data
    "attacker_ip": Kind("Attacker IP address", "indicator", "low", "ATTACK-IP", "[attacker address]", "hide_public"),
    "cve": Kind("CVE id", "indicator", "low", "CVE", "[CVE id]", "hide_public"),
    "hash": Kind("File hash", "indicator", "low", "HASH", "[file hash]", "hide_public"),
}

# ---- Aadhaar checksum (Verhoeff) ----------------------------------------------------------------
# The last digit of an Aadhaar number is a Verhoeff check digit, so a random 12-digit number is
# accepted only 1 time in 10. That keeps order numbers and phone numbers from being called Aadhaar.

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(digits: str) -> bool:
    """True if the last digit is the correct Verhoeff check digit for the others."""
    check = 0
    for position, digit in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[position % 8][int(digit)]]
    return check == 0


def verhoeff_digit(digits: str) -> str:
    """The check digit to add after `digits` (used to make fictional test numbers)."""
    check = 0
    for position, digit in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[(position + 1) % 8][int(digit)]]
    return str(_VERHOEFF_INV[check])


# ---- patterns ---------------------------------------------------------------------------------------

PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----.*?-----END (?:[A-Z]+ )*PRIVATE KEY-----", re.S)
# Keys and tokens with a well-known shape (kind, pattern, group holding the value)
KNOWN_SECRETS = [
    ("api_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),                    # Amazon access key
    ("api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}(?![\w-])"), 0),       # Google API key
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), 0),                # "sk-..." API keys
    ("token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), 0),            # GitHub token
    ("token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), 0),            # Slack token
    ("token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), 0),  # JWT
    ("token", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/-]{20,}=*)"), 1),
]
# "password: X", "api_key = X", "token: X" ... (the value is what gets hidden, not the word)
KEY_VALUE = re.compile(
    r"(?i)\b(passwords?|passwd|passcode|pwd|secret(?:[ _-]?key)?|client[ _-]?secret|api[ _-]?key|access[ _-]?key"
    r"|auth[ _-]?token|access[ _-]?token|token)\b\s*(?:is\s*)?[:=]\s*[\"']?([^\s\"',;]{4,})"
)
EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
INTERNAL_HOST = re.compile(
    r"(?i)(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:local|corp|internal|intranet|lan|localdomain)\b(?![.-]\w)"
)
BANK_ACCOUNT = re.compile(r"(?i)\b(?:a/c|acc(?:ount)?|acct)\.?\s*(?:no\.?|number|num|#)?\s*[:\-]?\s*(\d(?:[ -]?\d){8,17})(?!\d)")
AADHAAR = re.compile(r"(?<![\w-])[2-9]\d{3}([ -]?)\d{4}\1\d{4}(?![\w-])(?![ -]\d)")
PAN = re.compile(r"\b[A-Z]{3}[ABCFGHJLPT][A-Z]\d{4}[A-Z]\b")
IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
PASSPORT = re.compile(r"\b[A-PR-WYZ][1-9]\d{6}\b")
_STATES = ("AN|AP|AR|AS|BR|CH|CG|CT|DD|DL|DN|GA|GJ|HR|HP|JK|JH|KA|KL|LA|LD|MP|MH|MN|ML|MZ|NL|OD|OR|PY|PB|RJ|SK"
           "|TN|TS|TG|TR|UP|UK|UA|WB")
VEHICLE = re.compile(rf"\b(?:{_STATES})[ -]?\d{{1,2}}[ -]?[A-Z]{{1,3}}[ -]?\d{{4}}\b|\b\d{{2}}[ -]?BH[ -]?\d{{4}}[ -]?[A-Z]{{1,2}}\b")
# Indian mobile: 10 digits starting 6-9, optionally +91 / 0091 / 0 in front, single spaces or dashes allowed
PHONE = re.compile(r"(?<![\w+])(?<!\d[ -])(?:(?:\+|00)91[ -]?|0)?[6-9](?:[ -]?\d){9}(?!\w)(?![ -]\d)")
GPS_DECIMAL = re.compile(r"(?<![\d.])(-?\d{1,2}\.\d{4,})°?\s*([NS])?\s*,\s*(-?\d{1,3}\.\d{4,})°?\s*([EW])?(?!\d|\.\d)")
GPS_DMS = re.compile(
    r"\d{1,2}°\s*\d{1,2}['′]\s*(?:\d{1,2}(?:\.\d+)?[\"″]\s*)?[NS][,\s]+\d{1,3}°\s*\d{1,2}['′]\s*(?:\d{1,2}(?:\.\d+)?[\"″]\s*)?[EW]"
)
# Markings in capitals only ("restricted access" in a normal sentence is not a marking) ...
CLASSIFICATION_WORD = re.compile(r"\bTOP SECRET\b|\bSECRET\b|\bCONFIDENTIAL\b|\bRESTRICTED\b")
# ... or written after "Classification:" in any case, and "For official use only"
CLASSIFICATION_LINE = re.compile(r"(?i)\b(?:classification|classified|marking)\s*[:\-]\s*(top secret|secret|confidential|restricted)\b")
FOUO = re.compile(r"(?i)\bfor official use only\b|\bFOUO\b")
MARKING_RISK = {"TOP SECRET": "high", "SECRET": "high", "CONFIDENTIAL": "medium", "RESTRICTED": "medium",
                "FOR OFFICIAL USE ONLY": "low"}


@dataclass
class Hit:
    kind: str
    start: int
    end: int
    text: str    # as written in the source
    value: str   # normalised, so the same value written two ways is one finding
    risk: str


def find_hits(text: str) -> list[Hit]:
    """Everything sensitive in one page of text, in reading order. Detectors run from the most specific
    to the most general, and a place already taken is not claimed again (a phone number inside an
    email address, digits inside a key)."""
    hits: list[Hit] = []

    def free(start: int, end: int) -> bool:
        return all(end <= h.start or start >= h.end for h in hits)

    def add(kind: str, start: int, end: int, value: str | None = None, risk: str | None = None) -> None:
        if start < end and free(start, end):
            written = text[start:end]
            hits.append(Hit(kind, start, end, written, value if value is not None else written, risk or KINDS[kind].risk))

    for m in PRIVATE_KEY.finditer(text):
        add("private_key", m.start(), m.end())
    for kind, pattern, group in KNOWN_SECRETS:
        for m in pattern.finditer(text):
            add(kind, m.start(group), m.end(group))
    for m in KEY_VALUE.finditer(text):
        word, value = m.group(1), m.group(2).rstrip(".)]")
        if word == "SECRET" or not _looks_secret(value):  # "SECRET: ..." is a marking, "password: see below" is not one
            continue
        kind = "password" if word.lower().startswith(("pass", "pwd")) else "token" if "token" in word.lower() else "api_key"
        add(kind, m.start(2), m.start(2) + len(value))

    for m in EMAIL.finditer(text):
        add("email", m.start(), m.end(), m.group().lower())
    for m in INTERNAL_HOST.finditer(text):
        add("internal_host", m.start(), m.end(), m.group().lower())
    for m in IP_PATTERN.finditer(text):
        ip = m.group().replace("[.]", ".")
        if all(0 <= int(part) <= 255 for part in ip.split(".")):
            add("private_ip" if is_private_ip(ip) else "attacker_ip", m.start(), m.end(), ip)
    for m in CVE_PATTERN.finditer(text):
        add("cve", m.start(), m.end(), m.group().upper())
    for m in HASH_PATTERN.finditer(text):
        if not m.group().isdigit():
            add("hash", m.start(), m.end(), m.group().lower())

    for m in BANK_ACCOUNT.finditer(text):
        add("bank_account", m.start(1), m.end(1), _compact(m.group(1)))
    for m in AADHAAR.finditer(text):
        digits = _compact(m.group())
        if verhoeff_valid(digits):
            add("aadhaar", m.start(), m.end(), digits)
    for kind, pattern in (("pan", PAN), ("ifsc", IFSC), ("passport", PASSPORT), ("vehicle", VEHICLE)):
        for m in pattern.finditer(text):
            add(kind, m.start(), m.end(), _compact(m.group()).upper())
    for m in PHONE.finditer(text):
        add("phone", m.start(), m.end(), _compact(m.group())[-10:])

    for m in GPS_DECIMAL.finditer(text):
        if abs(float(m.group(1))) <= 90 and abs(float(m.group(3))) <= 180:
            add("gps", m.start(), m.end(), f"{float(m.group(1)):.4f},{float(m.group(3)):.4f}")
    for m in GPS_DMS.finditer(text):
        add("gps", m.start(), m.end(), re.sub(r"\s+", "", m.group()))

    for m in CLASSIFICATION_WORD.finditer(text):
        add("classification", m.start(), m.end(), m.group(), MARKING_RISK[m.group()])
    for m in CLASSIFICATION_LINE.finditer(text):
        word = m.group(1).upper()
        add("classification", m.start(1), m.end(1), word, MARKING_RISK[word])
    for m in FOUO.finditer(text):
        add("classification", m.start(), m.end(), "FOR OFFICIAL USE ONLY", "low")

    return sorted(hits, key=lambda h: h.start)


def _compact(text: str) -> str:
    """Letters and digits only: "98765 43210" -> "9876543210"."""
    return re.sub(r"[^0-9A-Za-z]", "", text)


def _looks_secret(value: str) -> bool:
    """A password or key has 6+ characters and a digit, a symbol, or mixed case ("see", "below" are not)."""
    return len(value) >= 6 and (
        any(c.isdigit() for c in value) or any(not c.isalnum() for c in value)
        or (any(c.isupper() for c in value) and any(c.islower() for c in value))
    )


# ---- the report for one job ---------------------------------------------------------------------------


@dataclass
class ScanSource:
    source_id: str          # "S1"
    filename: str
    pages: list[str]        # the page texts the rest of the app uses (hidden characters already removed)
    notes: list[dict]       # hidden characters and hidden text found while reading the file (see ingest.py)


def scan_sources(sources: list[ScanSource]) -> dict:
    """Scan every page of every source. Returns the safety report saved on the job (jobs.safety_json)."""
    # imported here: shield.py and tlp.py import from this module
    from app.safety.shield import find_suspicious
    from app.safety.tlp import suggest_tlp

    groups: dict[tuple[str, str], dict] = {}
    for source in sources:
        for page_number, page in enumerate(source.pages, start=1):
            for hit in find_hits(page):
                finding = groups.setdefault((hit.kind, hit.value), _new_finding(hit))
                finding["occurrences"].append(
                    {"source_id": source.source_id, "page": page_number, "start": hit.start, "end": hit.end, "text": hit.text}
                )
                if RISK_ORDER[hit.risk] > RISK_ORDER[finding["risk"]]:
                    finding["risk"] = hit.risk

    # ids and placeholders in the order things appear: P1, P2 ... (private), I1, I2 ... (indicators);
    # [PHONE-1], [PHONE-2] ... counted per kind
    findings, indicators, per_prefix = [], [], {}
    for finding in groups.values():
        kind = KINDS[finding["kind"]]
        per_prefix[kind.prefix] = per_prefix.get(kind.prefix, 0) + 1
        finding["placeholder"] = f"{kind.prefix}-{per_prefix[kind.prefix]}"
        finding["count"] = len(finding["occurrences"])
        target = indicators if kind.group == "indicator" else findings
        finding["id"] = f"{'I' if target is indicators else 'P'}{len(target) + 1}"
        target.append(finding)

    suspicious = find_suspicious(sources)
    tlp, reason = suggest_tlp(findings, indicators)
    return {
        "checked": {"sources": len(sources), "pages": sum(len(s.pages) for s in sources)},
        "findings": findings,
        "indicators": indicators,
        "suspicious": suspicious,
        "kinds_found": len({f["kind"] for f in findings}),
        "suggested_tlp": tlp,
        "tlp_reason": reason,
        "switched_off": {},  # filled in when the job starts: public outputs a RED / AMBER label switched off
    }


def _new_finding(hit: Hit) -> dict:
    kind = KINDS[hit.kind]
    return {
        "id": "",
        "kind": hit.kind,
        "label": kind.label,
        "group": kind.group,
        "risk": hit.risk,
        "text": hit.text,         # as first written in the source
        "value": hit.value,       # normalised
        "placeholder": "",
        "redaction": kind.redaction,
        "choice": kind.default,
        "occurrences": [],
    }


def all_findings(report: dict | None) -> list[dict]:
    """Private findings and indicators together (both can be hidden)."""
    report = report or {}
    return list(report.get("findings", [])) + list(report.get("indicators", []))
