"""Which font file to use, per language and role. All fonts are OFL-licensed TTF files bundled in
backend/app/assets/fonts, so exports look the same with no internet.

Roles: "heading" (Poppins), "body" (Hind), "mono" (IBM Plex Mono, for hashes and addresses).

Stage 8 (Indian languages): add an entry to FONT_SETS, e.g.
    "ta": {"heading": FontSet("Noto Sans Tamil", {"regular": "NotoSansTamil-Regular.ttf", ...}), ...}
and put the TTF files in assets/fonts. Languages without an entry use English ("en").

PDF and PNG files carry the font inside them. DOCX and PPTX files only name the font: the
computer that opens them needs Poppins and Hind installed (double-click each .ttf file in
assets/fonts to install it on a Mac), otherwise Word / Keynote shows a similar font.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import ImageFont

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


@dataclass(frozen=True)
class FontSet:
    family: str                 # the name Word / PowerPoint / Keynote know the font by
    files: dict[str, str]       # weight -> file name in FONT_DIR ("regular", "medium", "semibold", "bold")


FONT_SETS: dict[str, dict[str, FontSet]] = {
    "en": {
        "heading": FontSet("Poppins", {
            "regular": "Poppins-Regular.ttf", "medium": "Poppins-Medium.ttf",
            "semibold": "Poppins-SemiBold.ttf", "bold": "Poppins-Bold.ttf",
        }),
        "body": FontSet("Hind", {
            "regular": "Hind-Regular.ttf", "medium": "Hind-Medium.ttf",
            "semibold": "Hind-SemiBold.ttf", "bold": "Hind-Bold.ttf",
        }),
        "mono": FontSet("IBM Plex Mono", {"regular": "IBMPlexMono-Regular.ttf"}),
    },
}


def font_set(role: str, language: str = "en") -> FontSet:
    return FONT_SETS.get(language, FONT_SETS["en"])[role]


def family(role: str, language: str = "en") -> str:
    """Font name for DOCX / PPTX, e.g. family("heading") -> "Poppins"."""
    return font_set(role, language).family


def font_file(role: str, weight: str = "regular", language: str = "en") -> Path:
    """Path of the TTF file; falls back to the regular weight if that weight is not bundled."""
    files = font_set(role, language).files
    return FONT_DIR / files.get(weight, files["regular"])


@cache
def _measuring_font(role: str, weight: str, language: str):
    return ImageFont.truetype(str(font_file(role, weight, language)), size=1000)


def text_width(text: str, size: float, role: str = "body", weight: str = "regular", language: str = "en") -> float:
    """Width of one line of text in points, measured with the bundled font (for DOCX / PPTX, which cannot
    measure text themselves)."""
    return _measuring_font(role, weight, language).getlength(text) * size / 1000

