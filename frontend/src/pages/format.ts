import type { FactSheet, QuoteFound } from '../api'
import { locale, t } from '../i18n'

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
  const labels = types.map((type) => t(OUTPUT_LABELS[type] ?? type))
  return labels.length <= 2 ? labels.join(', ') : `${labels.slice(0, 2).join(', ')} +${labels.length - 2}`
}

// Today: "14:05". Other days: "28 Sep".
export function shortTime(iso: string): string {
  const date = new Date(iso)
  const today = new Date().toDateString() === date.toDateString()
  return today
    ? date.toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit', hour12: false })
    : date.toLocaleDateString(locale(), { day: 'numeric', month: 'short' })
}

// 75 -> "1:15"
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// Which AI is in use, for chips and status rows
export function aiLabel(mode: string | undefined): string {
  if (mode === 'local') return t('Sarvam 30B · local')
  if (mode === 'cloud') return t('Web · Sarvam Cloud')
  if (mode === 'mock') return t('Mock AI · test answers')
  return t('AI')
}

// Job numbers as printed everywhere: 142 -> "#0142"
export function jobNo(id: number): string {
  return `#${String(id).padStart(4, '0')}`
}

// Which AI wrote a job, for the "AI used" column (null: the AI has not started yet)
export function aiShort(mode: string | null | undefined): string {
  if (mode === 'local') return 'Sarvam 30B local'
  if (mode === 'cloud') return 'Sarvam cloud'
  if (mode === 'mock') return 'Mock'
  return '—'
}

export const LANGUAGE_LABELS: Record<string, string> = { en: 'EN', hi: 'हि', ta: 'த', bn: 'বা', te: 'తె' }

// Each language's own name (the same list as backend/app/auth/accounts.py LANGUAGES)
export const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English', hi: 'हिन्दी', bn: 'বাংলা', te: 'తెలుగు', mr: 'मराठी', ta: 'தமிழ்', ur: 'اردو', gu: 'ગુજરાતી', kn: 'ಕನ್ನಡ',
  or: 'ଓଡ଼ିଆ', ml: 'മലയാളം', pa: 'ਪੰਜਾਬੀ', as: 'অসমীয়া', mai: 'मैथिली', sat: 'ᱥᱟᱱᱛᱟᱲᱤ', ks: 'کٲشُر', ne: 'नेपाली', sd: 'سنڌي',
  doi: 'डोगरी', kok: 'कोंकणी', mni: 'ꯃꯤꯇꯩꯂꯣꯟ', brx: 'बड़ो', sa: 'संस्कृतम्',
}

// "Today", "Yesterday" or "28 Sep", for grouping lists by day
export function dayLabel(iso: string): string {
  const date = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString(locale(), { day: 'numeric', month: 'short', year: 'numeric' })
}

// "30 Sep, 10:21"
export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(locale(), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
}

// 2150000 -> "2.1 MB"
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  // memory and disk: "16 GB", "136 GB" (one decimal only for small numbers, e.g. "1.5 GB")
  const gb = bytes / 1024 ** 3
  return `${gb < 10 ? gb.toFixed(1) : Math.round(gb)} GB`
}

export { OUTPUT_LABELS }

// One fact sheet item that a sentence can be linked to, with where it is in the source.
export type TraceItem = {
  id: string
  kind: 'Fact' | 'Recommended action' | 'Date'
  text: string
  quote: string
  source_id?: string
  page?: number
  start?: number | null
  end?: number | null
  quote_found?: QuoteFound
}

export type FactLookup = Map<string, TraceItem>

// F1, F2... (facts), A1, A2... (recommended actions) and D1, D2... (dates) -> what they say and where
export function factLookup(sheet: FactSheet | null): FactLookup {
  const map: FactLookup = new Map()
  sheet?.key_facts.forEach((f) => map.set(f.id, { ...f, kind: 'Fact' }))
  sheet?.recommended_actions.forEach((a) => map.set(a.id, { ...a, quote: a.quote ?? '', kind: 'Recommended action' }))
  sheet?.dates.forEach((d) => {
    if (d.id) map.set(d.id, { ...d, id: d.id, text: `${d.date}: ${d.event}`, quote: d.quote ?? '', kind: 'Date' })
  })
  return map
}

export const FOUND_LABELS: Record<QuoteFound, string> = {
  exact: 'Found in source',
  close: 'Close match',
  no: 'Not found in source',
}

// Quality score colour: 85+ green, 60+ saffron, below 60 red
export function scoreTone(score: number | null | undefined): 'good' | 'fair' | 'poor' | 'none' {
  if (score === null || score === undefined) return 'none'
  return score >= 85 ? 'good' : score >= 60 ? 'fair' : 'poor'
}

// The backend counts text positions in Unicode characters (Python); JavaScript counts UTF-16 units.
// They differ only for characters like emoji. Converts a Python position into a JavaScript one.
export function jsIndex(text: string, pythonIndex: number): number {
  let js = 0
  for (let chars = 0; chars < pythonIndex && js < text.length; chars++) {
    const code = text.charCodeAt(js)
    js += code >= 0xd800 && code <= 0xdbff ? 2 : 1
  }
  return js
}

// e.g. "Wednesday, 30 September"
export function todayLabel(): string {
  return new Date().toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' })
}

// A SHA-256 fingerprint, shortened for display: "3f9a 7c21 … 8d02 e0b4"
export function shortHash(hash: string): string {
  return `${hash.slice(0, 4)} ${hash.slice(4, 8)} … ${hash.slice(-8, -4)} ${hash.slice(-4)}`
}
