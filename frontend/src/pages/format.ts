import type { Fact, FactSheet } from '../api'

// Small helpers shared by the pages.

const OUTPUT_LABELS: Record<string, string> = {
  x_thread: 'X thread',
  linkedin_post: 'LinkedIn post',
  executive_summary: 'Executive summary',
  infographic: 'Infographic',
  advisory: 'Advisory',
  presentation: 'Presentation',
  video_package: 'Video package',
}

// ["x_thread", "advisory", "presentation"] -> "X thread, Advisory +1"
export function outputKinds(types: string[]): string {
  const labels = types.map((t) => OUTPUT_LABELS[t] ?? t)
  return labels.length <= 2 ? labels.join(', ') : `${labels.slice(0, 2).join(', ')} +${labels.length - 2}`
}

// Today: "14:05". Other days: "28 Sep".
export function shortTime(iso: string): string {
  const date = new Date(iso)
  const today = new Date().toDateString() === date.toDateString()
  return today
    ? date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
    : date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

// 75 -> "1:15"
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// Which AI is in use, for chips and status rows
export function aiLabel(mode: string | undefined): string {
  if (mode === 'local') return 'Sarvam 30B · local'
  if (mode === 'cloud') return 'Sarvam · cloud'
  if (mode === 'mock') return 'Mock AI · test answers'
  return 'AI'
}

export type FactLookup = Map<string, { text: string; page?: number }>

// F1, F2... (facts) and A1, A2... (recommended actions) -> what they say
export function factLookup(sheet: FactSheet | null): FactLookup {
  const map: FactLookup = new Map()
  sheet?.key_facts.forEach((f: Fact) => map.set(f.id, { text: f.text, page: f.page }))
  sheet?.recommended_actions.forEach((a) => map.set(a.id, { text: a.text }))
  return map
}
