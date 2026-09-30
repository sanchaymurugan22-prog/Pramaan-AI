"""Safety check routes (Stage 6A), step 2 of a new transformation.

PUT /api/jobs/{id}/safety   save the operator's choices and the TLP label, while the job is a draft

    {"tlp": "AMBER", "choices": {"P1": "hide_all", "I2": "keep"}}

Choices: hide_public (hide in public outputs) | hide_all (hide everywhere) | keep.
Every change is saved in the safety_decisions table (who, when, what). The scan itself runs when the
sources are added (POST /api/jobs), and its report comes back in the job details ("safety").
"""

import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes.jobs import _get_job, job_detail
from app.safety.decisions import record
from app.safety.scanner import CHOICES, all_findings
from app.safety.tlp import LEVELS

router = APIRouter(prefix="/api", tags=["safety"])


class SafetyUpdate(BaseModel):
    tlp: str | None = None
    choices: dict[str, str] = {}


@router.put("/jobs/{job_id}/safety")
def save_safety(job_id: int, update: SafetyUpdate, db: Session = Depends(get_session)):
    job = _get_job(db, job_id)
    if job.status != "draft":
        raise HTTPException(409, "The safety check cannot be changed after the job has started.")
    if job.safety_json is None:
        raise HTTPException(409, "This job has no safety report (it was made before Stage 6A).")

    report = copy.deepcopy(job.safety_json)
    findings = {f["id"]: f for f in all_findings(report)}
    for finding_id, choice in update.choices.items():
        if finding_id not in findings:
            raise HTTPException(400, f"Unknown item '{finding_id}'.")
        if choice not in CHOICES:
            raise HTTPException(400, f"Choice must be one of: {', '.join(CHOICES)}.")

    first_confirmation = job.tlp is None
    for finding_id, choice in update.choices.items():
        finding = findings[finding_id]
        if finding["choice"] == choice:
            continue
        record(db, job, "choice",
               f"{finding['label']} {hint(finding)} ({where(finding)}): {CHOICES[finding['choice']]} → {CHOICES[choice]}",
               item=finding_id, value=choice)
        finding["choice"] = choice
    job.safety_json = report  # a new object, so SQLAlchemy saves the change

    if update.tlp is not None:
        tlp = update.tlp.upper().removeprefix("TLP:")
        if tlp not in LEVELS:
            raise HTTPException(400, "The label must be RED, AMBER, GREEN or CLEAR.")
        if tlp != job.tlp:
            suggested = report.get("suggested_tlp")
            note = "the suggested label" if tlp == suggested else f"suggested was TLP:{suggested}"
            record(db, job, "tlp", f"Sharing label set to TLP:{tlp} ({note}).", value=tlp)
            job.tlp = tlp

    if first_confirmation and job.tlp:
        counts = {choice: sum(f["choice"] == choice for f in findings.values()) for choice in CHOICES}
        record(db, job, "confirm",
               f"Safety check confirmed: {counts['hide_public']} hidden in public outputs, "
               f"{counts['hide_all']} hidden everywhere, {counts['keep']} kept.")
    db.commit()
    return job_detail(job)


def hint(finding: dict) -> str:
    """A value shown in the log without giving it away: "98•••••10". Keys and passwords: only "••••"."""
    text = finding["text"]
    if finding["group"] in ("secret", "marking", "indicator"):
        return f"“{text}”" if finding["group"] != "secret" else "“••••”"
    if len(text) <= 5:
        return "“•••”"
    return f"“{text[:2]}{'•' * min(len(text) - 4, 8)}{text[-2:]}”"


def where(finding: dict) -> str:
    pages = sorted({(o["source_id"], o["page"]) for o in finding["occurrences"]})
    return ", ".join(f"{source} page {page}" for source, page in pages[:4]) + ("…" if len(pages) > 4 else "")
