// The trust panels of the Results page (Stage 5), laid out like the design
// "13 · Results · Advisory with source trace":
//   SourcePanel       the source text, with the quote of the selected fact highlighted in yellow
//   CheckWarnings     sentences not linked to a (verified) fact, and values not in the source
//   QualityCard       the 0-100 score and what it is made of
//   ScoreBadge        a small score with a tooltip that explains it in plain words
//   ConsistencyPanel  does every output use the same numbers and dates for the same fact?
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { getSource, type Consistency, type Quality, type Sentence, type SourceText } from '../api'
import { Icon } from '../components/Icon'
import { FOUND_LABELS, jsIndex, scoreTone, type FactLookup } from './format'
import { FactChip } from './trace'
import { selectSentence, type Selection } from './traceState'
import { t } from '../i18n'

// ---- source text (loaded once per source, then kept) ----------------------------------------

const sourceCache = new Map<string, Promise<SourceText>>()

function useSourceText(jobId: number, sourceId: string | undefined) {
  const [loaded, setLoaded] = useState<{ key: string; source?: SourceText; error?: string } | null>(null)
  const key = `${jobId}/${sourceId}`
  useEffect(() => {
    if (!sourceId) return
    let current = true
    if (!sourceCache.has(key)) sourceCache.set(key, getSource(jobId, sourceId))
    sourceCache
      .get(key)!
      .then((source) => current && setLoaded({ key, source }))
      .catch((e) => {
        sourceCache.delete(key)
        if (current) setLoaded({ key, error: e instanceof Error ? e.message : 'Could not load the source.' })
      })
    return () => {
      current = false
    }
  }, [jobId, sourceId, key])
  return loaded?.key === key ? loaded : null
}

// ---- Source trace ---------------------------------------------------------------------------

type SourcePanelProps = {
  jobId: number
  facts: FactLookup
  selection: Selection
  sentence: Sentence | null // the selected sentence, if a sentence (not only a fact) was clicked
  where: string // e.g. "X thread · Post 2"
  select: (selection: Selection) => void
  onClose: () => void
}

export function SourcePanel({ jobId, facts, selection, sentence, where, select, onClose }: SourcePanelProps) {
  const fact = selection.factId ? facts.get(selection.factId) : undefined
  const open = Boolean(sentence || fact)
  // On narrow screens the open trace floats over the page like a dialog: Escape closes it, as everywhere else.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  return (
    <section className={open ? 'card side-card trace-card is-open' : 'card side-card trace-card'} aria-live="polite">
      <div className="row gap-8">
        <h2 className="side-title">{t("Source trace")}</h2>
        <div className="grow" />
        {fact?.page && fact.quote_found !== 'no' && (
          <span className="chip chip-navy">
            {t("{source_id} · Page {page}", { source_id: fact.source_id, page: fact.page })}</span>
        )}
        {open && (
          <button type="button" className="icon-btn icon-btn-sm" aria-label={t("Close source trace")} onClick={onClose}>
            <Icon name="cross" size={16} />
          </button>
        )}
      </div>

      {!open && (
        <p className="muted small">
          {t("Click any sentence of an output, or a fact chip like")} <span className="fact-chip">F1</span>{t(", to see where it comes from in the source.")}
        </p>
      )}

      {sentence && (
        <div className="stack gap-8">
          <span className="section-label">{where}</span>
          <blockquote className="trace-sentence">{sentence.text}</blockquote>
          {sentence.english && (
            <p className="small muted" lang="en">
              <strong>English:</strong> {sentence.english}
            </p>
          )}
          {(sentence.status === 'linked' || sentence.status === 'unverified') && (
            <div className="row gap-6 wrap small">
              <span className="muted">{t("Uses")}</span>
              {sentence.fact_ids.map((id) => (
                <FactChip
                  key={id}
                  id={id}
                  active={id === selection.factId}
                  onClick={() => select({ ...selection, factId: id, scroll: false })}
                />
              ))}
              {sentence.matched_by === 'words' && (
                <span className="muted">{t("· matched by its words (the AI did not cite this fact)")}</span>
              )}
            </div>
          )}
          {sentence.status === 'unlinked' && (
            <div className="trace-alert trace-alert-yellow">
              <strong>{t("Not linked to a fact.")}</strong> {t("No fact in the fact sheet supports this sentence. Check it, edit it, or remove it.")}
              {sentence.closest && (
                <>
                  {' '}
                  {t("The closest fact is")}{' '}
                  <FactChip
                    id={sentence.closest}
                    active={sentence.closest === selection.factId}
                    onClick={() => select({ ...selection, factId: sentence.closest, scroll: false })}
                  />{' '}
                  {t("(shown below), but it does not say the same thing.")}
                </>
              )}
            </div>
          )}
          {sentence.status === 'unverified' && (
            <div className="trace-alert trace-alert-yellow">
              <strong>{t("Linked fact not verified.")}</strong> {t("The fact this sentence uses could not be found in the source, so it may be made up. Check it against the source before using it.")}
            </div>
          )}
          {sentence.not_in_source.length > 0 && (
            <div className="trace-alert trace-alert-red">
              <strong>{t("Not in source:")}</strong> {sentence.not_in_source.map((f) => `${f.text} (${f.label.toLowerCase()})`).join(', ')}{t(". This does not appear in the source text.")}
            </div>
          )}
        </div>
      )}

      {fact && (
        <div className="stack gap-8">
          <div className="trace-fact">
            <span className="fact-id">{fact.id}</span>
            <div className="stack gap-4">
              <span>{fact.text}</span>
              <span className="row gap-6 wrap small muted">
                {fact.kind}
                {fact.source_id && ` · ${fact.source_id}`}
                {fact.page && t(" · page {page}", { page: fact.page })}
                {fact.quote_found && (
                  <span className={`chip chip-xs ${FOUND_CHIP[fact.quote_found]}`}>{FOUND_LABELS[fact.quote_found]}</span>
                )}
              </span>
            </div>
          </div>
          <SourceExcerpt jobId={jobId} fact={fact} />
        </div>
      )}
    </section>
  )
}

const FOUND_CHIP = { exact: 'chip-green', close: 'chip-saffron', no: 'chip-red' } as const

// The whole source page, scrolled so the highlighted quote is in view.
function SourceExcerpt({ jobId, fact }: { jobId: number; fact: NonNullable<ReturnType<FactLookup['get']>> }) {
  const loaded = useSourceText(jobId, fact.source_id)
  const [wide, setWide] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const mark = useRef<HTMLElement>(null)
  const raw = loaded?.source?.pages[(fact.page ?? 1) - 1]
  const page = raw === undefined ? undefined : reflow(raw)
  const hasSpan = page !== undefined && fact.start !== null && fact.start !== undefined && fact.end !== null && fact.end !== undefined

  useLayoutEffect(() => {
    if (box.current && mark.current) {
      box.current.scrollTop = Math.max(0, mark.current.offsetTop - box.current.clientHeight / 3)
    } else if (box.current) {
      box.current.scrollTop = 0
    }
  }, [fact.id, page, wide])

  if (!fact.source_id) return null
  if (loaded?.error) return <div className="alert alert-red small">{loaded.error}</div>
  if (page === undefined) return <p className="muted small">{t("Loading the source…")}</p>

  let body: ReactNode = page
  if (hasSpan) {
    const start = jsIndex(page, fact.start!)
    const end = jsIndex(page, fact.end!)
    body = (
      <>
        {page.slice(0, start)}
        <mark ref={mark} className="source-mark">
          {page.slice(start, end)}
        </mark>
        {page.slice(end)}
      </>
    )
  }
  return (
    <div className="stack gap-6">
      <span className="small muted">
        {t("{filename} · page {page}", { filename: loaded?.source?.filename, page: fact.page })}</span>
      {!hasSpan && (
        <div className="trace-alert trace-alert-yellow">
          {t("This fact's quote “{quote}” was not found in the source. Read the page below to check it.", { quote: fact.quote })}</div>
      )}
      <div ref={box} className={wide ? 'source-text is-wide' : 'source-text'}>
        {body}
      </div>
      <button type="button" className="btn btn-outline btn-xs" onClick={() => setWide(!wide)}>
        <Icon name="eye" size={16} />
        {wide ? t("Show less") : t("Show more of page {page}", { page: fact.page })}
      </button>
    </div>
  )
}

// Text files and PDFs break lines every ~100 characters, which reads badly in a narrow panel.
// Join those lines with a space, but keep paragraph breaks, list items and lines that end a sentence.
// One character is swapped for one, so the highlight positions stay exact.
function reflow(text: string): string {
  return text.replace(/([^\n.:!?])\n(?![\n\-•*]|\d+\.\s)/g, '$1 ')
}

// ---- warnings for the output on screen ------------------------------------------------------

export function CheckWarnings({ outputId, quality, select }: { outputId: number; quality: Quality; select: (s: Selection) => void }) {
  const sentences = quality.sentences ?? []
  const unlinked = sentences.filter((s) => s.status === 'unlinked')
  const unverified = sentences.filter((s) => s.status === 'unverified')
  const flagged = sentences.filter((s) => s.not_in_source.length > 0)
  if (!quality.sentences) return null
  // Green only when EVERY check passes (also format rules, fact ids, the leak check and the fact sheet match)
  const allPass =
    unlinked.length === 0 &&
    unverified.length === 0 &&
    flagged.length === 0 &&
    (quality.format_rules ?? []).every((r) => r.ok) &&
    quality.unknown_fact_ids.length === 0 &&
    (quality.leaks ?? []).length === 0 &&
    !quality.capped
  if (allPass) {
    return (
      <section className="side-card side-ok">
        <Icon name="shieldCheck" size={20} />
        <span>{t("Every sentence is linked to a fact found in the source, and every number, date and code is in the source.")}</span>
      </section>
    )
  }
  const jump = (s: Sentence) => select(selectSentence(outputId, s, true))
  return (
    <>
      {unlinked.length > 0 && (
        <section className="side-card side-warn">
          <div className="row gap-8">
            <Icon name="warning" size={20} />
            <strong>
              {t("{length} sentence{value} not linked to a fact", { length: unlinked.length, value: unlinked.length === 1 ? '' : 's' })}</strong>
          </div>
          {unlinked.map((s) => (
            <button key={s.id} type="button" className="warn-item" onClick={() => jump(s)}>
              “{s.text}”<span className="warn-where">{s.label}</span>
            </button>
          ))}
          <p className="small warn-hint">{t("Use Edit to change or remove them, or check them yourself.")}</p>
        </section>
      )}
      {unverified.length > 0 && (
        <section className="side-card side-warn">
          <div className="row gap-8">
            <Icon name="warning" size={20} />
            <strong>
              {t("{length} sentence{value}: linked fact not verified", { length: unverified.length, value: unverified.length === 1 ? '' : 's' })}</strong>
          </div>
          {unverified.map((s) => (
            <button key={s.id} type="button" className="warn-item" onClick={() => jump(s)}>
              “{s.text}”<span className="warn-where">{t("{label} · its fact's quote is not in the source", { label: s.label })}</span>
            </button>
          ))}
        </section>
      )}
      {flagged.length > 0 && (
        <section className="side-card side-bad">
          <div className="row gap-8">
            <Icon name="warning" size={20} />
            <strong>{t("Not in source")}</strong>
          </div>
          {flagged.map((s) => (
            <button key={s.id} type="button" className="warn-item" onClick={() => jump(s)}>
              {s.not_in_source.map((f) => f.text).join(', ')}
              <span className="warn-where">
                {t("{label} · not in the source", { label: s.label })}</span>
            </button>
          ))}
        </section>
      )}
    </>
  )
}

// ---- quality score --------------------------------------------------------------------------

export function QualityCard({ quality, versionNote }: { quality: Quality; versionNote: string }) {
  const parts = quality.score_parts
  if (quality.score === undefined || !parts) return null
  const rows: [string, string, number, number][] = [
    [parts.linked.label, `${parts.linked.done} / ${parts.linked.total}`, parts.linked.points, parts.linked.max],
    [
      parts.quotes.label,
      parts.quotes.total ? `${parts.quotes.done} / ${parts.quotes.total}${parts.quotes.close ? ` (+${parts.quotes.close} close)` : ''}` : 'none used',
      parts.quotes.points,
      parts.quotes.max,
    ],
    [parts.values.label, parts.values.problems ? `${parts.values.problems} not found` : 'all found', parts.values.points, parts.values.max],
    [parts.format.label, `${parts.format.done} / ${parts.format.total}`, parts.format.points, parts.format.max],
  ]
  return (
    <section className="card side-card">
      <div className="row gap-8">
        <h2 className="side-title">{t("Quality score")}</h2>
        <div className="grow" />
        <span className={`score-big score-${scoreTone(quality.score)}`}>{quality.score}</span>
      </div>
      <span className="small muted">{versionNote}</span>
      {quality.capped && (
        <span className="small" style={{ color: 'var(--red-dark)' }}>
          {t("Capped at 50: the fact sheet does not match the source.")}
        </span>
      )}
      {rows.map(([label, value, points, max]) => (
        <div key={label} className="stack gap-4">
          <div className="row gap-8 small">
            <span>{label}</span>
            <div className="grow" />
            <strong>{value}</strong>
          </div>
          <div className="bar" title={t("{points} of {max} points", { points: points, max: max })}>
            <div className={`bar-fill fill-${scoreTone((points / max) * 100)}`} style={{ width: `${(points / max) * 100}%` }} />
          </div>
        </div>
      ))}
      {(quality.format_rules ?? []).some((r) => !r.ok) && (
        <ul className="rule-list small">
          {quality.format_rules!
            .filter((r) => !r.ok)
            .map((r) => (
              <li key={r.rule}>
                <Icon name="cross" size={14} color="var(--red-dark)" /> {r.rule}: {r.detail}
              </li>
            ))}
        </ul>
      )}
      <p className="small muted">{quality.explanation}</p>
    </section>
  )
}

// A small score with a tooltip (on hover and on keyboard focus) that explains it in plain words.
// inButton: inside a button (a tab), which already takes the keyboard focus.
type ScoreBadgeProps = { score: number | null | undefined; explanation?: string; big?: boolean; inButton?: boolean }

export function ScoreBadge({ score, explanation, big, inButton }: ScoreBadgeProps) {
  if (score === null || score === undefined) return null
  if (!explanation) {
    // nothing to explain: no tooltip, so no extra Tab stop
    return (
      <span className={`score-badge score-bg-${scoreTone(score)} ${big ? 'score-badge-big' : ''}`}>
        {big ? t("Quality ") : <span className="sr-only">{t("Quality")} </span>}
        {score}
      </span>
    )
  }
  return (
    <span className="tip" tabIndex={inButton ? undefined : 0} aria-label={t("Quality {score}. {n}", { score: score, n: explanation ?? '' })}>
      <span className={`score-badge score-bg-${scoreTone(score)} ${big ? 'score-badge-big' : ''}`}>
        {big && t("Quality ")}
        {score}
      </span>
      {explanation && (
        <span className="tip-box" role="tooltip">
          {explanation}
        </span>
      )}
    </span>
  )
}

// ---- consistency across outputs -------------------------------------------------------------

type ConsistencyProps = {
  consistency: Consistency | null
  generating: boolean
  facts: FactLookup
  onOpen: (outputId: number, sentenceId: string, factId: string) => void
  onFact: (factId: string) => void
}

export function ConsistencyPanel({ consistency, generating, facts, onOpen, onFact }: ConsistencyProps) {
  if (!consistency) {
    return (
      <section className="card card-pad-sm row gap-12 wrap">
        <span className="section-label">{t("Consistency")}</span>
        <span className="muted small">
          {generating ? t("Checked when the outputs are ready.") : t("No outputs to compare yet.")}
        </span>
      </section>
    )
  }
  const { mismatches, agreed } = consistency
  return (
    <section className="card card-pad-sm stack gap-10">
      <div className="row gap-10 wrap">
        <span className="section-label">{t("Consistency across outputs")}</span>
        {consistency.ok ? (
          <span className="chip chip-green">
            <Icon name="check" size={14} strokeWidth={2.4} /> {t("All outputs agree")}
          </span>
        ) : (
          <span className="chip chip-red">
            {t("{length} mismatch{value}", { length: mismatches.length, value: mismatches.length === 1 ? '' : t("es") })}</span>
        )}
        <span className="muted small">
          {t("{checked} numbers, dates and times in {outputs} output{value} compared with the fact they come from.", { checked: consistency.checked, outputs: consistency.outputs, value: consistency.outputs === 1 ? '' : 's' })}</span>
      </div>
      {mismatches.length > 0 && (
        <ul className="mismatch-list">
          {mismatches.map((m) => (
            <li key={`${m.output_id}-${m.sentence_id}-${m.found}`} className="mismatch">
              <button type="button" className="fact-chip" title={facts.get(m.fact_id)?.text} onClick={() => onFact(m.fact_id)}>
                {m.fact_id}
              </button>
              <span className="grow">
                {t("The fact sheet says")} <strong>{m.expected.join(' / ')}</strong>{t(", but the")} <strong>{m.output_label}</strong> {t("says")}{' '}
                <strong className="mismatch-found">{m.found}</strong>.
              </span>
              <button type="button" className="btn btn-outline btn-xs" onClick={() => onOpen(m.output_id, m.sentence_id, m.fact_id)}>
                {t("Open")} {m.output_label}
                <Icon name="arrowRight" size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {agreed.length > 0 && (
        <div className="row gap-6 wrap small">
          <span className="muted">{t("Same everywhere:")}</span>
          {agreed.map((a) => (
            <button
              key={`${a.fact_id}-${a.value}`}
              type="button"
              className="agree-chip"
              title={t("{fact_id}: {n}\nUsed the same in: {n2}", { fact_id: a.fact_id, n: facts.get(a.fact_id)?.text ?? '', n2: a.outputs.join(', ') })}
              onClick={() => onFact(a.fact_id)}
            >
              <Icon name="check" size={13} strokeWidth={2.4} />
              {a.value} <span className="muted">{t("· {length} outputs", { length: a.outputs.length })}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
