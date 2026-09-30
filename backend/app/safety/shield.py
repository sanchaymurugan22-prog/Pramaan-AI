"""The prompt-injection shield (no AI).

A source can try to take control of the AI: "ignore previous instructions and ...". Three defences:

1. Before analysis we look for such text and show it in the Safety check as "Suspicious instructions found":
     - instructions aimed at the AI ("ignore previous instructions", "you are now", "system prompt",
       "reveal your ...", chat role tags like <|system|> or [INST]) in the visible text;
     - hidden characters (zero-width, bidi controls, invisible "tag" letters). ingest.py removes them
       from the text before anything else reads it (strip_hidden_chars);
     - hidden text in Word files (white or tiny font, "Hidden" runs) and PDFs (invisible, white or
       tiny text). ingest.py leaves it out of the text the AI reads.
2. All source text sent to the AI is wrapped in clear delimiters (fence), and the prompts say that
   text between them is data and must never be followed as instructions.
3. After writing, checks.py flags any link, phone number or email in an output that is not in the
   source (an injected "call this number" would show up there).
"""

import re
import unicodedata

# ---- 1a. instructions aimed at the AI -----------------------------------------------------------------

_I = re.IGNORECASE
INSTRUCTION_PATTERNS = [
    re.compile(r"\b(?:ignore|disregard|forget|skip)\s+(?:all\s+|any\s+|the\s+|your\s+|of\s+)*(?:previous|prior|above|earlier|preceding|former|original)\s+"
               r"(?:instructions?|prompts?|rules?|messages?|directions?|guidelines?|context)", _I),
    re.compile(r"\b(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+|any\s+|the\s+)*(?:your|these|those|system|safety)\s+"
               r"(?:instructions?|rules?|guidelines?|prompts?|filters?|restrictions?)", _I),
    re.compile(r"\byou\s+are\s+now\b", _I),
    re.compile(r"\bfrom\s+now\s+on,?\s+you\b", _I),
    re.compile(r"\bpretend\s+(?:to\s+be|you\s+are)\b", _I),
    re.compile(r"\b(?:new|updated|real)\s+instructions?\s*:", _I),
    re.compile(r"\b(?:reveal|print|show|repeat|leak)\s+(?:me\s+)?(?:your|the)\s+(?:system\s+|hidden\s+|original\s+)?"
               r"(?:prompt|instructions?|rules|password|api\s*key|secrets?)", _I),
    re.compile(r"\bsystem\s+prompt\b", _I),
    re.compile(r"\b(?:jailbreak|DAN\s+mode|developer\s+mode)\b", _I),
    re.compile(r"\bdo\s+not\s+(?:follow|obey)\s+(?:the|your)\s+(?:rules|instructions)", _I),
    # chat role tags and prompt markers used by different models
    re.compile(r"<\|?\s*(?:system|assistant|user|im_start|im_end|endoftext)\s*\|?>", _I),
    re.compile(r"\[/?(?:INST|SYS)\]|<</?SYS>>"),
    re.compile(r"^\s*#{2,}\s*(?:system|instruction)s?\b", _I | re.M),
    # "System: you are ..." (but not "System: Windows server" in a normal report)
    re.compile(r"^\s*(?:system|assistant)\s*:\s*(?:you|ignore|forget|from\s+now|your|new\s+rules?)\b", _I | re.M),
    # trying to close our own delimiters early (see fence below)
    re.compile(r"<<<|>>>"),
]


def find_instructions(text: str) -> list[tuple[int, int]]:
    """(start, end) of every phrase that speaks to the AI, in reading order, without overlaps."""
    spans: list[tuple[int, int]] = []
    for pattern in INSTRUCTION_PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            while start < end and text[start].isspace():  # role-tag patterns may start at a line break
                start += 1
            if start < end and all(end <= a or start >= b for a, b in spans):
                spans.append((start, end))
    return sorted(spans)


# ---- 1b. hidden characters ------------------------------------------------------------------------------

# zero-width space / joiners, direction marks, bidi embeddings and overrides, word joiner and invisible
# operators, bidi isolates, zero-width no-break space (BOM), Mongolian vowel separator
HIDDEN_CHARS = set("​‌‍‎‏‪‫‬‭‮⁠⁡⁢⁣⁤"
                   "⁦⁧⁨⁩﻿᠎")
TAG_CHARS = range(0xE0000, 0xE0080)  # invisible copies of ASCII letters, used to smuggle hidden text
# Zero-width (non-)joiners are normal inside Indian scripts (they shape conjuncts), so they are kept there.
JOINERS = {"‌", "‍"}
INDIC = range(0x0900, 0x0E00)  # Devanagari ... Malayalam, Sinhala


def _is_hidden(text: str, index: int) -> bool:
    char = text[index]
    if ord(char) in TAG_CHARS:
        return True
    if char not in HIDDEN_CHARS:
        return False
    if char in JOINERS and index > 0 and ord(text[index - 1]) in INDIC:
        return False
    return True


def strip_hidden_chars(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Remove hidden characters. Returns the clean text and [(position in the clean text, removed characters)]."""
    kept: list[str] = []
    removed: list[tuple[int, str]] = []
    position = 0  # length of the clean text so far
    for index, char in enumerate(text):
        if _is_hidden(text, index):
            if removed and removed[-1][0] == position:
                removed[-1] = (position, removed[-1][1] + char)
            else:
                removed.append((position, char))
        else:
            kept.append(char)
            position += 1
    return "".join(kept), removed


def describe_hidden_chars(chars: str) -> str:
    """'3 zero-width spaces, 1 right-to-left override' and any message hidden in tag letters."""
    counts: dict[str, int] = {}
    for char in chars:
        name = "invisible tag letter" if ord(char) in TAG_CHARS else unicodedata.name(char, f"U+{ord(char):04X}").lower()
        counts[name] = counts.get(name, 0) + 1
    text = ", ".join(f"{n} × {name}" for name, n in counts.items())
    message = "".join(chr(ord(c) - 0xE0000) for c in chars if ord(c) in TAG_CHARS and 0x20 <= ord(c) - 0xE0000 < 0x7F)
    if message.strip():
        text += f'. Hidden message: "{message.strip()[:200]}"'
    return text


# ---- 1. everything suspicious in a job's sources (for the safety report) --------------------------------


def find_suspicious(sources) -> list[dict]:
    """sources: scanner.ScanSource list. Returns the "Suspicious instructions found" items, numbered X1, X2 ..."""
    items: list[dict] = []

    def add(**item) -> None:
        items.append({"id": f"X{len(items) + 1}", "start": None, "end": None, **item})

    for source in sources:
        for page_number, page in enumerate(source.pages, start=1):
            # one item per line, with every phrase on it ("spans") highlighted
            lines: dict[int, list[tuple[int, int]]] = {}
            for start, end in find_instructions(page):
                lines.setdefault(page.rfind("\n", 0, start), []).append((start, end))
            for spans in lines.values():
                start, end = spans[0][0], spans[-1][1]
                add(kind="instruction", label="Instruction aimed at the AI", source_id=source.source_id,
                    page=page_number, start=start, end=end, spans=[list(span) for span in spans],
                    text=_line_around(page, start, end),
                    detail="Kept in the text, but the AI is told that source text is data and must not be followed.")
        for note in source.notes:
            if note["kind"] == "hidden_characters":
                add(kind="hidden_characters", label="Hidden characters", source_id=source.source_id,
                    page=note["page"], start=note["position"], end=note["position"],
                    text=describe_hidden_chars(note["chars"]),
                    detail="Removed before anything reads the source.")
            else:  # hidden_text
                talks_to_ai = bool(find_instructions(note["text"]))
                add(kind="hidden_text", label=f"Hidden text in the {note['file_kind']} file", source_id=source.source_id,
                    page=note["page"], text=note["text"][:400],
                    detail=f"{note['reason'].capitalize()}. "
                           + ("It speaks to the AI. " if talks_to_ai else "")
                           + "Left out of what the AI reads. If it is real content (e.g. white text on a coloured "
                             "box), paste it in the text box instead.")
    return items


def _line_around(text: str, start: int, end: int, limit: int = 220) -> str:
    """The line holding text[start:end], shortened around it if very long."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end == -1 else line_end
    if line_end - line_start > limit:
        line_start = max(line_start, start - limit // 3)
        line_end = min(line_end, end + limit // 2)
    return text[line_start:line_end].strip()


# ---- 2. delimiters ----------------------------------------------------------------------------------------


def fence(text: str, name: str) -> str:
    """Wrap data in <<<NAME ... NAME>>>. The same marks inside the data are broken up, so a source can
    never close the block early and add "instructions" after it."""
    safe = text.replace("<<<", "< < <").replace(">>>", "> > >")
    return f"<<<{name}\n{safe}\n{name}>>>"
