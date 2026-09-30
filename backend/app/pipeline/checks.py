"""Step 5 of the pipeline: check each output against the fact sheet.

Stage 3 keeps this simple: every piece of text in an output carries "fact_ids". Here we count
which pieces point at real facts and flag the ones that don't ("not linked to a fact"), so
nothing unsupported slips through silently. Stage 5 adds sentence-by-sentence tracing to the
source, cross-output number checks and a quality score.
"""

TEXT_FIELDS = ("text", "narration", "title", "label", "value")


def check_output(output_type: str, content: dict, fact_sheet: dict) -> dict:
    known_ids = {f["id"] for f in fact_sheet["key_facts"]} | {a["id"] for a in fact_sheet["recommended_actions"]}

    items = list(_grounded_items(content))
    unlinked, unknown_ids = [], set()
    for text, fact_ids in items:
        valid = [i for i in fact_ids if i in known_ids]
        unknown_ids.update(i for i in fact_ids if i not in known_ids)
        if not valid:
            unlinked.append(text)

    warnings = []
    if unlinked:
        warnings.append(f"{len(unlinked)} of {len(items)} parts are not linked to any fact in the fact sheet.")
    if unknown_ids:
        warnings.append(f"Refers to fact ids that do not exist: {', '.join(sorted(unknown_ids))}.")
    if output_type == "x_thread":
        for number, tweet in enumerate(content.get("tweets", []), start=1):
            if len(tweet.get("text", "")) > 280:
                warnings.append(f"Post {number} is {len(tweet['text'])} characters; X allows 280.")

    return {
        "parts": len(items),
        "linked": len(items) - len(unlinked),
        "unlinked": unlinked,
        "unknown_fact_ids": sorted(unknown_ids),
        "warnings": warnings,
    }


def _grounded_items(value):
    """Yield (text, fact_ids) for every object in the output that has a fact_ids list."""
    if isinstance(value, dict):
        if isinstance(value.get("fact_ids"), list):
            text = next((value[f] for f in TEXT_FIELDS if isinstance(value.get(f), str) and value[f]), "")
            yield text, [str(i) for i in value["fact_ids"]]
        for child in value.values():
            yield from _grounded_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _grounded_items(child)
