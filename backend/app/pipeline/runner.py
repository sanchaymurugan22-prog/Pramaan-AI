"""Runs jobs in the background, one at a time.

The local model can only work on one request at a time (llama-server runs with -np 1), so jobs
wait in a queue. Each step is saved to the database as soon as it finishes, so the web page can
show the fact sheet and every output as they arrive.

A job can be run again safely: finished steps (the fact sheet, done outputs) are skipped. That is
used to resume unfinished jobs when the server restarts, by the "Try again" button, and by
"Regenerate" (which marks one finished output as queued again; its old text is kept as a version).
After each output, every check is run again (checks.recheck_job), so scores appear as outputs arrive.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.ai import llm
from app.db import FactSheet, Job, SessionLocal, utc_now
from app.pipeline.factsheet import SourcePages, build_fact_sheet
from app.pipeline.generate import generate_output
from app.pipeline.ingest import load_pages
from app.pipeline.checks import recheck_job
from app.pipeline.output_types import OUTPUT_TYPES
from app.pipeline.versions import save_version

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
            db.commit()


def _run(db, job: Job) -> None:
    job.status, job.error = "generating", None
    report = _StepReporter(db, job)
    report("Starting")

    if job.fact_sheet is None:
        sources = [SourcePages(s.source_key, s.filename, load_pages(s.text_path)) for s in job.sources]
        try:
            sheet = build_fact_sheet(sources, on_progress=report)
        except llm.LLMError as exc:
            job.status, job.step, job.error = "failed", "", f"Could not build the fact sheet: {exc}"
            db.commit()
            return
        db.add(FactSheet(job=job, json=sheet))
        db.commit()

    sheet = job.fact_sheet.json
    for output in job.outputs:
        if output.status == "done":
            continue
        output.status, output.error, output.started_at = "generating", None, utc_now()
        step = f"Writing the {OUTPUT_TYPES[output.type]['label']}"
        report(step)
        had_text = bool(output.content_json)  # True when regenerating an output that was already written
        try:
            result = generate_output(
                output.type, sheet, job.settings_json, on_progress=lambda note, step=step: report(f"{step} · {note}")
            )
        except llm.LLMError as exc:
            if had_text:  # keep the previous version rather than losing it
                output.status, output.error = "done", f"Could not write it again ({exc}). The previous version is kept."
            else:
                output.status, output.error = "failed", str(exc)
        else:
            save_version(db, output, result.content, "regenerated" if had_text else "ai")
            output.status = "done"
            output.truncated, output.seconds, output.tokens = result.truncated, result.seconds, result.tokens
        output.finished_at = utc_now()
        db.commit()
        recheck_job(db, job)

    failed = [o for o in job.outputs if o.status != "done"]
    job.step = ""
    if len(failed) == len(job.outputs):
        job.status, job.error = "failed", f"No output could be written. {failed[0].error or ''}".strip()
    else:
        job.status = "ready"
        job.error = f"{len(failed)} output(s) failed. Use 'Try again' to retry them." if failed else None
    db.commit()
    recheck_job(db, job)


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
