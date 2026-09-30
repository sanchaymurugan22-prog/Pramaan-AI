"""Finds the "hard values" in a piece of text: numbers, dates, CVE ids, IP addresses, file hashes,
and (Stage 6A) links, email addresses and phone numbers.

These are the things an AI most often gets subtly wrong (43 instead of 42, 23 September instead of
22), so they are checked by exact rules, never by the AI:

  - "Not in source": every value in an output must also appear in the source text.
  - Consistency: the same fact must carry the same number / date in every output.

Each number also remembers the word after it (its "unit"), so "42 hospitals" and "42 hours" are
different things, and "1.2 million records" matches "1,200,000 records".

Every value must be in the SOURCE itself (the fact sheet does not count). A link or phone number that
an injected instruction slipped into an output is flagged too (prompt-injection shield). Placeholders
like [PHONE-1] are skipped.
"""

import re
from dataclasses import dataclass, field

from app.pipeline.factsheet import CVE_PATTERN, HASH_PATTERN, IP_PATTERN
from app.pipeline.trace import MONTHS, STOPWORDS, stem
from app.safety.scanner import EMAIL, PHONE

URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"'()\[\]]+")
PHONE_INTERNATIONAL = re.compile(r"(?<![\w+])\+\d{1,3}[ -]?\d(?:[ -]?\d){6,12}(?!\w)")
PLACEHOLDER = re.compile(r"\[[A-Z]+(?:-[A-Z]+)*-\d+\]")

NUMBER_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}  # "one" is left out: it is used too often in other senses ("one backup", "one of them")
MULTIPLIERS = {"thousand": 1e3, "lakh": 1e5, "lakhs": 1e5, "million": 1e6, "crore": 1e7, "crores": 1e7,
               "billion": 1e9}

_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_ORDINAL = r"(?:st|nd|rd|th)?"
DATE_PATTERNS = [
    # 22 September 2026, 22nd Sep
    re.compile(rf"\b(\d{{1,2}}){_ORDINAL}\s+(?:of\s+)?{_MONTH}\b\.?(?:,?\s+(\d{{4}}))?", re.IGNORECASE),
    # September 22, 2026
    re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}}){_ORDINAL}\b(?:,?\s+(\d{{4}}))?", re.IGNORECASE),
    # 2026-09-22
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    # 22/09/2026 or 22-09-2026 (day first, as written in India)
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"),
]
NUMBER = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)*)(?:st|nd|rd|th)?(?!\w)")
NUMBER_WORD = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)


@dataclass
class Value:
    kind: str                # number | date | cve | ip | hash | url | email | phone
    text: str                # as written, e.g. "1.2 million", "22 September 2026"
    start: int
    end: int
    keys: set[str] = field(default_factory=set)  # normalised forms used for comparing
    unit: str = ""           # number: stem of the word after it ("hospital"); date: ""
    unit_text: str = ""      # number: that word as written ("hospitals")
    year: str = ""           # date: the year, if written

    @property
    def label(self) -> str:
        return {"number": "Number", "date": "Date", "cve": "CVE id", "ip": "IP address", "hash": "File hash",
                "url": "Link", "email": "Email address", "phone": "Phone number"}[self.kind]


def find_values(text: str) -> list[Value]:
    """All hard values in `text`, in the order they appear. Codes first, so the digits inside a CVE
    id, IP address, hash or date are not also counted as numbers."""
    found: list[Value] = []
    taken: list[tuple[int, int]] = [(m.start(), m.end()) for m in PLACEHOLDER.finditer(text)]

    def free(start: int, end: int) -> bool:
        return all(end <= a or start >= b for a, b in taken)

    def add(value: Value) -> None:
        found.append(value)
        taken.append((value.start, value.end))

    for m in URL.finditer(text):
        link = m.group().rstrip(".,;:!?")
        add(Value("url", link, m.start(), m.start() + len(link), {_link_key(link)}))
    for m in EMAIL.finditer(text):
        if free(m.start(), m.end()):
            add(Value("email", m.group(), m.start(), m.end(), {m.group().lower()}))
    for pattern in (PHONE, PHONE_INTERNATIONAL):
        for m in pattern.finditer(text):
            if free(m.start(), m.end()):
                add(Value("phone", m.group(), m.start(), m.end(), {re.sub(r"\D", "", m.group())[-10:]}))

    for m in CVE_PATTERN.finditer(text):
        if not free(m.start(), m.end()):
            continue
        add(Value("cve", m.group(), m.start(), m.end(), {m.group().upper()}))
    for m in IP_PATTERN.finditer(text):
        if free(m.start(), m.end()):
            add(Value("ip", m.group(), m.start(), m.end(), {m.group().replace("[.]", ".")}))
    for m in HASH_PATTERN.finditer(text):
        if free(m.start(), m.end()) and not m.group().isdigit():
            add(Value("hash", m.group(), m.start(), m.end(), {m.group().lower()}))

    for pattern_number, pattern in enumerate(DATE_PATTERNS):
        for m in pattern.finditer(text):
            if not free(m.start(), m.end()):
                continue
            day, month, year = _date_parts(pattern_number, m.groups())
            if 1 <= day <= 31 and 1 <= month <= 12:
                add(Value("date", m.group().rstrip("."), m.start(), m.start() + len(m.group().rstrip(".")),
                          {f"{day}-{month}"}, year=year))

    for m in NUMBER.finditer(text):
        if free(m.start(1), m.end(1)):
            add(_number(text, m.group(1), m.start(1), m.end(1), m.end()))
    for m in NUMBER_WORD.finditer(text):
        if free(m.start(), m.end()):
            value = _number(text, str(NUMBER_WORDS[m.group().lower()]), m.start(), m.end(), m.end())
            value.text = m.group()
            add(value)

    return sorted(found, key=lambda v: v.start)


def _link_key(link: str) -> str:
    """https://www.Example.org/page/ -> example.org/page"""
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", link.lower()).rstrip("/")


def _date_parts(pattern_number: int, groups: tuple) -> tuple[int, int, str]:
    if pattern_number == 0:
        return int(groups[0]), MONTHS[groups[1].lower().rstrip(".")], groups[2] or ""
    if pattern_number == 1:
        return int(groups[1]), MONTHS[groups[0].lower().rstrip(".")], groups[2] or ""
    if pattern_number == 2:
        return int(groups[2]), int(groups[1]), groups[0]
    return int(groups[0]), int(groups[1]), groups[2]


def _number(text: str, digits: str, start: int, end: int, after: int) -> Value:
    """A number with the multiplier and the unit word that follow it: "1.2 million patient records"."""
    plain = digits.replace(",", "")
    try:
        amount = float(plain)
    except ValueError:  # e.g. "1.2.3" (a version number): compare as written
        return Value("number", digits, start, end, {plain})

    keys = {_clean(amount)}
    rest = text[after:]
    words = re.match(r"\s*(?:[+%]|-(?=\w))?\s*((?:[A-Za-z]+[\s-]*){0,3})", rest)
    following = [w.lower() for w in re.findall(r"[A-Za-z]+", words.group(1))] if words else []
    shown_end = end
    if following and following[0] in MULTIPLIERS:
        keys.add(_clean(amount * MULTIPLIERS[following[0]]))
        shown_end = after + rest.lower().index(following[0]) + len(following[0])
        following = following[1:]
    if rest.lstrip().startswith("%"):
        unit, unit_text = "percent", "%"
    else:
        unit_text = next((w for w in following if w not in STOPWORDS), "")
        unit = stem(unit_text) if unit_text else ""
    return Value("number", text[start:shown_end], start, shown_end, keys, unit=unit, unit_text=unit_text)


def _clean(amount: float) -> str:
    """1200000.0 -> "1200000", 1.2 -> "1.2" """
    return str(int(amount)) if amount == int(amount) else repr(round(amount, 6))


# ---- what is known (the fact sheet and the source) ---------------------------------------------


class KnownValues:
    """Every value found in the source text, for "is this in the source?"."""

    def __init__(self, texts: list[str]):
        self.keys: dict[str, set[str]] = {kind: set() for kind in
                                          ("number", "date", "cve", "ip", "hash", "url", "email", "phone")}
        for text in texts:
            for value in find_values(text):
                self.keys[value.kind] |= value.keys
                if value.year:
                    self.keys["number"].add(value.year)

    def missing(self, value: Value) -> bool:
        """True if this value does not appear anywhere in the source."""
        if not value.keys & self.keys[value.kind]:
            return True
        return bool(value.kind == "date" and value.year and value.year not in self.keys["number"])
