"""The Operator dashboard's numbers and "Needs your attention" list (Stage 9A). No AI, read only.

GET /api/dashboard   {"stats": {...}, "attention": [...], "latest_approval": {...} | null, "encrypted": true}

"Hours saved" is an ESTIMATE, labelled as one on the page: for every approved output, the time a person
usually needs to write it by hand (MANUAL_MINUTES below), with nothing taken off for checking.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import allow
from app.db import DATABASE_PATH, PLAIN_HEADER, Job, User, as_utc, get_session, utc_now
from app.pipeline.output_types import OUTPUT_TYPES

router = APIRouter(prefix="/api", tags=["dashboard"])

# Rough minutes to write each output by hand (for the "hours saved" estimate only)
MANUAL_MINUTES = {
    "advisory": 90, "executive_summary": 45, "presentation": 120, "video_package": 120,
    "infographic": 60, "linkedin_post": 20, "x_thread": 20,
}


def _time(value) -> str | None:
    return as_utc(value).isoformat() if value is not None else None


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_session), user: User = Depends(allow("operator"))):
    now = utc_now()
    jobs = db.scalars(select(Job).order_by(Job.id.desc())).all()
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)
    this_week = sum(as_utc(j.created_at) >= week_ago for j in jobs)
    last_week = sum(two_weeks_ago <= as_utc(j.created_at) < week_ago for j in jobs)
    approved_outputs = [o for j in jobs if j.status == "approved" for o in j.outputs if o.status == "done"]
    languages = sorted({o.language for j in jobs for o in j.outputs}) or ["en"]

    mine = [j for j in jobs if j.owner_id == user.id]
    approvals = [j for j in mine if j.status == "approved"]
    latest = max(approvals, key=lambda j: as_utc(j.updated_at), default=None)
    return {
        "stats": {
            "jobs_this_week": this_week,
            "jobs_last_week": last_week,
            "outputs_approved": len(approved_outputs),
            "formats_approved": len({o.type for o in approved_outputs}),
            "hours_saved": round(sum(MANUAL_MINUTES.get(o.type, 30) for o in approved_outputs) / 60),
            "languages": languages,
        },
        "attention": attention(mine),
        "watch_drafts": sum(j.created_via == "watch" and j.status == "draft" for j in mine),
        "latest_approval": {"id": latest.id, "title": latest.title, "at": _time(latest.updated_at)} if latest else None,
        "encrypted": _database_encrypted(),
    }


def attention(jobs: list[Job]) -> list[dict]:
    """What this Operator should look at next, most urgent first."""
    items = []
    for job in jobs:
        if job.status == "sent_back":
            note = next((r for r in reversed(job.reviews) if r.decision == "sent_back"), None)
            by = note.user.full_name if note and note.user else "The reviewer"
            items.append({"kind": "sent_back", "job_id": job.id, "title": f"Sent back: {job.title}",
                          "detail": f"{by}: “{note.notes}”" if note else "Open it to read the notes."})
        elif job.status == "failed":
            items.append({"kind": "failed", "job_id": job.id, "title": f"Could not finish: {job.title}",
                          "detail": "Open the job and use Try again."})
        elif job.status == "ready":
            leaks = [o for o in job.outputs if (o.quality_json or {}).get("leaks")]
            unlinked = [(o, len((o.quality_json or {}).get("unlinked", []))) for o in job.outputs]
            unlinked = [(o, n) for o, n in unlinked if n]
            if leaks:
                items.append({"kind": "leak", "job_id": job.id, "title": "Private data found in an output",
                              "detail": f"{job.title} · {OUTPUT_TYPES[leaks[0].type]['label']}"})
            elif unlinked:
                count = sum(n for _, n in unlinked)
                items.append({"kind": "unlinked", "job_id": job.id,
                              "title": f"{count} sentence{'s' if count != 1 else ''} not linked to the source",
                              "detail": f"{job.title} · {', '.join(OUTPUT_TYPES[o.type]['label'] for o, _ in unlinked[:2])}"})
            else:
                items.append({"kind": "ready", "job_id": job.id, "title": f"Ready to send for review: {job.title}",
                              "detail": f"{len(job.outputs)} outputs, quality {job.quality_score if job.quality_score is not None else '–'}"})
    watch = [j for j in jobs if j.created_via == "watch" and j.status == "draft"]
    if watch:
        items.append({"kind": "watch", "job_id": watch[0].id if len(watch) == 1 else None,
                      "title": f"Watch folder drafted {len(watch)} report{'s' if len(watch) != 1 else ''}",
                      "detail": "Waiting for you at the Safety check. Nothing is written until you start it."})
    order = {"sent_back": 0, "leak": 1, "failed": 2, "unlinked": 3, "watch": 4, "ready": 5}
    return sorted(items, key=lambda i: order[i["kind"]])[:6]


def _database_encrypted() -> bool:
    """True when the database file is not a plain SQLite file (it is SQLCipher-encrypted, Stage 6B)."""
    try:
        with DATABASE_PATH.open("rb") as file:
            return file.read(16) != PLAIN_HEADER
    except OSError:
        return False
