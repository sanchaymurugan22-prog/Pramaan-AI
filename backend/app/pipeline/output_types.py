"""The 7 output types and the JSON shape (schema) each one must follow.

The schemas are sent to llama.cpp, which then forces the model to write exactly this shape.
Every piece of text carries "fact_ids": the fact-sheet facts it is based on (grounding).
maxItems keeps answers short, because the local model is slow.
"""

# ---- small schema helpers ----------------------------------------------------------------

STR = {"type": "string"}
FACT_IDS = {"type": "array", "items": STR, "maxItems": 4}


def obj(properties: dict) -> dict:
    """A JSON object where every listed property is required and nothing else is allowed."""
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def array(items: dict, max_items: int, min_items: int = 1) -> dict:
    return {"type": "array", "items": items, "minItems": min_items, "maxItems": max_items}


# A sentence or paragraph plus the facts it uses
GROUNDED_TEXT = obj({"text": STR, "fact_ids": FACT_IDS})

SEVERITY = {"type": "string", "enum": ["low", "medium", "high", "critical", "unknown"]}

# ---- the fact sheet ------------------------------------------------------------------------

MAX_KEY_FACTS = 8  # per model answer (per chunk when a long source is split)
ENTITY_TYPES = [
    "organisation", "place", "person", "group", "product", "malware",
    "vulnerability", "file", "ip address", "other",
]

FACTSHEET_SCHEMA = obj(
    {
        "summary": STR,
        "severity": SEVERITY,
        # At most 8 facts, so the answer finishes well inside its token limit on the local model
        "key_facts": array(obj({"id": STR, "text": STR, "page": {"type": "integer"}, "quote": STR}), MAX_KEY_FACTS),
        # Actions before dates and entities: if the answer is cut off at the token limit,
        # the less important lists are the ones lost.
        "recommended_actions": array(STR, 6, 0),
        "dates": array(obj({"date": STR, "event": STR}), 5, 0),
        "entities": array(
            obj(
                {
                    "name": STR,
                    "type": {
                        "type": "string",
                        "enum": ENTITY_TYPES,
                    },
                }
            ),
            6,
            0,
        ),
    }
)

# ---- the 7 outputs, in the order they are generated (shortest first) -----------------------

OUTPUT_TYPES: dict[str, dict] = {
    "x_thread": {
        "label": "X thread",
        "description": "Short public thread, up to 5 posts",
        "public": True,
        "schema": obj({"tweets": array(obj({"text": {"type": "string", "maxLength": 280}, "fact_ids": FACT_IDS}), 5, 2)}),
    },
    "linkedin_post": {
        "label": "LinkedIn post",
        "description": "Professional public post",
        "public": True,
        "schema": obj({"paragraphs": array(GROUNDED_TEXT, 4), "hashtags": array(STR, 5, 0)}),
    },
    "executive_summary": {
        "label": "Executive summary",
        "description": "One page for senior officers",
        "public": False,
        "schema": obj(
            {
                "title": STR,
                "bottom_line": GROUNDED_TEXT,
                "key_points": array(GROUNDED_TEXT, 5),
                "actions_needed": array(GROUNDED_TEXT, 4),
            }
        ),
    },
    "infographic": {
        "label": "Infographic",
        "description": "Key numbers and steps for one image",
        "public": True,
        "schema": obj(
            {
                "headline": STR,
                "subheadline": STR,
                "key_numbers": array(obj({"value": STR, "label": STR, "fact_ids": FACT_IDS}), 4),
                "steps": array(GROUNDED_TEXT, 5),
                "layout": {"type": "string", "enum": ["vertical_steps", "number_grid", "timeline"]},
            }
        ),
    },
    "advisory": {
        "label": "Advisory",
        "description": "Structured, CERT-In style",
        "public": False,
        "schema": obj(
            {
                "title": STR,
                "severity": SEVERITY,
                "overview": GROUNDED_TEXT,
                "affected": array(GROUNDED_TEXT, 4),
                "description": GROUNDED_TEXT,
                "impact": GROUNDED_TEXT,
                "recommendations": array(GROUNDED_TEXT, 6),
            }
        ),
    },
    "presentation": {
        "label": "Presentation",
        "description": "Slides with speaker notes",
        "public": False,
        "schema": obj(
            {
                "title": STR,
                "slides": array(
                    obj({"title": STR, "bullets": array(STR, 4), "speaker_notes": STR, "fact_ids": FACT_IDS}), 6, 3
                ),
            }
        ),
    },
    "video_package": {
        "label": "Video package",
        "description": "Scenes, narration and subtitles",
        "public": False,
        "schema": obj(
            {
                "title": STR,
                "scenes": array(
                    obj({"visual": STR, "on_screen_text": STR, "narration": STR, "fact_ids": FACT_IDS}), 6, 2
                ),
            }
        ),
    },
}

OUTPUT_ORDER = list(OUTPUT_TYPES)  # short outputs first

# ---- settings the operator can choose (shown as dropdowns in the UI) -----------------------

SETTING_OPTIONS = {
    "audience": ["IT and security teams", "Senior officials", "General public", "Hospital administrators", "Media"],
    "tone": ["Formal", "Neutral", "Urgent", "Reassuring"],
    "objective": ["Warn and instruct", "Inform", "Brief leadership", "Raise awareness"],
    "style": ["Official", "Plain and simple", "Technical"],
    "detail_level": ["short", "medium", "detailed"],
}

DEFAULT_SETTINGS = {name: options[0] for name, options in SETTING_OPTIONS.items()} | {"detail_level": "medium"}

# Level of detail scales the token limit: short answers finish sooner on the slow local model.
DETAIL_TOKEN_FACTOR = {"short": 0.75, "medium": 1.0, "detailed": 1.3}
