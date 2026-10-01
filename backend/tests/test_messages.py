"""Stage 7 part 4: the "Is this real?" message checker. Exact match (also after WhatsApp-style changes),
changed copies with the changed words, unknown messages, and the rule-based scam signs."""

import json

import pytest

from app.db import SessionLocal
from app.signing import records
from app.signing.messages import check_message, scam_signs, similarity, word_diff
from tests.auth_helpers import signed_in_client
from tests.test_signing import approved_job

client = signed_in_client("operator", "message.operator")
admin = signed_in_client("admin", "message.admin")

SCAM = ("URGENT GOVT CYBER ALERT: Your hospital system is infected. Act within 1 hour or data will be deleted. "
        "Verify now at gov-alert-update.xyz and share the OTP sent to your phone.")


@pytest.fixture(scope="module")
def posts() -> dict:
    """A signed TLP:GREEN job; the published texts of its X thread and LinkedIn post."""
    job = approved_job(outputs=("x_thread", "linkedin_post"), tlp="GREEN")
    with SessionLocal() as db:
        public = json.loads(records.find_issue(db, job["record"]["record_no"]).public_manifest)
    texts = {t["label"]: t["text"] for t in public["texts"]}
    return {"record_no": job["record"]["record_no"], "post": texts["Post"], "tweet": texts["Post 2"], "job": job}


def check(text: str) -> dict:
    response = client.post("/api/check-message", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_an_exact_copy_is_genuine(posts):
    result = check(posts["post"])
    assert result["verdict"] == "genuine" and result["record_no"] == posts["record_no"]
    assert result["signs"] == [] and result["helpline"] == "Report cyber fraud: call 1930 or visit cybercrime.gov.in"
    assert check(posts["tweet"])["verdict"] == "genuine"  # one post of the thread on its own


def test_forwarding_changes_do_not_matter(posts):
    variants = [
        posts["post"].upper(),
        "  " + posts["post"].replace(" ", "   ").replace(".", " ") + "  ",
        "🚨 " + posts["post"] + " 🙏",
        posts["post"].replace(" ", " \u200b"),  # zero-width spaces
        posts["post"].replace("\n\n", "\n"),
    ]
    for variant in variants:
        assert check(variant)["verdict"] == "genuine", variant[:60]


def test_a_changed_copy_is_spotted_with_the_changed_words(posts):
    words = posts["post"].split()
    changed = " ".join(words[:8] + ["Pay", "the", "fine", "at", "bill-pay-now.in", "today."] + words[8:])
    result = check(changed)
    assert result["verdict"] == "changed" and result["record_no"] == posts["record_no"]
    assert result["similarity"] >= 0.5
    added = [d["text"] for d in result["diff"] if d["kind"] == "added"]
    assert added == ["Pay", "the", "fine", "at", "bill-pay-now.in", "today."]
    assert {s["kind"] for s in result["signs"]} >= {"unknown_link"}


def test_an_unknown_message_is_unverified(posts):
    result = check("The office canteen will be closed on Friday for cleaning.")
    assert result["verdict"] == "not_found" and result["record_no"] is None and result["signs"] == []


def test_a_scam_shows_why(posts):
    result = check(SCAM)
    assert result["verdict"] == "scam"
    signs = {s["kind"]: s for s in result["signs"]}
    assert set(signs) == {"asks_secret", "urgent", "unknown_link"}
    assert signs["unknown_link"]["detail"] == "gov-alert-update.xyz"
    assert signs["unknown_link"]["note"] == "made to look official"


def test_a_withdrawn_record_is_reported_as_withdrawn():
    job = approved_job(outputs=("linkedin_post",), tlp="CLEAR", title="Old helpline advisory")
    record_no = job["record"]["record_no"]
    with SessionLocal() as db:
        text = json.loads(records.find_issue(db, record_no).public_manifest)["texts"][0]["text"]
    admin.post(f"/api/admin/records/{record_no}/withdraw", json={"reason": "Helpline changed"})
    result = check(text)
    assert result["verdict"] == "withdrawn" and result["record_no"] == record_no


def test_a_restricted_record_matches_by_fingerprint_only():
    job = approved_job(outputs=("advisory",), tlp="AMBER", title="Restricted advisory for the message test")
    with SessionLocal() as db:
        manifest = json.loads(records.find_issue(db, job["record"]["record_no"]).manifest)
    # the internal text of the advisory (staff may paste it); only its fingerprint is published
    from app.signing.texts import output_texts
    from app.db import Output
    with SessionLocal() as db:
        output = db.get(Output, job["outputs"][0]["id"])
        [(label, text)] = output_texts(output.type, output.content_json)
    assert any(t["sha256"] for t in manifest["texts"])
    result = check(text)
    assert result["verdict"] == "genuine" and result["restricted"] is True and result["title"] is None


def test_an_empty_or_huge_message_is_refused():
    assert client.post("/api/check-message", json={"text": "   "}).status_code == 400
    assert client.post("/api/check-message", json={"text": "x" * 20_001}).status_code == 400


# ---- the rules on their own ---------------------------------------------------------------------


@pytest.mark.parametrize("text, kinds", [
    ("Share the OTP sent to your phone.", {"asks_secret"}),
    ("Never share your OTP or password with anyone.", set()),  # good advice, not a scam sign
    ("Do not pay the ransom.", set()),
    ("Pay now to avoid disconnection: 9876543210", {"asks_payment", "unknown_phone"}),
    ("Your SIM is blocked. Call +91 98765-43210 immediately.", {"urgent", "unknown_phone"}),
    ("Report fraud on 1930 or cybercrime.gov.in", set()),  # helpline and an official site
    ("Read the advisory at https://www.cert-in.org.in/advisory and download advisory.pdf", set()),
    ("Install the AnyDesk app so our officer can help", {"install_app"}),
    ("आपका खाता तुरंत बंद हो जाएगा। अपना ओटीपी बताएँ।", {"urgent", "asks_secret"}),
    ("Claim your refund at refunds-online.top", {"asks_payment", "unknown_link"}),
])
def test_scam_signs(text, kinds):
    assert {s["kind"] for s in scam_signs(text, [])} == kinds


def test_similarity_and_diff():
    a = "Patch your VPN gateway today and reset admin passwords."
    assert similarity(a, a) == 1.0
    assert similarity(a, "The canteen is closed on Friday.") < 0.2
    assert similarity("Patch your VPN gateway today", a) >= 0.5  # a cut-down copy
    diff = word_diff("Patch your VPN gateway tomorrow and reset admin passwords.", a)
    assert [(d["kind"], d["text"]) for d in diff if d["kind"] != "same"] == [("removed", "today"), ("added", "tomorrow")]


def test_check_message_on_its_own():
    published = [{"record_no": "PRM-2026-000009", "status": "replaced", "replaced_by": "PRM-2026-000010",
                  "title": "T", "restricted": False,
                  "texts": [{"sha256": "", "label": "Post", "output": "linkedin_post", "text": "Patch your VPN today."}]}]
    from app.signing.texts import text_hash
    published[0]["texts"][0]["sha256"] = text_hash("Patch your VPN today.")
    result = check_message("PATCH your VPN today!!! 🙏", published)
    assert result["verdict"] == "replaced" and result["replaced_by"] == "PRM-2026-000010"
