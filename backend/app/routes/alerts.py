"""Emergency alert (Stage 9A, Operators): a short public alert that goes to fast-track review.

POST /api/alerts/check     {"message": "..."}  live check while typing: characters, SMS parts, public-release check
POST /api/alerts/preview   {"message", "languages"}  Stage 8: the message in every chosen language, each with its
                           SMS length (160 characters in English, 70 in Indian scripts), values check and voice
POST /api/alerts           {"type", "severity", "area", "message", "outputs", "languages", "voice"}  make the alert
                           job and start the AI

The operator's message (with the alert type, severity and area) is the SOURCE of the job, so every
output is traced to what the operator wrote. The label is TLP:CLEAR (a public alert); a message with
private data in it, or panic wording, is refused. The AI starts at once (a person wrote and sent it).
When every output is ready, the job goes to the Reviewers by itself, marked "fast-track", and they are
notified (see runner.py). Nothing is published until a Reviewer approves and signs it.

Stage 8: the alert itself is an output too ("SMS alert", written by the Operator, not the AI). Like every
output it is translated into the chosen languages (IndicTrans2), checked (every number and the helpline must
survive), ticked by a native speaker, signed, and comes with a voice announcement (.mp3) in every language
that has a voice. The campaign kit (.zip) is the one-click alert kit.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import allow
from app.db import User, get_session
from app.pipeline import ingest, runner
from app.pipeline.output_types import DEFAULT_SETTINGS
from app.lang import languages
from app.routes.jobs import job_detail, log_created, save_draft, selected_languages, start_outputs
from app.safety.decisions import record
from app.safety.public_check import check_public_text

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
OPERATOR = allow("operator")

ALERT_TYPES = ["Cyber fraud", "Flood", "Cyclone", "Heatwave", "Health", "Other"]
SEVERITIES = ["Advisory", "Warning", "Emergency"]
SMS_CHARS = 160
MAX_CHARS = 480  # three SMS parts at most
DEFAULT_OUTPUTS = ["x_thread", "infographic"]
ALERT_OUTPUTS = ("x_thread", "linkedin_post", "infographic")  # public outputs the AI can add to the SMS
ALERT_SETTINGS = DEFAULT_SETTINGS | {"audience": "General public", "tone": "Reassuring",
                                     "objective": "Warn and instruct", "style": "Plain and simple", "detail_level": "short"}


def sms_parts(message: str) -> int:
    """How many SMS messages the text needs (160 characters in one, 153 per part; 70 / 67 in Indian scripts)."""
    return languages.sms_parts(message)


class AlertText(BaseModel):
    message: str


@router.post("/check")
def check_alert(body: AlertText, user: User = Depends(OPERATOR)):
    message = body.message.strip()
    return {"chars": len(message), "sms_parts": sms_parts(message), "max_chars": MAX_CHARS,
            "fits_one_sms": len(message) <= SMS_CHARS, **check_public_text(message)}


class Preview(BaseModel):
    message: str
    languages: list[str]


@router.post("/preview")
async def preview_alert(body: Preview, user: User = Depends(OPERATOR)):
    """Stage 8: the message in each language (machine translated, on this computer), for the preview cards."""
    from fastapi.concurrency import run_in_threadpool

    from app.lang import helplines, translate, tts
    from app.pipeline.translation import compare_values

    message = body.message.strip()
    if len(message) < 5:
        raise HTTPException(400, "Write the message first.")
    codes = selected_languages(body.languages)

    def one(code: str) -> dict:
        text = translate.translate_texts([message], code)[0]
        missing, extra = compare_values(message, text)
        extra += [f"{n} (helpline number read as a year?)" for n in helplines.not_read_as_phone(message, text)]
        lang = languages.get(code)
        return {"code": code, "name": lang.name, "native": lang.native, "rtl": lang.rtl, "text": text,
                "chars": len(text), "limit": lang.sms_limit, "sms_parts": languages.sms_parts(text),
                "changed": missing + extra, "voice": (v.name if (v := tts.voice_for(code)) else None)}

    try:
        return {"languages": [await run_in_threadpool(one, code) for code in codes]}
    except translate.TranslateError as exc:
        raise HTTPException(409, str(exc))


class NewAlert(BaseModel):
    type: str
    severity: str
    area: str = "All states and union territories"
    message: str
    outputs: list[str] = DEFAULT_OUTPUTS
    languages: list[str] = []  # Stage 8: Indian languages for the SMS and every output
    voice: bool = True         # Stage 8: a voice announcement (.mp3) in every language that has a voice


@router.post("", status_code=201)
def create_alert(body: NewAlert, db: Session = Depends(get_session), user: User = Depends(OPERATOR)):
    message = body.message.strip()
    if body.type not in ALERT_TYPES or body.severity not in SEVERITIES:
        raise HTTPException(400, "Choose an alert type and a severity from the list.")
    if len(message) < 20:
        raise HTTPException(400, "Write the alert message (at least 20 characters).")
    if len(message) > MAX_CHARS:
        raise HTTPException(400, f"Keep the alert under {MAX_CHARS} characters (it is {len(message)}).")
    check = check_public_text(message)
    if not check["ok"]:
        first = check["problems"][0]
        raise HTTPException(400, f"The public-release check failed: {first['label']} (“{first['text']}”). "
                                 "Change the message and try again.")
    outputs = list(dict.fromkeys(o for o in body.outputs if o != "sms"))
    if any(o not in ALERT_OUTPUTS for o in outputs):
        raise HTTPException(400, "An emergency alert can only make public outputs (X thread, LinkedIn post, infographic).")
    outputs = ["sms", *outputs]  # the alert itself, as a text message, is always made
    codes = selected_languages(body.languages)

    area = body.area.strip()[:120] or "All states and union territories"
    source_text = (f"{body.type} alert. Severity: {body.severity}. Area: {area}.\n\n{message}\n")
    source = ingest.from_text(source_text)
    source.filename = "emergency-alert.txt"
    job = save_draft(db, [source], f"Emergency alert: {body.type} · {body.severity}", user, dict(ALERT_SETTINGS),
                     created_via="emergency")
    job.alert_json = {"type": body.type, "severity": body.severity, "area": area, "message": message,
                      "chars": len(message), "sms_parts": sms_parts(message), "voice": body.voice}
    job.tlp = "CLEAR"
    record(db, job, "tlp", "TLP:CLEAR: an emergency alert is public by design. The public-release check passed "
                           "(no private data, no panic wording).", by=user, value="CLEAR")
    start_outputs(db, job, outputs, dict(ALERT_SETTINGS), user, codes)
    db.commit()
    log_created(job, user, how=" (emergency alert, fast-track review)")
    runner.submit(job.id)
    return job_detail(job)
