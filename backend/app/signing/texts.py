"""Text fingerprints: the same message, copied and forwarded, must give the same fingerprint.

normalise() makes two copies of a message equal even if WhatsApp, an SMS app or a person changed
spaces, capital letters, punctuation, emojis or invisible characters:

  1. Unicode NFKC (full-width letters, ligatures and similar look-alikes become plain letters)
  2. lower case
  3. remove punctuation (Unicode P*), symbols and emojis (S*), invisible format characters (Cf: zero-width
     spaces and joiners, direction marks), emoji variation selectors and keycap marks
  4. every run of spaces / new lines becomes one space; trim

The verify page does EXACTLY the same in JavaScript (verify-page/verify.js, normalise); test vectors
made here are checked there (tests/test_verify_page.py), so the two never drift apart.
Letters, digits and the vowel signs of Indian scripts (Mn / Mc) are kept.
"""

import hashlib
import re
import unicodedata

from app.exporters.common import text_of, texts
from app.pipeline.segments import segments

_DROP_EXTRA = {"⃣"} | {chr(c) for c in range(0xFE00, 0xFE10)} | {chr(c) for c in range(0xE0100, 0xE01F0)}
_SPACES = re.compile(r"\s+")

# Outputs people forward as a message; their text is published (for TLP:CLEAR / GREEN) so the
# "Is this real?" checker can also spot changed copies.
MESSAGE_OUTPUTS = ("x_thread", "linkedin_post")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    kept = []
    for char in text:
        category = unicodedata.category(char)
        if char in _DROP_EXTRA or category[0] in "PS" or category == "Cf":
            kept.append(" " if category[0] == "P" else "")  # "word,word" -> "word word"
        else:
            kept.append(char)
    return _SPACES.sub(" ", "".join(kept)).strip()


def text_hash(text: str) -> str:
    """SHA-256 (hex) of the normalised text."""
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def output_texts(output_type: str, content: dict) -> list[tuple[str, str]]:
    """The texts of one output that get a fingerprint: [(label, text), ...].
    X thread: the whole thread and each post on its own. LinkedIn post: the post with its hashtags.
    Everything else: all its text, in order."""
    if output_type == "x_thread":
        tweets = [text_of(t) for t in content.get("tweets", []) if text_of(t)]
        whole = "\n\n".join(f"{n}/{len(tweets)} {t}" for n, t in enumerate(tweets, start=1))
        return [("Whole thread", whole)] + [(f"Post {n}", t) for n, t in enumerate(tweets, start=1)]
    if output_type == "linkedin_post":
        body = "\n\n".join(texts(content.get("paragraphs")))
        tags = " ".join(f"#{tag.lstrip('#')}" for tag in content.get("hashtags", []) if tag)
        return [("Post", f"{body}\n\n{tags}".strip())]
    whole = "\n".join(seg.text for seg in segments(output_type, content) if seg.text and seg.text.strip())
    return [("Full text", whole)] if whole else []
