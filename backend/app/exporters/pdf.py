"""PDF files with ReportLab: advisory and executive summary.

Same layout as the Word file (see docx.py): tricolour strip and TLP label at the top of every
page, a top block with the title, job details and an empty QR code box, the sections from
blocks.py, and the footer "AI-assisted · pending human approval" with the page number.
The fonts are embedded in the PDF, so it looks the same on every computer.
"""

import io
from functools import cache
from pathlib import Path
from xml.sax.saxutils import escape

from app.exporters import reportlab_setup  # noqa: F401, I001  (first: words in two fonts, see there)
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.exporters.blocks import Block, document_blocks
from app.exporters.common import PALETTE, TLP_TEXT_COLOURS, ExportInfo, fit_title
from app.exporters.fonts import font_chain, needs_shaping
from app.exporters.shaped import font_runs, visual_runs, visual_words
from app.lang import languages

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN - 12  # the page frame keeps 6 points of padding on each side
QR_BOX = 30 * mm


def write_pdf(info: ExportInfo, content: dict, path: Path) -> Path:
    fonts = _register_fonts(info.language)
    styles = _styles(fonts, info.language)
    blocks = document_blocks(info.output_type, content, info.language)
    title = next((b.text for b in blocks if b.kind == "title"), info.output_label)
    subtitle_block = next((b for b in blocks if b.kind == "subtitle"), None)
    subtitle = subtitle_block.text if subtitle_block else ""
    severe = bool(subtitle_block and subtitle_block.label in ("high", "critical"))

    story = [_top_block(info, title, subtitle, severe, styles, fonts), Spacer(1, 6 * mm)]
    for block in blocks:
        if block.kind not in ("title", "subtitle"):
            story += _flowables(block, styles, fonts)

    def decorate(canvas, doc):
        _page_decoration(canvas, doc, info, fonts)

    document = SimpleDocTemplate(
        str(path) if isinstance(path, Path) else path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=22 * mm, bottomMargin=20 * mm,
        title=title, author=info.office_name, subject=info.job_title, creator="Pramaan AI", keywords=info.footer,
    )
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return path


# ---- fonts and styles ---------------------------------------------------------------------


@cache
def _register_fonts(language: str) -> dict[str, str]:
    """Register the bundled TTF fonts with ReportLab once; returns role -> registered font name.
    Stage 8: each role is a chain (the script's font, then the Latin one); "<role>/1" is the second font,
    used for Latin letters and digits in a line of Tamil (see _p)."""
    wanted = {
        "heading": ("heading", "semibold"), "heading_bold": ("heading", "bold"),
        "body": ("body", "regular"), "body_bold": ("body", "semibold"), "mono": ("mono", "regular"),
    }
    names = {}
    for key, (role, weight) in wanted.items():
        for index, path in enumerate(font_chain(role, weight, language)):
            name = f"{language}-{key}" + (f"/{index}" if index else "")
            pdfmetrics.registerFont(TTFont(name, str(path)))
            names[key + (f"/{index}" if index else "")] = name
            _CHAINS.setdefault(f"{language}-{key}", []).append((name, path))
    # lets <b> inside body text switch to the bold body font
    pdfmetrics.registerFontFamily(names["body"], normal=names["body"], bold=names["body_bold"],
                                  italic=names["body"], boldItalic=names["body_bold"])
    names["language"] = language
    return names


# registered main font name -> [(registered name, file)] of its chain (Stage 8)
_CHAINS: dict[str, list[tuple[str, Path]]] = {}


def _colour(name: str) -> HexColor:
    return HexColor("#" + PALETTE.get(name, name))


def _styles(fonts: dict[str, str], language: str = "en") -> dict[str, ParagraphStyle]:
    body = ParagraphStyle("body", fontName=fonts["body"], fontSize=10.5, leading=15, textColor=_colour("ink"), spaceAfter=5)
    if needs_shaping(language):  # Stage 8: harfbuzz shaping for Indian scripts; right to left for Urdu
        body.shaping = 1
        if languages.get(language).rtl:
            body.alignment = TA_RIGHT
            body.rtl = True  # _p makes an RtlParagraph
    return {
        "body": body,
        "eyebrow": ParagraphStyle("eyebrow", parent=body, fontName=fonts["heading"], fontSize=8.5, leading=11,
                                  textColor=_colour("saffron_dark"), spaceAfter=3),
        "title": ParagraphStyle("title", parent=body, fontName=fonts["heading_bold"], fontSize=20, leading=24,
                                textColor=_colour("navy"), spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=body, fontName=fonts["body_bold"], fontSize=11, leading=14,
                                   textColor=_colour("muted"), spaceAfter=2),
        "meta": ParagraphStyle("meta", parent=body, fontSize=9.5, leading=13, textColor=_colour("muted"), spaceAfter=0),
        "heading": ParagraphStyle("heading", parent=body, fontName=fonts["heading"], fontSize=12.5, leading=16,
                                  textColor=_colour("navy"), spaceBefore=9, spaceAfter=4),
        "item": ParagraphStyle("item", parent=body, leftIndent=16, bulletIndent=0, bulletFontName=fonts["heading"],
                               bulletColor=_colour("saffron_dark"), spaceAfter=4),
        "callout_label": ParagraphStyle("callout_label", parent=body, fontName=fonts["heading"], fontSize=8.5, leading=11,
                                        textColor=_colour("saffron_dark"), spaceAfter=2),
        "callout": ParagraphStyle("callout", parent=body, fontSize=11.5, leading=16, spaceAfter=0),
        "cell": ParagraphStyle("cell", parent=body, fontSize=9.5, leading=12.5, spaceAfter=0),
        "cell_small": ParagraphStyle("cell_small", parent=body, fontSize=8.5, leading=11, spaceAfter=0),
        "cell_head": ParagraphStyle("cell_head", parent=body, fontName=fonts["heading"], fontSize=8.5, leading=11,
                                    textColor=_colour("navy"), spaceAfter=0),
        "cell_mono": ParagraphStyle("cell_mono", parent=body, fontName=fonts["mono"], fontSize=8.5, leading=11, spaceAfter=0),
    }


def _p(text: str, style: ParagraphStyle, **kwargs) -> Paragraph:
    """A paragraph of plain text (escaped, so '<' or '&' in the text are shown, not read as markup).
    Stage 8: in an Indian language, each piece of the text uses the font of its chain that has its letters;
    right-to-left languages get an RtlParagraph."""
    if getattr(style, "rtl", False):
        return RtlParagraph(text, style)
    return Paragraph(_markup(text, style.fontName), style, **kwargs)


class RtlParagraph(Flowable):
    """A right-to-left paragraph (Urdu, Kashmiri, Sindhi), wrapped HERE: the words are measured (shaped),
    split into lines that fit, and each line is put in visual order (visual_words). ReportLab then only draws
    each finished line, right-aligned, as a one-line paragraph (each word shaped by harfbuzz)."""

    def __init__(self, text: str, style: ParagraphStyle, lines: list[list[str]] | None = None):
        super().__init__()
        self.text, self.style, self._fixed = text, style, lines
        self._lines: list[Paragraph] = []

    def _wrap_words(self, width: float) -> list[list[str]]:
        space = _width(" ", self.style.fontName, self.style.fontSize)
        lines, current, used = [], [], 0.0
        for word in self.text.split():
            w = _width(word, self.style.fontName, self.style.fontSize)
            if current and used + space + w > width:
                lines.append(current)
                current, used = [], 0.0
            used += (space if current else 0) + w
            current.append(word)
        return lines + [current] if current else lines

    def wrap(self, availWidth, availHeight):
        width = availWidth - self.style.leftIndent - self.style.rightIndent
        self._words = self._fixed or self._wrap_words(width)
        line_style = ParagraphStyle("rtl_line", parent=self.style, spaceBefore=0, spaceAfter=0)
        self._lines = [Paragraph(_markup(" ".join(visual_words(words)), self.style.fontName), line_style)
                       for words in self._words]
        self._heights = [line.wrap(availWidth, availHeight)[1] for line in self._lines]
        self.width, self.height = availWidth, sum(self._heights)
        return self.width, self.height

    def getSpaceBefore(self):
        return self.style.spaceBefore

    def getSpaceAfter(self):
        return self.style.spaceAfter

    def split(self, availWidth, availHeight):
        self.wrap(availWidth, availHeight)
        fit, used = 0, 0.0
        while fit < len(self._heights) and used + self._heights[fit] <= availHeight:
            used += self._heights[fit]
            fit += 1
        if fit == 0 or fit == len(self._words):
            return []
        return [RtlParagraph(self.text, self.style, self._words[:fit]), RtlParagraph(self.text, self.style, self._words[fit:])]

    def draw(self):
        y = self.height
        for line, height in zip(self._lines, self._heights):
            y -= height
            line.drawOn(self.canv, 0, y)


def _markup(text: str, font_name: str) -> str:
    chain = _CHAINS.get(font_name, [])
    if len(chain) < 2:
        return escape(text)
    return "".join(escape(piece) if index == 0 else f'<font name="{chain[index][0]}">{escape(piece)}</font>'
                   for piece, index in font_runs(text, [path for _, path in chain]))


def _string(canvas, x: float, y: float, text: str, font_name: str, size: float, align: str = "left") -> float:
    """canvas.drawString for any language: each piece in the font that has its letters, shaped, in visual
    order. Returns the width."""
    chain = _CHAINS.get(font_name, [(font_name, None)])
    if len(chain) < 2 and not font_name.startswith(tuple(f"{c}-" for c in languages.INDIAN)):
        canvas.setFont(font_name, size)
        width = pdfmetrics.stringWidth(text, font_name, size)
        start = {"left": x, "right": x - width, "centre": x - width / 2}[align]
        canvas.drawString(start, y, text)
        return width
    language = font_name.split("-", 1)[0]
    pieces = visual_runs(text, [path for _, path in chain], languages.get(language).rtl)
    widths = [_shaped_width(piece, chain[index][0], size) for piece, index, _ in pieces]
    start = {"left": x, "right": x - sum(widths), "centre": x - sum(widths) / 2}[align]
    for (piece, index, _), width in zip(pieces, widths):
        canvas.setFont(chain[index][0], size)
        canvas.drawString(start, y, piece, shaping=True)
        start += width
    return sum(widths)


def _width(text: str, font_name: str, size: float) -> float:
    """Width of a line as _string() draws it (without drawing it)."""
    chain = _CHAINS.get(font_name, [])
    if len(chain) < 2:
        return pdfmetrics.stringWidth(text, font_name, size)
    language = font_name.split("-", 1)[0]
    return sum(_shaped_width(piece, chain[index][0], size)
               for piece, index, _ in visual_runs(text, [path for _, path in chain], languages.get(language).rtl))


def _shaped_width(text: str, font_name: str, size: float) -> float:
    from reportlab.pdfgen.textobject import bidiShapedText
    return bidiShapedText(text, None, fontName=font_name, fontSize=size, shaping=True)[1]


# ---- page parts ---------------------------------------------------------------------------


class QRPlaceholder(Flowable):
    """A dashed box where Stage 7 puts the QR code after signing."""

    def __init__(self, size: float, fonts: dict[str, str], lines: tuple[str, str]):
        super().__init__()
        self.width = self.height = size
        self.fonts, self.lines = fonts, lines

    def draw(self):
        c = self.canv
        c.setStrokeColor(_colour("line_2"))
        c.setDash(3, 3)
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, self.height, 6)
        c.setFillColor(_colour("muted"))
        first, second = self.lines
        _string(c, self.width / 2, self.height / 2 + 3, first, self.fonts["heading"], 8.5, "centre")
        _string(c, self.width / 2, self.height / 2 - 9, second, self.fonts["body"], 7.5, "centre")


def _top_block(info: ExportInfo, title: str, subtitle: str, severe: bool, styles, fonts) -> Table:
    left = [_p(f"{info.output_label.upper()} · {info.job_label.upper()}", styles["eyebrow"]), _p(title, styles["title"])]
    if subtitle:
        colour = "red" if severe else "muted"
        left.append(_p(subtitle, ParagraphStyle("sub", parent=styles["subtitle"], textColor=_colour(colour))))
    left.append(_p(f"{info.job_title} · {info.label('Prepared {date}', date=info.date)}", styles["meta"]))
    if info.signed:  # Stage 7: the real QR code (verify address + record number)
        qr = [Image(io.BytesIO(info.qr_png(8)), width=QR_BOX, height=QR_BOX),
              _p(info.record_no, ParagraphStyle("qr", parent=styles["meta"], fontSize=7, leading=9, alignment=1))]
    else:
        qr = QRPlaceholder(QR_BOX, fonts, info.qr_placeholder)
    table = Table([[left, qr]], colWidths=[TEXT_WIDTH - QR_BOX - 6 * mm, QR_BOX + 6 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _colour("line")),
    ]))
    return table


def _page_decoration(canvas, doc, info: ExportInfo, fonts) -> None:
    """Drawn on every page: tricolour strip, header line with the TLP label, footer."""
    canvas.saveState()
    # Tricolour strip across the top: saffron | white | green
    third = PAGE_WIDTH / 3
    for number, colour in enumerate(("saffron", "white", "green")):
        canvas.setFillColor(_colour(colour))
        canvas.rect(number * third, PAGE_HEIGHT - 5, third, 5, stroke=0, fill=1)

    top = PAGE_HEIGHT - 13 * mm
    x = MARGIN + 6
    if info.logo_png:  # the office's logo, 8 mm high (Stage 9B letterhead)
        logo = ImageReader(io.BytesIO(info.logo_png))
        width, height = logo.getSize()
        canvas.drawImage(logo, x, top - 2.5 * mm, width=8 * mm * width / height, height=8 * mm, mask="auto")
        x += 8 * mm * width / height + 3 * mm
    canvas.setFillColor(_colour("muted"))
    _string(canvas, x, top, f"{info.office_name} · {info.output_label}", fonts["heading"], 8)
    if info.tlp_label:
        _tlp_label(canvas, info, fonts, PAGE_WIDTH - MARGIN - 6, top - 3)

    # Footer
    canvas.setStrokeColor(_colour("line"))
    canvas.setLineWidth(0.8)
    canvas.line(MARGIN + 6, 14 * mm, PAGE_WIDTH - MARGIN - 6, 14 * mm)
    canvas.setFillColor(_colour("saffron_dark"))
    footer_width = _string(canvas, MARGIN + 6, 9.5 * mm, info.footer, fonts["heading"], 8)
    canvas.setFillColor(_colour("muted"))
    # The job line fills the space the footer text leaves, never more (a long title is shortened with "…")
    room = TEXT_WIDTH - footer_width - 18
    line = fit_title(f"{info.job_label}: ", info.job_title, f"  ·  {info.label('Page {page}', page=doc.page)}",
                     lambda text: _width(text, fonts["body"], 8), room)
    _string(canvas, PAGE_WIDTH - MARGIN - 6, 9.5 * mm, line, fonts["body"], 8, "right")
    canvas.restoreState()


def _tlp_label(canvas, info: ExportInfo, fonts, right: float, bottom: float) -> None:
    text = info.tlp_label
    width = _width(text, fonts["heading"], 8) + 10
    canvas.setFillColor(_colour("black"))
    canvas.roundRect(right - width, bottom, width, 13, 3, stroke=0, fill=1)
    canvas.setFillColor(HexColor("#" + TLP_TEXT_COLOURS.get(info.tlp, "FFFFFF")))
    _string(canvas, right - width + 5, bottom + 3.8, text, fonts["heading"], 8)


# ---- blocks -------------------------------------------------------------------------------

CELL_PADDING = 6  # ReportLab's default left and right padding inside a table cell, in points
SMALLEST_MONO = 6.5


def _mono_style(style: ParagraphStyle, values: list[str], room: float) -> ParagraphStyle:
    """Codes and hashes should never break across lines: use a smaller size if the longest one is too wide."""
    widest = max((pdfmetrics.stringWidth(v, style.fontName, style.fontSize) for v in values), default=0)
    if widest <= room:
        return style
    size = max(SMALLEST_MONO, style.fontSize * room / widest - 0.05)
    return ParagraphStyle(f"{style.name}-fit", parent=style, fontSize=size, leading=size * 1.3)



def _flowables(block: Block, styles, fonts) -> list:
    if block.kind == "heading":
        return [_p(block.text, styles["heading"])]
    if block.kind == "paragraph":
        return [_p(block.text, styles["body"])]
    if block.kind in ("bullets", "numbered"):
        if styles["item"].wordWrap == "RTL":  # Stage 8: the marker goes on the right, as part of the line
            rtl_item = ParagraphStyle("item_rtl", parent=styles["item"], leftIndent=0, rightIndent=16)
            return [_p(f"{'•' if block.kind == 'bullets' else f'{number}.'} {item}", rtl_item)
                    for number, item in enumerate(block.items, start=1)]
        return [
            _p(item, styles["item"], bulletText="•" if block.kind == "bullets" else f"{number}.")
            for number, item in enumerate(block.items, start=1)
        ]
    if block.kind == "callout":
        box = Table([[[_p(block.label.upper(), styles["callout_label"]), _p(block.text, styles["callout"])]]],
                    colWidths=[TEXT_WIDTH])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _colour("saffron_light")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, _colour("saffron")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        return [KeepTogether([box]), Spacer(1, 4 * mm)]
    if block.kind == "table":
        cell = styles["cell_small"] if len(block.header) > 3 else styles["cell"]
        widths = [TEXT_WIDTH * share for share in (block.widths or [1 / len(block.header)] * len(block.header))]
        mono = {column: _mono_style(styles["cell_mono"], [row[column] for row in block.rows], widths[column] - 2 * CELL_PADDING)
                for column in block.mono_columns}
        rows = [[_p(value, styles["cell_head"]) for value in block.header]]
        rows += [
            [_p(value, mono.get(column, cell)) for column, value in enumerate(row)]
            for row in block.rows
        ]
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _colour("navy_light")),
            ("GRID", (0, 0), (-1, -1), 0.6, _colour("line_2")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return [table, Spacer(1, 3 * mm)]
    return []
