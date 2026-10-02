// Stage 8: the app's own words in English or Hindi (i18n). Every piece of interface text goes through t():
//
//     t('New transformation')                      -> 'नया रूपांतरण' when the app language is Hindi
//     t('{done} of {total} ready', { done, total })
//
// The Hindi words are in hi.json (made once with IndicTrans2 by scripts/make-ui-hindi.py, the most used ones
// read and corrected by a person). Any text without a Hindi entry stays in English. The app language is the
// signed-in user's language (Profile, or the switch at the top right), so it is remembered per user; before
// signing in, the language chosen on the welcome screens.
//
// Only the interface is translated. Outputs, sources and names are never touched by t().
import hi from './hi.json'

export type UiLanguage = 'en' | 'hi'
export const UI_LANGUAGES: UiLanguage[] = ['en', 'hi']

const DICTIONARIES: Record<UiLanguage, Record<string, string>> = { en: {}, hi: hi as Record<string, string> }

let current: UiLanguage = 'en'

// Any language other than Hindi shows the interface in English (outputs can still be in all 23).
export function uiLanguage(code: string | null | undefined): UiLanguage {
  return code === 'hi' ? 'hi' : 'en'
}

export function getLanguage(): UiLanguage {
  return current
}

// Called by App before it draws the pages (App keys the pages by the language, so all of them draw again).
export function setLanguage(code: string | null | undefined): UiLanguage {
  current = uiLanguage(code)
  if (typeof document !== 'undefined') document.documentElement.lang = current
  return current
}

export function t(text: string, values?: Record<string, unknown>): string {
  const out = (current === 'en' ? undefined : DICTIONARIES[current][text]) ?? text
  if (!values) return out
  return out.replace(/\{(\w+)\}/g, (whole, name: string) => (name in values ? shown(values[name]) : whole))
}

// A value as it appears: nothing for false / null / undefined (as JSX shows them); in Hindi, an English plural
// ending ("output{s}") is left out: the Hindi sentence already says it right.
function shown(value: unknown): string {
  if (value === false || value === null || value === undefined) return ''
  if (current !== 'en' && (value === 's' || value === 'es')) return ''
  return String(value)
}

// Dates and times in the app language ("2 अक्तू॰", "शुक्रवार, 2 अक्तूबर")
export function locale(): string {
  return current === 'hi' ? 'hi-IN' : 'en-IN'
}

