"""Things every exporter shares: the job details printed on each file, the footer, the palette,
and small helpers that turn output JSON into plain text.

Fact ids ("F3", "A1") stay in the JSON only. Exporters always print `text_of(item)`, which
returns just the sentence, so fact ids never appear in a file.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

# Printed on every exported file until a reviewer approves and signs it (Stage 7).
FOOTER = "AI-assisted · pending human approval"
# Text inside the empty box where the QR code goes after signing (Stage 7).
QR_PLACEHOLDER = "QR code\nadded when signed"

# Colours from the design (CLAUDE.md). Hex without "#", so each library can use them its own way.
PALETTE = {
    "saffron": "F28C28", "saffron_dark": "A34A00", "saffron_light": "FFF4E8", "saffron_mid": "FFDDB8",
    "green": "138808", "green_dark": "0E6A06", "green_light": "EBF7E7", "green_mid": "C9EBC1",
    "navy": "1E2F8F", "navy_dark": "15206B", "navy_light": "EEF0FB", "navy_mid": "D2D8F4",
    "ink": "1B1D26", "muted": "555B6B", "bg": "FBF8F2", "card": "FFFFFF", "line": "EFE7D9", "line_2": "E2D8C6",
    "red": "C0392B", "red_light": "FDEDEA", "yellow": "FCE68A", "yellow_light": "FFF8DB", "white": "FFFFFF",
    "black": "000000",
}

# Traffic Light Protocol label colours (FIRST TLP 2.0): coloured text on a black label.
TLP_TEXT_COLOURS = {"RED": "FF2B2B", "AMBER": "FFC000", "GREEN": "33FF00", "CLEAR": "FFFFFF"}


def rgb(name: str) -> tuple[int, int, int]:
    """Palette colour as (r, g, b), e.g. rgb("navy") -> (30, 47, 143)."""
    value = PALETTE.get(name, name)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


@dataclass
class ExportInfo:
    """The job details printed on every exported file."""

    job_id: int
    job_title: str
    date: str               # e.g. "30 Sep 2026" (the day the job was created, in this computer's time zone)
    tlp: str | None         # "RED" / "AMBER" / "GREEN" / "CLEAR", or None until the safety check sets it (Stage 6)
    output_type: str        # "advisory", ...
    output_label: str       # "Advisory", ...
    language: str = "en"    # fonts are picked per language (see fonts.py)

    @property
    def tlp_label(self) -> str | None:
        return f"TLP:{self.tlp}" if self.tlp else None

    def header_line(self) -> str:
        """One line with the job details, e.g. 'Job #12 · Hospital ransomware · 30 Sep 2026 · TLP:AMBER'."""
        parts = [f"Job #{self.job_id}", self.job_title, self.date]
        if self.tlp_label:
            parts.append(self.tlp_label)
        return " · ".join(parts)


def format_date(value: datetime) -> str:
    """Database times are UTC; show the date in this computer's time zone: '30 Sep 2026'."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%d %b %Y").lstrip("0")


def text_of(item) -> str:
    """The visible text of an output part: {"text": "...", "fact_ids": [...]} -> "..." (never the ids)."""
    if isinstance(item, dict):
        return str(item.get("text", "")).strip()
    return str(item or "").strip()


def texts(items) -> list[str]:
    """text_of for a list, leaving out empty parts."""
    return [t for t in (text_of(i) for i in (items or [])) if t]


def seconds_label(seconds: float) -> str:
    """12.5 -> '0:12' (for storyboard times)."""
    whole = int(round(seconds or 0))
    return f"{whole // 60}:{whole % 60:02d}"
