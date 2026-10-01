"""The "Is this real?" message checker (Stage 7). Paste a forwarded message (WhatsApp, SMS, email):

  1. Exact match: its normalised text (texts.normalise: spaces, case, punctuation, emojis, zero-width
     characters ignored) has the same SHA-256 as a text in a signed record -> "Genuine, matches record X"
     (or withdrawn / replaced by a newer version).
  2. Otherwise, a similarity check against the PUBLISHED texts (TLP:CLEAR / GREEN social posts), offline:
     5-character shingles of the normalised text, Jaccard similarity (or how much of the message is inside
     the record's text). 0.5 or more -> "Looks like record X but was changed", with the changed words.
  3. Otherwise "Not found - treat as unverified".
  Scam signs (rules, no AI) are listed whenever it is not an exact match: asks for an OTP / password / PIN /
  payment, urgent threats, links that are not government sites and not in any record, phone numbers not
  in any record, asks to install an app. Always shown: report cyber fraud on 1930 or cybercrime.gov.in.

The public page does EXACTLY the same in JavaScript (verify-page/verify.js, checkMessage); the tests
run the same messages through both. Only published data is used, so both give the same answer.
"""

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Record
from app.signing.texts import normalise, text_hash

SHINGLE = 5
SIMILAR = 0.5
HELPLINE = "Report cyber fraud: call 1930 or visit cybercrime.gov.in"

# Government and official domains that are fine in a message even if no record mentions them.
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".gov")
OFFICIAL_DOMAINS = {"cybercrime.gov.in", "cert-in.org.in", "sancharsaathi.gov.in", "india.gov.in", "rbi.org.in"}
HELPLINES = {"1930", "112", "100", "1098", "181", "14422"}

# re.A: \b and \d mean the same as in JavaScript (ASCII), so both checkers agree. Hindi words have no \b.
_FLAGS = re.I | re.A
_NEGATION = re.compile(r"\b(never|not|don'?t|do not|no one|nobody|nor)\b|कभी\s*न|मत|न करें", _FLAGS)
_SIGNS = [
    ("asks_secret", "Asks for your OTP, password or PIN",
     re.compile(r"\b(otp|one[\s-]?time[\s-]?password|password|passcode|pin|cvv|upi pin|atm pin|card number|card details|"
                r"bank details|net ?banking|login details)\b|ओटीपी|पासवर्ड|पिन", _FLAGS)),
    ("asks_payment", "Asks you to pay or send money",
     re.compile(r"\b(pay (now|the|a|your|rs|₹)|make (a )?payment|send money|transfer (rs|₹|money|the amount)|"
                r"processing fee|registration fee|pay a fine|refund|deposit|gift card|bitcoin|crypto(currency)?)\b|"
                r"भुगतान करें|पैसे भेजें|शुल्क जमा", _FLAGS)),
    ("urgent", "Pressure or threats",
     re.compile(r"\b(urgent(ly)?|immediately|act now|right now|within \d+ ?(hours?|hrs?|minutes?|mins?)|"
                r"last (chance|warning|date)|today only|will be (blocked|suspended|deactivated|deleted|disconnected)|"
                r"(account|sim|card|number) (is |will be )?(blocked|suspended|closed|deactivated)|legal action|arrest(ed)?|"
                r"police case|penalty)\b|तुरंत|गिरफ्तार|बंद (हो|कर) (जाएगा|दिया जाएगा)|ब्लॉक", _FLAGS)),
    ("install_app", "Asks you to install an app or share your screen",
     re.compile(r"\b(\.apk|apk file|anydesk|teamviewer|quick ?support|screen ?shar(e|ing)|install (this|the|our) app|"
                r"download (this|the|our) app)\b", _FLAGS)),
]
_URL = re.compile(r"\b((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,12})(?:/[^\s]*)?", _FLAGS)
# file names, not web addresses
_FILE_ENDINGS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "jpg", "jpeg", "png", "gif", "zip", "srt", "csv"}
# (^|non-digit) instead of a look-behind: older iPhone Safari cannot read look-behinds in JavaScript
_PHONE = re.compile(r"(^|\D)(?:\+?91[\s-]?|0)?([6-9]\d{4}[\s-]?\d{5})(?!\d)", _FLAGS)
_EMAIL = re.compile(r"\S+@\S+")


# ---- published data ----------------------------------------------------------------------------


def published_records(db: Session) -> list[dict]:
    """The PUBLIC part of every record (what records.json has), with its status."""
    issues, withdrawn, replaced_by = [], set(), {}
    for entry in db.scalars(select(Record).order_by(Record.seq)):
        public = json.loads(entry.public_manifest)
        if entry.kind == "issue":
            issues.append(public)
            if public.get("replaces"):
                replaced_by[public["replaces"]] = public["record_no"]
        else:
            withdrawn.add(entry.record_no)
    out = []
    for public in issues:
        no = public["record_no"]
        status = "withdrawn" if no in withdrawn else "replaced" if no in replaced_by else "genuine"
        out.append({"record_no": no, "status": status, "replaced_by": replaced_by.get(no),
                    "title": public.get("title"), "restricted": public.get("restricted", True),
                    "texts": public.get("texts", [])})
    return out


# ---- similarity and differences ----------------------------------------------------------------


def shingles(normalised: str) -> set[str]:
    if len(normalised) <= SHINGLE:
        return {normalised} if normalised else set()
    return {normalised[i:i + SHINGLE] for i in range(len(normalised) - SHINGLE + 1)}


def similarity(a: str, b: str) -> float:
    """How alike two texts are, 0 to 1: Jaccard of their shingles, or (a little lower) how much of the
    message is inside the record's text, so a cut-down copy of a long post is still recognised."""
    sa, sb = shingles(normalise(a)), shingles(normalise(b))
    if not sa or not sb:
        return 0.0
    common = len(sa & sb)
    return round(max(common / len(sa | sb), 0.85 * common / len(sa)), 4)


def word_diff(message: str, record_text: str) -> list[dict]:
    """The message's words, marked "same" or "added" (not in the record), with the record's words that
    are missing from the message marked "removed", in reading order. Words are compared normalised."""
    mine = [(w, normalise(w)) for w in message.split()]
    theirs = [(w, normalise(w)) for w in record_text.split()]
    a = [k for _, k in mine if k]
    b = [k for _, k in theirs if k]
    # longest common subsequence of the normalised words
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            table[i][j] = table[i + 1][j + 1] + 1 if a[i] == b[j] else max(table[i + 1][j], table[i][j + 1])
    out, i, j = [], 0, 0
    mine_words = [(w, k) for w, k in mine if k]
    theirs_words = [(w, k) for w, k in theirs if k]
    while i < len(a) or j < len(b):
        if i < len(a) and j < len(b) and a[i] == b[j]:
            out.append({"text": mine_words[i][0], "kind": "same"})
            i, j = i + 1, j + 1
        elif j < len(b) and (i == len(a) or table[i][j + 1] >= table[i + 1][j]):
            out.append({"text": theirs_words[j][0], "kind": "removed"})
            j += 1
        else:
            out.append({"text": mine_words[i][0], "kind": "added"})
            i += 1
    return out


# ---- scam signs ---------------------------------------------------------------------------------


def _negated(text: str, start: int) -> bool:
    """"never share your OTP": the 30 characters before the match say not to."""
    return bool(_NEGATION.search(text[max(0, start - 30):start]))


def _domain(link: str) -> str:
    return re.sub(r"(?i)^https?://", "", link).split("/")[0].lower().removeprefix("www.")


def scam_signs(text: str, records: list[dict]) -> list[dict]:
    known_text = " ".join(t.get("text", "") for r in records for t in r["texts"]).lower()
    known_digits = re.sub(r"\D", "", known_text)
    signs = []
    for kind, label, pattern in _SIGNS:
        found = next((m for m in pattern.finditer(text) if not _negated(text.lower(), m.start())), None)
        if found:
            signs.append({"kind": kind, "label": label, "detail": found.group(0).strip()})
    cleaned = _EMAIL.sub(" ", text)
    for match in _URL.finditer(cleaned):
        domain = _domain(match.group(1))
        if domain.rsplit(".", 1)[-1] in _FILE_ENDINGS:
            continue
        official = domain in OFFICIAL_DOMAINS or domain.endswith(OFFICIAL_SUFFIXES)
        if not official and domain not in known_text:
            looks_official = re.search(r"gov|sarkar|nic|cert|police|bank|rbi|uidai|aadhaar", domain)
            signs.append({"kind": "unknown_link", "label": "Suspicious link", "detail": domain,
                          "note": "made to look official" if looks_official else "not a government website"})
            break
    for match in _PHONE.finditer(text):
        digits = re.sub(r"\D", "", match.group(2))
        if digits not in HELPLINES and digits not in known_digits:
            signs.append({"kind": "unknown_phone", "label": "Phone number not in any signed record", "detail": match.group(2).strip()})
            break
    return signs


# ---- the check ----------------------------------------------------------------------------------


def check_message(text: str, records: list[dict]) -> dict:
    """verdict: genuine | replaced | withdrawn (exact match) | changed | scam | not_found."""
    text = text or ""
    digest = text_hash(text)
    base = {"helpline": HELPLINE, "sha256": digest, "normalised": normalise(text)}
    newest_first = list(reversed(records))  # if several records hold the same text, the newest decides
    for record in newest_first:
        hit = next((t for t in record["texts"] if t["sha256"] == digest), None)
        if hit:
            return base | {"verdict": record["status"], "record_no": record["record_no"],
                           "replaced_by": record["replaced_by"], "title": record["title"],
                           "restricted": record["restricted"], "label": hit.get("label"), "signs": []}

    best, best_score, best_text = None, 0.0, None
    for record in newest_first:
        for t in record["texts"]:
            if "text" in t:
                score = similarity(text, t["text"])
                if score > best_score:
                    best, best_score, best_text = record, score, t
    signs = scam_signs(text, records)
    if best is not None and best_score >= SIMILAR:
        diff = word_diff(text, best_text["text"])
        return base | {"verdict": "changed", "record_no": best["record_no"], "title": best["title"],
                       "record_status": best["status"], "similarity": best_score, "label": best_text.get("label"),
                       "diff": diff, "signs": signs}
    return base | {"verdict": "scam" if signs else "not_found", "record_no": None, "signs": signs}
