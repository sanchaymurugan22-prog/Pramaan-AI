"""A small addition to ReportLab for Indian scripts (Stage 8). Imported by pdf.py before anything else.

Words in two fonts. A line of Tamil uses Noto Sans Tamil for the Tamil letters and Hind for "CVE-2026" (the
Noto fonts have no Latin letters). ReportLab shapes a whole word with the FIRST font of the word and then uses
those glyph numbers in the other fonts too, which prints wrong letters or empty boxes in a word like "42টি" or
"(نمونہ)". The replacement below shapes each font's piece of such a word on its own (and, in a word with Urdu
letters, puts the pieces right to left and mirrors a bracket).

Right-to-left paragraphs are wrapped and ordered by pdf.py itself (RtlParagraph); ReportLab only draws lines.
"""

from reportlab.pdfbase import pdfmetrics, ttfonts
from reportlab.platypus import paragraph

from app.exporters.shaped import _is_rtl

_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")

_shape_one_font = ttfonts.shapeFragWord


def shape_each_font(word, features=dict(kern=True, liga=True, dlig=True), force=False):
    """ReportLab's shapeFragWord, but a word in several fonts is shaped one font at a time."""
    if isinstance(word, ttfonts.ShapedFragWord) or len(word) < 3:
        return _shape_one_font(word, features, force)
    frags = word[1:]
    if any(hasattr(f, "cbDefn") for f, _ in frags) or len({f.fontName for f, _ in frags}) == 1:
        return _shape_one_font(word, features, force)
    # A word with Urdu letters reads right to left: its pieces go in the opposite order, and a bracket on
    # its own is mirrored ("(" at the start of the word is drawn as ")" on its right).
    rtl = any(_is_rtl(c) for _, text in frags for c in text)
    pieces, total = [], 0.0
    for frag, text in (reversed(frags) if rtl else frags):
        if rtl and not any(_is_rtl(c) or c.isalnum() for c in text):
            text = text[::-1].translate(_MIRROR)
        single = word.__class__([pdfmetrics.stringWidth(text, frag.fontName, frag.fontSize), (frag, text)])
        shaped = _shape_one_font(single, features, True)
        total += shaped[0]
        pieces.extend(shaped[1:])
    new = ttfonts.makeShapedFragWord(word)(pieces)
    new.insert(0, total)
    return new


if getattr(ttfonts, "uharfbuzz", None) is not None and ttfonts.shapeFragWord is not shape_each_font:
    ttfonts.shapeFragWord = shape_each_font
    paragraph.shapeFragWord = shape_each_font
