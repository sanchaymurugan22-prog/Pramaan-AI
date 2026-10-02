"""Stage 8 part 3: exports in Indian scripts. Noto fonts for every script (with the Latin fonts behind them),
shaping (conjuncts, vowel signs, joined Arabic letters), right to left for Urdu / Kashmiri / Sindhi, and the
fixed words of every file in the output's language (labels.json)."""

import io
import zipfile

import pytest
from PIL import Image
from pypdf import PdfReader

from app.exporters import fonts, shaped
from app.lang import languages
from app.lang.labels import L, _table, keys
from tests.auth_helpers import signed_in_client
from tests.helpers import SAMPLE_REPORT
from tests.test_jobs_api import wait_for

operator = signed_in_client("operator", "scripts.operator")


@pytest.mark.parametrize("code", languages.INDIAN)
def test_every_language_has_fonts_for_all_its_labels(code):
    """Every label of every language is drawn without a single missing glyph (an empty box)."""
    table = _table()[code]
    # a label the translator got wrong (another script, a lost placeholder) stays in English: only a few
    assert set(table) <= set(keys()) and len(table) >= 0.9 * len(keys()), (code, set(keys()) - set(table))
    assert not any(languages.foreign_scripts(text, code) for text in table.values())
    for role, weight in (("body", "regular"), ("heading", "bold")):
        chain = fonts.font_chain(role, weight, code)
        assert all(path.exists() for path in chain)
        for text in table.values():
            glyphs, _ = shaped.shape(text.format(record_no="PRM-2026-000001", job_id=12, page=3, date="1 Oct",
                                                 tlp="TLP:GREEN", url="http://x", count=4, seconds=60, number=2, n=3,
                                                 title="T", job_title="J"), chain, languages.get(code).rtl)
            assert all(g.gid != 0 for g in glyphs), (code, text)


def test_shaping_joins_letters():
    chain = fonts.font_chain("body", "regular", "hi")
    glyphs, _ = shaped.shape("क्ष", chain)
    assert len(glyphs) < 3  # क + ् + ष become one conjunct
    tamil = fonts.font_chain("body", "regular", "ta")
    glyphs, _ = shaped.shape("கொ", tamil)  # the vowel sign ொ is drawn on both sides of க
    assert len(glyphs) == 3 and glyphs[0].gid != glyphs[-1].gid


def test_a_word_never_uses_two_fonts():
    tamil = fonts.font_chain("body", "regular", "ta")
    runs = shaped.font_runs("இங்கே CVE-2026-XXXXX (மாதிரி) 28ஆம் தேதி", tamil)
    assert runs == [("இங்கே ", 0), ("CVE-2026-XXXXX ", 1), ("(மாதிரி) 28ஆம் தேதி", 0)]


def test_right_to_left_order():
    assert shaped.visual_words(["یہاں", "CVE-2026", "42", "اسپتال"]) == ["اسپتال", "CVE-2026", "42", "یہاں"]
    urdu = fonts.font_chain("body", "regular", "ur")
    pieces = shaped.visual_runs("کام #2 · Incident", urdu, True)
    assert pieces[-1][0].strip() == "کام" and pieces[0][0].startswith("#2")


def test_labels():
    assert L("Overview", "en") == "Overview"
    assert L("Overview", "hi") == "अवलोकन"
    assert L("Job #{job_id}", "hi", job_id=7) == "कार्य #7" and L("May", "hi") == "मई"
    assert L("Do these {n} things now", "ta", n=4).count("4") == 1
    assert L("Not a label", "ta") == "Not a label"


@pytest.fixture(scope="module")
def job():
    response = operator.post("/api/jobs", data={
        "text": SAMPLE_REPORT.read_text(encoding="utf-8"),
        "outputs": ["advisory", "presentation", "infographic", "x_thread"], "languages": ["ta", "ur"]})
    assert response.status_code == 201, response.text
    done = wait_for(response.json()["id"])
    assert done["status"] == "ready"
    return done


def download(job, output_type, language, fmt) -> bytes:
    output = next(o for o in job["outputs"] if o["type"] == output_type and o["language"] == language)
    response = operator.get(f"/api/jobs/{job['id']}/outputs/{output['id']}/download", params={"format": fmt})
    assert response.status_code == 200, response.text
    return response.content


def test_pdf_embeds_the_script_fonts(job):
    for code, script_font in (("ta", "NotoSansTamil"), ("ur", "NotoNaskhArabic")):
        pdf = PdfReader(io.BytesIO(download(job, "advisory", code, "pdf")))
        names = {str(f.get("/BaseFont")) for page in pdf.pages for f in page["/Resources"]["/Font"].values()}
        fonts_used = {name.split("+")[-1] for name in names}
        assert any(script_font in n for n in fonts_used), (code, fonts_used)
        assert any("Hind" in n or "Poppins" in n for n in fonts_used)  # Latin letters and digits


def test_word_and_powerpoint_name_the_script_fonts(job):
    with zipfile.ZipFile(io.BytesIO(download(job, "advisory", "ta", "docx"))) as z:
        xml = z.read("word/document.xml").decode()
    assert 'w:cs="Noto Sans Tamil"' in xml and 'w:ascii="Hind"' in xml and "<w:szCs " in xml
    assert "பாதுகாப்பு ஆலோசனை" in xml or "ஆலோசனை" in xml  # the translated label
    with zipfile.ZipFile(io.BytesIO(download(job, "advisory", "ur", "docx"))) as z:
        xml = z.read("word/document.xml").decode()
    assert "<w:bidi/>" in xml and "<w:rtl/>" in xml and 'w:cs="Noto Naskh Arabic"' in xml
    with zipfile.ZipFile(io.BytesIO(download(job, "presentation", "ur", "pptx"))) as z:
        slide = z.read("ppt/slides/slide1.xml").decode()
    assert 'typeface="Noto Naskh Arabic"' in slide and 'rtl="1"' in slide


def test_infographic_png_in_tamil_and_urdu(job):
    for code in ("ta", "ur"):
        image = Image.open(io.BytesIO(download(job, "infographic", code, "png")))
        assert image.size == (1080, 1350)
        assert len(image.convert("L").getcolors(65536) or []) > 50  # really drawn, not blank
    text = download(job, "x_thread", "ur", "txt").decode()
    assert L("AI-assisted · pending human approval", "ur") in text
