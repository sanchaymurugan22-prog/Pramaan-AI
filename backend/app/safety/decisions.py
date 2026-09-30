"""The safety decision log: who decided what, and when, for every job (table safety_decisions).

Rows are only ever added, never changed, so the Results page (and later the reviewer) can see how
each item was handled.

Each decision records the signed-in user who made it (name and id). Automatic steps (the scan
itself) are recorded as "Pramaan (automatic)". Decisions made before Stage 6B say "Operator".
"""

from datetime import timezone

from app.db import SafetyDecision, User

AUTOMATIC = "Pramaan (automatic)"


def record(db, job, action: str, detail: str, by: User | None, item: str | None = None,
           value: str | None = None) -> SafetyDecision:
    """Add one decision. by: the signed-in user, or None for an automatic step.
    action: scan | choice | instruction | tlp | confirm | start ; item: P1, I2, X1 ; value: the new choice or label."""
    decision = SafetyDecision(job=job, actor=by.full_name if by else AUTOMATIC, user_id=by.id if by else None,
                              action=action, item=item, value=value, detail=detail)
    db.add(decision)
    return decision


def decision_json(decision: SafetyDecision) -> dict:
    created = decision.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": decision.id,
        "actor": decision.actor,
        "user_id": decision.user_id,
        "action": decision.action,
        "item": decision.item,
        "value": decision.value,
        "detail": decision.detail,
        "created_at": created.isoformat() if created else None,
    }
