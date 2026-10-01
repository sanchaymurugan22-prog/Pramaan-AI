"""The mock AI (AI_MODE=mock): instant answers built from the text it is ACTUALLY sent. No model.

It gets exactly the same messages the real AI would get, so it only ever sees the MASKED text
(placeholders like [PHONE-1], removed instructions left out). That makes masking, the leak check
and the trust checks testable without a model.

  fact sheet  up to 8 informative sentences of the source (numbers, dates, names, placeholders)
              become the facts, each quoting its own sentence word for word; dates found by
              pattern (D1 ...); actions from a "Recommended actions" list, or else from sentences
              that start with a verb ("Please ...", "Apply ..."); severity from simple keywords.
  outputs     simple templates filled with the facts, actions and dates of the fact sheet it is
              sent, each piece citing the ids it uses. One LinkedIn paragraph cites no fact on
              purpose, so the yellow "Not linked to a fact" warning can be seen.

Like a well-behaved AI, it never uses a sentence that gives the AI orders ("ignore previous
instructions ..."). Same input, same answer: regenerating gives the same text again.
"""

import re

MAX_FACTS = 8

# ---- reading the messages ------------------------------------------------------------------------------


def answer(kind: str, messages: list[dict]) -> dict:
    """The mock answer for one request ("factsheet", "x_thread", ...)."""
    if kind == "factsheet":
        source = _fenced(messages[-1]["content"], "SOURCE") or messages[-1]["content"]
        return fact_sheet(source)
    text = "\n".join(m["content"] for m in messages if m["role"] == "system")
    sheet = _parse_fact_sheet(_fenced(text, "FACT SHEET") or "")
    return BUILDERS[kind](sheet)


def _fenced(text: str, name: str) -> str | None:
    """The text between <<<NAME and NAME>>> (see app/safety/shield.fence)."""
    start, end = text.find(f"<<<{name}\n"), text.rfind(f"\n{name}>>>")
    if start < 0 or end < start:
        return None
    return text[start + len(name) + 4 : end]


# ---- 1. the fact sheet ------------------------------------------------------------------------------------

LIST_MARKER = re.compile(r"^\s*(?:[-•*▪]|\d{1,2}[.)])\s+")
LABEL_LINE = re.compile(r"^\s*[A-Za-z][\w/()'.-]*(?: [\w/()'.-]+){0,3}:\s")
SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)]?\s+(?=[A-Z0-9\[\"“(])")
PLACEHOLDER = re.compile(r"\[[A-Z]+(?:-[A-Z]+)*-\d+\]")
ACTION_HEADING = re.compile(r"(?i)^(?:\d+[.)]\s*)?(?:recommended actions?|recommendations|what (?:to|you should) do|actions? to take|next steps)\b")
VERBS = set("""apply patch update upgrade block reset report keep save sign please do don't never avoid check
review install turn enable disable change contact call back remove isolate share use follow verify ensure make
restore stop scan delete close open read tell inform warn watch monitor limit restrict rotate revoke""".split())
SEVERITY_WORDS = [
    ("critical", ("critical", "catastrophic")),
    ("high", ("ransomware", "breach", "exploited", "exploit", "attack", "compromise", "encrypted", "stolen", "leak")),
    ("medium", ("phishing", "suspicious", "vulnerability", "failed login", "malware", "unauthorised", "unauthorized")),
    ("low", ("maintenance", "notice", "reminder", "scheduled")),
]
METADATA = re.compile(r"(?i)^(?:report |issue )?(?:date|prepared by|issued by|classification|marking|subject|ref(?:erence)?|from|to)\s*:")
ORG_WORDS = ("Cell", "Office", "Team", "Department", "Ministry", "Bank", "Hospital", "Services", "Centre", "Center",
             "Agency", "Authority", "Board", "Council", "Directorate", "Division", "Unit", "Treasury")


class Unit:
    """One paragraph line-group of a page: a sentence run, a list item, or a "Label: value" line."""

    def __init__(self, text: str, page: int, item: bool, label: bool = False):
        self.text, self.page, self.item, self.label = text, page, item, label


def _pages(source: str) -> list[tuple[int, str]]:
    """[(page number, text)] from the [Page N] markers (the first line may be "Source S1: name")."""
    lines = source.split("\n", 1)
    if lines[0].startswith("Source ") and len(lines) > 1:
        source = lines[1]
    parts = re.split(r"^\[Page (\d+)\]\s*$", source, flags=re.M)
    if len(parts) == 1:
        return [(1, source)]
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]


def _units(page_number: int, text: str) -> list[Unit]:
    """Lines joined into units: a wrapped sentence is one unit, a list item or "Label: value" starts a new one."""
    units: list[Unit] = []
    for paragraph in re.split(r"\n\s*\n", text):
        current: Unit | None = None
        for line in paragraph.splitlines():
            line = line.strip()
            if not line:
                continue
            item = bool(LIST_MARKER.match(line))
            label = bool(LABEL_LINE.match(line)) and not item
            # a "Label: value" line is always a unit of its own
            if current is None or item or label or current.label or current.text.endswith(":"):
                if current:
                    units.append(current)
                current = Unit(line, page_number, item, label)
            else:
                current.text += " " + line
        if current:
            units.append(current)
    return units


def _sentences(unit: Unit) -> list[str]:
    text = LIST_MARKER.sub("", unit.text, count=1)
    return [s.strip() for s in SENTENCE_END.split(text) if s.strip()]


def _is_heading(text: str) -> bool:
    plain = LIST_MARKER.sub("", text)
    return plain.isupper() or (len(plain.split()) <= 5 and not plain.rstrip().endswith((".", "!", "?")) and ":" not in plain)


def fact_sheet(source: str) -> dict:
    from app.pipeline.values import find_values  # imported here: values.py imports modules that import this one
    from app.safety.shield import find_instructions

    units = [u for number, text in _pages(source) for u in _units(number, text)]
    actions = _actions(units, find_instructions)
    action_texts = {a.lower() for a in actions}

    # every sentence that could be a fact, with a score for how informative it is
    candidates = []
    for unit in units:
        for sentence in _sentences(unit):
            if (sentence.lower() in action_texts or "SAMPLE" in sentence or find_instructions(sentence)
                    or sentence.endswith(":") or _is_heading(sentence)):
                continue
            values = [v for v in find_values(sentence) if v.kind != "number" or not v.text.isdigit() or len(v.text) > 1]
            placeholders = PLACEHOLDER.findall(sentence)
            words = len(sentence.split())
            if unit.label:
                # "Aadhaar: [AADHAAR-1]" is worth keeping; "Report date: 30 September" is only paperwork
                if not placeholders or METADATA.match(sentence):
                    continue
                score = 1
            elif words < 5 and not (placeholders or values):
                continue
            else:
                score = 2 * bool(values) + 2 * bool(placeholders) + (words >= 8) + bool(re.search(r"\s[A-Z][a-z]+", sentence))
                score -= unit.item  # list items (timelines) repeat the dates; prefer running text
            if score > 0:
                candidates.append((score, len(candidates), unit.page, sentence))

    chosen = sorted(sorted(candidates, key=lambda c: (-c[0], c[1]))[:MAX_FACTS], key=lambda c: c[1])
    facts = [
        {"id": f"F{n}", "text": sentence, "page": page, "quote": " ".join(sentence.split()[:20])}
        for n, (_, _, page, sentence) in enumerate(chosen, start=1)
    ]
    whole = "\n".join(u.text for u in units)
    return {
        "summary": " ".join(f["text"] for f in facts[:2]) or "The source has no clear facts.",
        "severity": _severity(whole),
        "key_facts": facts,
        "recommended_actions": actions,
        "dates": _dates(units, find_values),
        "entities": _entities(whole),
    }


def _actions(units: list[Unit], find_instructions) -> list[str]:
    """The items under a "Recommended actions" heading; if there is none, sentences that start with a verb."""
    for index, unit in enumerate(units):
        if ACTION_HEADING.match(unit.text) and len(unit.text.split()) <= 6:
            found = []
            for item in units[index + 1 :]:
                if not item.item or (_is_heading(item.text) and len(found) > 0):
                    break
                found.append(LIST_MARKER.sub("", item.text, count=1))
            if found:
                return found[:6]
    found = []
    for unit in units:
        for sentence in _sentences(unit):
            first = re.sub(r"[^a-z']", "", sentence.split()[0].lower()) if sentence.split() else ""
            if first in VERBS and not find_instructions(sentence) and len(sentence.split()) >= 3:
                found.append(sentence)
    return found[:6]


def _dates(units: list[Unit], find_values) -> list[dict]:
    """Up to 5 dates, each with the words around it as the event."""
    dates, seen = [], set()
    for unit in units:
        for sentence in _sentences(unit):
            if "SAMPLE" in sentence or find_values is None:
                continue
            for value in find_values(sentence):
                if value.kind != "date" or value.text in seen:
                    continue
                seen.add(value.text)
                rest = (sentence[: value.start] + sentence[value.end :]).strip(" :-–,.")
                rest = re.sub(r"^(?:on|by|as of|from|since|date)\b[\s:,]*", "", rest, flags=re.I)
                event = " ".join(rest.split()[:8]).rstrip(",;:") or "Mentioned in the source"
                dates.append({"date": value.text, "event": event[0].upper() + event[1:]})
    return dates[:5]


def _severity(text: str) -> str:
    lower = text.lower()
    for level, words in SEVERITY_WORDS:
        if any(word in lower for word in words):
            return level
    return "unknown"


def _entities(text: str) -> list[dict]:
    """Names in quotes and organisation names (capitalised words ending in Cell, Office, Bank ...)."""
    names: list[dict] = []

    def add(name: str, kind: str) -> None:
        if name and not PLACEHOLDER.search(name) and name.lower() not in {n["name"].lower() for n in names}:
            names.append({"name": name, "type": kind})

    for m in re.finditer(r"[\"“]([A-Z][\w.-]{2,40})[\"”]", text):
        add(m.group(1), "group")
    org = re.compile(r"\b(?:[A-Z][a-zA-Z]+|IT)(?: (?:[A-Z][a-zA-Z]+|IT|of|for|and))*? (?:" + "|".join(ORG_WORDS) + r")\b")
    for m in org.finditer(text):
        add(m.group().removeprefix("The ").strip(), "organisation")
    return names[:6]


# ---- 2. the outputs, from the fact sheet they are sent --------------------------------------------------


class Sheet:
    def __init__(self):
        self.summary, self.severity = "", "unknown"
        self.facts: list[tuple[str, str]] = []     # (id, text)
        self.actions: list[tuple[str, str]] = []
        self.dates: list[tuple[str, str, str]] = []  # (id, date, event)


def _parse_fact_sheet(text: str) -> Sheet:
    """Read back the fact sheet text made by factsheet.fact_sheet_for_prompt."""
    sheet, section = Sheet(), None
    for line in text.splitlines():
        if line.startswith("Summary: "):
            sheet.summary = line[9:]
        elif line.startswith("Severity: "):
            sheet.severity = line[10:]
        elif line in ("Facts:", "Dates:", "Recommended actions:"):
            section = line
        elif line.startswith(("Named: ", "Indicators: ")):
            section = None
        elif m := re.match(r"([FAD]\d+): (.*)", line):
            item_id, rest = m.groups()
            if section == "Facts:":
                sheet.facts.append((item_id, rest))
            elif section == "Recommended actions:":
                sheet.actions.append((item_id, rest))
            elif section == "Dates:":
                date, _, event = rest.partition(": ")
                sheet.dates.append((item_id, date, event))
    return sheet


def _grounded(text: str, ids: list[str]) -> dict:
    return {"text": text, "fact_ids": ids}


def _words(text: str, limit: int) -> str:
    """The first `limit` words (a placeholder like [PHONE-1] counts as one word)."""
    words = text.split()
    return " ".join(words[:limit]).rstrip(",;:") if len(words) > limit else text


# A short caption must not end on one of these ("...through an unpatched", "...patch to", "...that did")
SMALL_WORDS = {
    "a", "an", "the", "to", "of", "in", "on", "at", "by", "for", "from", "with", "and", "or", "but", "that",
    "which", "who", "as", "was", "were", "is", "are", "be", "has", "have", "had", "been", "did", "do", "does",
    "its", "their", "his", "her", "our", "your", "this", "these", "those", "into", "than", "so", "not", "no",
    "since", "after", "before", "over", "under", "about", "through", "via", "per", "also", "all", "every",
    "some", "most", "mostly", "more", "very", "first", "if", "when", "while", "then", "it", "they", "there",
}
# Words that start a new part of a sentence: a good place to cut a caption
BREAK_WORDS = {"through", "via", "to", "on", "at", "in", "by", "for", "from", "with", "since", "after", "before",
               "because", "which", "who", "while", "when", "but", "and", "during", "until", "mostly"}
LEAD_IN = re.compile(r"^(?:As of|In|On|Since|By|After|Before|During|Today|Yesterday|However|Meanwhile)\b[^,]{0,30},\s+")


def _caption(text: str, limit: int) -> str:
    """A short phrase of at most `limit` words that reads well on a screen or a slide.
    "The attackers enter through an unpatched remote-access gateway" -> "The attackers enter";
    "As of 28 September, 42 hospitals in five states have reported ..." -> "42 hospitals in five states".
    Text that fits is kept whole (only a dangling small word at the end is dropped)."""
    words = text.strip().rstrip(".").split()
    if len(words) > limit:
        words = LEAD_IN.sub("", " ".join(words)).split()
    if len(words) > limit:
        # cut before the last linking word that leaves a whole "who did what" (at least 3 words)
        cuts = [i for i in range(3, limit + 1) if words[i].lower() in BREAK_WORDS]
        words = words[:cuts[-1]] if cuts else words[:limit]
    while len(words) > 1 and words[-1].lower().strip(",;:") in SMALL_WORDS:
        words.pop()
    caption = " ".join(words).rstrip(",;:-")
    return caption[:1].upper() + caption[1:]


def _fit(text: str, characters: int) -> str:
    """Whole words that fit in `characters`."""
    while len(text) > characters and " " in text:
        text = text.rsplit(" ", 1)[0].rstrip(",;:")
    return text


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


def _joined_actions(actions: list[tuple[str, str]]) -> str:
    return "; ".join(_lower_first(text.rstrip(".")) for _, text in actions) + "."


PLANTED = "Cyber safety is everyone's responsibility."  # cites no fact: shows the yellow warning


def x_thread(s: Sheet) -> dict:
    tweets = []
    if s.facts:
        tweets.append(_grounded(_fit("Alert: " + s.facts[0][1], 275), [s.facts[0][0]]))
    tweets += [_grounded(_fit(text, 275), [fid]) for fid, text in s.facts[1:3]]
    if s.actions:
        # as many actions as fit whole in one post
        for count in (3, 2, 1):
            chosen = s.actions[:count]
            text = "What to do: " + _joined_actions(chosen)
            if len(text) <= 258:
                break
        tweets.append(_grounded(_fit(text, 258) + " #CyberSecurity", [a for a, _ in chosen]))
    while len(tweets) < 2:
        tweets.append(_grounded("Stay alert and follow official guidance.", []))
    return {"tweets": tweets[:5]}


def linkedin_post(s: Sheet) -> dict:
    paragraphs = []
    if s.facts:
        paragraphs.append(_grounded(s.facts[0][1], [s.facts[0][0]]))
    if len(s.facts) > 1:
        paragraphs.append(_grounded(" ".join(text for _, text in s.facts[1:3]), [fid for fid, _ in s.facts[1:3]]))
    if s.actions:
        paragraphs.append(_grounded("What to do now: " + _joined_actions(s.actions[:4]), [a for a, _ in s.actions[:4]]))
    paragraphs.append(_grounded(PLANTED, []))
    return {"paragraphs": paragraphs, "hashtags": ["CyberSecurity", "StaySafe"]}


def executive_summary(s: Sheet) -> dict:
    first = s.facts[0] if s.facts else ("", s.summary)
    return {
        "title": "Briefing: " + _caption(first[1], 8),
        "bottom_line": _grounded(_words(first[1], 55), [first[0]] if first[0] else []),
        "key_points": [_grounded(text, [fid]) for fid, text in s.facts[1:5]] or [_grounded(s.summary, [])],
        "actions_needed": [_grounded(text, [aid]) for aid, text in s.actions[:4]]
        or [_grounded("Decide the next steps with the teams concerned.", [])],
    }


def infographic(s: Sheet) -> dict:
    numbers = []
    for fid, text in s.facts:
        plain = PLACEHOLDER.sub(" ", text)
        for m in re.finditer(r"(?<![\w.])(\d[\d,.]*(?: (?:million|lakh|crore|thousand))?) ((?:[A-Za-z-]+ ?){1,4})", plain):
            label = m.group(2).strip()
            if re.match(r"(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", label) or len(m.group(1)) == 4:
                continue  # a date or a year, not an amount
            if (m.group(1), label) not in {(n["value"], n["label"]) for n in numbers}:
                numbers.append({"value": m.group(1), "label": _fit(label, 40), "fact_ids": [fid]})
            break
    if not numbers:
        numbers = [{"value": date, "label": _fit(event, 40), "fact_ids": [did]} for did, date, event in s.dates[:3]]
    if not numbers:
        numbers = [{"value": s.severity.capitalize(), "label": "severity", "fact_ids": []}]
    steps = [_grounded(_fit(text.rstrip("."), 60), [aid]) for aid, text in s.actions[:4]]
    headline = _fit(_caption(s.facts[0][1], 7), 60) if s.facts else "Key facts"
    return {
        "headline": headline,
        "subheadline": _caption(s.facts[1][1], 12) if len(s.facts) > 1 else _caption(s.summary, 12),
        "key_numbers": numbers[:3],
        "steps": steps or [_grounded("Follow official guidance", [])],
        "layout": "number_grid" if numbers and numbers[0]["fact_ids"] else "vertical_steps",
    }


def advisory(s: Sheet) -> dict:
    facts = s.facts or [("", s.summary)]
    first_two = facts[:2]
    return {
        "title": "Advisory: " + _caption(facts[0][1], 8),
        "severity": s.severity if s.severity in ("low", "medium", "high", "critical") else "unknown",
        "overview": _grounded(" ".join(t for _, t in first_two), [f for f, _ in first_two if f]),
        "affected": [_grounded(t, [f]) for f, t in facts[2:4]] or [_grounded(facts[0][1], [facts[0][0]] if facts[0][0] else [])],
        "description": _grounded(facts[4][1] if len(facts) > 4 else facts[-1][1], [(facts[4] if len(facts) > 4 else facts[-1])[0]]),
        "impact": _grounded(facts[5][1] if len(facts) > 5 else facts[0][1], [(facts[5] if len(facts) > 5 else facts[0])[0]]),
        "recommendations": [_grounded(t, [a]) for a, t in s.actions[:6]]
        or [_grounded("Check the source and decide the next steps.", [])],
    }


def presentation(s: Sheet) -> dict:
    def slide(title, items):
        return {"title": title, "bullets": [_caption(text, 16) for _, text in items],
                "speaker_notes": " ".join(text for _, text in items), "fact_ids": [i for i, _ in items if i]}

    slides = []
    if s.facts:
        slides.append(slide("What happened", s.facts[:3]))
    if len(s.facts) > 3:
        slides.append(slide("More details", s.facts[3:6]))
    if s.dates:
        slides.append(slide("Key dates", [(did, f"{date}: {_caption(event, 10)}") for did, date, event in s.dates[:4]]))
    if s.actions:
        slides.append(slide("What to do now", s.actions[:4]))
    while len(slides) < 3:
        slides.append(slide("Summary", [("", _words(s.summary, 15) or "No facts were found.")]))
    return {"title": "Briefing: " + _caption(s.facts[0][1], 8) if s.facts else "Briefing", "slides": slides[:6]}


def video_package(s: Sheet) -> dict:
    def scene(item_id, text):
        caption = _caption(text, 6)
        return {"visual": f"Simple shapes and icons showing: {caption[:1].lower() + caption[1:]}", "on_screen_text": caption,
                "narration": text if len(text.split()) <= 40 else _caption(text, 38) + ".",
                "fact_ids": [item_id] if item_id else []}

    scenes = [scene(fid, text) for fid, text in s.facts[:3]]
    if s.actions:
        scenes.append(scene(s.actions[0][0], s.actions[0][1]))
    while len(scenes) < 2:
        scenes.append(scene("", "Stay alert and follow official guidance."))
    return {"title": "Video: " + (_caption(s.facts[0][1], 6) if s.facts else "key facts"), "scenes": scenes}


BUILDERS = {
    "x_thread": x_thread, "linkedin_post": linkedin_post, "executive_summary": executive_summary,
    "infographic": infographic, "advisory": advisory, "presentation": presentation, "video_package": video_package,
}
