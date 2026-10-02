import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  getJob,
  getSource,
  saveSafety,
  type Finding,
  type InstructionChoice,
  type JobDetail,
  type SafetyChoice,
  type SourceText,
  type Suspicious,
  type Tlp,
} from '../api'
import { Icon } from '../components/Icon'
import { Stepper } from '../components/Stepper'
import { TlpLabel } from '../components/TlpLabel'
import { links, navigate } from '../router'
import { OriginBadge } from '../components/JobsTable'
import { jobNo, jsIndex } from './format'
import { ALWAYS_CHECKED, CHOICES, findingIcon, INDICATOR_CHOICES, TLP_LEVELS, whereFound } from './safety'
import { t } from '../i18n'

// New transformation, step 2 of 3: the Safety check. Layout from the design
// "10 · New transformation · 2 Safety check". Everything here was found by rules (no AI):
//   - What we found: private data, with a choice for each (hide in public outputs / hide everywhere / keep)
//   - Attack indicators: public attacker addresses, CVE ids, file hashes (not private data)
//   - Suspicious instructions: text aimed at the AI (remove it from what the AI reads, or keep it),
//     hidden characters, hidden text
//   - The source, with all of it highlighted
//   - Sharing level (TLP), with the suggested one marked
export function SafetyCheck({ jobId }: { jobId: number }) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const [choices, setChoices] = useState<Choices>({})
  const [tlp, setTlp] = useState<Tlp | null>(null)
  const [focus, setFocus] = useState<string | null>(null) // finding or suspicious item shown in the source
  const [saving, setSaving] = useState(false)
  const sources = useSources(job)

  useEffect(() => {
    getJob(jobId)
      .then((loaded) => {
        setJob(loaded)
        const all = [...(loaded.safety?.findings ?? []), ...(loaded.safety?.indicators ?? [])]
        const instructions = (loaded.safety?.suspicious ?? []).filter((x) => x.choice)
        setChoices(Object.fromEntries([...all.map((f) => [f.id, f.choice]), ...instructions.map((x) => [x.id, x.choice!])]))
        setTlp(loaded.tlp ?? loaded.safety?.suggested_tlp ?? null)
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the job.")))
  }, [jobId])

  if (!job) {
    return (
      <main className="page">
        {error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}
      </main>
    )
  }
  const safety = job.safety
  if (job.status !== 'draft' || !safety) {
    return (
      <main className="page">
        <h1>{t("Safety check")}</h1>
        <div className="alert alert-yellow">
          {safety ? t("This job has already started, so its safety check is locked.") : t("This job was made before the safety check existed.")}{' '}
          <a href={links.job(job.id)}>{t("Open its results")}</a>.
        </div>
      </main>
    )
  }

  const all = [...safety.findings, ...safety.indicators]
  const hiddenCount = safety.findings.filter((f) => choices[f.id] !== 'keep').length
  const saved: Record<string, string | undefined> = Object.fromEntries([
    ...all.map((f) => [f.id, f.choice]),
    ...safety.suspicious.map((x) => [x.id, x.choice]),
  ])

  async function next() {
    if (!job || !tlp) return setError(t("Choose a sharing level (TLP)."))
    const changed = Object.fromEntries(Object.entries(choices).filter(([id, choice]) => saved[id] !== choice))
    setSaving(true)
    setError('')
    try {
      await saveSafety(job.id, { tlp, choices: changed })
      navigate(links.outputs(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not save the safety check."))
      setSaving(false)
    }
  }

  const choose = (id: string, choice: SafetyChoice | InstructionChoice) => setChoices((c) => ({ ...c, [id]: choice }))
  const show = (id: string) => setFocus((current) => (current === id ? null : id))

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">
            {t("New transformation · Job {id} · {title}", { id: jobNo(job.id), title: job.title })}</div>
          <h1>{t("Safety check")}</h1>
          {job.created_via === 'watch' && (
            <p className="muted row gap-8 wrap">
              <OriginBadge job={job} />
              {t("Found by your watch folder. Nothing has been written yet: check it, choose the sharing label, then continue.")}
            </p>
          )}
        </div>
        <div className="grow" />
        <a className="btn btn-outline" href={links.dashboard}>
          {t("Cancel")}
        </a>
      </div>
      <Stepper current={2} />

      <div className="safety-grid">
        <div className="stack gap-16">
          <Banner kinds={safety.kinds_found} suggested={safety.suggested_tlp} />

          <section className="card card-pad stack gap-14">
            <div className="row gap-12 wrap">
              <h2>{t("What we found")}</h2>
              <div className="grow" />
              <span className="muted small">
                {t("{pages} page{value} in {sources} source{value2} checked", { pages: safety.checked.pages, value: safety.checked.pages === 1 ? '' : 's', sources: safety.checked.sources, value2: safety.checked.sources === 1 ? '' : 's' })}</span>
            </div>
            <FindingTable
              findings={safety.findings}
              choices={choices}
              options={CHOICES}
              focus={focus}
              onChoose={choose}
              onShow={show}
              noneRows
            />
            <Preview findings={safety.findings} suspicious={safety.suspicious} choices={choices} sources={sources} />
          </section>

          {safety.indicators.length > 0 && (
            <section className="card card-pad stack gap-14">
              <div className="stack gap-4">
                <h2>{t("Attack indicators")}</h2>
                <p className="muted small">
                  {t("Attacker addresses, CVE ids and file hashes are not private data. They stay in the advisory and are left out of public posts, unless you choose otherwise.")}
                </p>
              </div>
              <FindingTable
                findings={safety.indicators}
                choices={choices}
                options={INDICATOR_CHOICES}
                focus={focus}
                onChoose={choose}
                onShow={show}
              />
            </section>
          )}

          <SuspiciousCard items={safety.suspicious} choices={choices} focus={focus} onShow={show} onChoose={choose} />

          <SourceView sources={sources} findings={all} suspicious={safety.suspicious} choices={choices} focus={focus} />
        </div>

        <div className="stack gap-16">
          <section className="card card-pad stack gap-14">
            <h2>{t("Sharing level (TLP)")}</h2>
            <div className="stack gap-10" role="radiogroup" aria-label={t("Sharing level")}>
              {TLP_LEVELS.map((level) => {
                const on = tlp === level.tlp
                return (
                  <button
                    key={level.tlp}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    className={on ? 'tlp-option is-on' : 'tlp-option'}
                    onClick={() => setTlp(level.tlp)}
                  >
                    <span className="radio" aria-hidden="true" />
                    <span className="stack gap-4 grow">
                      <span className="row gap-8 wrap">
                        <TlpLabel tlp={level.tlp} />
                        <span className="tlp-title">{t(level.title)}</span>
                        {safety.suggested_tlp === level.tlp && <span className="chip chip-saffron">{t("Suggested")}</span>}
                      </span>
                      <span className="tlp-desc">{t(level.description)}</span>
                    </span>
                  </button>
                )
              })}
            </div>
            <p className="hint">
              <strong>{t("Why TLP:{suggested_tlp}?", { suggested_tlp: safety.suggested_tlp })}</strong> {safety.tlp_reason}
            </p>
            {(tlp === 'RED' || tlp === 'AMBER') && (
              <p className="muted small">
                {t("With TLP:{tlp}, the LinkedIn post, X thread, infographic and video package are switched off. The advisory, executive summary and presentation are allowed.", { tlp: tlp })}</p>
            )}
          </section>

          <section className="card card-pad-sm row gap-12">
            <span className="find-icon tone-green">
              <Icon name="wifiOff" size={20} />
            </span>
            <span className="stack">
              <span className="muted small">{t("Processing mode")}</span>
              <strong>{t("Rule-based check · nothing leaves this computer")}</strong>
            </span>
          </section>

          {hiddenCount > 0 && (
            <section className="card card-pad-sm stack gap-6">
              <span className="section-label">{t("What the AI will see")}</span>
              <p className="muted small">
                {t("The AI never sees the")} {hiddenCount} {t("hidden item")}{hiddenCount === 1 ? '' : 's'}{t(": each is swapped for a placeholder like")} <code className="mono">[PHONE-1]</code> {t("before it reads the source.")}
              </p>
            </section>
          )}
        </div>
      </div>

      {error && <div className="alert alert-red">{error}</div>}
      <div className="row gap-12">
        <a
          className="btn btn-lg btn-outline"
          href={links.newJob}
          title={t("Start again with other sources. This draft stays in My jobs.")}
        >
          <Icon name="arrowLeft" size={18} strokeWidth={2} />
          {t("Back")}
        </a>
        <div className="grow" />
        <button type="button" className="btn btn-lg btn-saffron" onClick={next} disabled={saving || !tlp}>
          {saving ? t("Saving…") : t("Next: outputs and settings")}
          {!saving && <Icon name="arrowRight" size={18} strokeWidth={2} />}
        </button>
      </div>
    </main>
  )
}

// The operator's choice for each finding (P1, I1 ...) and each suspicious instruction (X1 ...)
type Choices = Record<string, SafetyChoice | InstructionChoice>

const INSTRUCTION_CHOICES: { value: InstructionChoice; label: string }[] = [
  { value: 'remove', label: 'Remove from what the AI reads' },
  { value: 'keep', label: 'Keep (AI told to ignore it)' },
]

// ---- the source texts (all sources of the job, loaded once) ------------------------------------------

function useSources(job: JobDetail | null): SourceText[] {
  const [loaded, setLoaded] = useState<SourceText[]>([])
  const ids = job?.sources.map((s) => s.id).join(',') ?? ''
  const jobId = job?.id
  useEffect(() => {
    if (!jobId || !ids) return
    let current = true
    Promise.all(ids.split(',').map((id) => getSource(jobId, id)))
      .then((texts) => current && setLoaded(texts))
      .catch(() => current && setLoaded([]))
    return () => {
      current = false
    }
  }, [jobId, ids])
  return loaded
}

// ---- banner ----------------------------------------------------------------------------------------------

function Banner({ kinds, suggested }: { kinds: number; suggested: Tlp }) {
  const found = kinds > 0
  return (
    <section className={found ? 'safety-banner' : 'safety-banner is-clean'}>
      <span className="banner-icon">
        <Icon name={found ? 'warning' : 'shieldCheck'} size={26} />
      </span>
      <span className="stack gap-2 grow">
        <span className="banner-title">
          {found ? t("We found {kinds} kind{n} of sensitive information", { kinds: kinds, n: kinds === 1 ? '' : 's' }) : t("No private data found")}
        </span>
        <span className="banner-text">
          {found
            ? t("Internal outputs can keep them. Public outputs will hide them automatically.")
            : t("Nothing personal, secret or marked was found in the sources.")}
        </span>
      </span>
      <span className="stack gap-6 banner-tlp">
        <span className="small">{t("Suggested sharing level")}</span>
        <TlpLabel tlp={suggested} />
      </span>
    </section>
  )
}

// ---- the table of findings -------------------------------------------------------------------------------

type TableProps = {
  findings: Finding[]
  choices: Choices
  options: { value: SafetyChoice; label: string }[]
  focus: string | null
  onChoose: (id: string, choice: SafetyChoice) => void
  onShow: (id: string) => void
  noneRows?: boolean // add "None found" rows for the main kinds (as in the design)
}

function FindingTable({ findings, choices, options, focus, onChoose, onShow, noneRows }: TableProps) {
  const found = new Set(findings.map((f) => f.kind))
  const empty = noneRows ? ALWAYS_CHECKED.filter((row) => !row.kinds.some((k) => found.has(k))) : []
  return (
    <div className="find-table" role="table">
      <div className="find-row find-head" role="row">
        <span role="columnheader">{t("Item")}</span>
        <span role="columnheader">{t("Found")}</span>
        <span role="columnheader">{t("Where")}</span>
        <span role="columnheader">{t("Action")}</span>
      </div>
      {findings.map((f) => (
        <div key={f.id} className={focus === f.id ? 'find-row is-focus' : 'find-row'} role="row">
          <button type="button" className="find-item" onClick={() => onShow(f.id)} title={t("Show it in the source")} role="cell">
            <span className={`find-icon ${f.group === 'indicator' ? 'tone-navy' : `risk-${f.risk}`}`}>
              <Icon name={findingIcon(f)} size={18} />
            </span>
            <span className="stack gap-1 find-text">
              <span className="find-label">{t(f.label)}</span>
              <span className="find-value mono">{shown(f)}</span>
              <span className="find-note">
                {t("{value} · public outputs show {redaction}", { value: f.group === 'indicator' ? t("Indicator") : t("{n} risk", { n: capital(f.risk) }), redaction: f.redaction })}</span>
            </span>
          </button>
          <span role="cell">{f.count}</span>
          <span role="cell" className="small">
            {whereFound(f)}
          </span>
          <span role="cell">
            <select
              className="input select-sm"
              aria-label={t("Action for {label}", { label: f.label })}
              value={choices[f.id]}
              onChange={(e) => onChoose(f.id, e.target.value as SafetyChoice)}
            >
              {options.map((o) => (
                <option key={o.value} value={o.value}>
                  {t(o.label)}
                </option>
              ))}
            </select>
          </span>
        </div>
      ))}
      {empty.map((row) => (
        <div key={row.label} className="find-row is-empty" role="row">
          <span className="find-item" role="cell">
            <span className="find-icon tone-green">
              <Icon name={row.icon} size={18} />
            </span>
            <span className="muted">{t(row.label)}</span>
          </span>
          <span role="cell">0</span>
          <span role="cell">—</span>
          <span role="cell">
            <span className="chip chip-green">
              <Icon name="check" size={14} strokeWidth={2.4} />
              {t("None found")}
            </span>
          </span>
        </div>
      ))}
    </div>
  )
}

// The value as shown in the table: passwords and keys only partly
function shown(f: Finding): string {
  if (f.group === 'secret') return `${f.text.slice(0, 3)}${'•'.repeat(Math.min(8, Math.max(3, f.text.length - 3)))}`
  return f.text.length > 70 ? `${f.text.slice(0, 67)}…` : f.text
}

const capital = (word: string) => word.charAt(0).toUpperCase() + word.slice(1)

// ---- "Preview in public outputs" -------------------------------------------------------------------------

function Preview({ findings, suspicious, choices, sources }: {
  findings: Finding[]
  suspicious: Suspicious[]
  choices: Choices
  sources: SourceText[]
}) {
  // a hidden value the AI will read (not one inside an instruction that is removed anyway)
  const removed = suspicious.filter((x) => x.remove && choices[x.id] === 'remove')
  const insideRemoved = (o: Finding['occurrences'][number]) =>
    removed.some((x) => x.source_id === o.source_id && x.page === o.page && o.start >= x.remove![0] && o.end <= x.remove![1])
  const hidden = findings.find((f) => choices[f.id] !== 'keep' && f.occurrences.some((o) => !insideRemoved(o)))
  if (!hidden) return null
  const where = hidden.occurrences.find((o) => !insideRemoved(o))!
  const page = sources.find((s) => s.id === where.source_id)?.pages[where.page - 1]
  if (!page) return null
  const start = jsIndex(page, where.start)
  const end = jsIndex(page, where.end)
  const before = page.slice(Math.max(0, start - 60), start).replace(/^\S*\s/, '').replace(/\s+/g, ' ')
  const after = page.slice(end, end + 60).replace(/\s\S*$/, '').replace(/\s+/g, ' ')
  return (
    <div className="preview-box">
      {t("Preview in public outputs: “…")}{before}
      <span className="redaction">{hidden.redaction}</span>
      {after}…”
    </div>
  )
}

// ---- suspicious instructions -------------------------------------------------------------------------------

type SuspiciousProps = {
  items: Suspicious[]
  choices: Choices
  focus: string | null
  onShow: (id: string) => void
  onChoose: (id: string, choice: InstructionChoice) => void
}

function SuspiciousCard({ items, choices, focus, onShow, onChoose }: SuspiciousProps) {
  if (items.length === 0) {
    return (
      <section className="card card-pad row gap-14 align-start">
        <span className="find-icon tone-green big">
          <Icon name="shieldCheck" size={22} />
        </span>
        <span className="stack gap-4">
          <h3>{t("No hidden instructions found")}</h3>
          <p className="muted small">
            {t("We look for text that tries to control the AI, such as “ignore your rules”, invisible characters, and white, tiny or hidden text in Word and PDF files.")}
          </p>
        </span>
      </section>
    )
  }
  return (
    <section className="card card-pad stack gap-12 suspicious-card">
      <div className="row gap-14 align-start">
        <span className="find-icon risk-high big">
          <Icon name="warning" size={22} />
        </span>
        <span className="stack gap-4">
          <h3>{t("Suspicious instructions found")}</h3>
          <p className="muted small">
            {t("By default each instruction is cut out of what the AI reads (shown struck through). If you keep one, the AI is still told that source text is data and must never be followed. Hidden characters and hidden text are always removed.")}
          </p>
        </span>
      </div>
      <ul className="suspicious-list">
        {items.map((item) => {
          const removed = item.kind === 'instruction' && choices[item.id] === 'remove'
          return (
            <li key={item.id} className="suspicious-row">
              <button
                type="button"
                className={focus === item.id ? 'suspicious-item is-focus' : 'suspicious-item'}
                onClick={() => onShow(item.id)}
                disabled={item.start === null}
                title={item.start === null ? t("Removed from the text, so it cannot be shown there") : t("Show it in the source")}
              >
                <span className="row gap-8 wrap">
                  <strong>{t(item.label)}</strong>
                  <span className="muted small">
                    {t("{source_id} · page {page}", { source_id: item.source_id, page: item.page })}</span>
                  {removed && <span className="chip chip-red chip-xs">{t("Removed from what the AI reads")}</span>}
                </span>
                <span className={removed ? 'suspicious-text struck' : 'suspicious-text'}>{item.text}</span>
                {item.kind !== 'instruction' && <span className="muted small">{t(item.detail)}</span>}
              </button>
              {item.kind === 'instruction' && item.choice && (
                <select
                  className="input select-sm"
                  aria-label={t("What to do with instruction {id}", { id: item.id })}
                  value={choices[item.id]}
                  onChange={(e) => onChoose(item.id, e.target.value as InstructionChoice)}
                >
                  {INSTRUCTION_CHOICES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {t(o.label)}
                    </option>
                  ))}
                </select>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ---- the source with everything highlighted -----------------------------------------------------------------

type Mark = { start: number; end: number; id: string; className: string; title: string }

function SourceView({ sources, findings, suspicious, choices, focus }: {
  sources: SourceText[]
  findings: Finding[]
  suspicious: Suspicious[]
  choices: Choices
  focus: string | null
}) {
  const [shownId, setShownId] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)

  // Show the source of the focused item
  const focusSource =
    findings.find((f) => f.id === focus)?.occurrences[0]?.source_id ?? suspicious.find((s) => s.id === focus)?.source_id
  const current = sources.find((s) => s.id === (focusSource ?? shownId)) ?? sources[0]

  // marks per page: [page number] -> marks, in order, without overlaps
  const marks = useMemo(() => {
    const byPage = new Map<number, Mark[]>()
    if (!current) return byPage
    const add = (page: number, mark: Mark) => {
      const list = byPage.get(page) ?? []
      if (list.every((m) => mark.end <= m.start || mark.start >= m.end)) list.push(mark)
      byPage.set(page, list)
    }
    suspicious
      .filter((s) => s.source_id === current.id && s.kind === 'instruction')
      .forEach((s) => {
        if (choices[s.id] === 'remove' && s.remove) {
          // the whole sentence the AI will not read, struck through
          const [a, b] = s.remove
          add(s.page, { start: a, end: b, id: s.id, className: 'scan-mark mark-removed', title: t("Removed from what the AI reads") })
        } else {
          ;(s.spans ?? [[s.start!, s.end!]]).forEach(([a, b]) =>
            add(s.page, { start: a, end: b, id: s.id, className: 'scan-mark mark-injection', title: t("{label} · kept", { label: s.label }) }),
          )
        }
      })
    findings.forEach((f) =>
      f.occurrences
        .filter((o) => o.source_id === current.id)
        .forEach((o) =>
          add(o.page, {
            start: o.start,
            end: o.end,
            id: f.id,
            className: `scan-mark ${f.group === 'indicator' ? 'mark-indicator' : `mark-${f.risk}`}${choices[f.id] === 'keep' ? ' is-kept' : ''}`,
            title: `${f.label} · ${CHOICES.find((c) => c.value === choices[f.id])?.label ?? ''}`,
          }),
        ),
    )
    byPage.forEach((list) => list.sort((a, b) => a.start - b.start))
    return byPage
  }, [current, findings, suspicious, choices])

  useLayoutEffect(() => {
    if (!focus || !box.current) return
    const target = box.current.querySelector<HTMLElement>(`[data-mark="${focus}"]`)
    if (target) box.current.scrollTop = target.offsetTop - box.current.clientHeight / 3
  }, [focus, current])

  if (!current) return null
  return (
    <section className="card card-pad stack gap-12">
      <div className="row gap-10 wrap">
        <h2>{t("Source")}</h2>
        <div className="grow" />
        {sources.length > 1 &&
          sources.map((s) => (
            <button
              key={s.id}
              type="button"
              className={s.id === current.id ? 'btn btn-xs btn-saffron-outline' : 'btn btn-xs btn-outline'}
              onClick={() => setShownId(s.id)}
            >
              {s.id} · {s.filename}
            </button>
          ))}
      </div>
      <div className="row gap-10 wrap small legend">
        <span className="scan-mark mark-high">{t("High risk")}</span>
        <span className="scan-mark mark-medium">{t("Medium")}</span>
        <span className="scan-mark mark-low">{t("Low")}</span>
        <span className="scan-mark mark-indicator">{t("Indicator")}</span>
        <span className="scan-mark mark-injection">{t("Aimed at the AI")}</span>
        <span className="scan-mark mark-removed">{t("Removed")}</span>
        <span className="muted">{t("Click a row above to find it here.")}</span>
      </div>
      <div className="source-text is-wide" ref={box}>
        {current.pages.map((page, index) => (
          <div key={index} className="scan-page">
            {current.pages.length > 1 && <div className="scan-page-label">{t("Page {value}", { value: index + 1 })}</div>}
            {highlight(page, marks.get(index + 1) ?? [], focus)}
          </div>
        ))}
      </div>
    </section>
  )
}

function highlight(page: string, marks: Mark[], focus: string | null): ReactNode[] {
  const parts: ReactNode[] = []
  let at = 0
  marks.forEach((m, i) => {
    const start = jsIndex(page, m.start)
    const end = jsIndex(page, m.end)
    if (start < at) return
    parts.push(page.slice(at, start))
    parts.push(
      <mark key={i} data-mark={m.id} className={m.id === focus ? `${m.className} is-focus` : m.className} title={t(m.title)}>
        {page.slice(start, end)}
      </mark>,
    )
    at = end
  })
  parts.push(page.slice(at))
  return parts
}
