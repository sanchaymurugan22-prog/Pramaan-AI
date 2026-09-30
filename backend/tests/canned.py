"""Fixed ("canned") answers, used only as test data.

They were the mock AI's answers before the mock became source-aware (app/ai/mock_ai.py). Tests of
the checks and the exporters use them as a known, stable output to check against, together with
samples/sample-ransomware-report.txt (the quotes really appear in that file). `canned_ai()` makes
the AI return them, for tests that need exactly these texts through the whole app.
"""

import copy
from contextlib import contextmanager

import pytest

MOCK_REPLIES: dict[str, dict] = {
    "factsheet": {
        "summary": (
            "A ransomware group called NightLedger is encrypting patient-record and billing systems at "
            "hospitals after entering through an unpatched remote-access gateway. By 28 September 2026, "
            "42 hospitals in five states had reported disruption."
        ),
        "severity": "high",
        "key_facts": [
            {
                "id": "F1",
                "text": "A ransomware group called NightLedger is encrypting patient-record and billing systems at hospitals.",
                "page": 1,
                "quote": 'A ransomware group calling itself "NightLedger" is encrypting patient-record and billing systems at hospitals.',
            },
            {
                "id": "F2",
                "text": "The attackers get in through an unpatched remote-access gateway, CVE-2026-XXXXX (sample).",
                "page": 1,
                "quote": "The attackers enter through an unpatched remote-access gateway, tracked here as CVE-2026-XXXXX (sample).",
            },
            {
                "id": "F3",
                "text": "By 28 September, 42 hospitals in five states had reported disruption.",
                "page": 1,
                "quote": "As of 28 September, 42 hospitals in five states have reported disruption",
            },
            {
                "id": "F4",
                "text": "Emergency care continued, but 11 hospitals used paper records for more than 48 hours.",
                "page": 1,
                "quote": "11 hospitals moved to paper records for more than 48 hours",
            },
            {
                "id": "F5",
                "text": "In three cases, backups on the same network were also encrypted.",
                "page": 1,
                "quote": "In three cases, backups kept on the same network were also encrypted",
            },
            {
                "id": "F6",
                "text": "The ransom note demands cryptocurrency within 72 hours and threatens to publish patient data.",
                "page": 1,
                "quote": "demands payment in cryptocurrency within 72 hours and threatens to publish stolen patient data",
            },
            {
                "id": "F7",
                "text": "About 1.2 million patient records may have been copied.",
                "page": 1,
                "quote": "About 1.2 million patient records may have been copied.",
            },
            {
                "id": "F8",
                "text": "Hospitals with offline backups recovered in under 2 days; the average was 4 days.",
                "page": 1,
                "quote": "Hospitals that had offline backups restored their systems in under 2 days.",
            },
        ],
        "dates": [
            {"date": "22 September 2026", "event": "First known exploitation of the gateway flaw"},
            {"date": "24 September 2026", "event": "First hospital reports encrypted billing servers"},
            {"date": "26 September 2026", "event": "Vendor publishes an emergency patch"},
            {"date": "28 September 2026", "event": "42 hospitals in five states report disruption"},
            {"date": "30 September 2026", "event": "Report issued"},
        ],
        "entities": [
            {"name": "NightLedger", "type": "group"},
            {"name": "Regional Cyber Coordination Cell", "type": "organisation"},
            {"name": "Remote-access gateway", "type": "product"},
        ],
        "recommended_actions": [
            "Apply the vendor's September patch to every remote-access gateway today.",
            "Block the two listed addresses at the network edge and review connection logs since 22 September.",
            "Reset administrator passwords and turn on two-step login for all remote access.",
            "Keep at least one backup offline and test that one restore works end to end.",
            "Report any sign of infection to the national cyber incident response team within 6 hours.",
            "Do not pay the ransom.",
        ],
    },
    "x_thread": {
        "tweets": [
            {
                "text": "Alert: a ransomware group is locking patient-record and billing systems at hospitals. 42 hospitals in five states have reported disruption since 22 September.",
                "fact_ids": ["F1", "F3"],
            },
            {
                "text": "The attackers get in through remote-access gateways that are missing the vendor's September update. A patch has been available since 26 September.",
                "fact_ids": ["F2"],
            },
            {
                "text": "Hospitals with offline backups recovered in under 2 days. Keep one backup offline and test it.",
                "fact_ids": ["F8", "A4"],
            },
            {
                "text": "Hospital IT teams: patch every gateway today, reset admin passwords, and report any sign of infection within 6 hours. #CyberSecurity",
                "fact_ids": ["A1", "A3", "A5"],
            },
        ]
    },
    "linkedin_post": {
        "paragraphs": [
            {
                "text": "42 hospitals in five states have reported ransomware disruption since 22 September 2026.",
                "fact_ids": ["F3"],
            },
            {
                "text": "The attackers enter through remote-access gateways that have not received the vendor's September update, then encrypt patient-record and billing systems. About 1.2 million patient records may have been copied.",
                "fact_ids": ["F1", "F2", "F7"],
            },
            {
                "text": "The lesson is clear: offline backups work. Hospitals that had them were back in under 2 days.",
                "fact_ids": ["F8"],
            },
            {
                "text": "Cyber hygiene is a leadership responsibility, not just an IT task.",
                "fact_ids": [],
            },
        ],
        "hashtags": ["CyberSecurity", "Ransomware", "HealthcareIT"],
    },
    "executive_summary": {
        "title": "Ransomware campaign against hospitals",
        "bottom_line": {
            "text": "A ransomware group is encrypting hospital patient-record and billing systems; 42 hospitals in five states are affected. Severity is high.",
            "fact_ids": ["F1", "F3"],
        },
        "key_points": [
            {"text": "Entry is through an unpatched remote-access gateway (CVE-2026-XXXXX, sample).", "fact_ids": ["F2"]},
            {"text": "11 hospitals ran on paper records for more than 48 hours; emergency care continued.", "fact_ids": ["F4"]},
            {"text": "About 1.2 million patient records may have been copied.", "fact_ids": ["F7"]},
            {"text": "Hospitals with offline backups recovered in under 2 days, against 4 days on average.", "fact_ids": ["F8"]},
        ],
        "actions_needed": [
            {"text": "Direct all hospitals to patch remote-access gateways today.", "fact_ids": ["A1"]},
            {"text": "Confirm every hospital keeps at least one tested offline backup this week.", "fact_ids": ["A4"]},
            {"text": "Reaffirm that no ransom is to be paid.", "fact_ids": ["A6"]},
        ],
    },
    "infographic": {
        "headline": "Ransomware is hitting hospitals",
        "subheadline": "Patch gateways and keep backups offline to recover fast.",
        "key_numbers": [
            {"value": "42", "label": "hospitals disrupted", "fact_ids": ["F3"]},
            {"value": "1.2 million", "label": "patient records at risk", "fact_ids": ["F7"]},
            {"value": "< 2 days", "label": "recovery with offline backups", "fact_ids": ["F8"]},
        ],
        "steps": [
            {"text": "Patch every remote-access gateway today", "fact_ids": ["A1"]},
            {"text": "Reset admin passwords, turn on two-step login", "fact_ids": ["A3"]},
            {"text": "Keep one backup offline and test it", "fact_ids": ["A4"]},
            {"text": "Report infections within 6 hours", "fact_ids": ["A5"]},
        ],
        "layout": "number_grid",
    },
    "advisory": {
        "title": "Ransomware campaign targeting hospital networks",
        "severity": "high",
        "overview": {
            "text": "A ransomware group called NightLedger is encrypting patient-record and billing systems at hospitals after entering through an unpatched remote-access gateway. As of 28 September 2026, 42 hospitals in five states have reported disruption.",
            "fact_ids": ["F1", "F2", "F3"],
        },
        "affected": [
            {"text": "Hospitals using the remote-access gateway without the vendor's September update.", "fact_ids": ["F2"]},
            {"text": "Patient-record and billing systems.", "fact_ids": ["F1"]},
        ],
        "description": {
            "text": "The flaw was first exploited on 22 September 2026. The attackers copy data out before encrypting files, and in three cases backups on the same network were also encrypted. The ransom note demands cryptocurrency within 72 hours.",
            "fact_ids": ["F5", "F6"],
        },
        "impact": {
            "text": "About 1.2 million patient records may have been copied. 11 hospitals used paper records for more than 48 hours.",
            "fact_ids": ["F7", "F4"],
        },
        "recommendations": [
            {"text": "Apply the vendor's September patch to every remote-access gateway today.", "fact_ids": ["A1"]},
            {"text": "Block the listed addresses at the network edge and review connection logs since 22 September.", "fact_ids": ["A2"]},
            {"text": "Reset administrator passwords and turn on two-step login for all remote access.", "fact_ids": ["A3"]},
            {"text": "Keep at least one backup offline and test a full restore.", "fact_ids": ["A4"]},
            {"text": "Report any sign of infection to the national cyber incident response team within 6 hours.", "fact_ids": ["A5"]},
            {"text": "Do not pay the ransom.", "fact_ids": ["A6"]},
        ],
    },
    "presentation": {
        "title": "Ransomware attack on hospital networks",
        "slides": [
            {
                "title": "What happened",
                "bullets": [
                    "NightLedger ransomware is encrypting hospital systems",
                    "42 hospitals in five states disrupted",
                    "First exploited on 22 September 2026",
                ],
                "speaker_notes": "Since 22 September a ransomware group has been attacking hospitals. By 28 September, 42 hospitals in five states had reported disruption.",
                "fact_ids": ["F1", "F3"],
            },
            {
                "title": "How they get in",
                "bullets": [
                    "Unpatched remote-access gateway (CVE-2026-XXXXX, sample)",
                    "Data copied out before encryption",
                    "Backups on the same network also encrypted",
                ],
                "speaker_notes": "The entry point is a remote-access gateway missing the September update. In three cases the attackers also encrypted backups kept on the same network.",
                "fact_ids": ["F2", "F5"],
            },
            {
                "title": "Impact",
                "bullets": [
                    "About 1.2 million patient records may be copied",
                    "11 hospitals on paper records for 48+ hours",
                    "Offline backups: recovery in under 2 days",
                ],
                "speaker_notes": "The biggest risk is the copied patient data. Hospitals with offline backups recovered much faster than the 4-day average.",
                "fact_ids": ["F7", "F4", "F8"],
            },
            {
                "title": "What to do now",
                "bullets": [
                    "Patch every gateway today",
                    "Reset admin passwords, enable two-step login",
                    "Keep one tested backup offline",
                    "Report infections within 6 hours",
                ],
                "speaker_notes": "These four steps close the entry point and make recovery fast. Do not pay the ransom.",
                "fact_ids": ["A1", "A3", "A4", "A5"],
            },
        ],
    },
    "video_package": {
        "title": "Ransomware is hitting hospitals: what to do",
        "scenes": [
            {
                "visual": "A hospital billing screen turns red with a lock icon.",
                "on_screen_text": "42 hospitals disrupted",
                "narration": "Since 22 September, a ransomware group has disrupted 42 hospitals in five states.",
                "fact_ids": ["F3"],
            },
            {
                "visual": "Animated door labelled 'gateway' left open.",
                "on_screen_text": "Unpatched gateways are the way in",
                "narration": "The attackers get in through remote-access gateways that are missing the September update.",
                "fact_ids": ["F2"],
            },
            {
                "visual": "Stack of patient files flying out of a server.",
                "on_screen_text": "1.2 million records at risk",
                "narration": "About 1.2 million patient records may have been copied.",
                "fact_ids": ["F7"],
            },
            {
                "visual": "Checklist ticking off: patch, passwords, offline backup.",
                "on_screen_text": "Patch. Reset. Back up offline.",
                "narration": "Patch every gateway today, reset admin passwords, and keep one backup offline. Hospitals that did recovered in under 2 days.",
                "fact_ids": ["A1", "A3", "A4", "F8"],
            },
        ],
    },
}


def reply(kind: str) -> dict:
    """The canned answer for one kind of request (a copy, so callers can change it safely)."""
    if kind not in MOCK_REPLIES:
        raise KeyError(f"No mock answer for '{kind}'")
    return copy.deepcopy(MOCK_REPLIES[kind])


def canned_answer(kind: str, messages: list[dict]) -> dict:
    return reply(kind)


@contextmanager
def canned_ai():
    """While active, the mock AI gives the fixed answers above instead of building them from the source."""
    from app.ai import mock_ai

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(mock_ai, "answer", canned_answer)
        yield
