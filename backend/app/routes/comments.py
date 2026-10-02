"""Line comments (Stage 9B, designs 25 and 28): a Reviewer comments on one sentence of one output.

GET    /api/jobs/{id}/comments            Operators and Reviewers: every comment, oldest first (taken-back ones left out)
POST   /api/jobs/{id}/comments            Reviewer: {"output_id", "sentence_id", "path", "quote", "text"}
DELETE /api/jobs/{id}/comments/{cid}      the Reviewer who wrote it, while the review is still open (kept, marked taken back)

A comment can name people with @ ("@Priya please check"): each gets a "mention" notification.
A comment can only be added while the job is with a reviewer ("in_review"), and not by someone who worked
on the job (separation of duties, as for approving). Sending back lists the comments of that version in
the notification; the Operator sees them next to the sentences.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, notifications
from app.auth.deps import allow
from app.db import Output, ReviewComment, User, as_utc, get_session, utc_now
from app.pipeline.output_types import OUTPUT_TYPES
from app.routes.jobs import _get_job
from app.routes.review import SEPARATION, worked_on_by

router = APIRouter(prefix="/api/jobs", tags=["review"])


def comment_json(c: ReviewComment, db: Session) -> dict:
    output = db.get(Output, c.output_id) if c.output_id else None
    return {
        "id": c.id, "job_version": c.job_version, "output_id": c.output_id,
        "output_label": OUTPUT_TYPES[output.type]["label"] if output else None,
        "sentence_id": c.sentence_id, "path": c.path, "quote": c.quote, "text": c.text,
        "author": c.author.full_name if c.author else None, "author_id": c.author_id,
        "created_at": as_utc(c.created_at).isoformat(),
    }


def comments_for(db: Session, job_id: int, version: int | None = None) -> list[ReviewComment]:
    query = select(ReviewComment).where(ReviewComment.job_id == job_id, ReviewComment.removed_at.is_(None))
    if version is not None:
        query = query.where(ReviewComment.job_version == version)
    return list(db.scalars(query.order_by(ReviewComment.id)))


@router.get("/{job_id}/comments")
def list_comments(job_id: int, db: Session = Depends(get_session), user: User = Depends(allow("operator", "reviewer"))):
    _get_job(db, job_id)
    return [comment_json(c, db) for c in comments_for(db, job_id)]


class NewComment(BaseModel):
    output_id: int | None = None
    sentence_id: str | None = None
    path: list[str | int] | None = None
    quote: str = ""
    text: str


@router.post("/{job_id}/comments", status_code=201)
def add_comment(job_id: int, form: NewComment, db: Session = Depends(get_session), user: User = Depends(allow("reviewer"))):
    job = _get_job(db, job_id)
    if job.status != "in_review":
        raise HTTPException(409, "Comments can only be added while the job is waiting for review.")
    if user.id in worked_on_by(db, job):
        raise HTTPException(403, SEPARATION)
    text = form.text.strip()
    if not 2 <= len(text) <= 2000:
        raise HTTPException(400, "Write the comment (2 to 2000 characters).")
    if form.output_id is not None and not any(o.id == form.output_id for o in job.outputs):
        raise HTTPException(400, "That output is not part of this job.")
    comment = ReviewComment(job_id=job.id, job_version=job.version, output_id=form.output_id,
                            sentence_id=(form.sentence_id or None) and form.sentence_id[:20], path=form.path,
                            quote=form.quote.strip()[:1000], text=text, author_id=user.id)
    db.add(comment)
    db.flush()
    where = comment_json(comment, db)["output_label"] or "the job"
    people = notifications.mentioned(db, text, author_id=user.id, job_people={job.owner_id} | worked_on_by(db, job))
    for person in people:
        notifications.notify(db, person.id, "mention", f"{user.full_name} mentioned you on “{job.title}”",
                             f"{where}: {text}", job)
    db.commit()
    audit.log("review", "comment_added", f"Commented on {where} of job #{job.id} v{job.version}", actor=user,
              target=f"job {job.id}")
    return {**comment_json(comment, db), "mentioned": [p.full_name for p in people]}


@router.delete("/{job_id}/comments/{comment_id}")
def take_back_comment(job_id: int, comment_id: int, db: Session = Depends(get_session),
                      user: User = Depends(allow("reviewer"))):
    job = _get_job(db, job_id)
    comment = db.get(ReviewComment, comment_id)
    if comment is None or comment.job_id != job.id or comment.removed_at is not None:
        raise HTTPException(404, "Comment not found.")
    if comment.author_id != user.id:
        raise HTTPException(403, "Only the Reviewer who wrote a comment can take it back.")
    if job.status != "in_review" or comment.job_version != job.version:
        raise HTTPException(409, "This review is finished; its comments are kept as they are.")
    comment.removed_at = utc_now()
    db.commit()
    audit.log("review", "comment_removed", f"Took back a comment on job #{job.id} v{job.version}", actor=user,
              target=f"job {job.id}")
    return {"ok": True}
