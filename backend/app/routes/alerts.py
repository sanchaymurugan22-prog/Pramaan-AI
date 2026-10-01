"""Emergency alert (Stage 9A, Operators): a short public alert that goes to fast-track review.

POST /api/alerts/check   {"message": "..."}  live check while typing: characters, SMS parts, public-release check
POST /api/alerts         {"type", "severity", "area", "message", "outputs"}  make the alert job and start the AI

The operator's message (with the alert type, severity and area) is the SOURCE of the job, so every
output is traced to what the operator wrote. The label is TLP:CLEAR (a public alert); a message with
private data in it, or panic wording, is refused. The AI starts at once (a person wrote and sent it).
When every output is ready, the job goes to the Reviewers by itself, marked "fast-track", and they are
notified (see runner.py). Nothing is published until a Reviewer approves and signs it.

Other languages and voice announcements come in Stage 8 (IndicTrans2, Indian TTS).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import allow
from app.db import User, get_session
from app.pipeline import ingest, runner
from app.pipeline.output_types import DEFAULT_SETTINGS, OUTPUT_TYPES
from app.routes.jobs import job_detail, log_created, save_draft, start_outputs
from app.safety.decisions import record
from app.safety.public_check import check_public_text

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
OPERATOR = allow("operator")

ALERT_TYPES = ["Cyber fraud", "Flood", "Cyclone", "Heatwave", "Health", "Other"]
SEVERITIES = ["Advisory", "Warning", "Emergency"]
SMS_CHARS = 160
MAX_CHARS = 480  # three SMS parts at most
DEFAULT_OUTPUTS = ["x_thread", "infographic"]
ALERT_SETTINGS = DEFAULT_SETTINGS | {"audience": "General public", "tone": "Reassuring",
                                     "objective": "Warn and instruct", "style": "Plain and simple", "detail_level": "short"}


def sms_parts(message: str) -> int:
    """How many SMS messages the text needs (160 characters in one, 153 per part when split)."""
    length = len(message)
    return 1 if length <= SMS_CHARS else -(-length // 153)


class AlertText(BaseModel):
    message: str


@router.post("/check")
def check_alert(body: AlertText, user: User = Depends(OPERATOR)):
    message = body.message.strip()
    return {"chars": len(message), "sms_parts": sms_parts(message), "max_chars": MAX_CHARS,
            "fits_one_sms": len(message) <= SMS_CHARS, **check_public_text(message)}


class NewAlert(BaseModel):
    type: str
    severity: str
    area: str = "All states and union territories"
    message: str
    outputs: list[str] = DEFAULT_OUTPUTS


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
    outputs = list(dict.fromkeys(body.outputs)) or DEFAULT_OUTPUTS
    if any(o not in OUTPUT_TYPES or not OUTPUT_TYPES[o]["public"] for o in outputs):
        raise HTTPException(400, "An emergency alert can only make public outputs (X thread, LinkedIn post, infographic).")

    area = body.area.strip()[:120] or "All states and union territories"
    source_text = (f"{body.type} alert. Severity: {body.severity}. Area: {area}.\n\n{message}\n")
    source = ingest.from_text(source_text)
    source.filename = "emergency-alert.txt"
    job = save_draft(db, [source], f"Emergency alert: {body.type} · {body.severity}", user, dict(ALERT_SETTINGS),
                     created_via="emergency")
    job.alert_json = {"type": body.type, "severity": body.severity, "area": area, "message": message,
                      "chars": len(message), "sms_parts": sms_parts(message)}
    job.tlp = "CLEAR"
    record(db, job, "tlp", "TLP:CLEAR: an emergency alert is public by design. The public-release check passed "
                           "(no private data, no panic wording).", by=user, value="CLEAR")
    start_outputs(db, job, outputs, dict(ALERT_SETTINGS), user)
    db.commit()
    log_created(job, user, how=" (emergency alert, fast-track review)")
    runner.submit(job.id)
    return job_detail(job)
