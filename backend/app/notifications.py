"""In-app notifications (Stage 9A). Nothing is sent outside the app: no email, no SMS (works offline).

Who gets what:
  finished / failed   the job's Operator, when the AI has finished writing (or could not)
  submitted           every active Reviewer except the one who submitted, when a job waits for review
  sent_back           the job's Operator, with the Reviewer's notes
  approved / signed   the job's Operator, when a Reviewer approves (approving also signs: two notes)
  watch               the Operator whose watch folder made a draft
  alert               every active Reviewer, when an Emergency alert waits for fast-track approval
  mention             a person named with @ in a Reviewer's comment ("@Priya please check this line");
                      shown on the "Mentions" tab of Notifications

`notify()` only adds rows to the session; the caller commits (so a notification is never saved
for something that was rolled back).
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Job, Notification, User

KINDS = {"finished", "failed", "submitted", "sent_back", "approved", "signed", "watch", "alert", "mention"}
# Profile & settings (Stage 9B): kinds a person may switch off. The rest (approved, signed, alerts ...)
# are always shown.
PREF_FOR_KIND = {"finished": "notify_ready", "failed": "notify_ready", "sent_back": "notify_sent_back",
                 "watch": "notify_watch"}


def notify(db: Session, user_id: int | None, kind: str, title: str, detail: str = "", job: Job | None = None) -> None:
    """Add one notification for one person (nothing happens for user_id None: a job made before Stage 6B)."""
    assert kind in KINDS, kind
    if user_id is None:
        return
    pref = PREF_FOR_KIND.get(kind)
    if pref:
        user = db.get(User, user_id)
        if user is not None and (user.prefs or {}).get(pref) is False:
            return  # switched off in Profile & settings
    db.add(Notification(user_id=user_id, kind=kind, title=title[:200], detail=detail[:1000],
                        job_id=job.id if job is not None else None))


def notify_reviewers(db: Session, kind: str, title: str, detail: str, job: Job, except_user: int | None) -> None:
    """The same notification for every active Reviewer (except the person who caused it). Emergency alerts go
    to the Reviewers on the emergency duty roster (Stage 9B), or to all of them if nobody is on it."""
    query = select(User.id).where(User.role == "reviewer", User.is_active.is_(True))
    if kind == "alert":
        on_duty = db.scalars(query.where(User.emergency_duty.is_(True))).all()
        if on_duty:
            query = query.where(User.emergency_duty.is_(True))
    reviewers = db.scalars(query)
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


# "@Priya", "@PriyaSharma", "@priya.sharma" or "@EMP-20311" (not an e-mail address: no letter before the @)
MENTION = re.compile(r"(?<![\w@])@(\w[\w.\-]*\w|\w)")


def _squash(text: str) -> str:
    return re.sub(r"[\s._\-]", "", text).lower()


def mentioned(db: Session, text: str) -> list[User]:
    """The people named with @ in a comment: by full name, employee id, or first name (when only one active
    Operator or Reviewer has it). Admins are not mentioned: they do not see jobs."""
    people = list(db.scalars(select(User).where(User.is_active.is_(True), User.role.in_(("operator", "reviewer")))))
    found: list[User] = []
    for token in MENTION.findall(text):
        key = _squash(token)
        matches = [u for u in people if key in (_squash(u.full_name), _squash(u.employee_id or "-"))]
        if not matches:
            first = [u for u in people if u.full_name.split() and _squash(u.full_name.split()[0]) == key]
            matches = first if len(first) == 1 else []
        found += [u for u in matches if u not in found]
    return found
