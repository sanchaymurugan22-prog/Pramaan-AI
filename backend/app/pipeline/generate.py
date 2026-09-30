"""Step 4 of the pipeline: write one output (X thread, advisory, ...) FROM THE FACT SHEET.

Every output uses the same system message (instructions + the fact sheet) and only the last
message changes. llama.cpp remembers the already-processed start of the prompt, so after the
first output it does not have to re-read the fact sheet: that saves time on the slow CPU.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.ai import llm
from app.ai.prompt_files import render_prompt
from app.config import max_tokens_for
from app.pipeline import checks
from app.pipeline.factsheet import fact_sheet_for_prompt
from app.pipeline.output_types import DETAIL_TOKEN_FACTOR, OUTPUT_TYPES

WORDS_PER_SECOND = 2.5  # normal speaking speed, used to time video narration and subtitles


@dataclass
class GeneratedOutput:
    content: dict
    quality: dict
    truncated: bool
    seconds: float
    tokens: int | None


def generate_output(
    output_type: str,
    fact_sheet: dict,
    job_settings: dict,
    on_progress: Callable[[str], None] | None = None,
) -> GeneratedOutput:
    """on_progress is called while the model works, with notes like "57 tokens written"."""
    spec = OUTPUT_TYPES[output_type]
    messages = [
        {"role": "system", "content": render_prompt("system", fact_sheet=fact_sheet_for_prompt(fact_sheet))},
        {"role": "user", "content": render_prompt(output_type, settings=settings_text(job_settings))},
    ]
    factor = DETAIL_TOKEN_FACTOR.get(job_settings.get("detail_level", "medium"), 1.0)
    max_tokens = int(max_tokens_for(output_type) * factor)

    reply = llm.chat_json(messages, spec["schema"], kind=output_type, max_tokens=max_tokens, on_progress=on_progress)

    content = reply.data
    if output_type == "advisory":
        # Indicators come straight from the source (found by exact patterns), never from the model.
        content["indicators"] = fact_sheet.get("indicators", {})
    elif output_type == "video_package":
        add_timings(content)
    elif output_type == "linkedin_post":
        content["hashtags"] = [tag.lstrip("#") for tag in content.get("hashtags", [])]

    quality = checks.check_output(output_type, content, fact_sheet)
    if reply.truncated:
        quality["warnings"].append("The answer was cut off at the token limit; the last part may be missing.")
    return GeneratedOutput(content, quality, reply.truncated, reply.seconds, reply.tokens)


def settings_text(job_settings: dict) -> str:
    return "\n".join(
        [
            f"Audience: {job_settings.get('audience', '')}",
            f"Tone: {job_settings.get('tone', '')}",
            f"Objective: {job_settings.get('objective', '')}",
            f"Style: {job_settings.get('style', '')}",
            f"Level of detail: {job_settings.get('detail_level', 'medium')}",
        ]
    )


# ---- video: scene timings and subtitles (worked out in code, not by the model) ------------


def add_timings(video: dict) -> None:
    """Give each scene a start and end time from its narration length, and build subtitles."""
    clock = 0.0
    subtitles = []
    for scene in video.get("scenes", []):
        scene["start"] = round(clock, 1)
        for sentence in _sentences(scene.get("narration", "")):
            seconds = max(1.5, len(sentence.split()) / WORDS_PER_SECOND)
            subtitles.append({"index": len(subtitles) + 1, "start": _srt_time(clock), "end": _srt_time(clock + seconds), "text": sentence})
            clock += seconds
        clock = max(clock, scene["start"] + 3.0)  # every scene is on screen for at least 3 seconds
        scene["end"] = round(clock, 1)
    video["duration_seconds"] = round(clock)
    video["subtitles"] = subtitles


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _srt_time(seconds: float) -> str:
    """12.5 -> '00:00:12,500' (the time format used in .srt subtitle files)"""
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
