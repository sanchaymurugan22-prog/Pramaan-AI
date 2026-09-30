"""Source tracing: find WHERE in the source a piece of text is, so the web page can highlight it.

Used for every fact's quote, every recommended action and every date in the fact sheet. The result
is saved on the fact sheet item:

    source_id, page       where it is
    start, end            character positions in that page's text (the highlight), or None
    quote_found           exact  = the same words in the same order
                          close  = most of the words, in about the same order (the model changed a word or two)
                          no     = not found: the page shows it with a warning

Words are compared in lower case and punctuation is ignored, so "42 hospitals, in five" matches
"42 Hospitals in five". Also here: the small word helpers that checks.py uses to link each output
sentence to a fact.
"""

import re
from dataclasses import dataclass

WORD = re.compile(r"\w+")
CLOSE_ENOUGH = 0.7  # share of the quote's word pairs that must be found for a "close" match


@dataclass
class Located:
    source_id: str
    page: int          # 1 = first page
    start: int | None  # character positions in the page text (Python string positions)
    end: int | None
    found: str         # exact | close | no


def words_with_positions(text: str) -> list[tuple[str, int, int]]:
    """"Hello, World" -> [("hello", 0, 5), ("world", 7, 12)]"""
    return [(m.group().lower(), m.start(), m.end()) for m in WORD.finditer(text)]


def locate(quote: str, pages: list[tuple[str, int, str]], prefer: tuple[str, int] | None = None) -> Located:
    """Find `quote` in the pages. pages = [(source_id, page_number, page_text), ...].

    The page in `prefer` (the one the model named) is searched first, then all the others.
    """
    quote_words = [w for w, _, _ in words_with_positions(quote)]
    fallback_source, fallback_page = prefer or (pages[0][:2] if pages else ("S1", 1))
    if not quote_words or not pages:
        return Located(fallback_source, fallback_page, None, None, "no")

    ordered = sorted(pages, key=lambda p: (p[0], p[1]) != prefer)
    tokenised = [(source_id, number, words_with_positions(text)) for source_id, number, text in ordered]

    # 1. exact: the same words, one after another
    for source_id, number, tokens in tokenised:
        index = _find_run(quote_words, [w for w, _, _ in tokens])
        if index is not None:
            return Located(source_id, number, tokens[index][1], tokens[index + len(quote_words) - 1][2], "exact")

    # 2. close: the stretch of page text that shares the most word pairs with the quote
    best: tuple[float, str, int, int, int] | None = None
    for source_id, number, tokens in tokenised:
        match = _best_window(quote_words, tokens)
        if match and (best is None or match[0] > best[0]):
            best = (match[0], source_id, number, match[1], match[2])
    if best and best[0] >= CLOSE_ENOUGH:
        return Located(best[1], best[2], best[3], best[4], "close")
    return Located(fallback_source, fallback_page, None, None, "no")


def _find_run(needle: list[str], haystack: list[str]) -> int | None:
    """Index where the word list `needle` appears in `haystack` without gaps, or None."""
    size = len(needle)
    first = needle[0]
    for index in range(len(haystack) - size + 1):
        if haystack[index] == first and haystack[index : index + size] == needle:
            return index
    return None


def _best_window(quote_words: list[str], tokens: list[tuple[str, int, int]]) -> tuple[float, int, int] | None:
    """Slide a window over the page; return (share of quote word pairs found, start, end) of the best one."""
    if len(quote_words) == 1:
        hit = next((t for t in tokens if t[0] == quote_words[0]), None)
        return (1.0, hit[1], hit[2]) if hit else None

    quote_pairs = set(zip(quote_words, quote_words[1:]))
    words = [w for w, _, _ in tokens]
    # Positions where a word pair of the quote starts. Only windows starting there can be the best.
    hits = [i for i in range(len(words) - 1) if (words[i], words[i + 1]) in quote_pairs]
    # A little wider than the quote, in case the model added a few words.
    width = len(quote_words) + len(quote_words) // 4 + 2
    best = None
    for number, start in enumerate(hits):
        inside = [i for i in hits[number:] if i + 1 < start + width]
        score = len({(words[i], words[i + 1]) for i in inside}) / len(quote_pairs)
        if best is None or score > best[0]:
            best = (score, tokens[start][1], tokens[inside[-1] + 1][2])
    return best


# ---- words for linking sentences to facts ------------------------------------------------------

STOPWORDS = set(
    """a an the and or but if of to in on at by for from with within without into onto over under about
    as is are was were be been being has have had do does did done not no nor so than then that this these
    those there here it its it's they them their we our you your he she his her i me my us will would can
    could should may might must shall also just very more most much many some any all each every other
    such only own same too out up down off again once while during before after above below between
    through until what which who whom whose when where why how now new one said says per via""".split()
)
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_SUFFIXES = (("ies", "y"), ("ied", "y"), ("ions", ""), ("ion", ""), ("ings", ""), ("ing", ""), ("ers", ""),
             ("ed", ""), ("s", ""))


def stem(word: str) -> str:
    """A very small word-ending cutter: "encrypted", "encryption", "encrypting" -> "encrypt"."""
    if word.endswith(("sses", "xes", "zes", "ches", "shes")) and len(word) > 5:
        return word[:-2]  # "patches" -> "patch", but "states" -> "state" (below)
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3 and not word.endswith("ss"):
            return word[: -len(suffix)] + replacement
    return word


def content_words(text: str) -> set[str]:
    """The words that carry meaning, cut to their stem. Small words and month names are left out
    (dates are compared separately, see values.py), numbers are kept ("42")."""
    result = set()
    for word, _, _ in words_with_positions(text):
        if word in STOPWORDS or word in MONTHS or (len(word) < 3 and not word.isdigit()):
            continue
        result.add(word if word.isdigit() else stem(word))
    return result
