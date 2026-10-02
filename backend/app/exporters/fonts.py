"""Which font file to use, per language and role. All fonts are OFL-licensed TTF files bundled in
backend/app/assets/fonts, so exports look the same with no internet.

Roles: "heading" (Poppins), "body" (Hind), "mono" (IBM Plex Mono, for hashes and addresses).

Stage 8 (Indian languages): every script has its own Noto font (Noto Sans Bengali, Tamil, Telugu, Kannada,
Malayalam, Gujarati, Gurmukhi, Oriya, Ol Chiki, Meetei Mayek, and Noto Naskh Arabic for Urdu, Kashmiri and
Sindhi). Those fonts have no Latin letters, so a line of Tamil that says "CVE-2026-12345" or "Microsoft" uses
the script font for the Tamil letters and the English font (Hind / Poppins) for the rest: font_chain()
gives both, in that order. Hindi, Marathi, Nepali and the other Devanagari languages use Hind and Poppins
themselves (both have Devanagari), with Noto Sans Devanagari behind them for rare letters.

PDF and PNG files carry the fonts inside them (and are shaped with harfbuzz, see shaped.py). DOCX and PPTX
files only name the fonts: Latin text uses Hind / Poppins, Indian scripts the Noto font ("complex script"
font). The computer that opens them needs those fonts installed (double-click each .ttf file in
assets/fonts on a Mac); otherwise Word / Keynote uses a similar font of the same script.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import ImageFont

from app.lang import languages

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


@dataclass(frozen=True)
class FontSet:
    family: str                 # the name Word / PowerPoint / Keynote know the font by
    files: dict[str, str]       # weight -> file name in FONT_DIR ("regular", "medium", "semibold", "bold")


POPPINS = FontSet("Poppins", {"regular": "Poppins-Regular.ttf", "medium": "Poppins-Medium.ttf",
                              "semibold": "Poppins-SemiBold.ttf", "bold": "Poppins-Bold.ttf"})
HIND = FontSet("Hind", {"regular": "Hind-Regular.ttf", "medium": "Hind-Medium.ttf",
                        "semibold": "Hind-SemiBold.ttf", "bold": "Hind-Bold.ttf"})
PLEX = FontSet("IBM Plex Mono", {"regular": "IBMPlexMono-Regular.ttf"})
LATIN = {"heading": POPPINS, "body": HIND, "mono": PLEX}


def _noto(family: str, stem: str) -> FontSet:
    """A Noto font with Regular and Bold (medium = regular, semibold = bold)."""
    regular, bold = f"{stem}-Regular.ttf", f"{stem}-Bold.ttf"
    return FontSet(family, {"regular": regular, "medium": regular, "semibold": bold, "bold": bold})


SCRIPT_FONTS: dict[str, FontSet] = {
    "Deva": _noto("Noto Sans Devanagari", "NotoSansDevanagari"),
    "Beng": _noto("Noto Sans Bengali", "NotoSansBengali"),
    "Taml": _noto("Noto Sans Tamil", "NotoSansTamil"),
    "Telu": _noto("Noto Sans Telugu", "NotoSansTelugu"),
    "Knda": _noto("Noto Sans Kannada", "NotoSansKannada"),
    "Mlym": _noto("Noto Sans Malayalam", "NotoSansMalayalam"),
    "Gujr": _noto("Noto Sans Gujarati", "NotoSansGujarati"),
    "Guru": _noto("Noto Sans Gurmukhi", "NotoSansGurmukhi"),
    "Orya": _noto("Noto Sans Oriya", "NotoSansOriya"),
    "Olck": _noto("Noto Sans Ol Chiki", "NotoSansOlChiki"),
    "Mtei": _noto("Noto Sans Meetei Mayek", "NotoSansMeeteiMayek"),
    "Arab": _noto("Noto Naskh Arabic", "NotoNaskhArabic"),
}


def script_of(language: str) -> str:
    return languages.get(language).script


def font_set(role: str, language: str = "en") -> FontSet:
    """The MAIN font of a role in a language: the script's Noto font, or Poppins / Hind for English and the
    Devanagari languages. Codes and hashes (mono) are always IBM Plex Mono."""
    script = script_of(language)
    if role == "mono" or script in ("Latn", "Deva"):
        return LATIN[role]
    return SCRIPT_FONTS[script]


def family(role: str, language: str = "en") -> str:
    """Font name for the Indian script in DOCX / PPTX (the "complex script" font), e.g. "Noto Sans Tamil"."""
    return font_set(role, language).family


def latin_family(role: str) -> str:
    """Font name for Latin letters and digits in DOCX / PPTX: "Poppins", "Hind" or "IBM Plex Mono"."""
    return LATIN[role].family


def _path(fonts: FontSet, weight: str) -> Path:
    return FONT_DIR / fonts.files.get(weight, fonts.files["regular"])


def font_file(role: str, weight: str = "regular", language: str = "en") -> Path:
    """Path of the main TTF file; falls back to the regular weight if that weight is not bundled."""
    return _path(font_set(role, language), weight)


def font_chain(role: str, weight: str = "regular", language: str = "en") -> list[Path]:
    """The main font, then the fonts for whatever it lacks: Latin letters and digits for a script font; the
    Noto Devanagari font behind Hind / Poppins for Devanagari languages."""
    main = font_set(role, language)
    chain = [_path(main, weight)]
    if main is not LATIN.get(role):
        chain.append(_path(LATIN[role], weight))
    elif script_of(language) == "Deva" and role != "mono":
        chain.append(_path(SCRIPT_FONTS["Deva"], weight))
    return chain


def needs_shaping(language: str) -> bool:
    """Indian scripts need harfbuzz shaping (conjuncts, vowel signs, joined Arabic letters)."""
    return script_of(language) != "Latn"


@cache
def _measuring_font(role: str, weight: str, language: str):
    return ImageFont.truetype(str(font_file(role, weight, language)), size=1000)


def text_width(text: str, size: float, role: str = "body", weight: str = "regular", language: str = "en") -> float:
    """Width of one line of text in points, measured with the bundled fonts (for DOCX / PPTX, which cannot
    measure text themselves). Indian scripts are shaped first, with the Latin fallback (shaped.py)."""
    if needs_shaping(language):
        from app.exporters.shaped import measure
        return measure(text, font_chain(role, weight, language), size)
    return _measuring_font(role, weight, language).getlength(text) * size / 1000
