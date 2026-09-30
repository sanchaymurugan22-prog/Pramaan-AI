"""Subtitles (.srt) for the video package.

The subtitle times were worked out when the video package was generated (generate.add_timings),
from the length of each narration sentence. An .srt file can only hold subtitles, so the job
details and "AI-assisted · pending human approval" are added as one last subtitle after the
narration ends (nothing earlier moves). The QR code placeholder is in the script .docx.
"""

import copy
from pathlib import Path

from typing import BinaryIO

from app.exporters.common import FOOTER, ExportInfo, save_text
from app.pipeline.generate import add_timings

CLOSING_SECONDS = 4.0


def write_srt(info: ExportInfo, content: dict, path: Path | BinaryIO) -> Path | BinaryIO:
    save_text(path, srt_text(info, content))
    return path


def srt_text(info: ExportInfo, content: dict) -> str:
    subtitles = content.get("subtitles")
    if not subtitles:  # older video packages: work the times out now
        content = copy.deepcopy(content)
        add_timings(content)
        subtitles = content.get("subtitles", [])

    cues = [(s["start"], s["end"], s["text"]) for s in subtitles if s.get("text")]
    last_end = _seconds(cues[-1][1]) if cues else 0.0
    cues.append((_time(last_end), _time(last_end + CLOSING_SECONDS), f"{FOOTER}\n{info.header_line()}"))

    # .srt format: number, "start --> end", the text, then a blank line
    return "\n".join(f"{number}\n{start} --> {end}\n{text}\n" for number, (start, end, text) in enumerate(cues, start=1))


def _seconds(value: str) -> float:
    """'00:01:02,500' -> 62.5"""
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _time(seconds: float) -> str:
    """62.5 -> '00:01:02,500'"""
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
