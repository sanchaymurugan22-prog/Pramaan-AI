"""Text in Indian scripts, drawn correctly (Stage 8).

Indian scripts need "shaping": letters join into conjuncts (क + ् + ष = क्ष), vowel signs move before the
letter they follow in memory (ि), Arabic letters change shape by position, and Urdu is written right to left
while its numbers and English words go left to right. Pillow can only do this with the libraqm + FriBiDi
libraries (not on the Intel Macs we target, and Homebrew is not available), so it is done here:

  font runs   each character uses the first font of the chain that has it (Noto Sans Tamil for Tamil
              letters, Hind for "CVE-2026-12345"); spaces and marks stay with the run they are in
  direction   for right-to-left languages, runs of Arabic letters are right to left, Latin letters and
              numbers left to right; the line shows them in visual order (a simple form of the Unicode
              bidi rules, enough for a line of Urdu with numbers and codes in it)
  shaping     harfbuzz (uharfbuzz) turns each run into positioned glyphs
  drawing     FreeType (freetype-py) draws each glyph by its number into the Pillow image

ShapedDraw wraps a Pillow ImageDraw and offers the same text(), textlength() and textbbox() calls, so the
infographic code does not change. visual_words() orders the words of a right-to-left line for pdf.py.
"""

import threading
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import freetype
import numpy as np
import uharfbuzz as hb
from PIL import Image

# FreeType is NOT thread-safe: every face shares freetype-py's one global FT_Library, and freetype-py calls
# FreeType through ctypes, which lets other threads run at the same time. Two downloads drawing Indian text at
# once (or signing, which makes every file) used to crash the whole server (a segfault in FT_Load_Glyph while
# another thread was opening a face). So EVERY FreeType call - opening a face, reading its size, loading and
# drawing a glyph - happens while holding this one lock, and each face is opened exactly once.
_lock = threading.RLock()
_ft_faces: dict[tuple[str, int], freetype.Face] = {}


# ---- fonts ------------------------------------------------------------------------------------------

@cache
def _face_data(path: str) -> bytes:
    return Path(path).read_bytes()


@cache
def _hb_font(path: str) -> hb.Font:
    with _lock:  # made once, then only read (harfbuzz may shape with one font from several threads)
        face = hb.Face(hb.Blob(_face_data(path)))
        font = hb.Font(face)
        font.scale = (face.upem, face.upem)
        return font


@cache
def _coverage(path: str) -> frozenset[int]:
    with _lock:
        return frozenset(hb.Face(hb.Blob(_face_data(path))).unicodes)


def _ft_face(path: str, size: int) -> freetype.Face:
    """The FreeType face of a font at a size, opened once. Call it (and use the face) only while holding _lock."""
    key = (path, size)
    face = _ft_faces.get(key)
    if face is None:
        face = freetype.Face(path)
        face.set_char_size(size * 64)
        _ft_faces[key] = face  # kept for good: a face freed while another thread draws would crash too
    return face


# ---- runs and direction -------------------------------------------------------------------------------

_RTL_RANGES = ((0x0590, 0x08FF), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFF))


def _is_rtl(ch: str) -> bool:
    cp = ord(ch)
    return any(a <= cp <= b for a, b in _RTL_RANGES) and unicodedata.category(ch)[0] in "LM"


def _is_ltr(ch: str) -> bool:
    return ch.isascii() and ch.isalnum() or (unicodedata.category(ch) == "Nd" and not _is_rtl(ch))


def _is_neutral(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "ZPS" or ch in "\t"


def font_runs(text: str, chain: list[Path]) -> list[tuple[str, int]]:
    """[(piece of text, index of the font in the chain)], in logical order.

    Letters (and their vowel signs) use the first font that has them. Everything else (digits, brackets,
    dashes) uses the font of the nearest letter IN THE SAME WORD, so a word is never split between two fonts
    ("CVE-2026-12345" all in Hind, "(மாதிரி)" all in Noto Sans Tamil): ReportLab shapes a word in one font.
    Spaces stay with the run before them."""
    covers = [_coverage(str(p)) for p in chain]

    def first(cp: int) -> int:
        return next((i for i, c in enumerate(covers) if cp in c), 0)

    choice: list[int | None] = [first(ord(ch)) if unicodedata.category(ch)[0] in "LM" else None for ch in text]
    for i, ch in enumerate(text):
        if choice[i] is not None:
            continue
        if ch.isspace():
            choice[i] = choice[i - 1] if i and choice[i - 1] is not None else None
            continue
        near = None
        for j in range(i - 1, -1, -1):  # the nearest letter to the left, in this word
            if text[j].isspace():
                break
            if unicodedata.category(text[j])[0] in "LM":
                near = choice[j]
                break
        if near is None:
            for j in range(i + 1, len(text)):  # ... else to the right
                if text[j].isspace():
                    break
                if unicodedata.category(text[j])[0] in "LM":
                    near = choice[j]
                    break
        if near is None and i and choice[i - 1] is not None:
            near = choice[i - 1]
        choice[i] = near if near is not None and ord(ch) in covers[near] else first(ord(ch))
    for i in range(len(text)):  # spaces at the very start
        if choice[i] is None:
            choice[i] = next((c for c in choice[i:] if c is not None), 0)
    runs: list[list] = []
    for ch, index in zip(text, choice):
        if runs and runs[-1][1] == index:
            runs[-1][0] += ch
        else:
            runs.append([ch, index])
    return [(t, i) for t, i in runs]


def _directions(text: str, rtl: bool) -> list[bool]:
    """True = right to left, per character. Neutrals between two runs of the same direction take it; others
    take the paragraph's direction."""
    strong = [True if _is_rtl(c) else False if _is_ltr(c) else None for c in text]
    # Unicode bidi rules W4-W5: "#", "%", "+" next to a number, and "." "," ":" "/" between two digits, go with the
    # number ("#2", "42%", "203.0.113.45" stay together, left to right)
    for i, c in enumerate(text):
        before = text[i - 1] if i else ""
        after = text[i + 1] if i + 1 < len(text) else ""
        if (c in "#%+$₹" and (before.isdigit() or after.isdigit())) or (c in ".,:/" and before.isdigit() and after.isdigit()):
            strong[i] = False
    out = []
    for i, s in enumerate(strong):
        if s is not None:
            out.append(s)
            continue
        before = next((strong[j] for j in range(i - 1, -1, -1) if strong[j] is not None), rtl)
        after = next((strong[j] for j in range(i + 1, len(text)) if strong[j] is not None), rtl)
        out.append(before if before == after else rtl)
    return out


def visual_runs(text: str, chain: list[Path], rtl: bool) -> list[tuple[str, int, bool]]:
    """[(text, font index, right to left)] in the order they appear on the line, left to right."""
    if not rtl:
        return [(t, i, False) for t, i in font_runs(text, chain)]
    pieces: list[tuple[str, int, bool]] = []
    position = 0
    dirs = _directions(text, rtl)
    for run, index in font_runs(text, chain):
        start = position
        for k in range(len(run) + 1):  # split the font run where the direction changes
            if k == len(run) or (k > 0 and dirs[position + k] != dirs[position + k - 1]):
                piece = run[start - position : k]
                if piece:
                    pieces.append((piece, index, dirs[start]))
                start = position + k
        position += len(run)
    # right-to-left paragraph: the order of the groups is reversed; a group of left-to-right pieces keeps
    # its own order (an English phrase or a number reads left to right inside the Urdu line)
    groups: list[list] = []
    for piece in pieces:
        if groups and not piece[2] and not groups[-1][-1][2]:
            groups[-1].append(piece)
        else:
            groups.append([piece])
    return [piece for group in reversed(groups) for piece in group]


# ---- shaping and measuring --------------------------------------------------------------------------

@dataclass
class Glyph:
    font: int      # index in the chain
    gid: int       # glyph number in that font
    x: float       # pen position (in em units of 1000)
    dx: float
    dy: float


def shape(text: str, chain: list[Path], rtl: bool = False) -> tuple[list[Glyph], float]:
    """Glyphs with positions in thousandths of the font size, and the total width (same units)."""
    glyphs, pen = [], 0.0
    for piece, index, right_to_left in visual_runs(text, chain, rtl):
        font = _hb_font(str(chain[index]))
        scale = 1000 / font.face.upem
        buffer = hb.Buffer()
        buffer.add_str(piece)
        buffer.guess_segment_properties()
        buffer.direction = "rtl" if right_to_left else "ltr"
        hb.shape(font, buffer, {"kern": True, "liga": True})
        for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions):
            glyphs.append(Glyph(index, info.codepoint, pen, pos.x_offset * scale, pos.y_offset * scale))
            pen += pos.x_advance * scale
    return glyphs, pen


def measure(text: str, chain: list[Path], size: float, rtl: bool = False) -> float:
    """Width of one line in points (or pixels) at `size`."""
    return shape(text, chain, rtl)[1] * size / 1000


# ---- drawing into a Pillow image -----------------------------------------------------------------------

class ShapedFont:
    """A font "chain" at one size, for ShapedDraw (instead of a Pillow FreeTypeFont)."""

    def __init__(self, chain: list[Path], size: int, rtl: bool = False):
        self.chain, self.size, self.rtl = [Path(p) for p in chain], int(size), rtl
        with _lock:
            face = _ft_face(str(self.chain[0]), self.size)
            self.ascent = face.size.ascender / 64
            self.descent = -face.size.descender / 64

    def getlength(self, text: str) -> float:
        return measure(text, self.chain, self.size, self.rtl)


class ShapedDraw:
    """A Pillow ImageDraw whose text(), textlength() and textbbox() also accept a ShapedFont. Everything
    else (rectangles, circles, Pillow fonts) goes to the real ImageDraw."""

    def __init__(self, draw, image: Image.Image):
        self._draw, self._image = draw, image

    def __getattr__(self, name):
        return getattr(self._draw, name)

    def textlength(self, text, font=None, **kwargs):
        if isinstance(font, ShapedFont):
            return font.getlength(text)
        return self._draw.textlength(text, font=font, **kwargs)

    def _origin(self, xy, text, font: ShapedFont, anchor: str | None):
        anchor = anchor or "la"
        width = font.getlength(text)
        x, y = xy
        x -= {"l": 0, "m": width / 2, "r": width}.get(anchor[0], 0)
        baseline = y + {"a": font.ascent, "m": (font.ascent - font.descent) / 2, "s": 0,
                        "d": -font.descent, "t": font.ascent}.get(anchor[1], font.ascent)
        return x, baseline, width

    def textbbox(self, xy, text, font=None, anchor=None, **kwargs):
        if not isinstance(font, ShapedFont):
            return self._draw.textbbox(xy, text, font=font, anchor=anchor, **kwargs)
        x, baseline, width = self._origin(xy, text, font, anchor)
        return (round(x), round(baseline - font.ascent), round(x + width), round(baseline + font.descent))

    def text(self, xy, text, fill=None, font=None, anchor=None, **kwargs):
        if not isinstance(font, ShapedFont):
            return self._draw.text(xy, text, fill=fill, font=font, anchor=anchor, **kwargs)
        x0, baseline, _ = self._origin(xy, text, font, anchor)
        glyphs, _ = shape(text, font.chain, font.rtl)
        colour = fill if isinstance(fill, tuple) else (0, 0, 0)
        scale = font.size / 1000
        with _lock:
            for g in glyphs:
                face = _ft_face(str(font.chain[g.font]), font.size)
                face.load_glyph(g.gid, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_NO_BITMAP)
                face.glyph.render(freetype.FT_RENDER_MODE_NORMAL)
                bitmap = face.glyph.bitmap
                if bitmap.width == 0 or bitmap.rows == 0:
                    continue
                mask = Image.fromarray(np.array(bitmap.buffer, dtype=np.uint8).reshape(bitmap.rows, bitmap.pitch)[:, :bitmap.width], "L")
                left = round(x0 + (g.x + g.dx) * scale) + face.glyph.bitmap_left
                top = round(baseline - g.dy * scale) - face.glyph.bitmap_top
                self._image.paste(Image.new("RGB", mask.size, colour[:3]), (left, top), mask)


# ---- right to left, word by word (for pdf.py's RtlParagraph) ------------------------------------------------

def visual_words(words: list[str]) -> list[str]:
    """The words of one right-to-left line, in the order they appear from left to right: words with Urdu
    letters (and punctuation) right to left; a run of English words or numbers keeps its own order."""
    groups: list[list[str]] = []
    for word in words:
        ltr = not any(_is_rtl(c) for c in word) and any(_is_ltr(c) for c in word)
        if ltr and groups and groups[-1][0] == "ltr":
            groups[-1].append(word)
        else:
            groups.append(["ltr" if ltr else "rtl", word])
    return [word for group in reversed(groups) for word in group[1:]]
