"""v1.2: helpline numbers in translations. "Report cyber fraud on 1930" became "... in (the year) 1930" in
Hindi, Bengali and Tamil. Helpline numbers now get "helpline number" in front before translating, and the
translation check flags a helpline number that no longer reads as one."""

import pytest

from app.lang import helplines, translate
from tests.test_translations import by, job_in, operator

# Real IndicTrans2 answers (2 Oct 2026). Without "helpline number" in front: a year or a date.
AS_A_YEAR = {
    "hi": "1930 में साइबर धोखाधड़ी की रिपोर्ट करें।",
    "bn": "1930 সালে সাইবার জালিয়াতির রিপোর্ট করুন।",
    "ta": "1930 இல் சைபர் மோசடிகளைப் புகாரளிக்கவும்.",
    "ur": "1930 میں سائبر فراڈ کی اطلاع دیں۔",
    "or": "1930 ମସିହାରେ ସାଇବର ଠକେଇ ବିଷଯ଼ରେ ରିପୋର୍ଟ କରନ୍ତୁ।",
    "ne": "सन् 1930 मा साइबर धोखाधडीको रिपोर्ट गर्नुहोस्।",
    "sa": "इदानीं 1930 तमे वर्षे काल् करोतु।",  # "call in the year 1930": a call word, but also "year"
}
# ... and with it: a phone number in every language
AS_A_PHONE = {
    "hi": "हेल्प लाइन नंबर 1930 पर साइबर धोखाधड़ी की रिपोर्ट करें।",
    "bn": "1930 নম্বরের হেল্পলাইনে সাইবার জালিয়াতির খবর দিন।",
    "ta": "சைபர் மோசடிகளை ஹெல்ப்லைன் எண் 1930 இல் புகாரளிக்கவும்.",
    "te": "సైబర్ మోసాలను హెల్ప్లైన్ నంబర్ 1930లో నివేదించండి.",
    "mr": "हेल्पलाईन क्रमांक 1930 वर सायबर फसवणुकीची तक्रार करा.",
    "ur": "ہیلپ لائن نمبر 1930 پر سائبر فراڈ کی اطلاع دیں۔",
    "gu": "હેલ્પલાઈન નંબર 1930 પર સાયબર છેતરપિંડીની જાણ કરો.",
    "kn": "ಸೈಬರ್ ವಂಚನೆಯನ್ನು ಸಹಾಯವಾಣಿ ಸಂಖ್ಯೆ 1930ರಲ್ಲಿ ವರದಿ ಮಾಡಿ.",
    "or": "ହେଲ୍ପଲାଇନ୍ ନମ୍ବର 1930 ରେ ସାଇବର ଠକେଇ ରିପୋର୍ଟ କରନ୍ତୁ।",
    "ml": "1930 എന്ന ഹെൽപ്പ് ലൈൻ നമ്പറിൽ സൈബർ തട്ടിപ്പുകൾ റിപ്പോർട്ട് ചെയ്യുക.",
    "pa": "ਹੈਲਪਲਾਈਨ ਨੰਬਰ 1930 ਉੱਤੇ ਸਾਈਬਰ ਧੋਖਾਧਡ਼ੀ ਦੀ ਰਿਪੋਰਟ ਕਰੋ।",
    "as": "হেল্পলাইন নম্বৰ 1930-ত চাইবাৰ জালিয়াতিৰ প্ৰতিবেদন দিয়ক।",
    "sat": "ᱦᱮᱞᱯᱞᱟᱭᱤᱱ ᱱᱚᱢᱵᱚᱨ 1930 ᱨᱮ ᱥᱟᱭᱵᱟᱨ ᱯᱷᱨᱳᱰ ᱨᱮᱭᱟᱜ ᱰᱚᱜᱚᱨ ᱮᱢ ᱢᱮ ᱾",
    "mni": "ꯂꯥꯏꯞꯂꯥꯏꯟ ꯅꯝꯕꯔ 1930ꯗ ꯁꯥꯏꯕꯔ ꯐ ꯭ ꯔꯣꯗꯀꯤ ꯄꯥꯎꯗꯝ ꯇꯧ ꯫",
    "sa": "1930 इति हेल्प्लैन्-सङ्ख्यायां सैबर्-कपटस्य विवरणं ददातु।",
}
ENGLISH = "Report cyber fraud on 1930."


@pytest.mark.parametrize("text, numbers, clarified", [
    ("Report cyber fraud on 1930.", ["1930"], "Report cyber fraud on helpline number 1930."),
    ("Call 1930 now.", ["1930"], "Call helpline number 1930 now."),
    ("Call 112 in an emergency.", ["112"], "Call helpline number 112 in an emergency."),
    ("Report it on 1930 or at cybercrime.gov.in.", ["1930"], "Report it on helpline number 1930 or at cybercrime.gov.in."),
    ("Contact 155260 or 1930.", ["155260", "1930"], "Contact helpline number 155260 or helpline number 1930."),
    # already clear: unchanged
    ("Call the national cyber crime helpline 1930 within one hour.", ["1930"], None),
    ("Dial 1800-11-4949 toll free.", ["1800-11-4949"], None),
    ("Report to 1930 helpline.", ["1930"], None),
    # not phone numbers: unchanged
    ("The attack hit 100 servers on 100 sites.", [], None),
    ("Over 112 hospitals and 1930 records since 1930.", [], None),
])
def test_helpline_numbers_get_a_word_before_translating(text, numbers, clarified):
    assert helplines.numbers(text) == numbers
    assert helplines.clarify(text) == (clarified or text)


@pytest.mark.parametrize("code", sorted(AS_A_YEAR))
def test_a_helpline_read_as_a_year_is_found(code):
    assert helplines.not_read_as_phone(ENGLISH, AS_A_YEAR[code]) == ["1930"]


@pytest.mark.parametrize("code", sorted(AS_A_PHONE))
def test_a_helpline_kept_as_a_phone_number_is_not_flagged(code):
    assert helplines.not_read_as_phone(ENGLISH, AS_A_PHONE[code]) == []


def test_every_engine_gets_the_clear_english(monkeypatch):
    sent = []
    monkeypatch.setattr(translate, "mock_translation", lambda text, lang: sent.append(text) or text)
    translate.translate_texts([ENGLISH, "Patch the gateway."], "bn")
    assert sent == ["Report cyber fraud on helpline number 1930.", "Patch the gateway."]


def test_the_translation_check_flags_it():
    """A translation that turned the helpline into a year is flagged on its line, with a warning."""
    job = job_in(["hi"], outputs=("x_thread",))
    english = by(job, "x_thread", "en")
    operator.put(f"/api/jobs/{job['id']}/outputs/{english['id']}",
                 json={"fields": [{"path": ["tweets", 0, "text"], "text": ENGLISH}]})
    from tests.test_jobs_api import wait_for
    hindi = by(wait_for(job["id"]), "x_thread", "hi")
    assert "helpline number 1930" in hindi["content"]["tweets"][0]["text"]  # what the engine was given
    assert not hindi["quality"]["translation"]["helplines"]

    edited = operator.put(f"/api/jobs/{job['id']}/outputs/{hindi['id']}",
                          json={"fields": [{"path": ["tweets", 0, "text"], "text": AS_A_YEAR["hi"]}]}).json()
    quality = by(edited, "x_thread", "hi")["quality"]
    assert quality["translation"]["helplines"] == [{"label": quality["sentences"][0]["label"], "number": "1930"}]
    flags = [f for s in quality["sentences"] for f in s["not_in_source"]]
    assert {"kind": "translation", "label": "Helpline number read as a year?", "text": "1930"} in flags
    assert quality["warnings"][0].startswith("Helpline number 1930 may have been translated as a year")


def test_the_alert_preview_flags_it(monkeypatch):
    monkeypatch.setattr(translate, "mock_translation", lambda text, lang: AS_A_YEAR["hi"])
    response = operator.post("/api/alerts/preview", json={"message": ENGLISH, "languages": ["hi"]})
    assert response.status_code == 200, response.text
    assert response.json()["languages"][0]["changed"] == ["1930 (helpline number read as a year?)"]
