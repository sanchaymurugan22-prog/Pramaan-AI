import { useEffect, useState } from 'react'
import { getJob, retryJob, type JobDetail, type JobOutput } from '../api'
import { Icon } from '../components/Icon'
import { OUTPUT_ICONS } from '../components/outputIcons'
import { links } from '../router'
import { duration, jobNo, shortTime } from './format'
import { t } from '../i18n'

// Design "12 · Generating (live progress)": step 4 of a new transformation. Asks the backend for news
// every 2 seconds. The page can be left at any time: the AI carries on, and a notification says when
// everything is ready.

const POLL_MS = 2000

function OutputRow({ output, step, now }: { output: JobOutput; step: string; now: number }) {
  let chip
  if (output.status === 'done') {
    chip = (
      <span className="chip chip-green">
        <Icon name="check" size={14} strokeWidth={2.4} />
        {t("Ready")}
      </span>
    )
  } else if (output.status === 'generating') {
    chip = (
      <span className="chip chip-saffron">
        <span className="spinner" aria-hidden="true" />
        {t("Writing")}
      </span>
    )
  } else if (output.status === 'failed') {
    chip = (
      <span className="chip chip-red">
        <Icon name="warning" size={14} strokeWidth={2.2} />
        {t("Failed")}
      </span>
    )
  } else {
    chip = (
      <span className="chip chip-neutral">
        <Icon name="clock" size={14} strokeWidth={2.2} />
        {t("Queued")}
      </span>
    )
  }
  const started = output.started_at ? new Date(output.started_at).getTime() : now
  const detail =
    output.status === 'done'
      ? `EN · ${duration(output.seconds ?? 0)}`
      : output.status === 'generating'
        ? `${step.split(' · ')[1] ?? 'Writing'} · ${duration((now - started) / 1000)}`
        : output.status === 'failed'
          ? output.error ?? 'Could not be written'
          : t("Starts after the outputs above")
  return (
    <li className="progress-row">
      <span className="progress-icon" aria-hidden="true">
        <Icon name={OUTPUT_ICONS[output.type] ?? 'file'} size={19} />
      </span>
      <span className="stack gap-1 grow">
        <span className="progress-name">{t(output.label)}</span>
        <span className="progress-detail">{detail}</span>
      </span>
      {chip}
    </li>
  )
}

// The first few sentences of the most recently finished output, to read while the rest is written.
function LivePreview({ job }: { job: JobDetail }) {
  const latest = [...job.outputs]
    .filter((o) => o.status === 'done' && o.fields.length > 0)
    .sort((a, b) => (b.finished_at ?? '').localeCompare(a.finished_at ?? ''))[0]
  const text = latest ? latest.fields.slice(0, 3).map((f) => f.text).join('\n\n') : job.fact_sheet?.summary
  return (
    <section className="card card-pad stack gap-14" aria-labelledby="preview-title">
      <div className="row gap-10 wrap">
        <h2 id="preview-title">{t("Live preview")}</h2>
        <div className="grow" />
        <span className="chip chip-saffron">{latest ? t("{label} · English", { label: latest.label }) : job.fact_sheet ? t("Fact sheet") : t("Waiting")}</span>
      </div>
      <div className="preview-text" aria-live="off">
        {text ? <p className="pre-line">{text}</p> : <p className="muted">{t("The first finished output appears here.")}</p>}
      </div>
      <ul className="clean-list-plain stack gap-8 small muted">
        <li className="row gap-8">
          <Icon name="bolt" size={16} />
          {t("One fact sheet is read once and reused for every output.")}
        </li>
        <li className="row gap-8">
          <Icon name="bell" size={16} />
          {t("You will get a notification when everything is ready.")}
        </li>
      </ul>
    </section>
  )
}

export function Progress({ jobId }: { jobId: number }) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const [round, setRound] = useState(0)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let timer: number | undefined
    let stopped = false
    async function load() {
      try {
        const latest = await getJob(jobId)
        if (stopped) return
        setJob(latest)
        setError('')
        if (latest.status === 'generating') timer = window.setTimeout(load, POLL_MS)
      } catch (e) {
        if (stopped) return
        setError(e instanceof Error ? e.message : t("Could not load the job."))
        timer = window.setTimeout(load, POLL_MS * 3)
      }
    }
    load()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [jobId, round])

  const generating = job?.status === 'generating'
  useEffect(() => {
    if (!generating) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [generating])

  if (!job) {
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>
  }

  const total = job.outputs.length
  const done = job.outputs.filter((o) => o.status === 'done').length
  const failed = job.outputs.filter((o) => o.status === 'failed').length
  const finished = !generating
  // Time left: the average time of the finished outputs, times the outputs still to write
  const timed = job.outputs.filter((o) => o.status === 'done' && o.seconds)
  const average = timed.length ? timed.reduce((sum, o) => sum + (o.seconds ?? 0), 0) / timed.length : null
  const left = average !== null ? Math.round((average * (total - done - failed)) / 60) : null
  const started = job.outputs.map((o) => o.started_at).filter(Boolean).sort()[0] ?? job.updated_at
  const percent = total ? Math.round((done / total) * 100) : 0
  const sheet = job.fact_sheet

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">
            {t("Job {id} · {value}", { id: jobNo(job.id), value: finished ? t("Finished") : t("Generating") })}</div>
          <h1>
            {finished ? t("{done} of {total} outputs ready", { done: done, total: total }) : t("Creating {total} output{n} in English", { total: total, n: total === 1 ? '' : 's' })}
          </h1>
          <p className="muted page-lead">
            {t("{title} · started {started}{value}", { title: job.title, started: shortTime(started), value: !finished && (left === null ? t(" · estimating time left…") : left <= 1 ? t(" · about a minute left") : t(" · about {left} minutes left", { left: left })) })}</p>
        </div>
        <div className="grow" />
        <a href={job.created_via === 'emergency' ? links.dashboard : links.jobs} className="btn btn-outline">
          {t("Keep working elsewhere")}
        </a>
        {done > 0 ? (
          <a href={links.job(job.id)} className="btn btn-saffron">
            {finished ? t("Open results") : t("Open ready outputs")}
            <Icon name="arrowRight" size={18} strokeWidth={2} />
          </a>
        ) : (
          <button type="button" className="btn btn-saffron" disabled>
            {t("Open ready outputs")}
          </button>
        )}
      </div>

      <p className="sr-only" role="status" aria-live="polite">
        {finished ? t("Finished: {done} of {total} outputs ready.", { done: done, total: total }) : t("{done} of {total} outputs ready.", { done: done, total: total })}
      </p>
      {error && <div className="alert alert-red">{error}</div>}
      {finished && job.status === 'in_review' && job.created_via === 'emergency' && (
        <div className="alert alert-green" role="status">
          {t("Every output is ready and the alert went to the Reviewers for fast-track approval. You will be notified when it is signed.")}
        </div>
      )}
      {finished && (job.status === 'failed' || failed > 0) && (
        <div className="alert alert-red row gap-10 wrap">
          <span className="grow">{job.error ?? t("{failed} output(s) could not be written.", { failed: failed })}</span>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={async () => {
              setJob(await retryJob(job.id))
              setRound((n) => n + 1)
            }}
          >
            <Icon name="refresh" size={16} strokeWidth={2} />
            {t("Try again")}
          </button>
        </div>
      )}

      <div className="progress-grid">
        <section className="card card-pad stack gap-12" aria-labelledby="sheet-title">
          <div className="row gap-12 align-start">
            <span className="progress-icon tone-green" aria-hidden="true">
              <Icon name="summary" size={19} />
            </span>
            <span className="stack gap-1 grow">
              <h2 id="sheet-title">{t("Fact sheet")}</h2>
              <span className="muted small">{t("Read once, reused by every output")}</span>
            </span>
            {sheet ? (
              <span className="chip chip-green">
                <Icon name="check" size={14} strokeWidth={2.4} />
                {t("Done ·")} {duration(sheet.seconds)}
              </span>
            ) : (
              <span className="chip chip-saffron">
                <span className="spinner" aria-hidden="true" />
                {t("Reading")}
              </span>
            )}
          </div>
          {!sheet && <p className="muted small">{job.step || t("Waiting in the queue")}…</p>}
          {sheet && (
            <ul className="clean-list-plain sheet-list">
              {sheet.key_facts.slice(0, 5).map((fact) => (
                <li key={fact.id} className="sheet-fact">
                  <Icon name={fact.quote_found === 'no' ? 'warning' : 'check'} size={18} color={fact.quote_found === 'no' ? 'var(--red-dark)' : 'var(--green-dark)'} strokeWidth={2.2} />
                  <span className="grow">
                    {fact.text}
                    {fact.quote_found === 'no' && <span className="sr-only"> {t("(not found in the source)")}</span>}
                  </span>
                  <span className="mono muted small" title={t("Source {source_id}, page {page}", { source_id: fact.source_id, page: fact.page })}>
                    p.{fact.page}
                  </span>
                </li>
              ))}
              {sheet.key_facts.length > 5 && <li className="muted small">{t("+ {value} more facts", { value: sheet.key_facts.length - 5 })}</li>}
            </ul>
          )}
        </section>

        <section className="card card-pad stack gap-12" aria-labelledby="outputs-title">
          <div className="row gap-10">
            <h2 id="outputs-title">{t("Outputs")}</h2>
            <div className="grow" />
            <span className="muted">
              {t("{done} of {total} ready", { done: done, total: total })}</span>
          </div>
          <div className="bar bar-thick" role="progressbar" aria-label={t("Outputs ready")} aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-valuetext={t("{done} of {total} ready", { done: done, total: total })}>
            <div className="bar-fill fill-fair" style={{ width: `${percent}%` }} />
          </div>
          <ul className="clean-list-plain">
            {job.outputs.map((output) => (
              <OutputRow key={output.id} output={output} step={job.step} now={now} />
            ))}
          </ul>
        </section>

        <LivePreview job={job} />
      </div>
    </main>
  )
}
