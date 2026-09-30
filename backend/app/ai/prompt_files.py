"""Load prompt templates from app/ai/prompts/*.md and fill in {{placeholders}}.

We use {{name}} instead of Python's {name} because the prompts contain JSON examples,
which are full of { and } characters.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def render_prompt(name: str, **values) -> str:
    """Read prompts/<name>.md and replace each {{key}} with its value."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text.strip()
