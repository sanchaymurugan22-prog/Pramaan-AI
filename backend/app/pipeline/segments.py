"""The text fields of each output type ("segments"), found by their path in the output JSON.

A path is a list of keys, e.g. ["tweets", 2, "text"] or ["slides", 0, "bullets", 1]. Paths are
used for three things:
  - checks.py splits each segment into sentences and links every sentence to a fact;
  - the web page shows the sentences of a path with their warnings (the path is the address);
  - the operator's edits come back as (path, new text), so only these fields can be changed and
    fact ids, indicators and severity stay as they were.

fact_ids = None marks a heading (a title, a picture description, a hashtag): it is checked for
numbers that are not in the source, but it does not need to be linked to a fact.
"""

import copy
from dataclasses import dataclass


@dataclass
class Segment:
    path: list
    label: str             # shown in the edit form and in warnings, e.g. "Post 2"
    text: str
    fact_ids: list[str] | None
    editable: bool = True  # shown in the edit form
    checked: bool = True   # split into sentences and checked


def _ids(item) -> list[str]:
    return [str(i) for i in (item.get("fact_ids") or [])] if isinstance(item, dict) else []


def _list(content: dict, key: str) -> list:
    value = content.get(key)
    return value if isinstance(value, list) else []


def segments(output_type: str, content: dict) -> list[Segment]:
    """Every text field of one output, in reading order."""
    c = content or {}
    out: list[Segment] = []

    def heading(path, label):
        value = _get(c, path)
        if isinstance(value, str):
            out.append(Segment(path, label, value, None))

    def grounded(path, label):
        item = _get(c, path)
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            out.append(Segment([*path, "text"], label, item["text"], _ids(item)))

    if output_type == "sms":  # Stage 8: the emergency alert as a text message
        grounded(["message"], "Message")
    elif output_type == "x_thread":
        for i, _ in enumerate(_list(c, "tweets")):
            grounded(["tweets", i], f"Post {i + 1}")
    elif output_type == "linkedin_post":
        for i, _ in enumerate(_list(c, "paragraphs")):
            grounded(["paragraphs", i], f"Paragraph {i + 1}")
        for i, _ in enumerate(_list(c, "hashtags")):
            heading(["hashtags", i], f"Hashtag {i + 1}")
    elif output_type == "executive_summary":
        heading(["title"], "Title")
        grounded(["bottom_line"], "Bottom line")
        for i, _ in enumerate(_list(c, "key_points")):
            grounded(["key_points", i], f"Key point {i + 1}")
        for i, _ in enumerate(_list(c, "actions_needed")):
            grounded(["actions_needed", i], f"Action needed {i + 1}")
    elif output_type == "infographic":
        heading(["headline"], "Headline")
        heading(["subheadline"], "Subheadline")
        for i, number in enumerate(_list(c, "key_numbers")):
            if not isinstance(number, dict):
                continue
            value, label = str(number.get("value", "")), str(number.get("label", ""))
            out.append(Segment(["key_numbers", i, "value"], f"Key number {i + 1}", value, _ids(number), checked=False))
            out.append(Segment(["key_numbers", i, "label"], f"Key number {i + 1} label", label, _ids(number), checked=False))
            # Checked as one sentence ("42 hospitals disrupted"), so the number keeps its unit.
            out.append(Segment(["key_numbers", i], f"Key number {i + 1}", f"{value} {label}".strip(), _ids(number),
                               editable=False))
        for i, _ in enumerate(_list(c, "steps")):
            grounded(["steps", i], f"Step {i + 1}")
    elif output_type == "advisory":
        heading(["title"], "Title")
        grounded(["overview"], "Overview")
        for i, _ in enumerate(_list(c, "affected")):
            grounded(["affected", i], f"Affected {i + 1}")
        grounded(["description"], "How the attack works")
        grounded(["impact"], "Impact")
        for i, _ in enumerate(_list(c, "recommendations")):
            grounded(["recommendations", i], f"Recommended action {i + 1}")
    elif output_type == "presentation":
        heading(["title"], "Title")
        for i, slide in enumerate(_list(c, "slides")):
            if not isinstance(slide, dict):
                continue
            heading(["slides", i, "title"], f"Slide {i + 1} title")
            for j, bullet in enumerate(slide.get("bullets") or []):
                if isinstance(bullet, str):
                    out.append(Segment(["slides", i, "bullets", j], f"Slide {i + 1} point {j + 1}", bullet, _ids(slide)))
            if isinstance(slide.get("speaker_notes"), str):
                out.append(Segment(["slides", i, "speaker_notes"], f"Slide {i + 1} speaker notes",
                                   slide["speaker_notes"], _ids(slide)))
    elif output_type == "video_package":
        heading(["title"], "Title")
        for i, scene in enumerate(_list(c, "scenes")):
            if not isinstance(scene, dict):
                continue
            heading(["scenes", i, "visual"], f"Scene {i + 1} picture")
            for key, label in (("on_screen_text", "on-screen text"), ("narration", "narration")):
                if isinstance(scene.get(key), str):
                    out.append(Segment(["scenes", i, key], f"Scene {i + 1} {label}", scene[key], _ids(scene)))
    return out


def _get(content, path: list):
    value = content
    for key in path:
        if isinstance(key, int) and isinstance(value, list) and 0 <= key < len(value):
            value = value[key]
        elif isinstance(key, str) and isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


# ---- human edits ---------------------------------------------------------------------------------


class EditError(Exception):
    """An edit that cannot be applied (unknown field, not text)."""


def apply_edits(output_type: str, content: dict, edits: list[tuple[list, str]]) -> dict:
    """A copy of `content` with the edited texts. Only editable fields can be changed.

    Emptying a list item (a post, a paragraph, a bullet, a step ...) removes it.
    """
    # "tweets.1.text" -> ["tweets", 1, "text"] (the path as it is in the JSON, with real list indexes)
    allowed = {_key(s.path): s.path for s in segments(output_type, content) if s.editable}
    new = copy.deepcopy(content)
    for path, text in edits:
        real_path = allowed.get(_key(path))
        if real_path is None:
            raise EditError(f"'{_key(path)}' is not a text field of this output.")
        if not isinstance(text, str):
            raise EditError(f"'{_key(path)}' must be text.")
        _get(new, real_path[:-1])[real_path[-1]] = text.strip()
    _drop_empty_items(new)
    return new


def _key(path: list) -> str:
    return ".".join(str(p) for p in path)


def _drop_empty_items(value) -> None:
    """Remove list items whose text was emptied: "" in a list, or {"text": "", ...} in a list."""
    if isinstance(value, dict):
        for child in value.values():
            _drop_empty_items(child)
    elif isinstance(value, list):
        value[:] = [
            item for item in value
            if not (item == "" or (isinstance(item, dict) and "text" in item and not str(item["text"]).strip()))
        ]
        for child in value:
            _drop_empty_items(child)
