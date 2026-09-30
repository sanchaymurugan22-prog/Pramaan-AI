"""Turns an output's JSON into a simple list of "blocks" (heading, paragraph, list, table ...).

The Word (docx.py) and PDF (pdf.py) exporters both draw these same blocks, so an advisory has
the same sections in both files and each layout is written only once.

Only the visible text is copied (via text_of); fact ids stay in the JSON.
"""

from dataclasses import dataclass, field

from app.exporters.common import seconds_label, text_of, texts


@dataclass
class Block:
    kind: str                       # title | subtitle | heading | paragraph | callout | bullets | numbered | table
    text: str = ""
    label: str = ""                 # callout only, e.g. "Bottom line"
    items: list[str] = field(default_factory=list)          # bullets / numbered
    header: list[str] = field(default_factory=list)         # table
    rows: list[list[str]] = field(default_factory=list)     # table
    widths: list[float] = field(default_factory=list)       # table: share of the page width per column
    mono_columns: list[int] = field(default_factory=list)   # table: columns shown in the code font


def document_blocks(output_type: str, content: dict) -> list[Block]:
    builders = {
        "advisory": advisory_blocks,
        "executive_summary": executive_summary_blocks,
        "video_package": video_script_blocks,
    }
    return builders[output_type](content)


def advisory_blocks(c: dict) -> list[Block]:
    blocks = [
        Block("title", c.get("title", "Advisory")),
        Block("subtitle", f"Severity: {str(c.get('severity', 'unknown')).upper()}"),
        Block("heading", "Overview"),
        Block("paragraph", text_of(c.get("overview"))),
        Block("heading", "Who and what is affected"),
        Block("bullets", items=texts(c.get("affected"))),
        Block("heading", "How the attack works"),
        Block("paragraph", text_of(c.get("description"))),
        Block("heading", "Impact"),
        Block("paragraph", text_of(c.get("impact"))),
    ]
    # Indicators were found in the source by exact patterns (not written by the AI).
    indicators = c.get("indicators") or {}
    rows = [
        [label, value]
        for key, label in (("cves", "Vulnerability (CVE)"), ("ips", "IP address"), ("hashes", "File fingerprint"))
        for value in indicators.get(key, [])
    ]
    if rows:
        blocks += [
            Block("heading", "Indicators found in the source"),
            Block("table", header=["Type", "Value"], rows=rows, widths=[0.3, 0.7], mono_columns=[1]),
        ]
    blocks += [
        Block("heading", "Recommended actions"),
        Block("numbered", items=texts(c.get("recommendations"))),
    ]
    return [b for b in blocks if _has_content(b)]


def executive_summary_blocks(c: dict) -> list[Block]:
    blocks = [
        Block("title", c.get("title", "Executive summary")),
        Block("callout", text_of(c.get("bottom_line")), label="Bottom line"),
        Block("heading", "Key points"),
        Block("bullets", items=texts(c.get("key_points"))),
        Block("heading", "Actions needed"),
        Block("numbered", items=texts(c.get("actions_needed"))),
    ]
    return [b for b in blocks if _has_content(b)]


def video_script_blocks(c: dict) -> list[Block]:
    scenes = c.get("scenes") or []
    rows = [
        [
            str(number),
            f"{seconds_label(scene.get('start', 0))}–{seconds_label(scene.get('end', 0))}",
            scene.get("visual", ""),
            scene.get("on_screen_text", ""),
            scene.get("narration", ""),
        ]
        for number, scene in enumerate(scenes, start=1)
    ]
    blocks = [
        Block("title", c.get("title", "Video package")),
        Block("subtitle", f"Script and storyboard · {len(scenes)} scenes · about {c.get('duration_seconds', 0)} seconds"),
        Block("heading", "Storyboard"),
        Block(
            "table",
            header=["Scene", "Time", "Visual", "On-screen text", "Narration"],
            rows=rows,
            widths=[0.08, 0.12, 0.27, 0.2, 0.33],
        ),
        Block("heading", "Narration script"),
    ]
    blocks += [
        Block("paragraph", f"Scene {number}: {scene.get('narration', '')}")
        for number, scene in enumerate(scenes, start=1)
        if scene.get("narration")
    ]
    return [b for b in blocks if _has_content(b)]


def _has_content(block: Block) -> bool:
    if block.kind in ("bullets", "numbered"):
        return bool(block.items)
    if block.kind == "table":
        return bool(block.rows)
    return bool(block.text.strip())
