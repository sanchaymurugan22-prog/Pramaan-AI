"""The safety decision log: who decided what, and when, for every job (table safety_decisions).

Rows are only ever added, never changed, so the Results page (and later the reviewer) can see how
each item was handled.

Until login arrives (later in Stage 6), the person is recorded as "Operator". Automatic steps
(the scan itself) are recorded as "Pramaan (automatic)".
"""

from datetime import timezone

from app.db import SafetyDecision

OPERATOR = "Operator"  # replaced by the signed-in user's name when login is added
AUTOMATIC = "Pramaan (automatic)"


def record(db, job, action: str, detail: str, actor: str = OPERATOR, item: str | None = None,
           value: str | None = None) -> SafetyDecision:
    """Add one decision.
    action: scan | choice | instruction | tlp | confirm | start ; item: P1, I2, X1 ; value: the new choice or label."""
    decision = SafetyDecision(job=job, actor=actor, action=action, item=item, value=value, detail=detail)
    db.add(decision)
    return decision


def decision_json(decision: SafetyDecision) -> dict:
    created = decision.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": decision.id,
        "actor": decision.actor,
        "action": decision.action,
        "item": decision.item,
        "value": decision.value,
        "detail": decision.detail,
        "created_at": created.isoformat() if created else None,
    }
