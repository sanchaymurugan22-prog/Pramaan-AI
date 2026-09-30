import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  downloadUrl,
  getJob,
  getVersion,
  kitUrl,
  listVersions,
  regenerateOutput,
  retryJob,
  type FactSheet,
  type JobDetail,
  type JobOutput,
  type VersionDetail,
  type VersionSummary,
} from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { StatusChip } from '../components/StatusChip'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { duration, factLookup, FOUND_LABELS, shortTime } from './format'
import { OutputEditor } from './OutputEditor'
import { ReviewPanel } from './ReviewPanel'
import { LeakAlert, SafetySection } from './SafetySection'
import { IndicatorTable, OutputBody, SeverityChip } from './OutputViews'
import { CheckWarnings, ConsistencyPanel, QualityCard, ScoreBadge, SourcePanel } from './TracePanels'
import { FactChip, TraceProvider } from './trace'
import { NO_SELECTION, sentencesByPath, type Selection } from './traceState'

const POLL_MS = 2000

type Tab = 'facts' | number // the fact sheet, or an output id

// Results of one job. While the job is generating, it asks the backend for news every 2 seconds
// and shows the fact sheet, then each output, as soon as they are ready.
// Layout as in the design "13 · Results · Advisory with source trace": a tab per output, the
// output on the left, and on the right the source trace, the warnings and the quality score.
export function Results({ jobId }: { jobId: number }) {
  const { user } = useAuth()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const [pollRound, setPollRound] = useState(0) // bump to start polling again (after "Try again" or "Regenerate")
  const [chosenTab, setTab] = useState<Tab | null>(null) // null until the reviewer picks a tab
  const [selection, setSelection] = useState<Selection>(NO_SELECTION)
  const [editing, setEditing] = useState<number | null>(null) // output id being edited
  const [viewing, setViewing] = useState<Record<number, VersionDetail | undefined>>({}) // old version on screen
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

  // Until a tab is picked: the first finished output, or the fact sheet while nothing is finished yet.
  const tab: Tab = chosenTab ?? job?.outputs.find((o) => o.status === 'done')?.id ?? 'facts'
  const facts = useMemo(() => factLookup(job?.fact_sheet ?? null), [job?.fact_sheet])
  const active = typeof tab === 'number' ? job?.outputs.find((o) => o.id === tab) : undefined
  const viewed = active ? viewing[active.id] : undefined
  const shownQuality = viewed ? viewed.quality : active?.quality
  const byPath = useMemo(() => sentencesByPath(shownQuality?.sentences), [shownQuality])

  if (!job) {
    return (
      <main className="page">
        {error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}
      </main>
    )
  }

  async function tryAgain() {
    try {
      setJob(await retryJob(jobId))
      setPollRound((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not restart the job.')
    }
  }

  async function regenerate(output: JobOutput) {
    const ok = window.confirm(
      `Write the ${output.label} again from the same fact sheet?\n\nThe current text (version ${output.version}) is kept as an older version.`,
    )
    if (!ok) return
    try {
      setViewing((v) => ({ ...v, [output.id]: undefined }))
      setSelection(NO_SELECTION)
      setJob(await regenerateOutput(jobId, output.id))
      setPollRound((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start writing it again.')
    }
  }

  function changeTab(next: Tab) {
    setTab(next)
    setSelection(NO_SELECTION)
    setEditing(null)
  }

  // From the consistency panel or a warning: show that output and that sentence.
  function openSentence(outputId: number, sentenceId: string, factId: string | null) {
    setTab(outputId)
    setEditing(null)
    setViewing((v) => ({ ...v, [outputId]: undefined }))
    setSelection({ outputId, sentenceId, factId, scroll: true })
  }

  const selectedSentence =
    active && selection.outputId === active.id && selection.sentenceId
      ? (shownQuality?.sentences?.find((s) => s.id === selection.sentenceId) ?? null)
      : null
  const done = job.outputs.filter((o) => o.status === 'done')
  // Only Operators change jobs, and not while a job is with a reviewer or approved (the backend refuses too).
  const canChange = user.role === 'operator' && job.status !== 'in_review' && job.status !== 'approved'
  const canRetry =
    canChange && job.status !== 'generating' && (job.status === 'failed' || job.outputs.some((o) => o.status === 'failed'))
  const scored = done.filter((o) => o.quality_score !== null)
  const lowest = scored.reduce<JobOutput | null>((low, o) => (!low || o.quality_score! < low.quality_score! ? o : low), null)
  const jobExplanation =
    scored.length > 0
      ? `Job quality ${job.quality_score} out of 100: the average of the ${scored.length} output score${scored.length === 1 ? '' : 's'}.` +
        (lowest && scored.length > 1 ? ` Lowest: ${lowest.label} (${lowest.quality_score}).` : '') +
        ' Each score counts sentences linked to a fact, quotes found in the source, numbers not in the source, and length rules.'
      : undefined

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-6">
          <div className="eyebrow">
            Job #{job.id}
            {job.version > 1 && ` · v${job.version}`} · {job.sources.length} source{job.sources.length === 1 ? '' : 's'} · English
            {job.owner && ` · by ${job.owner.full_name}`}
          </div>
          <h1>{job.title}</h1>
          <div className="row gap-10 wrap">
            {job.tlp && <TlpLabel tlp={job.tlp} />}
            <StatusChip status={job.status} />
            <span className="chip chip-navy">
              {done.length} of {job.outputs.length} ready
            </span>
            <ScoreBadge score={job.quality_score} explanation={jobExplanation} big />
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
        {/* One .zip with every finished output (latest versions, made without AI) */}
        {done.length > 0 ? (
          <a className="btn btn-saffron" href={kitUrl(job.id)} download>
            <Icon name="box" size={18} strokeWidth={2} />
            Download campaign kit (.zip)
          </a>
        ) : (
          <button type="button" className="btn btn-saffron" disabled title="Available when an output is ready">
            <Icon name="box" size={18} strokeWidth={2} />
            Download campaign kit (.zip)
          </button>
        )}
      </div>

      {error && <div className="alert alert-red">{error}</div>}
      {job.error && <div className={job.status === 'failed' ? 'alert alert-red' : 'alert alert-yellow'}>{job.error}</div>}
      {job.fact_sheet_check && !job.fact_sheet_check.ok && (
        <div className="alert alert-red stack gap-4" role="alert">
          <strong className="row gap-8">
            <Icon name="warning" size={18} strokeWidth={2.2} />
            The fact sheet does not match the source. Do not publish.
          </strong>
          <span>
            Only {job.fact_sheet_check.found} of {job.fact_sheet_check.total} fact quotes were found in the source, so the
            AI may have made facts up. Every quality score is capped at 50. Regenerate, or check each fact marked
            “Not found in source”.
          </span>
        </div>
      )}
      {job.status === 'draft' && (
        <div className="alert alert-yellow">
          This job has not started yet.{' '}
          {user.role === 'operator' && <a href={links.safety(job.id)}>Continue with the safety check</a>}
        </div>
      )}
      <ReviewPanel job={job} onChange={setJob} />

      <Sources job={job} />
      <SafetySection job={job} />
      <ConsistencyPanel
        consistency={job.consistency}
        generating={job.status === 'generating'}
        facts={facts}
        onOpen={openSentence}
        onFact={(factId) => setSelection({ outputId: null, sentenceId: null, factId })}
      />

      <nav className="output-tabs" aria-label="Outputs">
        <TabButton current={tab === 'facts'} onClick={() => changeTab('facts')}>
          <Icon name="file" size={18} />
          Fact sheet
          {job.fact_sheet && <span className="tab-count">{job.fact_sheet.key_facts.length}</span>}
        </TabButton>
        {job.outputs.map((o) => (
          <TabButton key={o.id} current={tab === o.id} onClick={() => changeTab(o.id)}>
            {o.label}
            {o.status === 'generating' && <span className="spinner" aria-label="Writing" />}
            {o.status === 'queued' && <span className="tab-count">…</span>}
            {o.status === 'failed' && <span className="tab-count tab-failed">!</span>}
            {o.status === 'done' && (o.quality?.leaks?.length ?? 0) > 0 && (
              <span className="tab-count tab-failed" title="Private data found">!</span>
            )}
            {o.status === 'done' && <ScoreBadge score={o.quality_score} explanation={o.quality?.explanation} inButton />}
          </TabButton>
        ))}
      </nav>

      <TraceProvider value={{ outputId: active?.id ?? null, byPath, facts, selection, select: setSelection }}>
        <div className="results-grid">
          <div className="results-main">
            {tab === 'facts' && (
              <FactSheetCard
                sheet={job.fact_sheet}
                generating={job.status === 'generating'}
                step={job.step}
                selectedFact={selection.outputId === null ? selection.factId : null}
                onFact={(factId) => setSelection({ outputId: null, sentenceId: null, factId })}
              />
            )}
            {active && (
              <OutputCard
                key={active.id}
                job={job}
                output={active}
                now={now}
                editing={editing === active.id}
                onEdit={(on) => {
                  setEditing(on ? active.id : null)
                  setSelection(NO_SELECTION)
                }}
                onSaved={(updated) => {
                  setJob(updated)
                  setEditing(null)
                  setViewing((v) => ({ ...v, [active.id]: undefined }))
                }}
                viewed={viewed}
                onView={(version) => {
                  setViewing((v) => ({ ...v, [active.id]: version }))
                  setSelection(NO_SELECTION)
                }}
                onRegenerate={() => regenerate(active)}
                canChange={canChange}
              />
            )}
          </div>
          <aside className="results-side">
            <SourcePanel
              jobId={job.id}
              facts={facts}
              selection={selection}
              sentence={selectedSentence}
              where={active && selectedSentence ? `${active.label} · ${selectedSentence.label}` : ''}
              select={setSelection}
              onClose={() => setSelection(NO_SELECTION)}
            />
            {active && shownQuality && editing !== active.id && (
              <>
                <CheckWarnings outputId={active.id} quality={shownQuality} select={setSelection} />
                <QualityCard
                  quality={shownQuality}
                  versionNote={
                    viewed
                      ? `Version ${viewed.version} · ${viewed.origin_label} (older version)`
                      : `Version ${active.version} · ${active.origin_label}`
                  }
                />
              </>
            )}
          </aside>
        </div>
      </TraceProvider>
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

function TabButton({ current, onClick, children }: { current: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" className={current ? 'output-tab is-current' : 'output-tab'} aria-current={current ? 'page' : undefined} onClick={onClick}>
      {children}
    </button>
  )
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
      <div className="row gap-10 wrap">
        <h2>{title}</h2>
        <div className="grow" />
        {right}
        {json !== undefined && (
          <button type="button" className="btn btn-outline btn-xs" onClick={() => setShowJson(!showJson)}>
            <Icon name="code" size={16} strokeWidth={2} />
            {showJson ? 'Hide JSON' : 'JSON'}
          </button>
        )}
      </div>
      {showJson ? <pre className="json-box">{JSON.stringify(json, null, 2)}</pre> : children}
    </section>
  )
}

type FactSheetProps = {
  sheet: FactSheet | null
  generating: boolean
  step: string
  selectedFact: string | null
  onFact: (factId: string) => void
}

function FactSheetCard({ sheet, generating, step, selectedFact, onFact }: FactSheetProps) {
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
      <p className="muted small">Click a fact to see its quote highlighted in the source.</p>
      {/\[[A-Z]+(?:-[A-Z]+)*-\d+\]/.test(JSON.stringify(sheet.key_facts)) && (
        <p className="hint">
          Values like <code className="mono">[PHONE-1]</code> were hidden in the Safety check: this is exactly what the
          AI saw. Internal outputs show the real value again where you allowed it; public outputs show a label.
        </p>
      )}
      {notFound > 0 && (
        <div className="alert alert-red">
          {notFound} fact{notFound === 1 ? '' : 's'} not found in the source (in red below). Sentences that use only
          these facts are marked “Linked fact not verified”. Check them before using.
        </div>
      )}
      {sheet.truncated && <div className="alert alert-yellow">The fact sheet was cut off at the token limit.</div>}

      <div className="fact-list">
        {sheet.key_facts.map((fact) => (
          <button
            type="button"
            key={fact.id}
            className={['fact', fact.quote_found === 'no' && 'is-unverified', selectedFact === fact.id && 'is-selected'].filter(Boolean).join(' ')}
            onClick={() => onFact(fact.id)}
          >
            <span className="fact-id">{fact.id}</span>
            <span className="stack gap-4 grow">
              <span>{fact.text}</span>
              <span className="fact-quote">
                “{fact.quote}” — {fact.source_id}, page {fact.page}{' '}
                <span className={`chip chip-xs ${{ exact: 'chip-green', close: 'chip-saffron', no: 'chip-red' }[fact.quote_found]}`}>
                  {FOUND_LABELS[fact.quote_found]}
                </span>
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="fact-extras">
        {sheet.dates.length > 0 && (
          <div className="stack gap-6">
            <span className="section-label">Dates</span>
            <ul className="clean-list small">
              {sheet.dates.map((d, i) => (
                <li key={d.id ?? i}>
                  {d.id && <FactChip id={d.id} active={selectedFact === d.id} onClick={() => onFact(d.id!)} />}{' '}
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
                  <FactChip id={a.id} active={selectedFact === a.id} onClick={() => onFact(a.id)} /> {a.text}
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

type OutputCardProps = {
  job: JobDetail
  output: JobOutput
  now: number
  editing: boolean
  onEdit: (on: boolean) => void
  onSaved: (job: JobDetail) => void
  viewed: VersionDetail | undefined
  onView: (version: VersionDetail | undefined) => void
  onRegenerate: () => void
  canChange: boolean // Operator, and the job is not with a reviewer or approved
}

function OutputCard({ job, output, now, editing, onEdit, onSaved, viewed, onView, onRegenerate, canChange }: OutputCardProps) {
  const [showVersions, setShowVersions] = useState(false)
  const busy = job.status === 'generating'
  const hasText = Boolean(output.content)
  const q = output.quality

  let status: ReactNode = null
  if (output.status === 'generating') {
    const started = output.started_at ? new Date(output.started_at).getTime() : now
    status = (
      <span className="row gap-6 chip chip-saffron">
        <span className="spinner" aria-hidden="true" />
        Writing… {duration((now - started) / 1000)}
      </span>
    )
  } else if (output.status === 'queued') {
    status = <span className="chip chip-neutral">Waiting</span>
  } else if (output.status === 'failed') {
    status = <span className="chip chip-red">Failed</span>
  } else if (output.seconds !== null && output.seconds > 0) {
    status = (
      <span className="muted small">
        {duration(output.seconds)}
        {output.tokens ? ` · ${output.tokens} tokens` : ''}
      </span>
    )
  }

  const toolbar = hasText && (
    <>
      <span className={output.origin === 'human' ? 'chip chip-saffron' : 'chip chip-neutral'} title="Latest version">
        {output.origin === 'human' && <Icon name="pencil" size={14} strokeWidth={2.2} />}v{output.version} · {output.origin_label}
      </span>
      {status}
      <button type="button" className="btn btn-outline btn-xs" onClick={() => setShowVersions(!showVersions)} aria-expanded={showVersions}>
        <Icon name="history" size={16} />
        Versions
      </button>
      {canChange && (
        <>
          <button
            type="button"
            className="btn btn-saffron-outline btn-xs"
            onClick={onRegenerate}
            disabled={busy || editing}
            title={busy ? 'Wait until the AI has finished' : 'Write this output again from the same fact sheet'}
          >
            <Icon name="refresh" size={16} strokeWidth={2} />
            Regenerate
          </button>
          <button
            type="button"
            className="btn btn-outline btn-xs"
            onClick={() => onEdit(!editing)}
            disabled={busy || output.status !== 'done'}
            title={busy ? 'Wait until the AI has finished' : 'Change the text yourself'}
          >
            <Icon name="pencil" size={16} strokeWidth={2} />
            {editing ? 'Stop editing' : 'Edit'}
          </button>
        </>
      )}
    </>
  )

  return (
    <Card title={output.label} right={toolbar || status} json={(viewed?.content ?? output.content) || undefined}>
      {showVersions && hasText && (
        <VersionList jobId={job.id} output={output} viewed={viewed} onView={onView} onClose={() => setShowVersions(false)} />
      )}
      {output.status === 'failed' && <div className="alert alert-red">{output.error}</div>}
      {output.status === 'done' && output.error && <div className="alert alert-yellow">{output.error}</div>}
      {!viewed && <LeakAlert output={output} />}
      {output.status === 'queued' && (
        <p className="muted">{hasText ? 'Waiting to be written again. The current version stays until then.' : 'Will be written after the outputs above.'}</p>
      )}
      {output.status === 'generating' && (
        <p className="muted">
          {hasText
            ? `The AI is writing a new version from the fact sheet. Version ${output.version} below stays until it is ready.`
            : 'The AI is writing this from the fact sheet. It appears here when finished.'}
        </p>
      )}
      {q && q.unknown_fact_ids.length > 0 && !viewed && (
        <div className="alert alert-yellow">Refers to fact ids that do not exist: {q.unknown_fact_ids.join(', ')}.</div>
      )}

      {editing && <OutputEditor jobId={job.id} output={output} onSaved={onSaved} onCancel={() => onEdit(false)} />}

      {!editing && viewed && (
        <div className="version-banner">
          <Icon name="history" size={18} />
          <span className="grow">
            You are looking at <strong>version {viewed.version}</strong> ({viewed.origin_label}
            {viewed.created_at ? `, ${shortTime(viewed.created_at)}` : ''}). Downloads always use the latest version (v{output.version}).
          </span>
          <button type="button" className="btn btn-outline btn-xs" onClick={() => onView(undefined)}>
            Back to latest
          </button>
        </div>
      )}

      {!editing && hasText && (viewed?.content ?? output.content) && (
        <div className={output.status === 'done' || viewed ? '' : 'is-stale'}>
          {output.type === 'infographic' && !viewed && !(output.quality?.leaks ?? []).length ? (
            <div className="infographic-layout">
              <InfographicPreview jobId={job.id} output={output} />
              <OutputBody type={output.type} content={output.content!} />
            </div>
          ) : (
            <OutputBody type={output.type} content={(viewed?.content ?? output.content)!} />
          )}
        </div>
      )}
      {!editing && output.status === 'done' && <Downloads jobId={job.id} output={output} tlp={job.tlp} />}
    </Card>
  )
}

// Every version of an output, newest first. "View" shows an older one (read only).
function VersionList({ jobId, output, viewed, onView, onClose }: {
  jobId: number
  output: JobOutput
  viewed: VersionDetail | undefined
  onView: (version: VersionDetail | undefined) => void
  onClose: () => void
}) {
  const [versions, setVersions] = useState<VersionSummary[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    listVersions(jobId, output.id)
      .then(setVersions)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the versions.'))
  }, [jobId, output.id, output.version])

  async function view(number: number) {
    if (number === output.version) return onView(undefined)
    try {
      onView(await getVersion(jobId, output.id, number))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load that version.')
    }
  }

  return (
    <div className="version-list">
      <div className="row gap-8">
        <span className="section-label grow">Versions</span>
        <button type="button" className="icon-btn icon-btn-sm" aria-label="Close versions" onClick={onClose}>
          <Icon name="cross" size={16} />
        </button>
      </div>
      {error && <div className="alert alert-red small">{error}</div>}
      {!versions && !error && <p className="muted small">Loading…</p>}
      {versions?.map((v) => {
        const current = v.version === output.version
        const shown = viewed ? viewed.version === v.version : current
        return (
          <div key={v.version} className={shown ? 'version-row is-shown' : 'version-row'}>
            <strong className="mono">v{v.version}</strong>
            <span className="grow">
              {v.origin_label}
              {v.created_at && <span className="muted"> · {shortTime(v.created_at)}</span>}
              {current && <span className="chip chip-green chip-xs">Latest</span>}
            </span>
            <ScoreBadge score={v.quality_score} />
            <button type="button" className="btn btn-outline btn-xs" disabled={shown} onClick={() => view(v.version)}>
              {shown ? 'On screen' : 'View'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

// Button text for each file type. The video package's Word file is its script and storyboard.
const FORMAT_LABELS: Record<string, string> = {
  pdf: 'PDF',
  docx: 'Word (.docx)',
  pptx: 'PowerPoint (.pptx)',
  png: 'Image (.png)',
  srt: 'Subtitles (.srt)',
  txt: 'Text (.txt)',
}

function formatLabel(type: string, format: string): string {
  if (type === 'video_package' && format === 'docx') return 'Script & storyboard (.docx)'
  return FORMAT_LABELS[format] ?? format.toUpperCase()
}

// Download links for one finished output (always its latest version). Plain links: the browser saves the file.
function Downloads({ jobId, output, tlp }: { jobId: number; output: JobOutput; tlp: JobDetail['tlp'] }) {
  if (output.formats.length === 0) return null
  if ((output.quality?.leaks ?? []).length > 0) {
    return (
      <div className="download-row">
        <span className="section-label">Download blocked</span>
        <span className="small" style={{ color: 'var(--red-dark)' }}>
          Private data found. Edit it out to download.
        </span>
      </div>
    )
  }
  return (
    <div className="download-row">
      <span className="section-label">Download v{output.version}</span>
      {tlp && <TlpLabel tlp={tlp} />}
      {output.formats.map((format) => (
        <a key={format} className="btn btn-outline btn-xs" href={downloadUrl(jobId, output.id, format)} download>
          <Icon name="download" size={16} strokeWidth={2} />
          {formatLabel(output.type, format)}
        </a>
      ))}
      <span className="muted small">AI-assisted · pending human approval</span>
    </div>
  )
}

// The real PNG, drawn by the backend. The version in the address makes the browser fetch it
// again after an edit or a regeneration.
function InfographicPreview({ jobId, output }: { jobId: number; output: JobOutput }) {
  const src = `${downloadUrl(jobId, output.id, 'png', true)}&v=${output.version}`
  return (
    <a className="infographic-preview" href={src} target="_blank" rel="noreferrer" title="Open the full-size image">
      <img src={src} alt="Infographic preview" width={1080} height={1350} />
    </a>
  )
}
