"""Step 5 of the pipeline: check every output against the fact sheet and the source. No AI is used,
so checks run again in a moment after a human edit.

For each output (check_output):
  1. Split every text field into sentences and link each sentence to the facts it uses. The model
     says which facts a piece of text uses (fact_ids); here we check each sentence really shares
     words with one of them. If not, we look for another fact that fits ("matched by words").
     A sentence with no fact is "Not linked to a fact" (yellow on the page). Never silently dropped.
  2. "Not in source": every number, date, CVE id, IP address and file hash in the output must also
     be in the fact sheet or the source (red on the page).
  3. Format rules: X posts at most 280 characters, slides at most 15 words a point, ...
  4. A quality score from 0 to 100 (see score_parts), with a plain-words explanation.

For the whole job (check_consistency): the same fact must carry the same number / date in every
output ("42 hospitals" everywhere); any output that says otherwise is listed.

recheck_job() runs all of this for a job and saves the results in the database.
"""

import copy
import re
from collections import defaultdict

from app.pipeline.segments import segments
from app.pipeline.trace import content_words
from app.pipeline.values import KnownValues, find_values

# Points for each part of the quality score (they add up to 100)
POINTS = {"linked": 40, "quotes": 25, "values": 20, "format": 15}
QUOTE_CREDIT = {"exact": 1.0, "close": 0.5, "no": 0.0}

# ---- sentences ---------------------------------------------------------------------------------

# A sentence ends at . ! ? or । (Hindi full stop), before a space and a word that does not start
# in lower case (so "e.g. this" and "1.2 million" are not split). A new line always ends one.
_BOUNDARY = re.compile(r"(?<=[.!?।])([\"'”’)\]]*)\s+(?=[^a-z\s])|\s*\n\s*")
_DECORATION = re.compile(r"[#@]\w+|https?://\S+")  # hashtags, @names and links are not claims


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence in text, without the spaces around it."""
    spans, start = [], 0
    for m in _BOUNDARY.finditer(text):
        spans.append((start, m.start() + len(m.group(1) or "")))
        start = m.end()
    spans.append((start, len(text)))
    result = []
    for a, b in spans:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a < b:
            result.append((a, b))
    return result


# ---- the fact sheet items a sentence can link to ------------------------------------------------


def sheet_items(sheet: dict) -> dict[str, dict]:
    """F1.. (key facts), A1.. (recommended actions) and D1.. (dates) by id."""
    items = {f["id"]: f for f in sheet.get("key_facts", []) if f.get("id")}
    items |= {a["id"]: a for a in sheet.get("recommended_actions", []) if a.get("id")}
    items |= {d["id"]: d for d in sheet.get("dates", []) if d.get("id")}
    return items


def item_text(item: dict) -> str:
    """The words of a fact sheet item: its text (or date and event) plus its quote from the source."""
    main = item.get("text") or f"{item.get('date', '')} {item.get('event', '')}"
    return f"{main} {item.get('quote', '')}"


def _words(text: str) -> set[str]:
    """Meaning-carrying words, plus each date as one word ("date:22-9") so dates can link too."""
    text = _DECORATION.sub(" ", text)
    words = content_words(text)
    words |= {f"date:{key}" for v in find_values(text) if v.kind == "date" for key in v.keys}
    return words


def _link(words: set[str], candidates: list[str], item_words: dict[str, set[str]], only_sentence: bool):
    """Which facts a sentence uses. Returns (fact ids, "model" | "words" | None, closest fact id)."""
    overlaps = {i: len(words & item_words[i]) for i in candidates if i in item_words}
    if only_sentence:
        # The model linked this one sentence to these facts: trust it if they share any word.
        chosen = [i for i, n in overlaps.items() if n >= 1]
    else:
        # Several sentences share the model's fact ids: each sentence must fit its fact on its own.
        chosen = [i for i, n in overlaps.items() if n >= 2 or (n >= 1 and n / len(words) >= 0.25)]
    if chosen:
        return chosen, "model", None

    # Not one of the model's facts: is there another fact the sentence clearly comes from?
    best_id, best = None, 0
    for item_id, other in item_words.items():
        n = len(words & other)
        if n > best:
            best_id, best = item_id, n
    if best >= 2 and best / len(words) >= 0.3:
        return [best_id], "words", None
    return [], None, best_id if best >= 1 else None


# ---- one output ----------------------------------------------------------------------------------


def check_output(output_type: str, content: dict, sheet: dict, known: KnownValues, truncated: bool = False) -> dict:
    items = sheet_items(sheet)
    item_words = {i: _words(item_text(item)) for i, item in items.items()}

    sentences, unknown_ids = [], set()
    for segment in segments(output_type, content):
        if not segment.checked:
            continue
        if segment.fact_ids:
            unknown_ids.update(i for i in segment.fact_ids if i not in items)
        spans = sentence_spans(segment.text)
        claims = [span for span in spans if _words(segment.text[span[0] : span[1]])]
        for start, end in spans:
            text = segment.text[start:end]
            words = _words(text)
            sentence = {
                "id": f"s{len(sentences) + 1}", "path": segment.path, "label": segment.label,
                "text": text, "start": start, "end": end,
                "status": "heading", "fact_ids": [], "matched_by": None, "closest": None,
                "not_in_source": [
                    {"kind": v.kind, "label": v.label, "text": v.text} for v in find_values(text) if known.missing(v)
                ],
            }
            if segment.fact_ids is not None:
                if not words:
                    sentence["status"] = "plain"  # only hashtags, links or punctuation
                else:
                    ids, how, closest = _link(words, segment.fact_ids, item_words, len(claims) == 1)
                    sentence.update(status="linked" if ids else "unlinked", fact_ids=ids, matched_by=how,
                                    closest=closest)
            sentences.append(sentence)

    rules = format_rules(output_type, content, truncated)
    quality = _score(sentences, items, rules)
    quality["unknown_fact_ids"] = sorted(unknown_ids)
    quality["warnings"] = _warnings(quality, rules, unknown_ids)
    return quality


def _score(sentences: list[dict], items: dict, rules: list[dict]) -> dict:
    claims = [s for s in sentences if s["status"] in ("linked", "unlinked")]
    linked = [s for s in claims if s["status"] == "linked"]
    used = sorted({i for s in linked for i in s["fact_ids"]}, key=_id_order)
    flags = [{"sentence_id": s["id"], **flag} for s in sentences for flag in s["not_in_source"]]
    rules_ok = [r for r in rules if r["ok"]]

    linked_share = len(linked) / len(claims) if claims else 1.0
    quote_share = sum(QUOTE_CREDIT.get(items[i].get("quote_found", "no"), 0) for i in used) / len(used) if used else 0.0
    found = sum(items[i].get("quote_found") == "exact" for i in used)
    close = sum(items[i].get("quote_found") == "close" for i in used)
    values_share = max(0.0, 1 - len(flags) / 3)  # each value not in the source costs a third
    format_share = len(rules_ok) / len(rules) if rules else 1.0

    parts = {
        "linked": {"label": "Sentences linked to a fact", "done": len(linked), "total": len(claims),
                   "points": round(POINTS["linked"] * linked_share), "max": POINTS["linked"]},
        "quotes": {"label": "Quotes found in the source", "done": found, "close": close, "total": len(used),
                   "points": round(POINTS["quotes"] * quote_share), "max": POINTS["quotes"]},
        "values": {"label": "Numbers and dates in the source", "problems": len(flags),
                   "points": round(POINTS["values"] * values_share), "max": POINTS["values"]},
        "format": {"label": "Length and format rules", "done": len(rules_ok), "total": len(rules),
                   "points": round(POINTS["format"] * format_share), "max": POINTS["format"]},
    }
    score = sum(p["points"] for p in parts.values())
    return {
        "score": score,
        "score_parts": parts,
        "explanation": _explain(score, parts, rules),
        "sentences": sentences,
        "facts_used": used,
        "not_in_source": flags,
        "format_rules": rules,
        # short lists kept for the older parts of the page and the tests
        "parts": len(claims),
        "linked": len(linked),
        "unlinked": [s["text"] for s in claims if s["status"] == "unlinked"],
    }


def _explain(score: int, parts: dict, rules: list[dict]) -> str:
    """The score in plain words, for the tooltip on the badge."""
    linked, quotes, values, fmt = parts["linked"], parts["quotes"], parts["values"], parts["format"]
    lines = [f"Quality {score} out of 100."]
    lines.append(f"{linked['done']} of {linked['total']} sentences are linked to a fact "
                 f"({linked['points']} of {linked['max']} points).")
    if quotes["total"]:
        close = f", {quotes['close']} only closely" if quotes["close"] else ""
        lines.append(f"The quotes of {quotes['done']} of the {quotes['total']} facts used were found word for word "
                     f"in the source{close} ({quotes['points']} of {quotes['max']}).")
    else:
        lines.append(f"No facts are used, so no quotes could be checked (0 of {quotes['max']}).")
    if values["problems"]:
        lines.append(f"{values['problems']} number(s), date(s) or code(s) are not in the fact sheet or the source "
                     f"({values['points']} of {values['max']}).")
    else:
        lines.append(f"Every number, date and code is in the source ({values['points']} of {values['max']}).")
    broken = [r["rule"] + (f" ({r['detail']})" if r["detail"] else "") for r in rules if not r["ok"]]
    if broken:
        lines.append(f"Rules not met: {'; '.join(broken)} ({fmt['points']} of {fmt['max']}).")
    else:
        lines.append(f"All {fmt['total']} length and format rules are met ({fmt['points']} of {fmt['max']}).")
    return " ".join(lines)


def _warnings(quality: dict, rules: list[dict], unknown_ids: set[str]) -> list[str]:
    warnings = []
    if quality["unlinked"]:
        warnings.append(f"{len(quality['unlinked'])} of {quality['parts']} sentences are not linked to any fact in the fact sheet.")
    if quality["not_in_source"]:
        shown = ", ".join(f"“{f['text']}”" for f in quality["not_in_source"][:4])
        warnings.append(f"Not in the source: {shown}.")
    if unknown_ids:
        warnings.append(f"Refers to fact ids that do not exist: {', '.join(sorted(unknown_ids))}.")
    warnings += [f"{r['rule']}: {r['detail']}" for r in rules if not r["ok"]]
    return warnings


def _id_order(item_id: str) -> tuple:
    """F2 before F10; facts, then actions, then dates."""
    return ("FAD".find(item_id[:1]), int(item_id[1:]) if item_id[1:].isdigit() else 0)


# ---- format rules ----------------------------------------------------------------------------------


def _count_words(text: str) -> int:
    return len(str(text or "").split())


def format_rules(output_type: str, content: dict, truncated: bool) -> list[dict]:
    """Length and shape rules per output type: [{"rule", "ok", "detail"}]. detail says what is wrong."""
    c = content or {}
    rules: list[dict] = []

    def rule(text: str, problems: list[str]) -> None:
        rules.append({"rule": text, "ok": not problems, "detail": "; ".join(problems)})

    def over(items, limit: int, name: str, measure=len, unit: str = "characters") -> list[str]:
        return [f"{name} {n} is {measure(t)} {unit}" for n, t in enumerate(items, start=1) if measure(t) > limit]

    if output_type == "x_thread":
        tweets = [t.get("text", "") for t in c.get("tweets", [])]
        rule("Every post is 280 characters or less (X limit)", over(tweets, 280, "Post"))
        rule("2 to 5 posts", [] if 2 <= len(tweets) <= 5 else [f"{len(tweets)} posts"])
    elif output_type == "linkedin_post":
        total = len("\n\n".join(p.get("text", "") for p in c.get("paragraphs", [])))
        rule("Post is 3,000 characters or less (LinkedIn limit)", [] if total <= 3000 else [f"{total:,} characters"])
        tags = c.get("hashtags", [])
        rule("At most 5 hashtags", [] if len(tags) <= 5 else [f"{len(tags)} hashtags"])
    elif output_type == "executive_summary":
        texts = [c.get("title", ""), c.get("bottom_line", {}).get("text", "")]
        texts += [p.get("text", "") for key in ("key_points", "actions_needed") for p in c.get(key, [])]
        words = sum(_count_words(t) for t in texts)
        rule("Fits on one page (400 words or less)", [] if words <= 400 else [f"{words} words"])
        bottom = _count_words(c.get("bottom_line", {}).get("text", ""))
        rule("Bottom line is 60 words or less", [] if bottom <= 60 else [f"{bottom} words"])
    elif output_type == "infographic":
        headline = c.get("headline", "")
        rule("Headline is 60 characters or less", [] if len(headline) <= 60 else [f"{len(headline)} characters"])
        rule("Each number label is 40 characters or less",
             over([n.get("label", "") for n in c.get("key_numbers", [])], 40, "Label"))
        rule("Each step is 60 characters or less", over([s.get("text", "") for s in c.get("steps", [])], 60, "Step"))
    elif output_type == "advisory":
        overview = _count_words(c.get("overview", {}).get("text", ""))
        rule("Overview is 120 words or less", [] if overview <= 120 else [f"{overview} words"])
        rule("Has at least one recommended action", [] if c.get("recommendations") else ["none"])
    elif output_type == "presentation":
        slides = c.get("slides", [])
        rule("3 to 6 slides", [] if 3 <= len(slides) <= 6 else [f"{len(slides)} slides"])
        problems = [f"Slide {n} has {len(s.get('bullets', []))} points" for n, s in enumerate(slides, 1)
                    if len(s.get("bullets", [])) > 5]
        rule("At most 5 points a slide", problems)
        problems = [f"Slide {n} point {m} is {_count_words(b)} words" for n, s in enumerate(slides, 1)
                    for m, b in enumerate(s.get("bullets", []), 1) if _count_words(b) > 15]
        rule("Each point is 15 words or less", problems)
        rule("Every slide has speaker notes",
             [f"Slide {n}" for n, s in enumerate(slides, 1) if not str(s.get("speaker_notes", "")).strip()])
    elif output_type == "video_package":
        scenes = c.get("scenes", [])
        rule("Each scene's narration is 40 words or less",
             over([s.get("narration", "") for s in scenes], 40, "Scene", _count_words, "words"))
        rule("On-screen text is 10 words or less",
             over([s.get("on_screen_text", "") for s in scenes], 10, "Scene", _count_words, "words"))
        seconds = c.get("duration_seconds", 0) or 0
        rule("Video is 2 minutes or shorter", [] if seconds <= 120 else [f"about {seconds} seconds"])

    rule("The AI finished writing (not cut off)", ["cut off at the token limit"] if truncated else [])
    return rules


# ---- all outputs of a job: the same numbers for the same fact ---------------------------------------


def check_consistency(sheet: dict, outputs: list[dict]) -> dict:
    """outputs: [{"id", "type", "label", "sentences"}] (sentences from check_output).

    For each linked sentence, every number (with its unit word) and date is compared with the facts
    the sentence is linked to. "43 hospitals" linked to a fact that says "42 hospitals" is a
    mismatch, unless 43 hospitals is what another fact says (then it just uses a second fact).
    """
    items = sheet_items(sheet)
    # item id -> {"hospital": {"42": "42"}, "date": {"28-9": "28 September"}}
    reference: dict[str, dict[str, dict[str, str]]] = {}
    for item_id, item in items.items():
        ref: dict[str, dict[str, str]] = defaultdict(dict)
        for v in find_values(item_text(item)):
            what = _what(v)
            if what:
                for key in v.keys:
                    ref[what].setdefault(key, f"{v.text} {v.unit_text}".strip() if v.kind == "number" else v.text)
        reference[item_id] = ref

    mismatches, agreed, seen = [], {}, set()
    checked = 0
    for output in outputs:
        for s in output["sentences"]:
            if s["status"] != "linked":
                continue
            for v in find_values(s["text"]):
                what = _what(v)
                relevant = [i for i in s["fact_ids"] if what and reference.get(i, {}).get(what)]
                if not relevant:
                    continue
                checked += 1
                match = next((i for i in relevant if v.keys & set(reference[i][what])), None)
                if match:
                    key = (match, what, min(v.keys & set(reference[match][what])))
                    entry = agreed.setdefault(key, {"fact_id": match, "value": reference[match][what][key[2]],
                                                    "outputs": []})
                    if output["label"] not in entry["outputs"]:
                        entry["outputs"].append(output["label"])
                    continue
                # Belongs to a fact the sentence is not linked to (e.g. "11 hospitals" is another fact)?
                if any(v.keys & set(ref.get(what, {})) for i, ref in reference.items() if i not in s["fact_ids"]):
                    continue
                dedupe = (output["id"], s["id"], v.text)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                fact_id = relevant[0]
                mismatches.append({
                    "fact_id": fact_id,
                    "what": "date" if what == "date" else f"number of {what}",
                    "expected": list(dict.fromkeys(reference[fact_id][what].values())),
                    "found": f"{v.text} {v.unit_text}".strip() if v.kind == "number" else v.text,
                    "output_id": output["id"], "output_type": output["type"], "output_label": output["label"],
                    "sentence_id": s["id"], "sentence": s["text"],
                })

    shared = sorted((a for a in agreed.values() if len(a["outputs"]) >= 2), key=lambda a: (-len(a["outputs"]), _id_order(a["fact_id"])))
    return {
        "ok": not mismatches,
        "checked": checked,
        "outputs": len(outputs),
        "mismatches": mismatches,
        "agreed": shared[:8],
    }


def _what(value) -> str:
    """What a value measures: a unit word for numbers ("hospital"), "date" for dates, "" otherwise."""
    if value.kind == "date":
        return "date"
    if value.kind == "number" and value.unit:
        return value.unit
    return ""


# ---- saving it all ----------------------------------------------------------------------------------


def known_values(sheet: dict, page_texts: list[str]) -> KnownValues:
    """Everything in the source and the fact sheet, for the "Not in source" check."""
    texts = list(page_texts) + [sheet.get("summary", "")]
    texts += [item_text(item) for item in sheet_items(sheet).values()]
    texts += [e.get("name", "") for e in sheet.get("entities", [])]
    texts += [value for values in (sheet.get("indicators") or {}).values() for value in values]
    return KnownValues(texts)


def needs_trace(sheet: dict) -> bool:
    """Fact sheets made before Stage 5 have no highlight positions or date ids yet."""
    return any("start" not in item for key in ("key_facts", "recommended_actions", "dates") for item in sheet.get(key, [])) \
        or any("id" not in d for d in sheet.get("dates", []))


def recheck_job(db, job) -> None:
    """Run every check for every finished output of a job and save the results (no AI call)."""
    # imported here: factsheet.py and ingest.py are not needed by the checks themselves
    from app.pipeline.factsheet import SourcePages, verify_quotes
    from app.pipeline.ingest import load_pages
    from app.pipeline.output_types import OUTPUT_TYPES

    if job.fact_sheet is None:
        return
    sources = [SourcePages(s.source_key, s.filename, load_pages(s.text_path)) for s in job.sources]
    sheet = job.fact_sheet.json
    if needs_trace(sheet):
        sheet = copy.deepcopy(sheet)
        verify_quotes(sheet, sources)
        job.fact_sheet.json = sheet  # a new object, so SQLAlchemy saves the change
    known = known_values(sheet, [page for s in sources for page in s.pages])

    finished = [o for o in job.outputs if o.content_json and o.status in ("done", "generating", "queued")]
    for output in finished:
        quality = check_output(output.type, output.content_json, sheet, known, output.truncated)
        output.quality_json, output.quality_score = quality, quality["score"]
        current = next((v for v in output.versions if v.version == output.version), None)
        if current is not None:
            current.quality_json, current.quality_score = quality, quality["score"]

    job.consistency_json = check_consistency(sheet, [
        {"id": o.id, "type": o.type, "label": OUTPUT_TYPES[o.type]["label"], "sentences": o.quality_json["sentences"]}
        for o in finished
    ])
    scores = [o.quality_score for o in finished if o.quality_score is not None]
    job.quality_score = round(sum(scores) / len(scores)) if scores else None
    db.commit()
