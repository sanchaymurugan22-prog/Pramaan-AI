import { useEffect, useState, type ReactNode } from 'react'
import { getJob, retryJob, type FactSheet, type JobDetail, type JobOutput } from '../api'
import { Icon } from '../components/Icon'
import { StatusChip } from '../components/StatusChip'
import { duration, factLookup, type FactLookup } from './format'
import { IndicatorTable, OutputBody, SeverityChip } from './OutputViews'

const POLL_MS = 2000

// Results of one job. While the job is generating, it asks the backend for news every 2 seconds
// and shows the fact sheet, then each output, as soon as they are ready.
export function Results({ jobId }: { jobId: number }) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const [pollRound, setPollRound] = useState(0) // bump to start polling again (after "Try again")
  const now = useNow(job?.status === 'generating')

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
        setError(e instanceof Error ? e.message : 'Could not load the job.')
        timer = window.setTimeout(load, POLL_MS * 3) // backend may be restarting; keep trying
      }
    }
    load()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [jobId, pollRound])

  async function tryAgain() {
    try {
      setJob(await retryJob(jobId))
      setPollRound((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not restart the job.')
    }
  }

  if (!job) {
    return (
      <main className="page">
        {error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}
      </main>
    )
  }

  const facts = factLookup(job.fact_sheet)
  const done = job.outputs.filter((o) => o.status === 'done').length
  const canRetry = job.status !== 'generating' && (job.status === 'failed' || job.outputs.some((o) => o.status !== 'done'))

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-6">
          <div className="eyebrow">
            Job #{job.id} · {job.sources.length} source{job.sources.length === 1 ? '' : 's'} · English
          </div>
          <h1>{job.title}</h1>
          <div className="row gap-10 wrap">
            <StatusChip status={job.status} />
            <span className="chip chip-navy">
              {done} of {job.outputs.length} ready
            </span>
            {job.status === 'generating' && job.step && (
              <span className="row gap-6 muted small">
                <span className="spinner" aria-hidden="true" />
                {job.step}…
              </span>
            )}
          </div>
        </div>
        <div className="grow" />
        {canRetry && (
          <button type="button" className="btn btn-outline" onClick={tryAgain}>
            <Icon name="refresh" size={18} strokeWidth={2} />
            Try again
          </button>
        )}
      </div>

      {error && <div className="alert alert-red">{error}</div>}
      {job.error && <div className={job.status === 'failed' ? 'alert alert-red' : 'alert alert-yellow'}>{job.error}</div>}

      <Sources job={job} />
      <FactSheetCard sheet={job.fact_sheet} generating={job.status === 'generating'} step={job.step} />
      {job.outputs.map((output) => (
        <OutputCard key={output.id} output={output} facts={facts} now={now} />
      ))}
    </main>
  )
}

// Ticks every second while `active`, so "Writing… 1:23" counts up.
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active])
  return now
}

function Sources({ job }: { job: JobDetail }) {
  return (
    <section className="card card-pad-sm row gap-12 wrap">
      <span className="section-label">Sources</span>
      {job.sources.map((s) => (
        <span key={s.id} className="source-pill" title={`SHA-256 ${s.sha256}`}>
          <Icon name="file" size={16} color="var(--muted)" />
          <strong>{s.id}</strong> {s.filename} · {s.pages} page{s.pages === 1 ? '' : 's'}
        </span>
      ))}
    </section>
  )
}

// A card with a title row, an optional "Show JSON" toggle, and a body.
function Card({ title, right, json, children }: { title: ReactNode; right?: ReactNode; json?: unknown; children: ReactNode }) {
  const [showJson, setShowJson] = useState(false)
  return (
    <section className="card card-pad stack gap-14">
      <div className="row gap-12 wrap">
        <h2>{title}</h2>
        <div className="grow" />
        {right}
        {json !== undefined && (
          <button type="button" className="btn btn-outline btn-xs" onClick={() => setShowJson(!showJson)}>
            <Icon name="code" size={16} strokeWidth={2} />
            {showJson ? 'Hide JSON' : 'Show JSON'}
          </button>
        )}
      </div>
      {showJson ? <pre className="json-box">{JSON.stringify(json, null, 2)}</pre> : children}
    </section>
  )
}

function FactSheetCard({ sheet, generating, step }: { sheet: FactSheet | null; generating: boolean; step: string }) {
  if (!sheet) {
    return (
      <Card title="Fact sheet">
        <p className="muted">
          {generating
            ? 'The AI is reading the source and building the fact sheet. Every output is written from it. ' +
              (step.startsWith('Reading') ? '' : `(${step})`)
            : 'No fact sheet.'}
        </p>
      </Card>
    )
  }
  const notFound = sheet.key_facts.filter((f) => f.quote_found === 'no').length
  return (
    <Card
      title="Fact sheet"
      json={sheet}
      right={
        <>
          <SeverityChip severity={sheet.severity} />
          {sheet.seconds > 0 && <span className="muted small">{duration(sheet.seconds)}</span>}
        </>
      }
    >
      <p className="lead">{sheet.summary}</p>
      {notFound > 0 && (
        <div className="alert alert-yellow">
          {notFound} fact{notFound === 1 ? '' : 's'} could not be matched to the exact words in the source. Check
          them before using.
        </div>
      )}
      {sheet.truncated && <div className="alert alert-yellow">The fact sheet was cut off at the token limit.</div>}

      <div className="fact-list">
        {sheet.key_facts.map((fact) => (
          <div key={fact.id} className={fact.quote_found === 'no' ? 'fact is-unlinked' : 'fact'}>
            <span className="fact-id">{fact.id}</span>
            <div className="stack gap-4 grow">
              <span>{fact.text}</span>
              <span className="fact-quote">
                “{fact.quote}” — {fact.source_id}, page {fact.page}{' '}
                {fact.quote_found === 'exact' && <span className="chip chip-green chip-xs">Found in source</span>}
                {fact.quote_found === 'close' && <span className="chip chip-saffron chip-xs">Close match</span>}
                {fact.quote_found === 'no' && <span className="chip chip-red chip-xs">Not found in source</span>}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="fact-extras">
        {sheet.dates.length > 0 && (
          <div className="stack gap-6">
            <span className="section-label">Dates</span>
            <ul className="clean-list small">
              {sheet.dates.map((d, i) => (
                <li key={i}>
                  <strong>{d.date}</strong> — {d.event}
                </li>
              ))}
            </ul>
          </div>
        )}
        {sheet.recommended_actions.length > 0 && (
          <div className="stack gap-6">
            <span className="section-label">Recommended actions</span>
            <ul className="clean-list small">
              {sheet.recommended_actions.map((a) => (
                <li key={a.id}>
                  <span className="fact-chip">{a.id}</span> {a.text}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {(sheet.indicators.cves.length > 0 || sheet.indicators.ips.length > 0 || sheet.indicators.hashes.length > 0) && (
        <div className="stack gap-6">
          <span className="section-label">Indicators (found in the source by exact pattern)</span>
          <IndicatorTable indicators={sheet.indicators} />
        </div>
      )}
      {sheet.entities.length > 0 && (
        <p className="small muted">
          <strong>Named:</strong> {sheet.entities.map((e) => `${e.name} (${e.type})`).join(', ')}
        </p>
      )}
    </Card>
  )
}

function OutputCard({ output, facts, now }: { output: JobOutput; facts: FactLookup; now: number }) {
  const q = output.quality
  let right: ReactNode = null
  if (output.status === 'done') {
    right = (
      <>
        {q && (
          <span className={q.linked === q.parts ? 'chip chip-green' : 'chip chip-saffron'}>
            {q.linked}/{q.parts} parts linked to facts
          </span>
        )}
        {output.seconds !== null && output.seconds > 0 && (
          <span className="muted small">
            {duration(output.seconds)}
            {output.tokens ? ` · ${output.tokens} tokens` : ''}
          </span>
        )}
      </>
    )
  } else if (output.status === 'generating') {
    const started = output.started_at ? new Date(output.started_at).getTime() : now
    right = (
      <span className="row gap-6 chip chip-saffron">
        <span className="spinner" aria-hidden="true" />
        Writing… {duration((now - started) / 1000)}
      </span>
    )
  } else if (output.status === 'queued') {
    right = <span className="chip chip-neutral">Waiting</span>
  } else {
    right = <span className="chip chip-red">Failed</span>
  }

  return (
    <Card title={output.label} right={right} json={output.content ?? undefined}>
      {output.status === 'failed' && <div className="alert alert-red">{output.error}</div>}
      {output.status === 'queued' && <p className="muted">Will be written after the outputs above.</p>}
      {output.status === 'generating' && (
        <p className="muted">The AI is writing this from the fact sheet. It appears here when finished.</p>
      )}
      {output.status === 'done' && output.content && (
        <>
          {q && q.warnings.length > 0 && (
            <div className="alert alert-yellow">
              {q.warnings.map((w) => (
                <div key={w}>{w}</div>
              ))}
            </div>
          )}
          <OutputBody type={output.type} content={output.content} facts={facts} />
        </>
      )}
    </Card>
  )
}
