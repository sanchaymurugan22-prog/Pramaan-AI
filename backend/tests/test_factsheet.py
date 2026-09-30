"""Tests for the fact sheet: chunking, merging, indicators and quote checking."""

from tests.helpers import SAMPLE_REPORT

from app.pipeline import factsheet
from app.pipeline.factsheet import Chunk, SourcePages
from app.pipeline.ingest import from_file


def sample_sources():
    return [SourcePages("S1", SAMPLE_REPORT.name, from_file(SAMPLE_REPORT.name, SAMPLE_REPORT.read_bytes()).pages)]


def test_short_source_is_one_chunk():
    chunks = factsheet.make_chunks(sample_sources(), max_chars=6000)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("[Page 1]")


def test_long_source_is_split_with_page_ranges():
    pages = ["word " * 300] * 5  # 5 pages of ~1500 characters
    chunks = factsheet.make_chunks([SourcePages("S1", "long.txt", pages)], max_chars=3500)
    assert [(c.first_page, c.last_page) for c in chunks] == [(1, 2), (3, 4), (5, 5)]
    assert all(len(c.text) <= 3500 for c in chunks)


def test_one_huge_page_is_split_too():
    page = "\n\n".join(["A sentence about the incident. " * 20] * 10)  # ~6000 characters
    chunks = factsheet.make_chunks([SourcePages("S1", "big.txt", [page])], max_chars=2000)
    assert len(chunks) >= 3
    assert all(c.first_page == 1 for c in chunks)


def test_indicators_are_found_by_pattern():
    indicators = factsheet.find_indicators(SAMPLE_REPORT.read_text(encoding="utf-8"))
    assert indicators["cves"] == ["CVE-2026-XXXXX"]
    assert indicators["ips"] == ["203.0.113.45", "198.51.100.23"]
    assert len(indicators["hashes"]) == 1 and len(indicators["hashes"][0]) == 64


def test_defanged_ip_and_bad_ip():
    indicators = factsheet.find_indicators("seen 203.0.113[.]9 and version 999.1.1.1")
    assert indicators["ips"] == ["203.0.113.9"]


def test_merge_removes_duplicates_and_renumbers():
    chunk1 = Chunk("S1", "a.txt", 1, 2, "")
    chunk2 = Chunk("S1", "a.txt", 3, 4, "")
    part1 = {"summary": "One.", "severity": "medium", "key_facts": [{"id": "F1", "text": "42 hospitals hit.", "page": 2, "quote": "q"}],
             "dates": [], "entities": [], "recommended_actions": ["Patch now."]}
    part2 = {"summary": "Two.", "severity": "high", "key_facts": [
                {"id": "F1", "text": "42 Hospitals hit", "page": 3, "quote": "q"},     # duplicate
                {"id": "F2", "text": "Backups encrypted.", "page": 99, "quote": "q"}],  # page outside the chunk
             "dates": [], "entities": [], "recommended_actions": ["Patch now", "Go offline."]}
    sheet = factsheet.merge_partials([(chunk1, part1), (chunk2, part2)])
    assert [f["id"] for f in sheet["key_facts"]] == ["F1", "F2"]
    assert sheet["key_facts"][1]["page"] == 3
    assert sheet["severity"] == "high"
    assert sheet["summary"] == "One. Two."
    assert [a["id"] for a in sheet["recommended_actions"]] == ["A1", "A2"]


def test_quotes_are_checked_against_the_source():
    sources = [SourcePages("S1", "a.txt", ["Nothing here.", "As of 28 September, 42 hospitals in five states have reported disruption."])]
    sheet = {"key_facts": [
        {"id": "F1", "source_id": "S1", "page": 1, "quote": "42 hospitals in five states have reported disruption"},
        {"id": "F2", "source_id": "S1", "page": 1, "quote": "As of 28 September, 42 hospitals in 5 states have reported disruption"},
        {"id": "F3", "source_id": "S1", "page": 1, "quote": "Attackers demand payment in cryptocurrency"},
    ]}
    factsheet.verify_quotes(sheet, sources)
    found = [(f["quote_found"], f["page"]) for f in sheet["key_facts"]]
    assert found == [("exact", 2), ("close", 2), ("no", 1)]


def test_mock_fact_sheet_for_sample_is_fully_grounded():
    sheet = factsheet.build_fact_sheet(sample_sources())
    assert sheet["key_facts"], "expected facts"
    assert all(f["quote_found"] == "exact" for f in sheet["key_facts"])
    assert sheet["indicators"]["cves"] == ["CVE-2026-XXXXX"]
    text = factsheet.fact_sheet_for_prompt(sheet)
    assert "F1: " in text and "A1: " in text and "203.0.113.45" in text
