"""Clock times ("14:00", "2 pm") and time ranges ("10:00 to 14:00") are ONE value everywhere: in the
"Not in source" check, the consistency panel and the quality score. Before this fix "14:00 security
updates" was read as the number 14 and the number "00 security"."""

import pytest

from app.pipeline import checks
from app.pipeline.values import KnownValues, find_values
from tests.helpers import SAMPLE_REPORT
from tests.test_mock_and_source_checks import run_job

INJECTION = (SAMPLE_REPORT.parent / "sample-injection.txt").read_bytes()
SOURCE = ("The staff email service will be unavailable on Saturday, 4 October 2026, from 10:00 to 14:00 "
          "while security updates are installed. Please sign out before 10:00.")


def values(text: str) -> list[tuple[str, str]]:
    return [(v.kind, v.text) for v in find_values(text)]


# ---- 1. finding times ----------------------------------------------------------------------------------


def test_a_clock_time_is_one_value_not_two_numbers():
    assert values("Restart at 14:00 security updates follow.") == [("time", "14:00")]


def test_a_time_range_is_one_value():
    [value] = find_values("from 10:00 to 14:00 while")
    assert (value.kind, value.text) == ("time", "10:00 to 14:00")
    assert value.keys == {"10:00-14:00"} and value.ends == ("10:00", "14:00")
    for joined in ("10:00-14:00", "10:00 – 14:00", "10:00 until 14:00", "10 am to 2 pm"):
        [value] = find_values(joined)
        assert value.keys == {"10:00-14:00"}, joined


@pytest.mark.parametrize("text, key", [
    ("14:00", "14:00"), ("09:30", "9:30"), ("9:30", "9:30"), ("2 pm", "14:00"), ("2:00 p.m.", "14:00"),
    ("10.30 am", "10:30"), ("12 am", "0:00"), ("12 pm", "12:00"), ("23:59:59", "23:59:59"),
])
def test_times_written_in_different_ways(text, key):
    [value] = find_values(f"It happens at {text} today")
    assert value.kind == "time" and value.keys == {key}


def test_things_that_are_not_times():
    assert values("1.25 million records; version 1.2.3") == [("number", "1.25 million"), ("number", "1.2.3")]
    assert values("See 22/09/2026 and 2026-09-22.") == [("date", "22/09/2026"), ("date", "2026-09-22")]
    # an impossible clock is still one value, never "25" and "00"
    assert values("at 25:00 hours") == [("time", "25:00")]


# ---- 2. "Not in source" ---------------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Down from 10:00 to 14:00.", "Down 10:00-14:00.", "Down from 10 am to 2 pm.", "Back after 14:00.",
    "Sign out before 10:00.",
])
def test_times_from_the_source_are_not_flagged(text):
    known = KnownValues([SOURCE])
    assert [v.text for v in find_values(text) if known.missing(v)] == []


@pytest.mark.parametrize("text, flagged", [
    ("Down from 10:00 to 15:00.", "10:00 to 15:00"), ("Back after 15:00.", "15:00"), ("Back at 3 pm.", "3 pm"),
])
def test_times_not_in_the_source_are_flagged(text, flagged):
    known = KnownValues([SOURCE])
    assert [v.text for v in find_values(text) if known.missing(v)] == [flagged]


def test_a_range_is_known_when_the_source_gives_both_times_separately():
    known = KnownValues(["Work starts at 10:00. It ends at 14:00."])
    [value] = find_values("from 10:00 to 14:00")
    assert not known.missing(value)


# ---- 3. sentences, consistency and the score ---------------------------------------------------------

SHEET = {
    "summary": "", "entities": [], "dates": [], "recommended_actions": [], "indicators": {},
    "key_facts": [
        {"id": "F1", "text": "The staff email service will be unavailable on 4 October 2026 from 10:00 to 14:00.",
         "quote": "unavailable on Saturday, 4 October 2026, from 10:00 to 14:00", "quote_found": "exact",
         "source_id": "S1", "page": 1},
    ],
}


def check(text: str) -> dict:
    content = {"tweets": [{"text": text, "fact_ids": ["F1"]}]}
    return checks.check_output("x_thread", content, SHEET, KnownValues([SOURCE]))


def consistency(*texts: str) -> dict:
    outputs = [{"id": n, "type": "x_thread", "label": f"Output {n}", "sentences": check(text)["sentences"]}
               for n, text in enumerate(texts, start=1)]
    return checks.check_consistency(SHEET, outputs)


def test_a_sentence_with_a_time_range_scores_full_points_for_values():
    quality = check("The staff email service is unavailable on 4 October 2026 from 10:00 to 14:00.")
    assert quality["not_in_source"] == []
    assert quality["score_parts"]["values"]["points"] == quality["score_parts"]["values"]["max"]
    assert quality["sentences"][0]["status"] == "linked"


def test_a_wrong_time_costs_points():
    right = check("The staff email service is unavailable from 10:00 to 14:00.")
    wrong = check("The staff email service is unavailable from 10:00 to 15:00.")
    assert [f["text"] for f in wrong["not_in_source"]] == ["10:00 to 15:00"]
    assert wrong["score"] < right["score"]


def test_outputs_that_give_the_same_range_agree():
    result = consistency("The email service is unavailable from 10:00 to 14:00.",
                         "Email service down 10:00-14:00 on 4 October 2026.")
    assert result["ok"]
    assert ("F1", "10:00 to 14:00") in {(a["fact_id"], a["value"]) for a in result["agreed"]}
    assert all("00" != a["value"].split()[0] for a in result["agreed"])


def test_one_end_of_the_range_agrees_with_it():
    assert consistency("The email service is unavailable until 14:00.")["ok"]


def test_a_different_time_for_the_same_fact_is_a_mismatch():
    result = consistency("The email service is unavailable from 10:00 to 14:00.",
                         "The email service is unavailable from 10:00 to 16:00.")
    [mismatch] = result["mismatches"]
    assert (mismatch["what"], mismatch["found"], mismatch["expected"]) == ("time", "10:00 to 16:00", ["10:00 to 14:00"])


def test_the_maintenance_sample_never_shows_00_security():
    """The whole job, with the mock AI: no "00 ..." number anywhere on the Results page."""
    job = run_job(INJECTION, "sample-injection.txt", ["x_thread", "linkedin_post", "advisory", "executive_summary"])
    shown = [a["value"] for a in job["consistency"]["agreed"]]
    shown += [m["found"] for m in job["consistency"]["mismatches"]]
    for out in job["outputs"]:
        shown += [f["text"] for f in out["quality"]["not_in_source"]]
    assert not any(value.startswith("00") for value in shown), shown
    assert job["consistency"]["ok"]
    for out in job["outputs"]:
        assert not any(f["kind"] == "time" for f in out["quality"]["not_in_source"]), out["type"]
