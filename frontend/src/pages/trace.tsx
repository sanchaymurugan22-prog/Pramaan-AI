// Sentence -> source tracing on the Results page.
//
// The backend splits every text field of an output into sentences and links each one to the facts it
// uses (quality.sentences, see backend/app/pipeline/checks.py). <Traced> shows one text field with
// its sentences: small fact chips after each sentence, a yellow underline for "Not linked to a fact",
// a red underline for numbers / dates / codes that are "Not in source". Clicking a sentence or a chip
// selects it, and the "Source trace" panel on the right shows where it comes from.
import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react'
import type { Path, Sentence } from '../api'
import { pathKey, selectSentence, TraceContext, useTrace, type TraceState } from './traceState'

export function TraceProvider({ value, children }: { value: TraceState; children: ReactNode }) {
  return <TraceContext.Provider value={value}>{children}</TraceContext.Provider>
}

// One text field of an output, drawn sentence by sentence.
export function Traced({ path, text }: { path: Path; text: string }) {
  const trace = useTrace()
  const sentences = trace?.byPath.get(pathKey(path))
  if (!trace || !sentences) return <>{text}</>

  const parts: ReactNode[] = []
  let cursor = 0
  for (const s of sentences) {
    const at = text.indexOf(s.text, cursor)
    if (at < 0) continue // (the text changed since it was checked; show it plainly)
    if (at > cursor) parts.push(text.slice(cursor, at))
    parts.push(<SentenceSpan key={s.id} sentence={s} />)
    cursor = at + s.text.length
  }
  if (cursor < text.length) parts.push(text.slice(cursor))
  return <>{parts}</>
}

function SentenceSpan({ sentence: s }: { sentence: Sentence }) {
  const trace = useTrace()!
  const ref = useRef<HTMLSpanElement>(null)
  const selected = trace.selection.outputId === trace.outputId && trace.selection.sentenceId === s.id
  const claim = s.status === 'linked' || s.status === 'unlinked'
  const interactive = claim || s.not_in_source.length > 0

  useEffect(() => {
    if (selected && trace.selection.scroll) ref.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [selected, trace.selection.scroll])

  if (!interactive) return <>{s.text}</>

  const open = () => trace.outputId !== null && trace.select(selectSentence(trace.outputId, s))
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      open()
    }
  }
  const classes = ['sent', s.status === 'unlinked' && 'is-unlinked', selected && 'is-selected'].filter(Boolean).join(' ')
  return (
    <span
      ref={ref}
      className={classes}
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={onKey}
      title="Show where this comes from in the source"
    >
      <FlaggedText text={s.text} flags={s.not_in_source.map((f) => f.text)} />
      <SentenceTags sentence={s} />
    </span>
  )
}

// The sentence text with every "Not in source" value underlined in red.
function FlaggedText({ text, flags }: { text: string; flags: string[] }) {
  if (flags.length === 0) return <>{text}</>
  const parts: ReactNode[] = []
  let cursor = 0
  for (const flag of flags) {
    const at = text.indexOf(flag, cursor)
    if (at < 0) continue
    parts.push(text.slice(cursor, at))
    parts.push(
      <span key={`${at}-${flag}`} className="not-in-source" title="Not in source: this is not in the fact sheet or the source">
        {flag}
      </span>,
    )
    cursor = at + flag.length
  }
  parts.push(text.slice(cursor))
  return <>{parts}</>
}

// Small tags after a sentence: its fact chips, or "Not linked to a fact", and "Not in source".
function SentenceTags({ sentence: s }: { sentence: Sentence }) {
  const trace = useTrace()!
  return (
    <span className="sent-tags">
      {s.status === 'linked' &&
        s.fact_ids.map((id) => (
          <FactChip key={id} id={id} onClick={() => trace.select({ outputId: trace.outputId, sentenceId: s.id, factId: id })} />
        ))}
      {s.status === 'unlinked' && <span className="tag tag-yellow">Not linked to a fact</span>}
      {s.not_in_source.length > 0 && <span className="tag tag-red">Not in source</span>}
    </span>
  )
}

// A clickable fact id (F1, A3, D2). Shows the fact's text as a tooltip.
export function FactChip({ id, onClick, active }: { id: string; onClick: () => void; active?: boolean }) {
  const trace = useTrace()
  const fact = trace?.facts.get(id)
  return (
    <button
      type="button"
      className={active ? 'fact-chip is-active' : 'fact-chip'}
      title={fact ? `${id}: ${fact.text}` : id}
      onClick={(e) => {
        e.stopPropagation() // do not also select the whole sentence
        onClick()
      }}
    >
      {id}
    </button>
  )
}

// Tags only (no text) for a field drawn in pieces, like an infographic number tile.
export function TraceTags({ path }: { path: Path }) {
  const trace = useTrace()
  const sentences = trace?.byPath.get(pathKey(path)) ?? []
  return (
    <>
      {sentences.map((s) => (
        <SentenceTags key={s.id} sentence={s} />
      ))}
    </>
  )
}
