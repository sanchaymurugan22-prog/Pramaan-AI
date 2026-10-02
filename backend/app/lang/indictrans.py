"""AI4Bharat IndicTrans2 (English -> 22 Indian languages) on CTranslate2, fully offline (Stage 8).

The model (distilled 200M, MIT licence) is converted once to CTranslate2 8-bit by
scripts/convert-indictrans2.py and lives in models/indictrans2-en-indic-ct2 (about 0.3 GB of memory).

Before and after the model, the text is prepared exactly as AI4Bharat's own IndicTransToolkit does
(IndicProcessor, ported here so the heavy indic-nlp library is not needed):
  English in:  punctuation normalised; numbers, links and e-mail addresses swapped for <ID1>, <ID2> ...
               (so the model copies them instead of translating them); Moses tokenisation; then
               "eng_Latn hin_Deva <text>" and SentencePiece pieces.
  Indic out:   placeholders put back; the model writes most languages in Devanagari ("script
               unification"), so the text is converted to the target script (Tamil, Bengali ...) by
               Unicode offset; then the spaces around punctuation are tidied.
Pramaan adds one thing: the security values the checks care about (CVE ids, IP addresses, hashes, hidden
value placeholders like [PHONE-1], times like 10:00) are always protected the same way, and Indian digits
in the answer are written as 0-9, so every number and indicator survives unchanged.
"""

import re
import threading
from pathlib import Path

import regex

from app.lang.languages import Language

# --- English pre-processing (IndicProcessor._punc_norm, _wrap_with_placeholders) -------------------

_PUNC_REPLACEMENTS = [
    (regex.compile(r"\r"), ""),
    (regex.compile(r"\(\s*"), "("),
    (regex.compile(r"\s*\)"), ")"),
    (regex.compile(r"\s:\s?"), ":"),
    (regex.compile(r"\s;\s?"), ";"),
    (regex.compile(r"[`´‘‚’]"), "'"),
    (regex.compile(r"[„“”«»]"), '"'),
    (regex.compile(r"[–—]"), "-"),
    (regex.compile(r"\.\.\."), "..."),
    (regex.compile(r" %"), "%"),
    (regex.compile(r" [?!;]"), lambda m: m.group(0).strip()),
]
_MULTISPACE = regex.compile(r"[ ]{2,}")
_END_BRACKET_SPACE_PUNC = regex.compile(r"\) ([\.!:?;,])")
_DIGIT_SPACE_PERCENT = regex.compile(r"(\d) %")
_DOUBLE_QUOT_PUNC = regex.compile(r"\"([,\.]+)")
_DIGIT_NBSP_DIGIT = regex.compile(r"(\d) (\d)")

# Pramaan's own values first (the checks compare these with the source), then AI4Bharat's patterns.
_PROTECT = [
    regex.compile(r"\[[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+\]"),            # hidden-value placeholders [PHONE-1]
    regex.compile(r"\[[A-Za-z][A-Za-z .'-]{1,30}\]"),                 # public labels [phone number], [CVE id]
    regex.compile(r"\bCVE-\d{4}-[\dX]{4,}\b", regex.I),                # CVE ids (also sample ones)
    regex.compile(r"\b[0-9a-fA-F]{32,128}\b"),                         # file hashes
    regex.compile(r"\b\d{1,3}(?:\[?\.\]?\d{1,3}){3}\b"),               # IP addresses (also 1[.]2[.]3[.]4)
    regex.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # e-mail (AI4Bharat)
    regex.compile(r"\b(?<![\w/.])(?:(?:https?|ftp)://)?(?:(?:[\w-]+\.)+(?!\.))(?:[\w/\-?#&=%.]+)+(?!\.\w+)\b"),  # links
    regex.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),                    # times 10:00
    regex.compile(  # numbers with separators, ranges, percentages (AI4Bharat)
        r"(~?\d+\.?\d*\s?%?\s?-?\s?~?\d+\.?\d*\s?%|~?\d+%|\d+[-\/.,:']\d+[-\/.,:'+]\d+(?:\.\d+)?|\d+[-\/.:'+]\d+(?:\.\d+)?)"),
    regex.compile(r"[A-Za-z0-9]*[#|@]\w+"),                            # hashtags, handles (AI4Bharat)
]


def _punc_norm(text: str) -> str:
    for pattern, replacement in _PUNC_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    text = _MULTISPACE.sub(" ", text)
    text = _END_BRACKET_SPACE_PUNC.sub(r")\1", text)
    text = _DIGIT_SPACE_PERCENT.sub(r"\1%", text)
    text = _DOUBLE_QUOT_PUNC.sub(r'\1"', text)
    text = _DIGIT_NBSP_DIGIT.sub(r"\1.\2", text)
    return text.strip()


def protect(text: str) -> tuple[str, dict[str, str]]:
    """Swap values for <ID1>, <ID2> ... Returns the new text and {placeholder: value}."""
    found: dict[str, str] = {}
    for pattern in _PROTECT:
        for match in sorted(set(pattern.findall(text)), key=len, reverse=True):
            if not match or match in found.values():
                continue
            if len(match.replace(".", "").replace(" ", "").replace(":", "")) < 3 and not match.startswith("["):
                continue  # "4" or "a.m": short things the model copies by itself
            key = f"<ID{len(found) + 1}>"
            found[key] = match
            text = text.replace(match, key)
    return regex.sub(r"\s+", " ", text).strip(), found


# The model sometimes writes a placeholder back changed: "< ID1 >", "[ID1]", or "ID" spelt in the target
# script ("<आईडी1>", "<আইডি1>", "<آئی ڈی 1>", "<ഐ. ഡി. 1>"). Any short word in brackets followed by the
# placeholder's number is accepted, if the word is "ID" or is not written in Latin letters at all.
_PLACEHOLDER_ANY = re.compile(r"[<\[]([^<>\[\]\d]{0,24}?)\s*(\d{1,3})\s*[>\]]")


def restore(text: str, found: dict[str, str]) -> str:
    def put_back(match: re.Match) -> str:
        word = re.sub(r"[\s.\-]", "", match.group(1))
        is_id = word.upper() == "ID" or (0 < len(word) <= 8 and not re.search(r"[A-Za-z]", word))
        key = f"<ID{match.group(2)}>"
        return found[key] if is_id and key in found else match.group(0)

    return _PLACEHOLDER_ANY.sub(put_back, text)


# --- Indic post-processing (UnicodeIndicTransliterator, trivial_detokenize) -----------------------

_SCRIPT_START = {"Deva": 0x0900, "Beng": 0x0980, "Guru": 0x0A00, "Gujr": 0x0A80, "Orya": 0x0B00,
                 "Taml": 0x0B80, "Telu": 0x0C00, "Knda": 0x0C80, "Mlym": 0x0D00}


def _tamil_offset(offset: int) -> int:
    """Tamil has no separate voiced / aspirated plosives: use the plain ones (indic-nlp's rule)."""
    if 0x15 <= offset <= 0x28 and offset != 0x1C and not ((offset - 0x15) % 5 == 0 or (offset - 0x15) % 5 == 4):
        offset = 0x15 + 5 * ((offset - 0x15) // 5)
    if offset in (0x2B, 0x2C, 0x2D):
        offset = 0x2A
    if offset == 0x36:
        offset = 0x37
    return offset


def from_devanagari(text: str, script: str) -> str:
    """The model's Devanagari answer -> the target script (Brahmi scripts share one Unicode layout)."""
    if script not in _SCRIPT_START or script == "Deva":
        return text
    out = []
    for c in text:
        offset = ord(c) - 0x0900
        if 0 <= offset <= 0x6F and c not in "\u0964\u0965":  # not the danda
            if script == "Taml":
                offset = _tamil_offset(offset)
            c = chr(_SCRIPT_START[script] + offset)
        out.append(c)
    return "".join(out)


_LEFT_ATTACH = re.compile(r" ([!%)\]},.:;>?\u0964\u0965])")
_RIGHT_ATTACH = re.compile(r"([#$(\[{<@]) ")
_BOTH_ATTACH = re.compile(r" ([-/\\]) ")
_NUM_SEQ = re.compile(r"([0-9]+ [,.:/] )+[0-9]+")


def detokenize(text: str) -> str:
    text = _NUM_SEQ.sub(lambda m: m.group(0).replace(" ", ""), text)
    text = _BOTH_ATTACH.sub(r"\1", text)
    text = _LEFT_ATTACH.sub(r"\1", text)
    text = _RIGHT_ATTACH.sub(r"\1", text)
    for quote in "'\"`":  # quotes alternate: opening attaches right, closing attaches left
        parts, count = [], 0
        for c in text:
            if c == quote:
                parts.append("@RA" if count % 2 == 0 else "@LA")
                count += 1
            else:
                parts.append(c)
        text = "".join(parts).replace("@RA ", quote).replace(" @LA", quote).replace("@RA", quote).replace("@LA", quote)
    return text


_INDIC_DIGITS = {}
for start in (0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x06F0, 0x0660, 0x1C50, 0xABF0):
    for d in range(10):
        _INDIC_DIGITS[start + d] = str(d)


def ascii_digits(text: str) -> str:
    """Official documents use the international form of Indian numerals (0-9); it also keeps the checks exact."""
    return text.translate(_INDIC_DIGITS)


# IndicTrans2 learnt from text where ":" after a word had been turned into the visarga "ः" (it looks alike).
# After a vowel sign or anusvara, at the end of a word, it is always a colon ("चेतावनीः" -> "चेतावनी:");
# a real visarga follows a consonant ("अतः", "प्रातः") and is kept.
_VISARGA_COLON = re.compile(r"(?<=[\u0901\u0902\u093E-\u094C])\u0903(?=\s|$)")


def postprocess(text: str, lang: Language, found: dict[str, str]) -> str:
    text = _VISARGA_COLON.sub(":", text)  # in Devanagari, before any change of script
    if lang.script == "Arab":
        text = text.replace(" ؟", "؟").replace(" ۔", "۔").replace(" ،", "،").replace("ٮ۪", "ؠ")
    if lang.code == "or":
        text = text.replace("ଯ଼", "ୟ")
    text = from_devanagari(restore(text, found), lang.script)
    text = ascii_digits(detokenize(restore(text, found))).strip()
    # A hashtag or @name the model dropped (it often leaves out the last one) goes back at the end
    missing = [v for v in found.values() if v[:1] in "#@" and v not in text]
    return " ".join([text, *missing]).strip()


# --- the model -----------------------------------------------------------------------------------

class IndicTrans2:
    """Loaded once (about 0.3 GB) and kept; translate() is safe to call from several threads."""

    def __init__(self, folder: Path, threads: int = 4):
        import ctranslate2
        import sentencepiece
        from sacremoses import MosesPunctNormalizer, MosesTokenizer

        self.translator = ctranslate2.Translator(str(folder), device="cpu", inter_threads=1, intra_threads=threads)
        self.spm_src = sentencepiece.SentencePieceProcessor(model_file=str(folder / "model.SRC"))
        self.moses_norm, self.moses_tok = MosesPunctNormalizer(), MosesTokenizer(lang="en")
        self.lock = threading.Lock()  # one batch at a time: the model already uses every core

    def _source_tokens(self, sentence: str, lang: Language) -> tuple[list[str], dict[str, str]]:
        text, found = protect(_punc_norm(sentence))
        text = " ".join(self.moses_tok.tokenize(self.moses_norm.normalize(text), escape=False))
        return ["eng_Latn", lang.tag, *self.spm_src.encode(text, out_type=str), "</s>"], found

    def translate(self, sentences: list[str], lang: Language, beam_size: int = 4) -> list[str]:
        prepared = [self._source_tokens(s, lang) for s in sentences]
        with self.lock:
            results = self.translator.translate_batch(
                [tokens for tokens, _ in prepared], beam_size=beam_size, max_batch_size=16, max_decoding_length=256,
                repetition_penalty=1.0,
            )
        out = []
        for (_, found), result in zip(prepared, results):
            text = "".join(result.hypotheses[0]).replace("▁", " ").strip()  # as IndicTransTokenizer does
            out.append(postprocess(text, lang, found))
        return out
