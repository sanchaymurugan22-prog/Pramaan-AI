// Shared state for sentence -> source tracing (see trace.tsx for the components that draw it).
import { createContext, useContext } from 'react'
import type { Path, Sentence } from '../api'
import type { FactLookup } from './format'

// What the reviewer clicked. scroll = also scroll the sentence into view (from a link elsewhere).
export type Selection = { outputId: number | null; sentenceId: string | null; factId: string | null; scroll?: boolean }

export const NO_SELECTION: Selection = { outputId: null, sentenceId: null, factId: null }

export type TraceState = {
  outputId: number | null
  byPath: Map<string, Sentence[]>
  facts: FactLookup
  selection: Selection
  select: (selection: Selection) => void
}

export const TraceContext = createContext<TraceState | null>(null)

export const pathKey = (path: Path) => path.join('.')

export function sentencesByPath(sentences: Sentence[] | undefined): Map<string, Sentence[]> {
  const map = new Map<string, Sentence[]>()
  for (const s of sentences ?? []) {
    const key = pathKey(s.path)
    map.set(key, [...(map.get(key) ?? []), s])
  }
  return map
}

export function useTrace(): TraceState | null {
  return useContext(TraceContext)
}

// The first fact to show for a sentence: one it uses, or (if it uses none) the closest one.
export function selectSentence(outputId: number, s: Sentence, scroll = false): Selection {
  return { outputId, sentenceId: s.id, factId: s.fact_ids[0] ?? s.closest ?? null, scroll }
}

// Props for making a whole block (e.g. a number tile) select its sentence when clicked.
export function useTraceBlock(path: Path): { className: string; onClick?: () => void } {
  const trace = useTrace()
  const s = trace?.byPath.get(pathKey(path))?.[0]
  if (!trace || !s || trace.outputId === null) return { className: '' }
  const selected = trace.selection.outputId === trace.outputId && trace.selection.sentenceId === s.id
  const outputId = trace.outputId
  return {
    className: ['is-traceable', s.status === 'unlinked' && 'is-unlinked', selected && 'is-selected'].filter(Boolean).join(' '),
    onClick: () => trace.select(selectSentence(outputId, s)),
  }
}
