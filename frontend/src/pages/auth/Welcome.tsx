// Design 01 · Splash and design 02 · Language selection (Stage 9B).
// The splash shows once per browser, while the app checks that the backend is running; the language
// screen keeps the choice in this browser before sign-in, and in the profile after it.
import { useEffect, useState } from 'react'
import { getFormOptions, type Health, type Language } from '../../api'
import { Icon, type IconName } from '../../components/Icon'
import { LogoSeal } from '../../components/Logo'
import { Mandala } from '../../components/Mandala'
import { TricolourStrip } from '../../components/TricolourStrip'
import { markWelcomed, storedLanguage, storeLanguage } from '../../localPrefs'
import { links, navigate } from '../../router'
import { aiLabel } from '../format'
import { BrandMark } from './AuthLayout'

const BADGES: { icon: IconName; text: string; tone: string }[] = [
  { icon: 'wifiOff', text: 'Works fully offline', tone: 'green' },
  { icon: 'globe', text: '22 Indian languages', tone: 'saffron' },
  { icon: 'award', text: 'Every document signed', tone: 'navy' },
]

export function Splash({ health }: { health: Health | null | undefined }) {
  // The bar fills as the check finishes: grey while checking, tricolour when ready, red if not running
  const state = health === undefined ? 'checking' : health === null ? 'down' : 'ready'
  function start() {
    markWelcomed()
    navigate(storedLanguage() ? links.login : links.language)
  }
  return (
    <div className="splash">
      <TricolourStrip />
      <div className="splash-mandala-left" aria-hidden="true">
        <Mandala size={420} petals={16} color="var(--saffron)" opacity={0.45} />
      </div>
      <div className="splash-mandala-right" aria-hidden="true">
        <Mandala size={460} petals={16} color="var(--green)" opacity={0.45} />
      </div>
      <main className="splash-body">
        <span className="splash-seal">
          <LogoSeal size={136} />
        </span>
        <h1 className="splash-name">Pramaan AI</h1>
        <span className="splash-devanagari" lang="hi">
          प्रमाण
        </span>
        <p className="splash-tagline">Content you can prove.</p>
        <p className="muted splash-sub">One source · every format · every Indian language</p>
        <ul className="splash-badges">
          {BADGES.map((b) => (
            <li key={b.text}>
              <span className={`splash-badge-icon tone-${b.tone}`} aria-hidden="true">
                <Icon name={b.icon} size={16} />
              </span>
              {b.text}
            </li>
          ))}
        </ul>
        <div className={`splash-progress is-${state}`} aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="muted small" role="status">
          {state === 'checking' && 'Checking this computer…'}
          {state === 'ready' && `Ready · ${aiLabel(health?.ai_mode)}`}
          {state === 'down' && 'The backend is not running. Start it with ./scripts/start.sh'}
        </p>
        <button type="button" className="btn btn-lg btn-navy" onClick={start} disabled={state !== 'ready'} autoFocus>
          Get started
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </button>
      </main>
      <p className="muted small splash-foot">Built on Indian AI · Sarvam AI · BharatGen · AI4Bharat (IIT Madras)</p>
    </div>
  )
}

// English name of each language, shown under its own script
const ENGLISH: Record<string, string> = {
  en: 'English', hi: 'Hindi', bn: 'Bengali', te: 'Telugu', mr: 'Marathi', ta: 'Tamil', ur: 'Urdu', gu: 'Gujarati',
  kn: 'Kannada', or: 'Odia', ml: 'Malayalam', pa: 'Punjabi', as: 'Assamese', mai: 'Maithili', sat: 'Santali',
  ks: 'Kashmiri', ne: 'Nepali', sd: 'Sindhi', doi: 'Dogri', kok: 'Konkani', mni: 'Manipuri', brx: 'Bodo', sa: 'Sanskrit',
}

// Before sign-in only; signed in, the language is changed on Profile & settings.
export function LanguagePicker() {
  const [languages, setLanguages] = useState<Language[]>([])
  const [chosen, setChosen] = useState(storedLanguage() ?? 'en')
  const [error, setError] = useState('')

  useEffect(() => {
    getFormOptions()
      .then((o) => setLanguages(o.languages))
      .catch(() => setError('Could not load the languages. Is the backend running?'))
  }, [])

  function next() {
    storeLanguage(chosen)
    navigate(links.login)
  }

  const name = languages.find((l) => l.code === chosen)?.name ?? 'English'
  return (
    <div className="language-page">
      <TricolourStrip />
      <div className="language-mandala" aria-hidden="true">
        <Mandala size={320} petals={16} color="var(--saffron)" opacity={0.3} />
      </div>
      <header className="row gap-12 language-head">
        <BrandMark />
        <div className="grow" />
        <span className="eyebrow">Step 1 of 2 · Language</span>
      </header>
      <main className="language-main">
        <div className="row gap-20 wrap align-start">
          <div className="stack gap-6 grow">
            <h1 className="language-title">Choose your language</h1>
            <p className="language-sub">
              <span lang="hi">अपनी भाषा चुनें</span> · <span lang="ta">உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்</span> ·{' '}
              <span lang="bn">আপনার ভাষা বেছে নিন</span>
            </p>
          </div>
          <p className="notice notice-green language-note">
            <Icon name="globe" size={20} />
            <span>
              Your choice is saved now. The app's own words are in English until Stage 8; outputs in all 23 languages
              are translated offline by Indian AI.
            </span>
          </p>
        </div>
        {error && <div className="alert alert-red">{error}</div>}
        <div className="language-grid" role="radiogroup" aria-label="Language">
          {languages.map((l) => (
            <label key={l.code} className={chosen === l.code ? 'language-card is-on' : 'language-card'}>
              <input type="radio" name="language" className="sr-only" checked={chosen === l.code} onChange={() => setChosen(l.code)} />
              <span className="language-native" lang={l.code}>
                {l.name}
              </span>
              <span className="row">
                <span className="muted small grow">{ENGLISH[l.code] ?? l.code}</span>
                {chosen === l.code && (
                  <span className="language-tick" aria-hidden="true">
                    <Icon name="check" size={14} strokeWidth={3} />
                  </span>
                )}
              </span>
            </label>
          ))}
        </div>
      </main>
      <footer className="language-foot">
        <span className="muted">
          Selected: <strong>{name}</strong> · You can change this any time in Profile &amp; settings.
        </span>
        <div className="grow" />
        <button type="button" className="btn btn-lg btn-navy" onClick={next}>
          Continue
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </button>
      </footer>
    </div>
  )
}
