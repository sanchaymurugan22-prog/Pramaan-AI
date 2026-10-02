"""Big numbers written with words: "1.2 million" = "12 लाख" = "12 লক্ষ" = 1,200,000 (v1.2).

Translations write big numbers the Indian way: IndicTrans2 turns "1.2 million" into "12 लाख" (12 lakh) in
Hindi, "12 லட்சம்" in Tamil, "12 لاکھ" in Urdu. That is the same value, but the translation check compared the
digits ("1.2" against "12") and said "Changed in translation". Now both sides are worked out first:

    amounts(text)  [(value, the words as written)] for every "number + scale word" and every number written
                   with group commas ("12,00,000", "1,200,000"), e.g. [(1200000, "12 लाख")]

The scale words are the ones IndicTrans2 writes (tried on 2 Oct 2026 in all 22 languages), plus English.
A wrong scale is still caught: "1.2 crore" for "1.2 million" is 12,000,000, not 1,200,000.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

THOUSAND, LAKH, MILLION, CRORE, BILLION = 10**3, 10**5, 10**6, 10**7, 10**9

# The beginning of each word (Indian languages add endings: "లక్షల", "ലക്ഷം", "लक्षरूप्यकाणि")
SCALE_WORDS: dict[str, int] = {
    # English
    "thousand": THOUSAND, "lakh": LAKH, "lac": LAKH, "million": MILLION, "mn": MILLION, "crore": CRORE,
    "cr": CRORE, "billion": BILLION, "bn": BILLION,
    # Devanagari: Hindi, Marathi, Nepali, Maithili, Dogri, Konkani, Bodo, Sanskrit
    "हजार": THOUSAND, "हज़ार": THOUSAND, "सहस्र": THOUSAND, "रोजा": THOUSAND,
    "लाख": LAKH, "लक्ष": LAKH, "लक्ख": LAKH,
    "मिलियन": MILLION, "दशलक्ष": MILLION,
    "करोड़": CRORE, "करोड": CRORE, "कोटि": CRORE, "कोटी": CRORE, "कौटि": CRORE,
    "अरब": BILLION, "अब्ज": BILLION, "बिलियन": BILLION,
    # Bengali, Assamese
    "হাজার": THOUSAND, "হাজাৰ": THOUSAND, "লাখ": LAKH, "লক্ষ": LAKH, "মিলিয়ন": MILLION, "দশলক্ষ": MILLION,
    "কোটি": CRORE, "বিলিয়ন": BILLION,
    # Tamil
    "ஆயிரம்": THOUSAND, "லட்சம்": LAKH, "மில்லியன்": MILLION, "கோடி": CRORE, "பில்லியன்": BILLION,
    # Telugu
    "వేల": THOUSAND, "వేయి": THOUSAND, "లక్ష": LAKH, "మిలియన్": MILLION, "కోటి": CRORE, "కోట్ల": CRORE,
    "బిలియన్": BILLION,
    # Kannada
    "ಸಾವಿರ": THOUSAND, "ಲಕ್ಷ": LAKH, "ಮಿಲಿಯನ್": MILLION, "ಕೋಟಿ": CRORE, "ಬಿಲಿಯನ್": BILLION,
    # Malayalam
    "ആയിരം": THOUSAND, "ലക്ഷ": LAKH, "മില്യൺ": MILLION, "ദശലക്ഷ": MILLION, "കോടി": CRORE, "ബില്യൺ": BILLION,
    # Gujarati
    "હજાર": THOUSAND, "લાખ": LAKH, "મિલિયન": MILLION, "કરોડ": CRORE, "અબજ": BILLION, "બિલિયન": BILLION,
    # Punjabi (ੜ is also written ਡ਼)
    "ਹਜ਼ਾਰ": THOUSAND, "ਹਜਾਰ": THOUSAND, "ਲੱਖ": LAKH, "ਮਿਲੀਅਨ": MILLION, "ਕਰੋੜ": CRORE, "ਕਰੋਡ਼": CRORE,
    "ਬਿਲੀਅਨ": BILLION,
    # Odia (ୟ is also written ଯ଼)
    "ହଜାର": THOUSAND, "ଲକ୍ଷ": LAKH, "ମିଲିୟନ": MILLION, "ମିଲିଯ଼ନ": MILLION, "କୋଟି": CRORE,
    "ବିଲିୟନ": BILLION, "ବିଲିଯ଼ନ": BILLION,
    # Urdu, Kashmiri, Sindhi
    "ہزار": THOUSAND, "لاکھ": LAKH, "لک": LAKH, "ملین": MILLION, "کروڑ": CRORE, "ڪروڙ": CRORE,
    "ارب": BILLION, "بلین": BILLION,
    # Santali (Ol Chiki)
    "ᱦᱟᱡᱟᱨ": THOUSAND, "ᱞᱚᱠᱠᱷ": LAKH, "ᱠᱳᱴᱤ": CRORE,
}
# Manipuri (Meetei Mayek) puts the word BEFORE the number: "ꯂꯥꯈ 12" = 12 lakh
WORD_FIRST: dict[str, int] = {"ꯂꯥꯈ": LAKH, "ꯀꯔꯣꯔ": CRORE, "ꯃꯤꯂꯤꯌꯟ": MILLION, "ꯕꯤꯂꯤꯌꯟ": BILLION}

_ENGLISH = {w for w in SCALE_WORDS if w.isascii()}
_SCALE = {unicodedata.normalize("NFC", w).lower(): v for w, v in SCALE_WORDS.items()}
_NUMBER = r"(?<![\d.,])(\d+(?:[.,]\d+)*)"


def _words(words) -> str:
    return "|".join(re.escape(unicodedata.normalize("NFC", w)) for w in sorted(words, key=len, reverse=True))


# "1.2 million", "12 लाख", "35 करोड़", "12-lakh"; English words must be whole words ("mn", not "mni...")
_AFTER = re.compile(rf"{_NUMBER}[  -]?(?:(?P<en>{_words(_ENGLISH)})\b|(?P<indic>{_words(set(SCALE_WORDS) - _ENGLISH)}))",
                    re.IGNORECASE)
_BEFORE = re.compile(rf"(?P<word>{_words(WORD_FIRST)})\s?{_NUMBER}")
# 1,200,000 and 12,00,000 (Indian grouping): the same number without the commas
_GROUPED = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{2,3})+(?![\d,]|\.\d)")


def _value(digits: str, scale: int = 1) -> int | Decimal | None:
    try:
        value = Decimal(digits.replace(",", "")) * scale
    except InvalidOperation:
        return None
    return int(value) if value == value.to_integral_value() else value.normalize()


def amounts(text: str) -> list[tuple[int | Decimal, str, tuple[int, int]]]:
    """[(value, text as written, (start, end))] for each big number written with a word or group commas. The
    positions are in the NFC form of the text (unicodedata.normalize("NFC", text))."""
    text = unicodedata.normalize("NFC", text or "")
    found: list[tuple[int | Decimal, str, tuple[int, int]]] = []
    for match in _AFTER.finditer(text):
        value = _value(match.group(1), _SCALE[(match.group("en") or match.group("indic")).lower()])
        if value is not None:
            found.append((value, match.group(0), match.span()))
    for match in _BEFORE.finditer(text):
        value = _value(match.group(2), WORD_FIRST[match.group("word")])
        if value is not None:
            found.append((value, match.group(0), match.span()))
    taken = [span for _, _, span in found]
    for match in _GROUPED.finditer(text):
        if not any(a <= match.start() < b for a, b in taken):
            found.append((_value(match.group(0)), match.group(0), match.span()))
    return sorted(found, key=lambda f: f[2])
