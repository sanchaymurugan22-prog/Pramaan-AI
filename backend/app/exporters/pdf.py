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

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.exporters.blocks import Block, document_blocks
from app.exporters.common import PALETTE, QR_PLACEHOLDER, TLP_TEXT_COLOURS, ExportInfo, fit_title
from app.exporters.fonts import font_file

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN - 12  # the page frame keeps 6 points of padding on each side
QR_BOX = 30 * mm


def write_pdf(info: ExportInfo, content: dict, path: Path) -> Path:
    fonts = _register_fonts(info.language)
    styles = _styles(fonts)
    blocks = document_blocks(info.output_type, content)
    title = next((b.text for b in blocks if b.kind == "title"), info.output_label)
    subtitle = next((b.text for b in blocks if b.kind == "subtitle"), "")

    story = [_top_block(info, title, subtitle, styles, fonts), Spacer(1, 6 * mm)]
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
    """Register the bundled TTF fonts with ReportLab once; returns role -> registered font name."""
    wanted = {
        "heading": ("heading", "semibold"), "heading_bold": ("heading", "bold"),
        "body": ("body", "regular"), "body_bold": ("body", "semibold"), "mono": ("mono", "regular"),
    }
    names = {}
    for key, (role, weight) in wanted.items():
        name = f"{language}-{key}"
        pdfmetrics.registerFont(TTFont(name, str(font_file(role, weight, language))))
        names[key] = name
    # lets <b> inside body text switch to the bold body font
    pdfmetrics.registerFontFamily(names["body"], normal=names["body"], bold=names["body_bold"],
                                  italic=names["body"], boldItalic=names["body_bold"])
    return names


def _colour(name: str) -> HexColor:
    return HexColor("#" + PALETTE.get(name, name))


def _styles(fonts: dict[str, str]) -> dict[str, ParagraphStyle]:
    body = ParagraphStyle("body", fontName=fonts["body"], fontSize=10.5, leading=15, textColor=_colour("ink"), spaceAfter=5)
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
    """A paragraph of plain text (escaped, so '<' or '&' in the text are shown, not read as markup)."""
    return Paragraph(escape(text), style, **kwargs)


# ---- page parts ---------------------------------------------------------------------------


class QRPlaceholder(Flowable):
    """A dashed box where Stage 7 puts the QR code after signing."""

    def __init__(self, size: float, fonts: dict[str, str]):
        super().__init__()
        self.width = self.height = size
        self.fonts = fonts

    def draw(self):
        c = self.canv
        c.setStrokeColor(_colour("line_2"))
        c.setDash(3, 3)
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, self.height, 6)
        c.setFillColor(_colour("muted"))
        first, second = QR_PLACEHOLDER.split("\n")
        c.setFont(self.fonts["heading"], 8.5)
        c.drawCentredString(self.width / 2, self.height / 2 + 3, first)
        c.setFont(self.fonts["body"], 7.5)
        c.drawCentredString(self.width / 2, self.height / 2 - 9, second)


def _top_block(info: ExportInfo, title: str, subtitle: str, styles, fonts) -> Table:
    left = [_p(f"{info.output_label.upper()} · JOB #{info.job_id}", styles["eyebrow"]), _p(title, styles["title"])]
    if subtitle:
        colour = "red" if "HIGH" in subtitle or "CRITICAL" in subtitle else "muted"
        left.append(_p(subtitle, ParagraphStyle("sub", parent=styles["subtitle"], textColor=_colour(colour))))
    left.append(_p(f"{info.job_title} · Prepared {info.date}", styles["meta"]))
    if info.signed:  # Stage 7: the real QR code (verify address + record number)
        qr = [Image(io.BytesIO(info.qr_png(8)), width=QR_BOX, height=QR_BOX),
              _p(info.record_no, ParagraphStyle("qr", parent=styles["meta"], fontSize=7, leading=9, alignment=1))]
    else:
        qr = QRPlaceholder(QR_BOX, fonts)
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
    canvas.setFont(fonts["heading"], 8)
    canvas.drawString(x, top, f"{info.office_name} · {info.output_label}")
    if info.tlp_label:
        _tlp_label(canvas, info, fonts, PAGE_WIDTH - MARGIN - 6, top - 3)

    # Footer
    canvas.setStrokeColor(_colour("line"))
    canvas.setLineWidth(0.8)
    canvas.line(MARGIN + 6, 14 * mm, PAGE_WIDTH - MARGIN - 6, 14 * mm)
    canvas.setFont(fonts["heading"], 8)
    canvas.setFillColor(_colour("saffron_dark"))
    canvas.drawString(MARGIN + 6, 9.5 * mm, info.footer)
    canvas.setFont(fonts["body"], 8)
    canvas.setFillColor(_colour("muted"))
    # The job line fills the space the footer text leaves, never more (a long title is shortened with "…")
    room = TEXT_WIDTH - pdfmetrics.stringWidth(info.footer, fonts["heading"], 8) - 18
    line = fit_title(f"Job #{info.job_id}: ", info.job_title, f"  ·  Page {doc.page}",
                     lambda text: pdfmetrics.stringWidth(text, fonts["body"], 8), room)
    canvas.drawRightString(PAGE_WIDTH - MARGIN - 6, 9.5 * mm, line)
    canvas.restoreState()


def _tlp_label(canvas, info: ExportInfo, fonts, right: float, bottom: float) -> None:
    text = info.tlp_label
    width = pdfmetrics.stringWidth(text, fonts["heading"], 8) + 10
    canvas.setFillColor(_colour("black"))
    canvas.roundRect(right - width, bottom, width, 13, 3, stroke=0, fill=1)
    canvas.setFillColor(HexColor("#" + TLP_TEXT_COLOURS.get(info.tlp, "FFFFFF")))
    canvas.setFont(fonts["heading"], 8)
    canvas.drawString(right - width + 5, bottom + 3.8, text)


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
