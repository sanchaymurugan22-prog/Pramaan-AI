"""Admin system pages (Stage 9B, designs 30, 34, 36). Admins only; no job content is shown here.

GET  /api/admin/overview         users, jobs, signed documents, fake messages caught, this computer, requests, security events
GET  /api/admin/ai               AI mode and model, the models of the plan, speed measured from real runs, the last speed test
POST /api/admin/ai/speed-test    ask the AI for a short answer and time it
GET  /api/admin/security         the security policy and what it protects (scanner, TLP rules, encryption, signing keys, sessions)
PUT  /api/admin/security         change the policy (every change goes into the audit trail)
"""

import os
import shutil
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import app_settings, audit
from app.ai import llm
from app.auth.accounts import ROLE_LABELS
from app.auth.deps import allow
from app.config import settings
from app.db import AccountRequest, AuditEntry, Job, Record, User, as_utc, get_session, utc_now
from app.pipeline.output_types import OUTPUT_TYPES
from app.routes.dashboard import _database_encrypted
from app.safety.tlp import LEVEL_INFO, LEVELS, public_outputs, switched_off
from app.signing.signer import SigningError, get_signer

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = allow("admin")

AI_LABELS = {"local": "Sarvam 30B · on this computer", "cloud": "Sarvam · hosted (development only)",
             "mock": "Mock AI · test answers"}


def this_computer() -> dict:
    """Processor load, memory, disk: read from this computer (no extra software needed)."""
    cores = os.cpu_count() or 1
    try:
        load = round(min(100.0, os.getloadavg()[0] / cores * 100))
    except (OSError, AttributeError):
        load = None
    try:
        memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        memory = None
    disk = shutil.disk_usage(settings.data_dir)
    return {"processors": cores, "load_percent": load, "memory_bytes": memory, "disk_total_bytes": disk.total,
            "disk_free_bytes": disk.free, "encrypted": _database_encrypted(), "ai_mode": settings.ai_mode,
            "ai_label": AI_LABELS.get(settings.ai_mode, settings.ai_mode)}


@router.get("/overview")
def overview(db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    now = utc_now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    jobs = db.scalars(select(Job.created_at)).all()
    this_month = sum(as_utc(t) >= month_start for t in jobs)
    last_month = sum(last_month_start <= as_utc(t) < month_start for t in jobs)
    issued = db.scalar(select(func.count()).select_from(Record).where(Record.kind == "issue")) or 0
    withdrawn = db.scalar(select(func.count()).select_from(Record).where(Record.kind == "withdraw")) or 0
    counters = app_settings.get("counters")
    pending = db.scalars(select(AccountRequest).where(AccountRequest.status == "pending")
                         .order_by(AccountRequest.id)).all()
    quiet = ("sign_in", "sign_out", "session_ended", "password_changed", "audit_verified")
    events = db.scalars(select(AuditEntry).where(AuditEntry.category == "security", AuditEntry.action.not_in(quiet))
                        .order_by(AuditEntry.seq.desc()).limit(5)).all()
    return {
        "users": {role: sum(u.role == role for u in users) for role in ROLE_LABELS} | {"total": len(users)},
        "jobs": {"this_month": this_month, "last_month": last_month},
        "records": {"issued": issued, "withdrawn": withdrawn},
        "checker": counters,
        "computer": this_computer(),
        "requests": [{"id": r.id, "kind": r.kind, "full_name": r.full_name or r.username, "username": r.username,
                      "role": r.role, "role_label": ROLE_LABELS.get(r.role or "", ""), "employee_id": r.employee_id,
                      "division": r.division or "", "created_at": as_utc(r.created_at).isoformat()} for r in pending],
        "security_events": [{"seq": e.seq, "action": e.action, "detail": e.detail, "actor": e.actor,
                             "created_at": e.created_at} for e in events],
    }


# ---- AI models and performance (design 34) ---------------------------------------------------------


def performance(db: Session) -> list[dict]:
    """Measured from real runs: for each AI mode, how long outputs and fact sheets took."""
    rows: dict[str, dict] = {}
    for job in db.scalars(select(Job).where(Job.ai_mode.is_not(None))):
        r = rows.setdefault(job.ai_mode, {"ai_mode": job.ai_mode, "outputs": 0, "seconds": 0.0, "tokens": 0,
                                          "token_seconds": 0.0, "fact_sheets": 0, "fact_sheet_seconds": 0.0,
                                          "by_type": {}})
        if job.fact_sheet and job.fact_sheet.json.get("seconds") is not None:
            r["fact_sheets"] += 1
            r["fact_sheet_seconds"] += float(job.fact_sheet.json["seconds"])
        for o in job.outputs:
            if o.status != "done" or o.seconds is None:
                continue
            r["outputs"] += 1
            r["seconds"] += o.seconds
            if o.tokens:
                r["tokens"] += o.tokens
                r["token_seconds"] += o.seconds
            t = r["by_type"].setdefault(o.type, {"count": 0, "seconds": 0.0})
            t["count"] += 1
            t["seconds"] += o.seconds
    result = []
    for r in rows.values():
        result.append({
            "ai_mode": r["ai_mode"], "label": AI_LABELS.get(r["ai_mode"], r["ai_mode"]), "outputs": r["outputs"],
            "average_output_seconds": round(r["seconds"] / r["outputs"], 1) if r["outputs"] else None,
            "tokens_per_second": round(r["tokens"] / r["token_seconds"], 2) if r["token_seconds"] else None,
            "fact_sheets": r["fact_sheets"],
            "average_fact_sheet_seconds": round(r["fact_sheet_seconds"] / r["fact_sheets"], 1) if r["fact_sheets"] else None,
            "by_type": [{"type": key, "label": OUTPUT_TYPES[key]["label"], "count": v["count"],
                         "average_seconds": round(v["seconds"] / v["count"], 1)} for key, v in sorted(r["by_type"].items())],
        })
    return result


def language_models() -> list[dict]:
    """Stage 8: translation, voices and speech-to-text, with whether each is installed and in use."""
    from app.lang import stt, translate, tts

    t, v, s = translate.status(), tts.status(), stt.status()
    voices = v["voices"]
    piper = [f"{code}: {x['name']}" for code, x in voices.items() if x["engine"] == "piper"]
    say = [f"{code}: {x['name']}" for code, x in voices.items() if x["engine"] == "say"]

    def state(in_use: bool, ready: bool) -> str:
        return ("in_use" if ready else "missing") if in_use else ("standby" if ready else "off")

    return [
        {"name": "IndicTrans2 (distilled 200M)", "job": "Translation into 22 Indian languages", "made_by": "AI4Bharat (IIT Madras)",
         "runtime": "CTranslate2 on this computer", "status": state(t["engine"] == "indictrans2", t["engine"] != "indictrans2" or t["ready"]),
         "detail": t["detail"] if t["engine"] == "indictrans2" else f"TRANSLATE_ENGINE={t['engine']}"},
        {"name": "Piper voices", "job": "Narration: Hindi, Telugu, Malayalam, Urdu", "made_by": "Piper (data: AI4Bharat, IIT Madras)",
         "runtime": "sherpa-onnx on this computer", "status": state(v["engine"] == "piper", bool(piper)),
         "detail": ", ".join(piper) or "Not installed: run scripts/download-models.py --only tts"},
        {"name": "macOS voices", "job": "Narration fallback: Hindi, Indian English", "made_by": "Apple",
         "runtime": "macOS say", "status": state(v["engine"] in ("piper", "say"), bool(say)),
         "detail": ", ".join(say) or "Only on a Mac"},
        {"name": "IndicConformer", "job": "Speech to text: Hindi, Tamil", "made_by": "AI4Bharat (IIT Madras)",
         "runtime": "onnxruntime on this computer",
         "status": state(s["engine"] == "onnx", s["languages"]["hi"]["ready"] or s["languages"]["ta"]["ready"]),
         "detail": ", ".join(c for c in ("hi", "ta") if s["languages"][c]["ready"]) or "Not installed: run scripts/download-models.py --only stt"},
        {"name": "Whisper small", "job": "Speech to text: English", "made_by": "OpenAI (MIT licence)",
         "runtime": "onnxruntime on this computer", "status": state(s["engine"] == "onnx", s["languages"]["en"]["ready"]),
         "detail": "Installed" if s["languages"]["en"]["ready"] else "Not installed: run scripts/download-models.py --only stt"},
    ]


@router.get("/ai")
def ai_models(db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    mode = settings.ai_mode
    info = llm.describe()
    models = [
        {"name": "Sarvam 30B (GGUF)", "job": "Fact sheet and writing", "made_by": "Sarvam AI", "runtime": "llama.cpp on this computer",
         "status": "in_use" if mode == "local" else "standby", "detail": settings.llm_base_url},
        {"name": "Sarvam hosted", "job": "Fact sheet and writing (development only)", "made_by": "Sarvam AI",
         "runtime": "Internet (not for real data)", "status": "in_use" if mode == "cloud" else "off", "detail": settings.sarvam_model},
        {"name": "Mock AI", "job": "Test answers built from the source by rules", "made_by": "Pramaan AI",
         "runtime": "No model", "status": "in_use" if mode == "mock" else "off", "detail": "For tests and demos"},
        *language_models(),
    ]
    return {"ai_mode": mode, "label": AI_LABELS.get(mode, mode), "model": info.get("model", ""),
            "base_url": info.get("base_url", ""), "models": models, "performance": performance(db),
            "speed_test": app_settings.get("speed_test"), "timeout_seconds": settings.llm_timeout_seconds}


@router.post("/ai/speed-test")
async def speed_test(admin: User = Depends(admin_only)):
    """A short answer from the AI, timed. On the slow local model this takes about a minute."""
    messages = [{"role": "user", "content": "In two short sentences, explain why software updates matter for security."}]
    started = time.monotonic()
    try:
        reply = await run_in_threadpool(llm.chat, messages, 80)
        error = None
    except llm.LLMError as exc:
        reply, error = "", str(exc)
    seconds = round(time.monotonic() - started, 2)
    words = len(reply.split())
    result = {"at": utc_now().isoformat(), "ai_mode": settings.ai_mode, "ok": error is None, "error": error,
              "seconds": seconds, "words": words, "words_per_second": round(words / seconds, 2) if seconds and words else None}
    app_settings.put("speed_test", result, by=admin)
    audit.log("system", "speed_test", f"AI speed test ({settings.ai_mode}): " +
              (f"{words} words in {seconds} s" if error is None else f"failed: {error}"), actor=admin)
    return result


# ---- security and policies (design 36) ---------------------------------------------------------------


def security_state(db: Session) -> dict:
    policy = app_settings.policy()
    try:
        signer = get_signer().describe()
    except SigningError as exc:
        signer = {"kind": "dsc", "label": "Class 3 DSC on a USB token", "error": str(exc)}
    holders = db.scalars(select(User).where(User.role == "reviewer", User.is_active.is_(True))).all()
    return {
        "scanner": [{"key": key, "label": label, "on": policy["scanner"].get(key, True)}
                    for key, (label, _) in app_settings.SCANNER_SWITCHES.items()],
        "classification_words": policy["classification_words"],
        "built_in_words": ["TOP SECRET", "SECRET", "CONFIDENTIAL", "RESTRICTED", "FOR OFFICIAL USE ONLY"],
        "idle_minutes": policy["idle_minutes"], "idle_choices": app_settings.IDLE_CHOICES,
        "lock_after": policy["lock_after"], "lock_choices": app_settings.LOCK_CHOICES,
        "tlp": [{"level": level, **LEVEL_INFO[level], "public_allowed": not switched_off(level)} for level in LEVELS],
        "public_outputs": [OUTPUT_TYPES[k]["label"] for k in public_outputs()],
        "encryption": {"database": _database_encrypted(), "files": True, "key_place": ".env (DB_KEY), never in the database"},
        "signer": signer,
        "reviewers": [{"name": u.full_name, "dsc_holder": bool(u.dsc_holder)} for u in holders],
        "max_session_hours": 8,
    }


@router.get("/security")
def get_security(db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    return security_state(db)


class SecurityChange(BaseModel):
    scanner: dict[str, bool] | None = None
    classification_words: list[str] | None = None
    idle_minutes: int | None = None
    lock_after: int | None = None


@router.put("/security")
def change_security(change: SecurityChange, db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    policy = app_settings.policy()
    words: list[str] = []
    if change.scanner is not None:
        unknown = [k for k in change.scanner if k not in app_settings.SCANNER_SWITCHES]
        if unknown:
            raise HTTPException(400, f"Unknown scanner check: {unknown[0]}")
        for key, on in change.scanner.items():
            if policy["scanner"].get(key, True) != on:
                words.append(f"{app_settings.SCANNER_SWITCHES[key][0]} {'on' if on else 'OFF'}")
                policy["scanner"][key] = on
    if change.classification_words is not None:
        cleaned = []
        for word in change.classification_words:
            word = " ".join(word.split()).upper()
            if not 2 <= len(word) <= 40 or not all(c.isalnum() or c in " -" for c in word):
                raise HTTPException(400, "Classification words: 2 to 40 letters, numbers, spaces or dashes.")
            if word not in cleaned:
                cleaned.append(word)
        if cleaned != policy["classification_words"]:
            words.append(f"classification words: {', '.join(cleaned) or 'none extra'}")
            policy["classification_words"] = cleaned[:30]
    if change.idle_minutes is not None:
        if change.idle_minutes not in app_settings.IDLE_CHOICES:
            raise HTTPException(400, "Sign out after 15, 30 or 60 minutes.")
        if change.idle_minutes != policy["idle_minutes"]:
            words.append(f"sign out after {change.idle_minutes} minutes without activity")
            policy["idle_minutes"] = change.idle_minutes
    if change.lock_after is not None:
        if change.lock_after not in app_settings.LOCK_CHOICES:
            raise HTTPException(400, "Lock after 3, 5 or 10 wrong passwords.")
        if change.lock_after != policy["lock_after"]:
            words.append(f"lock after {change.lock_after} wrong passwords")
            policy["lock_after"] = change.lock_after
    if words:
        app_settings.put("security", policy, by=admin)
        audit.log("security", "policy_changed", f"Changed the security policy: {'; '.join(words)}", actor=admin)
    return security_state(db)
