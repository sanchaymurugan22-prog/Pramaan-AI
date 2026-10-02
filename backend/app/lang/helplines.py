"""Helpline and phone numbers in translations (v1.2).

"Report cyber fraud on 1930" was translated as "Report cyber fraud in (the year) 1930" in Hindi, Bengali,
Tamil and most other languages: on its own, a four-digit number after "on" reads like a year. Tried with
IndicTrans2 in all 22 languages: with the words "helpline number" in front, every language kept it a phone
number ("हेल्प लाइन नंबर 1930 पर", "1930 নম্বরের হেল্পলাইনে", "ஹெல்ப்லைன் எண் 1930").

clarify()        before translating: a helpline number without such a word gets one ("on 1930" -> "on
                 helpline number 1930", "Call 1930" -> "Call helpline number 1930"). The number itself is
                 never changed, so the value checks still find it.
numbers()        the helpline / phone numbers of an English text (for the check).
read_as_phone()  after translating: the number must stand next to a word for helpline, number, call or phone
                 in the translation's script (words seen in IndicTrans2's translations). If not, it may
                 have become a year or a date, and the check flags it for the Reviewer.
"""

import re

# Indian helplines that are often written alone ("call 112"): cyber fraud, emergency, police, fire,
# ambulance, child, women, senior citizens, the old cyber fraud number
KNOWN = ("1930", "112", "100", "101", "102", "108", "1098", "181", "1091", "14567", "155260")
_KNOWN = "|".join(sorted(KNOWN, key=len, reverse=True))
_TOLL_FREE = r"1800[- ]?\d{2,4}[- ]?\d{3,4}"

# words that already say "this is a phone number" (English)
_PHONE_WORD = r"(?:help\s?line|hotline|toll[- ]free|number|no\.|phone|telephone|mobile|whatsapp)"
# a number after these is a phone number, whatever it is
_CALL = r"(?:call|dial|ring|phone|telephone|sms|text|whatsapp|contact)"
# ... after these, only a known helpline is (and only if no noun follows: "on 100 servers" is not a helpline)
_PREPOSITION = r"(?:on|at|to|via|through|or|and)"
_AFTER_OK = r"(?=\s*(?:$|[^\w\s]|(?:or|and|in|within|to|for|if|immediately|now|right|as|at|from|toll|helpline|"\
            r"free|24|day|days|any)\b))"

_ALREADY = re.compile(rf"\b{_PHONE_WORD}\s*(?:[:\-]\s*)?(?:is\s+)?(?P<number>{_TOLL_FREE}|\d{{3,6}})\b", re.I)
_AFTER_CALL = re.compile(rf"\b(?P<verb>{_CALL})(?:\s+(?:the|us|on|at))?\s+(?P<number>{_TOLL_FREE}|\d{{3,6}})\b", re.I)
_AFTER_PREPOSITION = re.compile(rf"\b{_PREPOSITION}\s+(?P<number>{_KNOWN}|{_TOLL_FREE})\b{_AFTER_OK}", re.I)
_BEFORE_HELPLINE = re.compile(rf"\b(?P<number>{_KNOWN}|{_TOLL_FREE})\s+{_PHONE_WORD}", re.I)


def _spans(text: str) -> list[tuple[int, int, bool]]:
    """(start, end, already has a phone word) of every helpline number in an English text."""
    found: dict[int, tuple[int, int, bool]] = {}
    for pattern, named in ((_ALREADY, True), (_BEFORE_HELPLINE, True), (_AFTER_CALL, False), (_AFTER_PREPOSITION, False)):
        for match in pattern.finditer(text):
            start, end = match.span("number")
            if start not in found or named:
                found[start] = (start, end, named or found.get(start, (0, 0, False))[2])
    return sorted(found.values())


def numbers(text: str) -> list[str]:
    """The helpline / phone numbers of an English text, e.g. ["1930", "112"]."""
    return list(dict.fromkeys(text[start:end] for start, end, _ in _spans(text or "")))


def clarify(text: str) -> str:
    """The English text with "helpline number" in front of each helpline number that has no such word."""
    for start, _, named in reversed(_spans(text)):
        if not named:
            text = text[:start] + "helpline number " + text[start:]
    return text


# "helpline", "number", "call", "phone" as IndicTrans2 writes them, per script (any form of the word: these
# are the beginnings). English is there too: the AI model sometimes keeps "helpline" in Latin letters.
PHONE_WORDS = (
    "helpline", "help line", "hotline", "number", "call", "phone", "dial", "toll",
    # Devanagari (Hindi, Marathi, Nepali, Maithili, Dogri, Konkani, Bodo, Sanskrit)
    "हेल्प", "हैलप", "हेल्प्लैन", "नंबर", "नम्बर", "क्रमांक", "सङ्ख्या", "संख्या", "सहायिका", "कॉल", "काल", "फोन",
    "फ़ोन", "दूरभाष", "सम्पर्क", "संपर्क",
    "হেল্প", "নম্বর", "নম্বৰ", "কল", "ফোন",             # Bengali, Assamese
    "హెల్ప్", "నంబర్", "కాల్", "ఫోన్",                   # Telugu
    "ஹெல்ப்", "எண்", "அழை", "தொலைபேசி", "போன்",         # Tamil
    "હેલ્પ", "નંબર", "કૉલ", "કોલ", "ફોન",                 # Gujarati
    "ಸಹಾಯವಾಣಿ", "ಹೆಲ್ಪ್", "ಸಂಖ್ಯೆ", "ಕರೆ", "ಫೋನ್",        # Kannada
    "ହେଲ୍ପ", "ନମ୍ବର", "କଲ୍", "ଫୋନ୍",                     # Odia
    "ഹെൽപ്പ്", "ഹെൽപ്", "നമ്പ", "വിളി", "ഫോൺ",          # Malayalam
    "ਹੈਲਪ", "ਨੰਬਰ", "ਕਾਲ", "ਫ਼ੋਨ", "ਫੋਨ",                 # Punjabi
    "ہیلپ", "نمبر", "کال", "ڪال", "فون",                 # Urdu, Kashmiri, Sindhi
    "ᱦᱮᱞᱯ", "ᱯᱞᱟᱭᱤᱱ", "ᱱᱚᱢᱵᱚᱨ", "ᱱᱟᱢᱵᱟᱨ", "ᱯᱷᱳᱱ",          # Santali (Ol Chiki)
    "ꯍꯦꯜꯞ", "ꯂꯥꯏꯟ", "ꯅꯝꯕꯔ", "ꯐꯣꯟ",                        # Manipuri (Meetei Mayek)
)
_NEAR = 20  # characters on each side: "हेल्प लाइन नंबर 1930 पर", "1930 എന്ന ഹെൽപ്പ് ലൈൻ നമ്പറിൽ"

# "year" (and "in the year") right next to the number: wrong even if a phone word is near ("1930 तमे वर्षे काल्
# करोतु" is Sanskrit for "call in the year 1930")
YEAR_WORDS = (
    "year", "वर्ष", "साल", "सन्", "सन ", "मायथाइ",           # Devanagari (मायथाइ: Bodo)
    "সাল", "বছর", "চন",                      # Bengali, Assamese
    "సంవత్సర", "ஆண்டு", "ವರ್ಷ", "ಇಸವಿ", "വർഷ", "વર્ષ", "સાલ", "ਸਾਲ", "ਸੰਨ", "ମସିହା", "ବର୍ଷ",
    "سال", "سنہ",                             # Urdu, Kashmiri, Sindhi
    "ꯆꯍꯤ", "ꯏꯪ ",                             # Manipuri
)
_YEAR_NEAR = 12


def read_as_phone(number: str, translated: str) -> bool:
    """True if the number appears in the translation next to a helpline / number / call / phone word (and no
    word for "year"). False if it stands alone or beside "year": it may now be a year or a date. A number
    missing altogether is reported by the value check, not here."""
    lowered = translated.lower()
    for match in re.finditer(rf"(?<!\d){re.escape(number)}(?!\d)", lowered):
        window = lowered[max(0, match.start() - _NEAR): match.end() + _NEAR]
        close = lowered[max(0, match.start() - _YEAR_NEAR): match.end() + _YEAR_NEAR]
        if any(word in window for word in PHONE_WORDS) and not any(word in close for word in YEAR_WORDS):
            return True
    return False


def not_read_as_phone(english: str, translated: str) -> list[str]:
    """The helpline numbers of the English that the translation may have turned into a year or a date."""
    return [n for n in numbers(english) if n in translated and not read_as_phone(n, translated)]
