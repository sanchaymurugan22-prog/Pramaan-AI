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
