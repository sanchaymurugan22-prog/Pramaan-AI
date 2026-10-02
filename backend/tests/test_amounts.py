"""v1.2: "1.2 million" -> "12 लाख" is correct, not "Changed in translation". Big numbers written with words
(million, lakh, crore, thousand, billion, in every script) are compared by value."""

import pytest

from app.lang.amounts import amounts
from app.pipeline.translation import compare_values
from tests.test_translations import by, job_in, operator
from tests.test_jobs_api import wait_for

# Real IndicTrans2 translations (2 Oct 2026): the same values, written the Indian way
SAME = [
    ("1.2 million patient records may be exposed.", "12 लाख रोगी रिकॉर्ड उजागर हो सकते हैं।"),            # hi
    ("1.2 million patient records may be exposed.", "12 লক্ষ রোগীর রেকর্ড উন্মোচিত হতে পারে।"),          # bn
    ("1.2 million patient records may be exposed.", "12 லட்சம் நோயாளிகளின் பதிவுகள் அம்பலப்படுத்தப்படலாம்."),  # ta
    ("1.2 million patient records may be exposed.", "12 లక్షల మంది రోగుల రికార్డులు బహిర్గతం కావచ్చు."),  # te
    ("1.2 million patient records may be exposed.", "12 لاکھ مریضوں کے ریکارڈ بے نقاب ہو سکتے ہیں۔"),     # ur
    ("1.2 million patient records may be exposed.", "12 ਲੱਖ ਮਰੀਜ਼ਾਂ ਦੇ ਰਿਕਾਰਡ ਬੇਨਕਾਬ ਹੋ ਸਕਦੇ ਹਨ।"),       # pa
    ("1.2 million patient records may be exposed.", "12 ലക്ഷം രോഗികളുടെ രേഖകൾ തുറന്നുകാട്ടപ്പെടാം."),     # ml
    ("1.2 million patient records may be exposed.", "12 लक्षा: रोगिनः अभिलेखा: उद्घाटिता: भवितुम् अर्हन्ति।"),  # sa
    ("1.2 million patient records may be exposed.", "ꯑꯅꯥꯕ ꯂꯥꯈ 12ꯒꯤ ꯔꯦꯀꯣꯔ ꯭ ꯗꯁꯤꯡ ꯎꯠꯄ ꯌꯥꯏ ꯫"),           # mni: word first
    ("1.2 million patient records may be exposed.", "1.2 मिलियन रोगी रिकॉर्ड"),                           # kept as million
    ("The fraud cost 35 crore rupees.", "धोखाधड़ी में 35 करोड़ रुपये खर्च हुए।"),
    ("The fraud cost 35 crore rupees.", "ਇਸ ਧੋਖਾਧਡ਼ੀ ਦੀ ਕੀਮਤ 35 ਕਰੋਡ਼ ਰੁਪਏ ਸੀ।"),                      # ੜ written ਡ਼
    ("About 250 thousand users and 3 billion requests.", "लगभग 250 हजार उपयोगकर्ता और 3 अरब अनुरोध।"),
    ("About 250 thousand users and 3 billion requests.", "ഏകദേശം 250,000 ഉപയോക്താക്കളും 3 ബില്യൺ അഭ്യർത്ഥനകളും."),
    ("About 250 thousand users and 3 billion requests.", "சுமார் 250 ஆயிரம் பயனர்கள் மற்றும் 3 பில்லியன் கோரிக்கைகள்."),
    ("Losses reached 12 lakh rupees.", "ನಷ್ಟವು 12 ಲಕ್ಷ ರೂಪಾಯಿಗಳನ್ನು ತಲುಪಿದೆ."),
    ("1,200,000 records", "12,00,000 रिकॉर्ड"),                                                           # Indian grouping
]
# ... and real changes, which must still be flagged
CHANGED = [
    ("1.2 million patient records", "1.2 ᱠᱳᱴᱤ ᱦᱚᱲ", ["1.2 million"], ["1.2 ᱠᱳᱴᱤ"]),               # crore, not million
    ("About 250 thousand users", "تقریبا 250 ملین کنزیومرز", ["250 thousand"], ["250 ملین"]),      # million, not thousand
    ("1.2 million records", "1.2 रिकॉर्ड", ["1.2 million"], ["1.2"]),                              # "million" lost
    ("12 lakh rupees", "13 लाख रुपये", ["12 lakh"], ["13 लाख"]),
]


@pytest.mark.parametrize("english, translated", SAME)
def test_lakh_crore_and_million_are_the_same_value(english, translated):
    assert compare_values(english, translated) == ([], [])


@pytest.mark.parametrize("english, translated, missing, extra", CHANGED)
def test_a_different_value_is_still_flagged(english, translated, missing, extra):
    assert compare_values(english, translated) == (missing, extra)


def test_amounts():
    assert [(v, w) for v, w, _ in amounts("1.2 million, 12 lakh, 35 crore, 2 bn and 12,00,000")] == [
        (1200000, "1.2 million"), (1200000, "12 lakh"), (350000000, "35 crore"), (2000000000, "2 bn"),
        (1200000, "12,00,000")]
    assert amounts("CVE-2026-1234 on 203.0.113.45 at 10:00, 42 hospitals since 2026") == []
    assert amounts("the mnemonic 3 mni") == []  # English words only as whole words


def test_no_false_alarm_in_a_job():
    """The bug as seen: an edited Hindi translation saying "12 लाख" for "1.2 million" has no warning."""
    job = job_in(["hi"], outputs=("x_thread",))
    english = by(job, "x_thread", "en")
    operator.put(f"/api/jobs/{job['id']}/outputs/{english['id']}",
                 json={"fields": [{"path": ["tweets", 0, "text"], "text": "1.2 million patient records may be exposed."}]})
    hindi = by(wait_for(job["id"]), "x_thread", "hi")
    edited = operator.put(f"/api/jobs/{job['id']}/outputs/{hindi['id']}",
                          json={"fields": [{"path": ["tweets", 0, "text"], "text": SAME[0][1]}]}).json()
    quality = by(edited, "x_thread", "hi")["quality"]
    assert quality["translation"]["changed"] == []
    assert not any(f["kind"] == "translation" for s in quality["sentences"] for f in s["not_in_source"])
    assert not any(w.startswith("Values changed in translation") for w in quality["warnings"])
