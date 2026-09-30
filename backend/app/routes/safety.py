"""Safety check routes (Stage 6A), step 2 of a new transformation.

PUT /api/jobs/{id}/safety   save the operator's choices and the TLP label, while the job is a draft

    {"tlp": "AMBER", "choices": {"P1": "hide_all", "I2": "keep", "X1": "keep"}}

Choices for private data and indicators (P1, I1 ...): hide_public (hide in public outputs) | hide_all
(hide everywhere) | keep. For suspicious instructions (X1 ...): remove (from what the AI reads) | keep.
Every change is saved in the safety_decisions table (who, when, what). The scan itself runs when the
sources are added (POST /api/jobs), and its report comes back in the job details ("safety").
"""

import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import audit
from app.auth.deps import allow
from app.db import User, get_session
from app.routes.jobs import _get_job, job_detail
from app.safety.decisions import record
from app.safety.masking import Masker
from app.safety.scanner import CHOICES, all_findings
from app.safety.shield import INSTRUCTION_CHOICES
from app.safety.tlp import LEVELS

router = APIRouter(prefix="/api", tags=["safety"])


class SafetyUpdate(BaseModel):
    tlp: str | None = None
    choices: dict[str, str] = {}


@router.put("/jobs/{job_id}/safety")
def save_safety(job_id: int, update: SafetyUpdate, db: Session = Depends(get_session),
                user: User = Depends(allow("operator"))):
    job = _get_job(db, job_id)
    if job.status != "draft":
        raise HTTPException(409, "The safety check cannot be changed after the job has started.")
    if job.safety_json is None:
        raise HTTPException(409, "This job has no safety report (it was made before Stage 6A).")

    report = copy.deepcopy(job.safety_json)
    findings = {f["id"]: f for f in all_findings(report)}
    instructions = {x["id"]: x for x in report.get("suspicious", []) if x["kind"] == "instruction"}
    for item_id, choice in update.choices.items():
        if item_id in findings:
            allowed = CHOICES
        elif item_id in instructions:
            allowed = INSTRUCTION_CHOICES
        else:
            raise HTTPException(400, f"Unknown item '{item_id}'.")
        if choice not in allowed:
            raise HTTPException(400, f"Choice for {item_id} must be one of: {', '.join(allowed)}.")

    before = len(job.safety_decisions)
    first_confirmation = job.tlp is None
    for item_id, choice in update.choices.items():
        instruction = instructions.get(item_id)
        if instruction is not None:
            old = instruction.get("choice", "keep")
            if old != choice:
                shown = Masker(report).mask(" ".join(instruction["text"].split()))  # no private values in the log
                record(db, job, "instruction",
                       f"Suspicious instruction “{shown[:60]}{'…' if len(shown) > 60 else ''}” ({instruction['source_id']} "
                       f"page {instruction['page']}): {INSTRUCTION_CHOICES[old]} → {INSTRUCTION_CHOICES[choice]}",
                       by=user, item=item_id, value=choice)
                instruction["choice"] = choice
            continue
        finding_id = item_id
        finding = findings[finding_id]
        if finding["choice"] == choice:
            continue
        record(db, job, "choice",
               f"{finding['label']} {hint(finding)} ({where(finding)}): {CHOICES[finding['choice']]} → {CHOICES[choice]}",
               by=user, item=finding_id, value=choice)
        finding["choice"] = choice
    job.safety_json = report  # a new object, so SQLAlchemy saves the change

    if update.tlp is not None:
        tlp = update.tlp.upper().removeprefix("TLP:")
        if tlp not in LEVELS:
            raise HTTPException(400, "The label must be RED, AMBER, GREEN or CLEAR.")
        if tlp != job.tlp:
            suggested = report.get("suggested_tlp")
            note = "the suggested label" if tlp == suggested else f"suggested was TLP:{suggested}"
            record(db, job, "tlp", f"Sharing label set to TLP:{tlp} ({note}).", by=user, value=tlp)
            job.tlp = tlp

    if first_confirmation and job.tlp:
        counts = {choice: sum(f["choice"] == choice for f in findings.values()) for choice in CHOICES}
        removed = sum(x.get("choice") == "remove" for x in instructions.values())
        detail = (f"Safety check confirmed: {counts['hide_public']} hidden in public outputs, "
                  f"{counts['hide_all']} hidden everywhere, {counts['keep']} kept.")
        if instructions:
            detail += (f" Suspicious instructions: {removed} removed from what the AI reads, "
                       f"{len(instructions) - removed} kept (AI told to ignore them).")
        record(db, job, "confirm", detail, by=user)
    db.commit()
    audit.log_decisions(user, job, job.safety_decisions[before:])
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
