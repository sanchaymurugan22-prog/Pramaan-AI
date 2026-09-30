"""Step 2 of the pipeline: build ONE fact sheet from the sources.

Every output is later written from this fact sheet (not from the raw source), so all outputs
say the same thing.

The local model has a 4096-token context, so a long source is split into chunks. We ask the
model for facts from each chunk, then merge the answers in code (no extra model call).

Grounding: each fact comes with a quote. We check the quote really is in the source and
record where ("quote_found": exact / close / no). Indicators (CVEs, IP addresses, file hashes)
are found with exact patterns, not by the model, so they can never be made up.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.ai import llm
from app.ai.prompt_files import render_prompt
from app.config import max_tokens_for, settings
from app.pipeline.output_types import FACTSHEET_SCHEMA

MAX_FACTS_TOTAL = 15  # the merged fact sheet is sent with every output prompt, so keep it small
SEVERITY_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class SourcePages:
    source_id: str      # "S1", "S2", ...
    filename: str
    pages: list[str]    # pages[0] is page 1


@dataclass
class Chunk:
    source_id: str
    filename: str
    first_page: int
    last_page: int
    text: str           # with [Page N] markers


def build_fact_sheet(sources: list[SourcePages], on_progress: Callable[[str], None] = lambda message: None) -> dict:
    """Ask the model for facts (chunk by chunk), merge them, and check every quote."""
    chunks = make_chunks(sources, settings.factsheet_chunk_chars)
    # With several chunks, ask for fewer facts from each so the merged sheet stays small.
    max_facts = settings.factsheet_max_facts if len(chunks) == 1 else max(3, settings.factsheet_max_facts * 2 // 3)
    system = render_prompt("factsheet", max_facts=f"up to {max_facts}")

    partials = []
    for number, chunk in enumerate(chunks, start=1):
        step = f"Reading the source for facts (part {number} of {len(chunks)})"
        on_progress(step)
        header = f"Source {chunk.source_id}: {chunk.filename}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"<<<SOURCE\n{header}\n{chunk.text}\nSOURCE>>>"},
        ]
        reply = llm.chat_json(
            messages,
            FACTSHEET_SCHEMA,
            kind="factsheet",
            max_tokens=max_tokens_for("factsheet"),
            on_progress=lambda note, step=step: on_progress(f"{step} · {note}"),
        )
        partials.append((chunk, reply))

    sheet = merge_partials([(chunk, reply.data) for chunk, reply in partials])
    sheet["indicators"] = find_indicators("\n".join(page for s in sources for page in s.pages))
    verify_quotes(sheet, sources)
    sheet["parts"] = len(chunks)
    sheet["truncated"] = any(reply.truncated for _, reply in partials)
    sheet["seconds"] = round(sum(reply.seconds for _, reply in partials), 1)
    return sheet


# ---- chunking -----------------------------------------------------------------------------


def make_chunks(sources: list[SourcePages], max_chars: int) -> list[Chunk]:
    """Group pages into chunks of at most about max_chars characters. Very long pages are split."""
    chunks: list[Chunk] = []
    for source in sources:
        # Every page (or piece of a very long page) with its [Page N] marker
        blocks: list[tuple[int, str]] = []
        for number, page in enumerate(source.pages, start=1):
            if page.strip():
                blocks += [(number, f"[Page {number}]\n{piece}") for piece in _split_long(page, max_chars)]

        current: list[tuple[int, str]] = []
        for block in blocks:
            if current and sum(len(text) for _, text in current) + len(block[1]) > max_chars:
                chunks.append(_to_chunk(source, current))
                current = []
            current.append(block)
        if current:
            chunks.append(_to_chunk(source, current))
    return chunks


def _to_chunk(source: SourcePages, blocks: list[tuple[int, str]]) -> Chunk:
    text = "\n\n".join(text for _, text in blocks)
    return Chunk(source.source_id, source.filename, blocks[0][0], blocks[-1][0], text)


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split text longer than max_chars at paragraph breaks, then line breaks, then anywhere."""
    if len(text) <= max_chars:
        return [text]
    for separator in ("\n\n", "\n", ". "):
        parts = text.split(separator)
        if len(parts) > 1:
            pieces, current = [], ""
            for part in parts:
                candidate = f"{current}{separator}{part}" if current else part
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        pieces.append(current)
                    current = part
            if current:
                pieces.append(current)
            return [p for piece in pieces for p in _split_long(piece, max_chars)]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


# ---- merging ------------------------------------------------------------------------------


def _key(text: str) -> str:
    """Lower-case words only, used to spot duplicates and to compare quotes."""
    return " ".join(re.findall(r"\w+", text.lower()))


def merge_partials(partials: list[tuple[Chunk, dict]]) -> dict:
    """Combine the per-chunk answers into one fact sheet, renumbering facts F1, F2, ..."""
    facts, dates, entities, actions = [], [], [], []
    seen_facts, seen_dates, seen_entities, seen_actions = set(), set(), set(), set()
    summaries: list[str] = []
    severity = "unknown"

    for chunk, data in partials:
        if data.get("summary"):
            summaries.append(data["summary"].strip())
        if SEVERITY_RANK.get(data.get("severity", ""), 0) > SEVERITY_RANK[severity]:
            severity = data["severity"]

        for fact in data.get("key_facts", []):
            key = _key(fact.get("text", ""))
            if not key or key in seen_facts or len(facts) >= MAX_FACTS_TOTAL:
                continue
            seen_facts.add(key)
            page = fact.get("page")
            if not isinstance(page, int) or not chunk.first_page <= page <= chunk.last_page:
                page = chunk.first_page  # the model's page is outside this chunk; use the chunk's first page
            facts.append(
                {
                    "id": f"F{len(facts) + 1}",
                    "text": fact.get("text", "").strip(),
                    "source_id": chunk.source_id,
                    "page": page,
                    "quote": fact.get("quote", "").strip(),
                }
            )

        for item in data.get("dates", []):
            key = _key(f"{item.get('date', '')} {item.get('event', '')}")
            if key and key not in seen_dates:
                seen_dates.add(key)
                dates.append({"date": item.get("date", ""), "event": item.get("event", "")})

        for item in data.get("entities", []):
            key = _key(item.get("name", ""))
            if key and key not in seen_entities:
                seen_entities.add(key)
                entities.append({"name": item.get("name", ""), "type": item.get("type", "other")})

        for action in data.get("recommended_actions", []):
            key = _key(action)
            if key and key not in seen_actions:
                seen_actions.add(key)
                actions.append({"id": f"A{len(actions) + 1}", "text": action.strip()})

    return {
        "summary": " ".join(summaries),
        "severity": severity,
        "key_facts": facts,
        "dates": dates,
        "entities": entities,
        "recommended_actions": actions,
    }


# ---- indicators ---------------------------------------------------------------------------

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-(?:\d{4,7}|X{4,7})\b", re.IGNORECASE)
# Also catches "defanged" addresses written like 203.0.113[.]45
IP_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}(?:\.|\[\.\])){3}\d{1,3}(?![\d.])")
HASH_PATTERN = re.compile(r"\b(?:[a-fA-F0-9]{64}|[a-fA-F0-9]{40}|[a-fA-F0-9]{32})\b")


def find_indicators(text: str) -> dict:
    """CVE ids, IPv4 addresses and file hashes (MD5 / SHA-1 / SHA-256) found in the source."""

    def unique(values):
        return list(dict.fromkeys(values))  # remove repeats, keep order

    ips = []
    for match in IP_PATTERN.findall(text):
        ip = match.replace("[.]", ".")
        if all(0 <= int(part) <= 255 for part in ip.split(".")):
            ips.append(ip)
    return {
        "cves": unique(m.upper() for m in CVE_PATTERN.findall(text)),
        "ips": unique(ips),
        "hashes": unique(m.lower() for m in HASH_PATTERN.findall(text)),
    }


# ---- quote checking -----------------------------------------------------------------------


def verify_quotes(sheet: dict, sources: list[SourcePages]) -> None:
    """For each fact, find its quote in the source and set quote_found, source_id and page.

    exact = the quote's words appear in the source in the same order
    close = most of the quote's word pairs appear on one page (the model changed a word or two)
    no    = not found: the UI shows this fact with a warning
    """
    pages = [(s.source_id, number, _key(text)) for s in sources for number, text in enumerate(s.pages, start=1)]

    for fact in sheet["key_facts"]:
        quote = _key(fact.get("quote", ""))
        fact["quote_found"] = "no"
        if not quote:
            continue
        # Look on the page the model gave first, then everywhere else.
        ordered = sorted(pages, key=lambda p: (p[0], p[1]) != (fact["source_id"], fact["page"]))
        exact = next((p for p in ordered if quote in p[2]), None)
        if exact:
            fact["quote_found"], fact["source_id"], fact["page"] = "exact", exact[0], exact[1]
            continue
        best = max(ordered, key=lambda p: _pair_overlap(quote, p[2]), default=None)
        if best and _pair_overlap(quote, best[2]) >= 0.7:
            fact["quote_found"], fact["source_id"], fact["page"] = "close", best[0], best[1]


def _pair_overlap(quote: str, page: str) -> float:
    """Share of the quote's word pairs (bigrams) that also appear in the page."""
    words = quote.split()
    if len(words) < 2:
        return 1.0 if quote in page.split() else 0.0
    quote_pairs = set(zip(words, words[1:]))
    page_words = page.split()
    page_pairs = set(zip(page_words, page_words[1:]))
    return len(quote_pairs & page_pairs) / len(quote_pairs)


# ---- the fact sheet as prompt text ---------------------------------------------------------


def fact_sheet_for_prompt(sheet: dict) -> str:
    """A compact text version of the fact sheet for the output prompts (no quotes: saves tokens)."""
    lines = [f"Summary: {sheet['summary']}", f"Severity: {sheet['severity']}", "Facts:"]
    lines += [f"{f['id']}: {f['text']}" for f in sheet["key_facts"]]
    if sheet["dates"]:
        lines.append("Dates:")
        lines += [f"- {d['date']}: {d['event']}" for d in sheet["dates"]]
    if sheet["entities"]:
        lines.append("Named: " + ", ".join(f"{e['name']} ({e['type']})" for e in sheet["entities"]))
    indicators = sheet.get("indicators", {})
    parts = [
        f"{label}: {', '.join(indicators[key])}"
        for key, label in (("cves", "CVE"), ("ips", "IP addresses"), ("hashes", "File hashes"))
        if indicators.get(key)
    ]
    if parts:
        lines.append("Indicators: " + "; ".join(parts))
    if sheet["recommended_actions"]:
        lines.append("Recommended actions:")
        lines += [f"{a['id']}: {a['text']}" for a in sheet["recommended_actions"]]
    return "\n".join(lines)
