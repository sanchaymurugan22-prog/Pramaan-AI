"""The 23 languages of Pramaan AI: English and the 22 languages of the Eighth Schedule (Stage 8).

For each one: its name in English and in its own script, the script, the IndicTrans2 language tag
(FLORES-200 style, e.g. hin_Deva), whether it is written right to left, and the SMS length limit.

SMS: English fits the GSM-7 alphabet (160 characters in one SMS); any Indian script needs UCS-2,
which allows only 70 characters in one SMS.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str        # ISO 639 code used everywhere in the app ("hi", "ta", "kok" ...)
    name: str        # in English
    native: str      # in its own script, as shown in the language pickers
    script: str      # ISO 15924: Latn, Deva, Beng, Taml, Arab ...
    tag: str         # IndicTrans2 tag
    rtl: bool = False

    @property
    def sms_limit(self) -> int:
        return 160 if self.script == "Latn" else 70


LANGUAGES: dict[str, Language] = {lang.code: lang for lang in [
    Language("en", "English", "English", "Latn", "eng_Latn"),
    Language("hi", "Hindi", "हिन्दी", "Deva", "hin_Deva"),
    Language("bn", "Bengali", "বাংলা", "Beng", "ben_Beng"),
    Language("te", "Telugu", "తెలుగు", "Telu", "tel_Telu"),
    Language("mr", "Marathi", "मराठी", "Deva", "mar_Deva"),
    Language("ta", "Tamil", "தமிழ்", "Taml", "tam_Taml"),
    Language("ur", "Urdu", "اردو", "Arab", "urd_Arab", rtl=True),
    Language("gu", "Gujarati", "ગુજરાતી", "Gujr", "guj_Gujr"),
    Language("kn", "Kannada", "ಕನ್ನಡ", "Knda", "kan_Knda"),
    Language("or", "Odia", "ଓଡ଼ିଆ", "Orya", "ory_Orya"),
    Language("ml", "Malayalam", "മലയാളം", "Mlym", "mal_Mlym"),
    Language("pa", "Punjabi", "ਪੰਜਾਬੀ", "Guru", "pan_Guru"),
    Language("as", "Assamese", "অসমীয়া", "Beng", "asm_Beng"),
    Language("mai", "Maithili", "मैथिली", "Deva", "mai_Deva"),
    Language("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "Olck", "sat_Olck"),
    Language("ks", "Kashmiri", "کٲشُر", "Arab", "kas_Arab", rtl=True),
    Language("ne", "Nepali", "नेपाली", "Deva", "npi_Deva"),
    Language("sd", "Sindhi", "سنڌي", "Arab", "snd_Arab", rtl=True),
    Language("doi", "Dogri", "डोगरी", "Deva", "doi_Deva"),
    Language("kok", "Konkani", "कोंकणी", "Deva", "gom_Deva"),
    Language("mni", "Manipuri", "ꯃꯤꯇꯩꯂꯣꯟ", "Mtei", "mni_Mtei"),
    Language("brx", "Bodo", "बड़ो", "Deva", "brx_Deva"),
    Language("sa", "Sanskrit", "संस्कृतम्", "Deva", "san_Deva"),
]}

INDIAN = [code for code in LANGUAGES if code != "en"]


def get(code: str) -> Language:
    return LANGUAGES.get(code) or LANGUAGES["en"]


def label(code: str) -> str:
    """ "हिन्दी (Hindi)" for messages; just "English" for English."""
    lang = get(code)
    return lang.name if lang.code == "en" else f"{lang.native} ({lang.name})"


def sms_parts(text: str) -> int:
    """How many SMS messages a text needs (GSM-7: 160 / 153 per part; UCS-2: 70 / 67 per part)."""
    ucs2 = any(ord(c) > 0x7F for c in text)
    single, multi = (70, 67) if ucs2 else (160, 153)
    n = len(text)
    return 1 if n <= single else -(-n // multi)


# Unicode blocks of the scripts, to spot a word the translator wrote in the wrong script
_SCRIPT_RANGES = {
    "Deva": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)], "Beng": [(0x0980, 0x09FF)], "Guru": [(0x0A00, 0x0A7F)],
    "Gujr": [(0x0A80, 0x0AFF)], "Orya": [(0x0B00, 0x0B7F)], "Taml": [(0x0B80, 0x0BFF)], "Telu": [(0x0C00, 0x0C7F)],
    "Knda": [(0x0C80, 0x0CFF)], "Mlym": [(0x0D00, 0x0D7F)], "Olck": [(0x1C50, 0x1C7F)], "Mtei": [(0xABC0, 0xABFF)],
    "Arab": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
}


def script_of_letter(ch: str) -> str | None:
    if ch.isascii():
        return "Latn" if ch.isalpha() else None
    cp = ord(ch)
    return next((name for name, ranges in _SCRIPT_RANGES.items() if any(a <= cp <= b for a, b in ranges)), None)


def foreign_scripts(text: str, language: str) -> set[str]:
    """Scripts other than the language's own (and Latin, for names and codes) used for letters in `text`.
    Bengali and Assamese share one script; Santali may also be written with Latin letters."""
    import unicodedata
    own = get(language).script
    # letters and vowel signs only: the danda "।" is in the Devanagari block but Bengali, Odia and Punjabi use it
    found = {script_of_letter(c) for c in text if unicodedata.category(c)[0] in "LM"}
    return {s for s in found if s and s not in (own, "Latn")}

