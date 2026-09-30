"""Step 2 of the pipeline: build ONE fact sheet from the sources.

Every output is later written from this fact sheet (not from the raw source), so all outputs
say the same thing.

The local model has a 4096-token context, so a long source is split into chunks. We ask the
model for facts from each chunk, then merge the answers in code (no extra model call).

Grounding: each fact comes with a quote. We check the quote really is in the source and
record where ("quote_found": exact / close / no, plus the character positions used to highlight
it; see trace.py). Recommended actions (A1, A2 ...) and dates (D1, D2 ...) are found in the
source the same way, by their own words. Indicators (CVEs, IP addresses, file hashes)
are found with exact patterns, not by the model, so they can never be made up. Entity types are
corrected with simple rules after the model answers (see fix_entity_type).

Safety (Stage 6A): the model reads the source with every hidden value replaced by a placeholder
([PHONE-1], see app/safety/masking.py), inside <<<SOURCE ... SOURCE>>> delimiters. The saved fact
sheet shows "Hide in public outputs" values again and "Hide everywhere" values as labels.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.ai import llm
from app.ai.prompt_files import render_prompt
from app.config import max_tokens_for, settings
from app.pipeline.output_types import ENTITY_TYPES, FACTSHEET_SCHEMA
from app.pipeline.trace import locate
from app.safety.shield import fence

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


def build_fact_sheet(sources: list[SourcePages], on_progress: Callable[[str], None] = lambda message: None,
                     masker=None) -> dict:
    """Ask the model for facts (chunk by chunk), merge them, and check every quote.

    masker (app/safety/masking.Masker): hides the values the operator chose to hide before the model
    reads the source. None = nothing hidden (jobs from before Stage 6A).
    """
    readable = sources
    if masker is not None:
        readable = [SourcePages(s.source_id, s.filename, [masker.mask(page) for page in s.pages]) for s in sources]
    chunks = make_chunks(readable, settings.factsheet_chunk_chars)
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
            {"role": "user", "content": fence(f"{header}\n{chunk.text}", "SOURCE")},
        ]
        reply = llm.chat_json(
            messages,
            FACTSHEET_SCHEMA,
            kind="factsheet",
            max_tokens=max_tokens_for("factsheet"),
            on_progress=lambda note, step=step: on_progress(f"{step} · {note}"),
        )
        # The JSON shape already allows at most 8 facts; this also covers servers that ignore it.
        reply.data["key_facts"] = reply.data.get("key_facts", [])[:max_facts]
        partials.append((chunk, reply))

    sheet = merge_partials([(chunk, reply.data) for chunk, reply in partials])
    sheet["indicators"] = find_indicators("\n".join(page for s in sources for page in s.pages))
    # Quotes are found in the real source: placeholders in them are swapped back for the search only.
    verify_quotes(sheet, sources, unmask=masker.unmask if masker is not None else None)
    if masker is not None:
        indicators = masker.indicators_for(sheet["indicators"], public=False)  # without "Hide everywhere" ones
        sheet = masker.view_json(sheet)
        sheet["indicators"] = indicators
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
                dates.append({"id": f"D{len(dates) + 1}", "date": item.get("date", ""), "event": item.get("event", "")})

        for item in data.get("entities", []):
            key = _key(item.get("name", ""))
            if key and key not in seen_entities:
                seen_entities.add(key)
                entities.append({"name": item.get("name", ""), "type": fix_entity_type(item.get("name", ""), item.get("type", ""))})

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
# (an address at the end of a sentence, "... from 10.1.2.3.", is still found)
IP_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}(?:\.|\[\.\])){3}\d{1,3}(?!\d|\.\d)")
HASH_PATTERN = re.compile(r"\b(?:[a-fA-F0-9]{64}|[a-fA-F0-9]{40}|[a-fA-F0-9]{32})\b")


def is_private_ip(ip: str) -> bool:
    """True for addresses inside an organisation's own network: 10.x, 172.16-31.x, 192.168.x.
    These are private data (see app/safety/scanner.py), never attack indicators."""
    parts = [int(p) for p in ip.split(".")]
    return parts[0] == 10 or (parts[0] == 172 and 16 <= parts[1] <= 31) or parts[:2] == [192, 168]


def find_indicators(text: str) -> dict:
    """CVE ids, public IPv4 addresses and file hashes (MD5 / SHA-1 / SHA-256) found in the source.
    Private addresses (10.x, 192.168.x ...) are left out: they are the organisation's own data."""

    def unique(values):
        return list(dict.fromkeys(values))  # remove repeats, keep order

    ips = []
    for match in IP_PATTERN.findall(text):
        ip = match.replace("[.]", ".")
        if all(0 <= int(part) <= 255 for part in ip.split(".")) and not is_private_ip(ip):
            ips.append(ip)
    return {
        "cves": unique(m.upper() for m in CVE_PATTERN.findall(text)),
        "ips": unique(ips),
        "hashes": unique(m.lower() for m in HASH_PATTERN.findall(text)),
    }


# ---- entity types --------------------------------------------------------------------------

# Common file endings, so "READ_ME_NIGHTLEDGER.txt" is a file but "example.com" is not.
FILE_PATTERN = re.compile(
    r"[\w\-. ]+\.(?:exe|dll|sys|bat|cmd|ps1|vbs|js|jar|msi|scr|lnk|iso|zip|rar|7z|txt|pdf|docx?|xlsx?|pptx?|html?|sh|py|bin|dat|log|tmp)",
    re.IGNORECASE,
)


def fix_entity_type(name: str, entity_type: str) -> str:
    """Correct the model's entity type with simple rules (it often calls CVE ids and file names "malware").

    CVE id -> vulnerability, IP address -> ip address, file name or file hash -> file.
    Anything else keeps the model's type (or "other" if the type is unknown).
    """
    name = name.strip().strip("'\"`")
    if CVE_PATTERN.search(name):
        return "vulnerability"
    if IP_PATTERN.fullmatch(name):
        return "ip address"
    if FILE_PATTERN.fullmatch(name) or HASH_PATTERN.fullmatch(name):
        return "file"
    return entity_type if entity_type in ENTITY_TYPES else "other"


# ---- quote checking -----------------------------------------------------------------------


def verify_quotes(sheet: dict, sources: list[SourcePages], unmask: Callable[[str], str] | None = None) -> None:
    """Find every fact's quote in the source, and every action and date by its own words.

    Sets on each item: quote_found (exact / close / no), source_id, page, start, end (the characters
    to highlight on that page). Actions and dates get a "quote" too: the source text that was found.
    Safe to run again (older fact sheets are brought up to date this way).
    unmask: turns placeholders like [PHONE-1] back into the real value, so the quote can be found.
    """
    pages = [(s.source_id, number, text) for s in sources for number, text in enumerate(s.pages, start=1)]
    real = unmask or (lambda text: text)

    for fact in sheet.get("key_facts", []):
        found = locate(real(fact.get("quote", "")), pages, prefer=(fact.get("source_id"), fact.get("page")))
        _set_trace(fact, found)

    for number, action in enumerate(sheet.get("recommended_actions", []), start=1):
        action.setdefault("id", f"A{number}")
        _set_trace(action, locate(real(action.get("text", "")), pages), pages)

    for number, item in enumerate(sheet.get("dates", []), start=1):
        item.setdefault("id", f"D{number}")
        found = locate(real(f"{item.get('date', '')} {item.get('event', '')}"), pages)
        if found.found == "no":  # the event was reworded: at least show where the date is
            found = locate(real(item.get("date", "")), pages)
            if found.found == "exact":
                found.found = "close"
        _set_trace(item, found, pages)


def _set_trace(item: dict, found, pages: list | None = None) -> None:
    item["quote_found"], item["source_id"], item["page"] = found.found, found.source_id, found.page
    item["start"], item["end"] = found.start, found.end
    if pages is not None:  # actions and dates: keep the words found in the source as their quote
        page_text = next((text for sid, number, text in pages if (sid, number) == (found.source_id, found.page)), "")
        item["quote"] = page_text[found.start : found.end] if found.start is not None else ""


# ---- the fact sheet as prompt text ---------------------------------------------------------


def fact_sheet_for_prompt(sheet: dict) -> str:
    """A compact text version of the fact sheet for the output prompts (no quotes: saves tokens)."""
    lines = [f"Summary: {sheet['summary']}", f"Severity: {sheet['severity']}", "Facts:"]
    lines += [f"{f['id']}: {f['text']}" for f in sheet["key_facts"]]
    if sheet["dates"]:
        lines.append("Dates:")
        lines += [f"{d.get('id', '-')}: {d['date']}: {d['event']}" for d in sheet["dates"]]
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
