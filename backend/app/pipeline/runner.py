"""Runs jobs in the background, one at a time.

The local model can only work on one request at a time (llama-server runs with -np 1), so jobs
wait in a queue. Each step is saved to the database as soon as it finishes, so the web page can
show the fact sheet and every output as they arrive.

A job can be run again safely: finished steps (the fact sheet, done outputs) are skipped. That is
used to resume unfinished jobs when the server restarts, by the "Try again" button, and by
"Regenerate" (which marks one finished output as queued again; its old text is kept as a version).
After each output, every check is run again (checks.recheck_job), so scores appear as outputs arrive.

Only jobs that have passed the Safety check are run ("draft" jobs wait for the operator). Every AI
call gets the job's Masker, so values the operator chose to hide never reach the model.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app import audit, notifications
from app.ai import llm
from app.config import settings
from app.db import FactSheet, Job, Review, SessionLocal, utc_now
from app.pipeline.factsheet import SourcePages, build_fact_sheet
from app.pipeline.generate import generate_output, rewrite_output
from app.pipeline.ingest import load_pages
from app.pipeline.checks import recheck_job
from app.pipeline.output_types import OUTPUT_TYPES
from app.pipeline.versions import save_version
from app.safety.masking import Masker

log = logging.getLogger("pramaan.runner")

# One worker thread = one job at a time, in the order they were submitted.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pramaan-job")


def submit(job_id: int) -> None:
    """Put a job in the queue. Returns straight away."""
    _executor.submit(run_job, job_id)


def resume_unfinished() -> None:
    """Called when the server starts: queue again any job that was still running when it stopped."""
    with SessionLocal() as db:
        for job_id in db.scalars(select(Job.id).where(Job.status == "generating").order_by(Job.id)):
            submit(job_id)


def run_job(job_id: int) -> None:
    """Build the fact sheet (if not done yet), then each output that is not done yet."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        try:
            _run(db, job)
        except Exception as exc:  # never leave a job stuck in "generating"
            log.exception("Job %s failed", job_id)
            db.rollback()
            job.status, job.step, job.error = "failed", "", f"Unexpected error: {exc}"
            notifications.job_finished(db, job, 0, len(job.outputs))
            db.commit()


def _run(db, job: Job) -> None:
    job.status, job.error = "generating", None
    job.ai_mode = settings.ai_mode  # shown on "My jobs": which AI wrote it
    report = _StepReporter(db, job)
    report("Starting")
    masker = Masker(job.safety_json)

    if job.fact_sheet is None:
        sources = [SourcePages(s.source_key, s.filename, load_pages(s.text_path)) for s in job.sources]
        try:
            sheet = build_fact_sheet(sources, on_progress=report, masker=masker)
        except llm.LLMError as exc:
            job.status, job.step, job.error = "failed", "", f"Could not build the fact sheet: {exc}"
            notifications.job_finished(db, job, 0, len(job.outputs))
            db.commit()
            return
        db.add(FactSheet(job=job, json=sheet))
        db.commit()

    sheet = job.fact_sheet.json
    # English outputs first, then the translations (Stage 8): each is made from its finished English output
    for output in sorted(job.outputs, key=lambda o: (o.language != "en", o.position)):
        if output.status == "done":
            continue
        if output.language != "en":
            _translate(db, job, output, masker, report)
            recheck_job(db, job)
            continue
        if output.type == "sms":  # Stage 8: the alert's text message is what the Operator wrote, not the AI's
            if not output.content_json:
                message = (job.alert_json or {}).get("message", "")
                save_version(db, output, {"message": {"text": message, "fact_ids": []}}, "operator")
            output.status, output.finished_at, output.seconds = "done", utc_now(), 0.0
            db.commit()
            recheck_job(db, job)
            continue
        output.status, output.error, output.started_at = "generating", None, utc_now()
        had_text = bool(output.content_json)  # True when regenerating an output that was already written
        change = output.rewrite if had_text else None  # "shorter" / "formal" / "simpler"
        output.rewrite = None
        step = f"{'Rewriting' if change else 'Writing'} the {OUTPUT_TYPES[output.type]['label']}"
        report(step)
        try:
            progress = lambda note, step=step: report(f"{step} · {note}")  # noqa: E731
            if change:
                result = rewrite_output(output.type, sheet, output.content_json, change, job.settings_json,
                                        on_progress=progress, masker=masker)
            else:
                result = generate_output(output.type, sheet, job.settings_json, on_progress=progress, masker=masker)
        except llm.LLMError as exc:
            if had_text:  # keep the previous version rather than losing it
                output.status, output.error = "done", f"Could not write it again ({exc}). The previous version is kept."
            else:
                output.status, output.error = "failed", str(exc)
        else:
            save_version(db, output, result.content, change or ("regenerated" if had_text else "ai"))
            output.status = "done"
            output.truncated, output.seconds, output.tokens = result.truncated, result.seconds, result.tokens
            queue_translations(job, output)  # a new English text: its translations are made again
        output.finished_at = utc_now()
        db.commit()
        recheck_job(db, job)

    failed = [o for o in job.outputs if o.status != "done"]
    recheck_job(db, job)  # every check, BEFORE the job is shown as finished (fast-track needs the leak check)
    job.step = ""
    if len(failed) == len(job.outputs):
        job.status, job.error = "failed", f"No output could be written. {failed[0].error or ''}".strip()
    else:
        job.status = "ready"
        job.error = f"{len(failed)} output(s) failed. Use 'Try again' to retry them." if failed else None
    notifications.job_finished(db, job, len(job.outputs) - len(failed), len(failed))
    fast_tracked = _fast_track(db, job)  # in the same commit: an alert never shows as "ready" in between
    db.commit()
    done = len(job.outputs) - len(failed)
    audit.log("system", "generated", f"Wrote {done} of {len(job.outputs)} output{'s' if len(job.outputs) != 1 else ''} "
                                     f"for job #{job.id}" + (f" ({len(failed)} failed)" if failed else ""),
              target=f"job {job.id}")
    if fast_tracked:
        audit.log("review", "submitted", f"Emergency alert job #{job.id} sent for fast-track review",
                  target=f"job {job.id}")


def queue_translations(job: Job, english) -> None:
    """The English output changed (written again, or edited): its translations are made again from it.
    Their native-speaker check starts again too (it was for the old text)."""
    for output in job.outputs:
        if output.language != "en" and output.source_output_id == english.id and output.status != "queued":
            output.status, output.error = "queued", None


def _translate(db, job: Job, output, masker: Masker, report) -> None:
    """Make (or make again) one translated output from its English output."""
    from app.lang import languages
    from app.lang.translate import TranslateError
    from app.pipeline.translation import engine_label, translate_content

    english = next((o for o in job.outputs if o.id == output.source_output_id), None)
    lang = languages.get(output.language)
    step = f"Translating the {OUTPUT_TYPES[output.type]['label']} into {lang.name}"
    report(step)
    output.status, output.error, output.started_at = "generating", None, utc_now()
    db.commit()
    had_text = bool(output.content_json)
    if english is None or english.status != "done" or not english.content_json:
        output.status = "done" if had_text else "failed"
        output.error = "The English output was not written, so it could not be translated."
    else:
        try:
            content, seconds = translate_content(output.type, english.content_json, output.language, masker,
                                                 OUTPUT_TYPES[output.type]["public"])
        except TranslateError as exc:
            output.status = "done" if had_text else "failed"
            output.error = (f"Could not translate it again ({exc}). The previous translation is kept." if had_text
                            else str(exc))
        else:
            save_version(db, output, content, "retranslated" if had_text else "translated")
            output.status, output.seconds, output.tokens, output.truncated = "done", round(seconds, 1), None, False
            output.source_version, output.engine = english.version, engine_label()
    output.finished_at = utc_now()
    db.commit()


def _fast_track(db, job: Job) -> bool:
    """Emergency alerts (Stage 9A): when every output is ready the first time, send the job to the
    Reviewers by itself, marked fast-track. The Operator pressed "Send for fast-track approval" already;
    nothing is published until a Reviewer approves and signs it. If anything failed or private data was
    found, it stays with the Operator. Returns True if it was sent (the caller commits)."""
    if job.created_via != "emergency" or job.status != "ready" or job.reviews:
        return False
    if any(o.status != "done" or (o.quality_json or {}).get("leaks") for o in job.outputs):
        return False
    job.status = "in_review"
    db.add(Review(job=job, user_id=job.owner_id, decision="submitted", job_version=job.version,
                  notes="Emergency alert: fast-track review"))
    notifications.notify_reviewers(db, "alert", f"Fast-track: {job.title}",
                                   (job.alert_json or {}).get("message", "")[:200], job, except_user=job.owner_id)
    return True


class _StepReporter:
    """Saves "what is happening now" (job.step) for the web page to show.

    Progress notes arrive several times a second while the model writes, so those are saved at most
    every 2 seconds. A new step (e.g. "Writing the X thread") is always saved straight away.
    """

    def __init__(self, db, job: Job):
        self.db, self.job, self.last_save = db, job, 0.0

    def __call__(self, message: str) -> None:
        new_step = message.split(" · ")[0] != self.job.step.split(" · ")[0]
        if new_step or time.monotonic() - self.last_save >= 2:
            self.job.step = message
            self.db.commit()
            self.last_save = time.monotonic()
