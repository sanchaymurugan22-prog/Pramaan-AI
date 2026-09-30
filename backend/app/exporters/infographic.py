"""The infographic as a 1080 x 1350 PNG image (portrait, the size social media uses), drawn with Pillow.

It follows the output's "layout" field (the "Suggested layout" on the Results page):
  number_grid     big number tiles first, then the numbered steps
  vertical_steps  a small row of numbers, then large numbered steps
  timeline        a small row of numbers, then the steps along a timeline line

The footer has an empty dashed box for the QR code (Stage 7), "AI-assisted · pending human
approval", the job title and date, and the TLP label if set. If the text is long, everything is
drawn again slightly smaller until it fits.
"""

import math
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.exporters.common import FOOTER, TLP_TEXT_COLOURS, ExportInfo, rgb, text_of, texts
from app.exporters.fonts import font_file

WIDTH, HEIGHT = 1080, 1350
PAD = 72
INNER = WIDTH - 2 * PAD
FOOTER_TOP = HEIGHT - 190
TILE_COLOURS = ["navy", "saffron", "green", "navy_dark"]
STEP_COLOURS = [("saffron", "saffron_light"), ("navy", "card"), ("green", "green_light")]


def write_png(info: ExportInfo, content: dict, path: Path) -> Path:
    # Draw at full size; if the text does not fit above the footer, try again a bit smaller.
    scale = 1.0
    while True:
        image, bottom = _draw(info, content, scale)
        if bottom <= FOOTER_TOP - 24 or scale <= 0.6:
            break
        scale = round(scale - 0.06, 2)
    image.save(path, "PNG", optimize=True)
    return path


def _draw(info: ExportInfo, c: dict, scale: float) -> tuple[Image.Image, int]:
    image = Image.new("RGB", (WIDTH, HEIGHT), rgb("card"))
    draw = ImageDraw.Draw(image)
    lang = info.language
    s = lambda size: max(10, round(size * scale))  # noqa: E731  (scale a font size)

    _mandala(image, WIDTH - 150, 150)
    # tricolour strip: saffron | white | green
    draw.rectangle((0, 0, WIDTH // 3, 14), fill=rgb("saffron"))
    draw.rectangle((2 * WIDTH // 3, 0, WIDTH, 14), fill=rgb("green"))

    y = 70
    y = _pill(draw, PAD, y, "Public alert", _font("heading", "semibold", 24, lang), "red", "red_light") + round(28 * scale)

    y = _paragraph(draw, c.get("headline", ""), PAD, y, INNER, _font("heading", "bold", s(76), lang), "navy", s(80), max_lines=3)
    y += round(22 * scale)
    y = _paragraph(draw, c.get("subheadline", ""), PAD, y, INNER, _font("body", "regular", s(36), lang), "muted", s(44), max_lines=3)
    y += round(36 * scale)

    numbers = [n for n in (c.get("key_numbers") or []) if isinstance(n, dict) and n.get("value")]
    steps = texts(c.get("steps"))
    layout = c.get("layout") or "number_grid"
    if layout not in ("number_grid", "vertical_steps", "timeline"):
        layout = "number_grid"

    if layout == "number_grid":
        y = _number_tiles(draw, numbers, y, scale, lang)
    else:
        y = _number_row(draw, numbers, y, scale, lang)
    if steps:
        y += round(34 * scale)
        heading = f"Do these {len(steps)} things now" if len(steps) > 1 else "Do this now"
        y = _paragraph(draw, heading, PAD, y, INNER, _font("heading", "semibold", s(42), lang), "ink", s(50)) + round(18 * scale)
        if layout == "timeline":
            y = _timeline(draw, steps, y, scale, lang)
        else:
            y = _step_rows(draw, steps, y, scale * (1.12 if layout == "vertical_steps" else 1.0), lang)

    _footer(draw, info)
    return image, y


# ---- layout parts -------------------------------------------------------------------------


def _number_tiles(draw, numbers: list[dict], y: int, scale: float, lang: str) -> int:
    """Big coloured tiles, two per row (an odd last tile takes the whole row)."""
    if not numbers:
        return y
    gap = 24
    half_w = (INNER - gap) // 2
    tile_h = round(220 * scale)
    for index, number in enumerate(numbers):
        row, column = divmod(index, 2)
        alone = index == len(numbers) - 1 and column == 0  # last tile with no partner
        tile_w = INNER if alone else half_w
        x0 = PAD + column * (half_w + gap)
        y0 = y + row * (tile_h + gap)
        draw.rounded_rectangle((x0, y0, x0 + tile_w, y0 + tile_h), radius=22, fill=rgb(TILE_COLOURS[index % 4]))
        value_font = _fit_font(draw, str(number["value"]), "heading", "bold", round(84 * scale), tile_w - 56, lang)
        label_top = _value(draw, x0 + 28, y0 + round(18 * scale), str(number["value"]), value_font, "white") + round(10 * scale)
        _paragraph(draw, str(number.get("label", "")), x0 + 28, label_top, tile_w - 56,
                   _font("body", "medium", round(30 * scale), lang), "white", round(34 * scale), max_lines=2)
    rows = math.ceil(len(numbers) / 2)
    return y + rows * tile_h + (rows - 1) * gap


def _number_row(draw, numbers: list[dict], y: int, scale: float, lang: str) -> int:
    """A compact row of numbers (for the steps and timeline layouts)."""
    if not numbers:
        return y
    gap = 18
    box_w = (INNER - gap * (len(numbers) - 1)) // len(numbers)
    box_h = round(165 * scale)
    for index, number in enumerate(numbers):
        x0 = PAD + index * (box_w + gap)
        colour = TILE_COLOURS[index % 4]
        draw.rounded_rectangle((x0, y, x0 + box_w, y + box_h), radius=18, fill=rgb(f"{colour}_light" if colour != "navy_dark" else "navy_light"))
        value_font = _fit_font(draw, str(number["value"]), "heading", "bold", round(54 * scale), box_w - 36, lang)
        label_top = _value(draw, x0 + 18, y + round(14 * scale), str(number["value"]), value_font, colour) + round(8 * scale)
        _paragraph(draw, str(number.get("label", "")), x0 + 18, label_top, box_w - 36,
                   _font("body", "medium", round(24 * scale), lang), "ink", round(27 * scale), max_lines=2)
    return y + box_h


def _step_rows(draw, steps: list[str], y: int, scale: float, lang: str) -> int:
    """Numbered steps in soft coloured rows, like the design."""
    font = _font("heading", "medium", round(31 * scale), lang)
    line_h = round(40 * scale)
    radius = round(30 * scale)
    for index, step in enumerate(steps):
        colour, background = STEP_COLOURS[index % 3]
        lines = _wrap(draw, step, font, INNER - 3 * radius - 40)[:2]
        row_h = max(2 * radius + round(26 * scale), len(lines) * line_h + round(30 * scale))
        draw.rounded_rectangle((PAD, y, PAD + INNER, y + row_h), radius=18, fill=rgb(background))
        cx, cy = PAD + 20 + radius, y + row_h // 2
        _numbered_circle(draw, cx, cy, radius, index + 1, colour, lang)
        text_y = cy - len(lines) * line_h // 2
        for line in lines:
            draw.text((cx + radius + 22, text_y), line, font=font, fill=rgb("ink"))
            text_y += line_h
        y += row_h + round(14 * scale)
    return y - round(14 * scale)


def _timeline(draw, steps: list[str], y: int, scale: float, lang: str) -> int:
    """Steps along a vertical line, each with a numbered dot."""
    font = _font("heading", "medium", round(31 * scale), lang)
    label_font = _font("heading", "semibold", round(22 * scale), lang)
    line_h = round(40 * scale)
    radius = round(26 * scale)
    x_line = PAD + radius
    top = y
    centres = []
    for index, step in enumerate(steps):
        lines = _wrap(draw, step, font, INNER - 2 * radius - 40)[:2]
        colour = STEP_COLOURS[index % 3][0]
        centres.append((y + radius, index + 1, colour))
        draw.text((x_line + radius + 24, y - round(4 * scale)), f"STEP {index + 1}", font=label_font, fill=rgb(colour))
        text_y = y + round(26 * scale)
        for line in lines:
            draw.text((x_line + radius + 24, text_y), line, font=font, fill=rgb("ink"))
            text_y += line_h
        y = max(text_y, y + 2 * radius) + round(22 * scale)
    draw.line((x_line, top + radius, x_line, centres[-1][0]), fill=rgb("line_2"), width=6)
    for cy, number, colour in centres:
        _numbered_circle(draw, x_line, cy, radius, number, colour, lang)
    return y - round(22 * scale)


def _footer(draw, info: ExportInfo) -> None:
    lang = info.language
    draw.line((PAD, FOOTER_TOP, PAD + INNER, FOOTER_TOP), fill=rgb("line"), width=2)
    # QR code placeholder (Stage 7 puts the real QR code here after signing)
    box = (PAD, FOOTER_TOP + 30, PAD + 124, FOOTER_TOP + 154)
    _dashed_rect(draw, box, rgb("line_2"))
    small = _font("heading", "semibold", 20, lang)
    draw.text(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2 - 12), "QR code", font=small, fill=rgb("muted"), anchor="mm")
    draw.text(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2 + 14), "when signed", font=_font("body", "regular", 18, lang),
              fill=rgb("muted"), anchor="mm")

    x = box[2] + 28
    text_width = PAD + INNER - x
    draw.text((x, FOOTER_TOP + 34), "Scan to check this is genuine.", font=_font("body", "medium", 26, lang), fill=rgb("ink"))
    draw.text((x, FOOTER_TOP + 70), FOOTER, font=_font("heading", "semibold", 24, lang), fill=rgb("saffron_dark"))
    job_line = _shorten(draw, f"Job #{info.job_id} · {info.job_title}", _font("body", "regular", 22, lang), text_width)
    draw.text((x, FOOTER_TOP + 106), job_line, font=_font("body", "regular", 22, lang), fill=rgb("muted"))
    date_font = _font("body", "regular", 22, lang)
    draw.text((x, FOOTER_TOP + 134), info.date, font=date_font, fill=rgb("muted"))
    if info.tlp_label:
        label_font = _font("heading", "semibold", 22, lang)
        width = draw.textlength(info.tlp_label, font=label_font) + 24
        left = x + draw.textlength(info.date, font=date_font) + 20
        draw.rounded_rectangle((left, FOOTER_TOP + 132, left + width, FOOTER_TOP + 164), radius=6, fill=rgb("black"))
        draw.text((left + 12, FOOTER_TOP + 148), info.tlp_label, font=label_font,
                  fill=rgb(TLP_TEXT_COLOURS.get(info.tlp, "FFFFFF")), anchor="lm")


# ---- drawing helpers ----------------------------------------------------------------------


@cache
def _font(role: str, weight: str, size: int, language: str = "en") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_file(role, weight, language)), size)


def _fit_font(draw, text: str, role: str, weight: str, size: int, max_width: int, lang: str):
    """The biggest font (up to size) that fits the text on one line."""
    while size > 20 and draw.textlength(text, font=_font(role, weight, size, lang)) > max_width:
        size -= 4
    return _font(role, weight, size, lang)


def _value(draw, x: int, y: int, text: str, font, colour: str) -> int:
    """Draw a big number; returns the y just below its lowest letter (so "days" never touches the label)."""
    draw.text((x, y), text, font=font, fill=rgb(colour))
    return max(draw.textbbox((x, y), text, font=font)[3], draw.textbbox((x, y), "0", font=font)[3])


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Split text into lines that fit max_width pixels."""
    lines, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _shorten(draw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _paragraph(draw, text: str, x: int, y: int, width: int, font, colour: str, line_height: int, max_lines: int = 4) -> int:
    """Draw wrapped text; returns the y just below it. Extra lines are cut with '…'."""
    lines = _wrap(draw, text_of(text), font, width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _shorten(draw, lines[-1] + " …", font, width)
    for line in lines:
        draw.text((x, y), line, font=font, fill=rgb(colour))
        y += line_height
    return y


def _pill(draw, x: int, y: int, text: str, font, colour: str, background: str) -> int:
    width = draw.textlength(text, font=font) + 36
    draw.rounded_rectangle((x, y, x + width, y + 44), radius=22, fill=rgb(background))
    draw.text((x + 18, y + 22), text, font=font, fill=rgb(colour), anchor="lm")
    return y + 44


def _numbered_circle(draw, cx: int, cy: int, radius: int, number: int, colour: str, lang: str) -> None:
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=rgb(colour))
    draw.text((cx, cy), str(number), font=_font("heading", "bold", round(radius * 1.1), lang), fill=rgb("white"), anchor="mm")


def _dashed_rect(draw, box: tuple[int, int, int, int], colour, dash: int = 10, width: int = 3) -> None:
    x0, y0, x1, y1 = box
    for start in range(x0, x1, dash * 2):
        draw.line((start, y0, min(start + dash, x1), y0), fill=colour, width=width)
        draw.line((start, y1, min(start + dash, x1), y1), fill=colour, width=width)
    for start in range(y0, y1, dash * 2):
        draw.line((x0, start, x0, min(start + dash, y1)), fill=colour, width=width)
        draw.line((x1, start, x1, min(start + dash, y1)), fill=colour, width=width)


def _mandala(image: Image.Image, cx: int, cy: int) -> None:
    """A faint saffron mandala in the top-right corner, as in the design."""
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    colour = (*rgb("saffron"), 60)
    for radius in (40, 90, 150, 200):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=colour, width=2)
    for petal in range(12):
        angle = petal * math.pi / 6
        px, py = cx + 120 * math.cos(angle), cy + 120 * math.sin(angle)
        draw.ellipse((px - 30, py - 30, px + 30, py + 30), outline=colour, width=2)
    image.paste(layer, (0, 0), layer)
