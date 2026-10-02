import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import {
  addLanguages,
  downloadUrl,
  listenUrl,
  getJob,
  getVersion,
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
import { Icon, type IconName } from '../components/Icon'
import { LanguagePicker } from '../components/LanguagePicker'
import { languageByCode, useLanguages } from '../languages'
import { OUTPUT_ICONS } from '../components/outputIcons'
import { StatusChip } from '../components/StatusChip'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { duration, factLookup, FOUND_LABELS, jobNo, shortTime, type FactLookup } from './format'
import { OutputEditor } from './OutputEditor'
import { ReviewPanel } from './ReviewPanel'
import { LeakAlert, SafetySection } from './SafetySection'
import { IndicatorTable, OutputBody, SeverityChip, type ViewMeta } from './OutputViews'
import { CheckWarnings, ConsistencyPanel, QualityCard, ScoreBadge, SourcePanel } from './TracePanels'
import { FactChip, TraceProvider } from './trace'
import { NO_SELECTION, sentencesByPath, type Selection } from './traceState'

const POLL_MS = 2000

// A tab: the fact sheet, one output, or "Social posts" (LinkedIn post + X thread together, design 16)
type Tab = 'facts' | 'social' | number
type TabInfo = { key: Tab; label: string; icon: IconName; outputs: JobOutput[] }

// The order of the tabs in the designs 13-18
const TAB_ORDER = ['advisory', 'executive_summary', 'presentation', 'video_package', 'social', 'infographic']
const SOCIAL = ['linkedin_post', 'x_thread']

// Stage 8: the output of a type in the chosen language (the English one if it was not translated into it)
function outputIn(job: JobDetail, type: string, lang: string): JobOutput | undefined {
  return job.outputs.find((o) => o.type === type && o.language === lang) ?? job.outputs.find((o) => o.type === type && o.language === 'en')
}

function tabsOf(job: JobDetail, lang: string): TabInfo[] {
  const tabs: TabInfo[] = []
  for (const kind of TAB_ORDER) {
    if (kind === 'social') {
      const social = SOCIAL.map((t) => outputIn(job, t, lang)).filter((o): o is JobOutput => Boolean(o))
      if (social.length) tabs.push({ key: 'social', label: 'Social posts', icon: 'share', outputs: social })
    } else {
      // The tab key is the English output's id, so the same tab stays open when the language changes
      const english = job.outputs.find((o) => o.type === kind && o.language === 'en')
      const output = outputIn(job, kind, lang)
      if (english && output) tabs.push({ key: english.id, label: output.label, icon: OUTPUT_ICONS[kind] ?? 'file', outputs: [output] })
    }
  }
  tabs.push({ key: 'facts', label: 'Fact sheet', icon: 'summary', outputs: [] })
  return tabs
}

// Results of one job (designs 13-18). While the job is generating, it asks the backend for news every
// 2 seconds and shows each output as soon as it is ready. A tab per output; the output on the left, and
// on the right the source trace, the warnings and the quality score of the output being looked at.
export function Results({ jobId }: { jobId: number }) {
  const { user } = useAuth()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const [pollRound, setPollRound] = useState(0) // bump to start polling again (after "Try again" or "Regenerate")
  const [chosenTab, setTab] = useState<Tab | null>(null) // null until a tab is picked
  const [selection, setSelection] = useState<Selection>(NO_SELECTION)
  const [editing, setEditing] = useState<number | null>(null) // output id being edited
  const [viewing, setViewing] = useState<Record<number, VersionDetail | undefined>>({}) // old version on screen
  const [lang, setLang] = useState('en') // Stage 8: the language shown
  const now = useNow(job?.status === 'generating')
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map())

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

  const facts = useMemo(() => factLookup(job?.fact_sheet ?? null), [job?.fact_sheet])
  const tabs = job ? tabsOf(job, lang) : []
  // Until a tab is picked: the first tab with a finished output, or the fact sheet while nothing is finished.
  const tab: Tab = chosenTab ?? tabs.find((t) => t.outputs.some((o) => o.status === 'done'))?.key ?? 'facts'
  const current = tabs.find((t) => t.key === tab) ?? tabs.at(-1)
  const shown = current?.outputs ?? []
  // The output the side panels describe: the one a sentence was picked in, else the first on screen
  const active = shown.find((o) => o.id === selection.outputId) ?? shown[0]
  const viewed = active ? viewing[active.id] : undefined
  const shownQuality = viewed ? viewed.quality : active?.quality

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
      (output.language !== 'en'
        ? `Translate the ${output.label} again from the English?`
        : `Write the ${output.label} again from the same fact sheet?`) +
        `\n\nThe current text (version ${output.version}) is kept as an older version.`,
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

  function changeLanguage(code: string) {
    setLang(code)
    setSelection(NO_SELECTION)
    setEditing(null)
  }

  function changeTab(next: Tab) {
    setTab(next)
    setSelection(NO_SELECTION)
    setEditing(null)
  }

  // ARIA tabs: arrow keys move between tabs, Home / End to the first / last one
  function onTabKey(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    const moves: Record<string, number> = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1 }
    if (!(e.key in moves)) return
    e.preventDefault()
    const next = tabs[(moves[e.key] + tabs.length) % tabs.length]
    changeTab(next.key)
    tabRefs.current.get(String(next.key))?.focus()
  }

  // From the consistency panel or a warning: show that output and that sentence.
  function openSentence(outputId: number, sentenceId: string, factId: string | null) {
    const output = job?.outputs.find((o) => o.id === outputId)
    if (output && output.language !== lang) setLang(output.language)
    const target = tabsOf(job!, output?.language ?? lang).find((t) => t.outputs.some((o) => o.id === outputId))
    if (target) setTab(target.key)
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
  const hasVersions = job.version > 1 || done.some((o) => o.version > 1)
  const meta = (output: JobOutput): ViewMeta => ({
    title: job.title,
    tlp: job.tlp,
    recordNo: job.record?.current ? job.record.record_no : null,
    audience: job.settings?.audience ?? '',
    quality: viewing[output.id]?.quality ?? output.quality,
  })

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-6">
          <div className="eyebrow">
            Job {jobNo(job.id)}
            {job.version > 1 && ` · v${job.version}`} · {job.sources.length} source{job.sources.length === 1 ? '' : 's'} ·{' '}
            {job.languages.length > 1 ? `${job.languages.length} languages` : 'English'}
            {job.owner && ` · by ${job.owner.full_name}`}
          </div>
          <h1>{job.title}</h1>
        </div>
        <div className="grow" />
        <div className="row gap-10 wrap head-actions">
          <span className="chip chip-navy">
            <Icon name="clock" size={14} strokeWidth={2.2} />
            {done.length} of {job.outputs.length} ready
          </span>
          {job.tlp && <TlpLabel tlp={job.tlp} />}
          <StatusChip status={job.status} />
          <ScoreBadge score={job.quality_score} explanation={jobExplanation} big />
          {canRetry && (
            <button type="button" className="btn btn-outline" onClick={tryAgain}>
              <Icon name="refresh" size={18} strokeWidth={2} />
              Try again
            </button>
          )}
          {hasVersions && (
            <a className="btn btn-outline" href={links.compare(job.id)}>
              <Icon name="compare" size={18} strokeWidth={2} />
              Compare versions
            </a>
          )}
          {done.length > 0 ? (
            <a className="btn btn-outline" href={links.kit(job.id)}>
              <Icon name="box" size={18} strokeWidth={2} />
              Campaign kit
            </a>
          ) : (
            <button type="button" className="btn btn-outline" disabled title="Available when an output is ready">
              <Icon name="box" size={18} strokeWidth={2} />
              Campaign kit
            </button>
          )}
        </div>
      </div>
      {job.status === 'generating' && job.step && (
        <p className="row gap-6 muted small" role="status">
          <span className="spinner" aria-hidden="true" />
          {job.step}… <a href={links.progress(job.id)}>See live progress</a>
        </p>
      )}

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
      {user.role === 'operator' && <ReviewerComments job={job} onOpen={openSentence} />}

      <div className="tab-bar" role="tablist" aria-label="Outputs">
        {tabs.map((t, index) => {
          const isCurrent = t.key === tab
          const scores = t.outputs.map((o) => o.quality_score).filter((n): n is number => n !== null)
          const working = t.outputs.some((o) => o.status === 'generating')
          const waiting = t.outputs.length > 0 && t.outputs.every((o) => o.status === 'queued')
          const problem = t.outputs.some((o) => o.status === 'failed' || (o.status === 'done' && (o.quality?.leaks?.length ?? 0) > 0))
          return (
            <button
              key={String(t.key)}
              ref={(el) => {
                if (el) tabRefs.current.set(String(t.key), el)
              }}
              type="button"
              role="tab"
              id={`tab-${t.key}`}
              aria-selected={isCurrent}
              aria-controls="tab-panel"
              tabIndex={isCurrent ? 0 : -1}
              className={isCurrent ? 'output-tab is-current' : 'output-tab'}
              onClick={() => changeTab(t.key)}
              onKeyDown={(e) => onTabKey(e, index)}
            >
              <Icon name={t.icon} size={18} color={isCurrent ? 'var(--saffron-dark)' : 'var(--icon)'} />
              {t.label}
              {working && <span className="spinner" aria-label="Writing" />}
              {waiting && <span className="tab-count">Waiting</span>}
              {problem && (
                <span className="tab-count tab-failed">
                  ! <span className="sr-only">Needs attention</span>
                </span>
              )}
              {t.key === 'facts' && job.fact_sheet && <span className="tab-count">{job.fact_sheet.key_facts.length}</span>}
              {scores.length > 0 && <ScoreBadge score={Math.min(...scores)} />}
            </button>
          )
        })}
      </div>

      {tab !== 'facts' && <LanguageBar job={job} lang={lang} onChange={changeLanguage} canChange={canChange} onAdded={(updated) => {
        setJob(updated)
        setPollRound((n) => n + 1)
      }} />}

      <div className="results-grid" id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        <div className="results-main">
          {tab === 'facts' && (
            <TraceProvider value={{ outputId: null, byPath: new Map(), facts, selection, select: setSelection }}>
              <FactSheetCard
                sheet={job.fact_sheet}
                generating={job.status === 'generating'}
                step={job.step}
                selectedFact={selection.outputId === null ? selection.factId : null}
                onFact={(factId) => setSelection({ outputId: null, sentenceId: null, factId })}
              />
              <Sources job={job} />
              <SafetySection job={job} />
              <ConsistencyPanel
                consistency={job.consistency}
                generating={job.status === 'generating'}
                facts={facts}
                onOpen={openSentence}
                onFact={(factId) => setSelection({ outputId: null, sentenceId: null, factId })}
              />
            </TraceProvider>
          )}
          {tab === 'social' && <PublicNotice job={job} />}
          <div className={tab === 'social' ? 'social-grid' : 'stack gap-20'}>
            {shown.map((output) => (
              <OutputPanel
                key={output.id}
                job={job}
                output={output}
                meta={meta(output)}
                now={now}
                facts={facts}
                selection={selection}
                select={setSelection}
                editing={editing === output.id}
                onEdit={(on) => {
                  setEditing(on ? output.id : null)
                  setSelection(NO_SELECTION)
                }}
                onSaved={(updated) => {
                  setJob(updated)
                  setEditing(null)
                  setViewing((v) => ({ ...v, [output.id]: undefined }))
                }}
                viewed={viewing[output.id]}
                onView={(version) => {
                  setViewing((v) => ({ ...v, [output.id]: version }))
                  setSelection(NO_SELECTION)
                }}
                onRegenerate={() => regenerate(output)}
                canChange={canChange}
              />
            ))}
          </div>
        </div>
        <aside className="results-side" aria-label="Source trace and checks">
          <TraceProvider value={{ outputId: active?.id ?? null, byPath: new Map(), facts, selection, select: setSelection }}>
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
                    (shown.length > 1 ? `${active.label} · ` : '') +
                    (viewed
                      ? `Version ${viewed.version} · ${viewed.origin_label} (older version)`
                      : `Version ${active.version} · ${active.origin_label}`)
                  }
                />
              </>
            )}
          </TraceProvider>
        </aside>
      </div>
    </main>
  )
}

// Stage 8: English | हिन्दी | தமிழ் ... above the outputs (design 13), and "Add language" for Operators.
function LanguageBar({ job, lang, onChange, canChange, onAdded }: {
  job: JobDetail
  lang: string
  onChange: (code: string) => void
  canChange: boolean
  onAdded: (job: JobDetail) => void
}) {
  const info = useLanguages()
  const [adding, setAdding] = useState(false)
  const [chosen, setChosen] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const canAdd = canChange && job.status !== 'generating' && job.status !== 'draft' && info?.translation.ready
  if (job.languages.length < 2 && !canAdd) return null

  async function translate() {
    setBusy(true)
    setError('')
    try {
      onAdded(await addLanguages(job.id, chosen))
      setAdding(false)
      setChosen([])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start the translation.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="lang-bar stack gap-10">
      <div className="row gap-8 wrap" role="group" aria-label="Language of the outputs">
        {job.languages.map((code) => {
          const l = languageByCode(info, code)
          const outputs = job.outputs.filter((o) => o.language === code)
          const working = outputs.some((o) => o.status === 'generating' || o.status === 'queued')
          const unchecked = code !== 'en' && outputs.some((o) => o.status === 'done' && !o.translation?.native_check.checked)
          return (
            <button key={code} type="button" className={code === lang ? 'pill is-on' : 'pill'} aria-pressed={code === lang}
                    lang={code} dir={l?.rtl ? 'rtl' : undefined} onClick={() => onChange(code)}>
              {l?.native ?? code}
              {l && code !== 'en' && <span className="sr-only"> ({l.name})</span>}
              {working && <span className="spinner" aria-label="Translating" />}
              {unchecked && !working && <span className="dot-yellow" title="Machine translated: needs a native-speaker check" />}
            </button>
          )
        })}
        {canAdd && !adding && (
          <button type="button" className="pill pill-more" onClick={() => setAdding(true)}>
            <Icon name="plus" size={14} strokeWidth={2.4} />
            Add language
          </button>
        )}
      </div>
      {adding && (
        <div className="card card-pad stack gap-12 add-languages">
          <LanguagePicker info={info ? { ...info, languages: info.languages.filter((l) => !job.languages.includes(l.code) || l.code === 'en') } : null}
                          selected={chosen} onChange={setChosen} label="Translate every output into" />
          {error && <div className="alert alert-red">{error}</div>}
          <div className="row gap-10">
            <button type="button" className="btn btn-saffron" disabled={busy || chosen.length === 0} onClick={translate}>
              {busy ? 'Starting…' : `Translate into ${chosen.length || ''} language${chosen.length === 1 ? '' : 's'}`}
            </button>
            <button type="button" className="btn btn-outline" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// Stage 8: on a translated output, "Machine translated - needs a native-speaker check" until a Reviewer ticks it
function TranslationNote({ output }: { output: JobOutput }) {
  const t = output.translation
  if (!t || output.status === 'failed') return null
  if (t.stale || output.status !== 'done') {
    return (
      <div className="notice notice-neutral" role="status">
        <span className="spinner" aria-hidden="true" />
        <span>The English text changed, so this is being translated again from it.</span>
      </div>
    )
  }
  const source = `Translated from the English${t.source_version ? ` (version ${t.source_version})` : ''} by ${t.engine}.`
  return t.native_check.checked ? (
    <div className="notice notice-green">
      <Icon name="shieldCheck" size={20} />
      <span>
        <strong>Checked by a native speaker</strong> · {t.native_check.by}
        {t.native_check.at ? `, ${shortTime(t.native_check.at)}` : ''}. {source}
      </span>
    </div>
  ) : (
    <div className="notice notice-yellow">
      <Icon name="warning" size={20} />
      <span>
        <strong>Machine translated - needs a native-speaker check.</strong> {source} A Reviewer ticks the check before
        it can be signed.
      </span>
    </div>
  )
}

// Stage 9B: the Reviewer's line comments on the version that was sent back, each with a link to its sentence
function ReviewerComments({ job, onOpen }: { job: JobDetail; onOpen: (outputId: number, sentenceId: string, factId: string | null) => void }) {
  if (job.status !== 'sent_back') return null
  const comments = job.comments.filter((c) => c.job_version === job.version)
  if (comments.length === 0) return null
  return (
    <section className="card card-pad stack gap-12" aria-labelledby="comments-title">
      <h2 id="comments-title">
        Line comments from the Reviewer ({comments.length})
      </h2>
      <ul className="clean-list-plain stack gap-10">
        {comments.map((c) => (
          <li key={c.id} className="comment comment-card">
            <span className="comment-icon" aria-hidden="true">
              <Icon name="pencil" size={18} />
            </span>
            <span className="stack gap-2 grow">
              <span className="small muted">
                {c.author} · {c.output_label ?? 'Whole job'}
              </span>
              {c.quote && <q className="comment-quote">{c.quote}</q>}
              <span>{c.text}</span>
            </span>
            {c.output_id && c.sentence_id && (
              <button type="button" className="btn btn-outline btn-xs" onClick={() => onOpen(c.output_id!, c.sentence_id!, null)}>
                Show the line
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

// One output with its own sentence tracing (the Social posts tab shows two side by side).
function OutputPanel(props: OutputCardProps & { facts: FactLookup; selection: Selection; select: (s: Selection) => void }) {
  const { output, viewed, facts, selection, select } = props
  const quality = viewed ? viewed.quality : output.quality
  const byPath = useMemo(() => sentencesByPath(quality?.sentences), [quality])
  return (
    <TraceProvider value={{ outputId: output.id, byPath, facts, selection, select }}>
      <OutputCard {...props} />
    </TraceProvider>
  )
}

// Social posts tab: what was hidden because these posts are public, and the public-release check.
function PublicNotice({ job }: { job: JobDetail }) {
  const hidden = (job.safety?.findings ?? []).filter((f) => f.choice !== 'keep').length
  const check = job.public_check
  return (
    <div className="notice-grid">
      <div className="notice notice-saffron">
        <Icon name="eyeOff" size={20} />
        <span>
          {hidden > 0 ? (
            <>
              <strong>
                {hidden} sensitive detail{hidden === 1 ? '' : 's'} hidden
              </strong>{' '}
              because these are public posts{job.tlp ? ` (TLP:${job.tlp} source)` : ''}.
            </>
          ) : (
            <>No private data was found in the source, so nothing needed hiding.</>
          )}
        </span>
      </div>
      {check && (
        <div className={check.ok ? 'notice notice-green' : 'notice notice-red'} role={check.ok ? undefined : 'alert'}>
          <Icon name={check.ok ? 'shieldCheck' : 'warning'} size={20} />
          {check.ok ? (
            <span>
              <strong>Public-release check passed.</strong> No panic wording or shouting.
            </span>
          ) : (
            <span>
              <strong>Public-release check: {check.problems.length} problem{check.problems.length === 1 ? '' : 's'}.</strong>{' '}
              {check.problems.slice(0, 3).map((p) => `${p.where}: ${p.label} (“${p.text}”)`).join('; ')}
            </span>
          )}
        </div>
      )}
    </div>
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
          <Icon name={s.transcript ? 'volume' : 'file'} size={16} color="var(--muted)" />
          <strong>{s.id}</strong> {s.filename} ·{' '}
          {s.transcript
            ? `${duration(s.transcript.seconds)} recording, turned into text by ${s.transcript.model}`
            : `${s.pages} page${s.pages === 1 ? '' : 's'}`}
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
  meta: ViewMeta
  now: number
  editing: boolean
  onEdit: (on: boolean) => void
  onSaved: (job: JobDetail) => void
  viewed: VersionDetail | undefined
  onView: (version: VersionDetail | undefined) => void
  onRegenerate: () => void
  canChange: boolean // Operator, and the job is not with a reviewer or approved
}

function OutputCard({ job, output, meta, now, editing, onEdit, onSaved, viewed, onView, onRegenerate, canChange }: OutputCardProps) {
  const [showVersions, setShowVersions] = useState(false)
  const busy = job.status === 'generating'
  const hasText = Boolean(output.content)
  const q = output.quality

  const translated = output.language !== 'en'
  const info = useLanguages()
  const language = languageByCode(info, output.language)
  const { user } = useAuth()
  const readAloud = Boolean(user.prefs?.read_aloud) // Stage 8: Profile & settings → "Read results aloud"
  const [listening, setListening] = useState(false)

  let status: ReactNode = null
  if (output.status === 'generating') {
    const started = output.started_at ? new Date(output.started_at).getTime() : now
    status = (
      <span className="row gap-6 chip chip-saffron">
        <span className="spinner" aria-hidden="true" />
        {translated ? 'Translating…' : 'Writing…'} {duration((now - started) / 1000)}
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
      {readAloud && output.status === 'done' && language?.voice && (
        <button type="button" className="btn btn-outline btn-xs" aria-pressed={listening} onClick={() => setListening(!listening)}>
          <Icon name="volume" size={16} />
          {listening ? 'Stop' : 'Listen'}
        </button>
      )}
      {canChange && (
        <>
          <button
            type="button"
            className="btn btn-saffron-outline btn-xs"
            onClick={onRegenerate}
            disabled={busy || editing}
            title={busy ? 'Wait until the AI has finished' : translated ? 'Translate it again from the English' : 'Write this output again from the same fact sheet'}
          >
            <Icon name="refresh" size={16} strokeWidth={2} />
            {translated ? 'Translate again' : 'Regenerate'}
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
    <Card title={translated ? <>{output.label} <span className="muted" lang={output.language}>· {language?.native ?? output.language}</span></> : output.label}
          right={toolbar || status} json={(viewed?.content ?? output.content) || undefined}>
      {translated && !viewed && <TranslationNote output={output} />}
      {listening && (
        <audio autoPlay controls src={listenUrl(job.id, output.id, output.version)} onEnded={() => setListening(false)}
               aria-label={`${output.label} read aloud`} className="listen-audio" />
      )}
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
        <div className={output.status === 'done' || viewed ? '' : 'is-stale'} lang={output.language} dir={language?.rtl ? 'rtl' : undefined}>
          {output.type === 'infographic' && !viewed && !(output.quality?.leaks ?? []).length ? (
            <div className="infographic-layout">
              <InfographicPreview jobId={job.id} output={output} />
              <OutputBody type={output.type} content={output.content!} meta={meta} />
            </div>
          ) : (
            <>
              {output.type === 'video_package' && !viewed && output.status === 'done' && !(output.quality?.leaks ?? []).length && (
                <VideoPreview jobId={job.id} output={output} />
              )}
              <OutputBody type={output.type} content={(viewed?.content ?? output.content)!} meta={meta} />
            </>
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
  mp3: 'Narration (.mp3)',
  mp4: 'Video (.mp4)',
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

// Stage 8: the video package as a real video (.mp4: storyboard pictures, captions and the narration) and the
// narration alone (.mp3). Made on this computer when asked: it takes a few seconds to half a minute.
function VideoPreview({ jobId, output }: { jobId: number; output: JobOutput }) {
  const [show, setShow] = useState(false)
  const info = useLanguages()
  const language = languageByCode(info, output.language)
  const hasVoice = output.formats.includes('mp3')
  const version = `&v=${output.version}`
  return (
    <div className="video-preview stack gap-10">
      {show ? (
        <>
          <video controls preload="metadata" src={`${downloadUrl(jobId, output.id, 'mp4', true)}${version}`} className="video-player">
            <track kind="captions" />
          </video>
          {hasVoice && (
            <audio controls preload="none" src={`${downloadUrl(jobId, output.id, 'mp3', true)}${version}`} aria-label="Narration" />
          )}
        </>
      ) : (
        <button type="button" className="btn btn-outline" onClick={() => setShow(true)}>
          <Icon name="play" size={18} strokeWidth={2} />
          Make and watch the video
        </button>
      )}
      <p className="muted small">
        {hasVoice
          ? `Narrated by ${language?.voice ?? 'an Indian voice'}, with captions in the picture and as subtitles.`
          : `Audio is not available for ${language?.name ?? output.language_label}: the video has captions and no sound.`}
      </p>
    </div>
  )
}
