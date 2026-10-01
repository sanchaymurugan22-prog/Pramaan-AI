"""In-app notifications (Stage 9A). Nothing is sent outside the app: no email, no SMS (works offline).

Who gets what:
  finished / failed   the job's Operator, when the AI has finished writing (or could not)
  submitted           every active Reviewer except the one who submitted, when a job waits for review
  sent_back           the job's Operator, with the Reviewer's notes
  approved / signed   the job's Operator, when a Reviewer approves (approving also signs: two notes)
  watch               the Operator whose watch folder made a draft
  alert               every active Reviewer, when an Emergency alert waits for fast-track approval

`notify()` only adds rows to the session; the caller commits (so a notification is never saved
for something that was rolled back).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Job, Notification, User

KINDS = {"finished", "failed", "submitted", "sent_back", "approved", "signed", "watch", "alert"}


def notify(db: Session, user_id: int | None, kind: str, title: str, detail: str = "", job: Job | None = None) -> None:
    """Add one notification for one person (nothing happens for user_id None: a job made before Stage 6B)."""
    assert kind in KINDS, kind
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title[:200], detail=detail[:1000],
                        job_id=job.id if job is not None else None))


def notify_reviewers(db: Session, kind: str, title: str, detail: str, job: Job, except_user: int | None) -> None:
    """The same notification for every active Reviewer (except the person who caused it)."""
    reviewers = db.scalars(select(User.id).where(User.role == "reviewer", User.is_active.is_(True)))
    for reviewer_id in reviewers:
        if reviewer_id != except_user:
            notify(db, reviewer_id, kind, title, detail, job)


def job_finished(db: Session, job: Job, done: int, failed: int) -> None:
    """Called by the runner when the AI stops working on a job."""
    total = done + failed
    if done == 0:
        notify(db, job.owner_id, "failed", f"Could not write the outputs of “{job.title}”",
               "Open the job and use Try again.", job)
    elif failed:
        notify(db, job.owner_id, "failed", f"{done} of {total} outputs are ready",
               f"{job.title} · {failed} failed: open the job and use Try again.", job)
    else:
        notify(db, job.owner_id, "finished", f"All {total} output{'s are' if total != 1 else ' is'} ready", job.title, job)
