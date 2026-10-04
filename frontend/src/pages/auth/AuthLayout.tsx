// Layouts for the pages shown before signing in (designs 03-07).
//   SplitLayout: brand panel on the left, the form on the right (Sign in, Request access)
//   CentredLayout: one card in the middle of the page (Forgot password, Request sent, Change password)
import type { ReactNode } from 'react'
import { Icon, type IconName } from '../../components/Icon'
import { LogoSeal } from '../../components/Logo'
import { Mandala } from '../../components/Mandala'
import { TricolourStrip } from '../../components/TricolourStrip'
import { t } from '../../i18n'

const FEATURES: { icon: IconName; title: string; note: string }[] = [
  { icon: 'shieldCheck', title: 'Secure cloud-powered AI', note: 'Runs online with Sarvam AI' },
  { icon: 'globe', title: 'Access from anywhere', note: 'Use Pramaan AI securely through your browser' },
  { icon: 'award', title: 'Signed and verifiable', note: 'A QR code proves every document is genuine' },
]

export function BrandMark({ big = false }: { big?: boolean }) {
  return (
    <div className="row gap-12">
      <LogoSeal size={big ? 58 : 42} />
      <div className="stack">
        <span className={big ? 'brand-name brand-name-big' : 'brand-name'}>{t("Pramaan AI")}</span>
        {big && <span className="brand-devanagari">प्रमाण</span>}
      </div>
    </div>
  )
}

export function SplitLayout({ tone, children }: { tone: 'saffron' | 'green'; children: ReactNode }) {
  const colour = tone === 'saffron' ? 'var(--saffron)' : 'var(--green)'
  return (
    <div className="auth-split">
      <aside className={`auth-brand auth-brand-${tone}`}>
        <div className="auth-brand-mandala-top">
          <Mandala size={130} petals={8} color="var(--navy)" opacity={0.25} />
        </div>
        <div className="auth-brand-mandala-bottom">
          <Mandala size={520} petals={16} color={colour} opacity={0.45} />
        </div>
        <BrandMark big />
        <div className="stack gap-12 auth-brand-copy">
          <h1 className="auth-headline">
            {t("One report in.")}
            <br />
            {t("Every format out.")}
          </h1>
          <p className="auth-lead">
            {t("Turn threat reports, policies and news into advisories, briefings, slides and posts, safely and in your language.")}
          </p>
        </div>
        <ul className="auth-features">
          {FEATURES.map((f) => (
            <li key={f.title} className="row gap-14">
              <span className="auth-feature-icon">
                <Icon name={f.icon} size={20} color={f.icon === 'wifiOff' ? 'var(--green-dark)' : 'var(--saffron-dark)'} />
              </span>
              <span className="stack">
                <strong>{t(f.title)}</strong>
                <span className="muted small">{f.note}</span>
              </span>
            </li>
          ))}
        </ul>
        <div className="grow" />
        <p className="muted small auth-built-on">{t("Built on Indian AI · Sarvam · BharatGen · AI4Bharat")}</p>
      </aside>
      <main className="auth-form-side">
        <TricolourStrip />
        <div className="auth-form-wrap">{children}</div>
      </main>
    </div>
  )
}

export function CentredLayout({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <div className="auth-centred">
      <TricolourStrip />
      <div className="auth-centred-mandala-right">
        <Mandala size={420} petals={12} color="var(--green)" opacity={0.35} />
      </div>
      <div className="auth-centred-mandala-left">
        <Mandala size={480} petals={16} color="var(--saffron)" opacity={0.35} />
      </div>
      <header className="auth-centred-head">
        <BrandMark />
      </header>
      <main className={wide ? 'card auth-card auth-card-wide' : 'card auth-card'}>{children}</main>
    </div>
  )
}

// A password box with a show / hide button.
export function PasswordInput(props: {
  id: string
  value: string
  onChange: (value: string) => void
  autoComplete: 'current-password' | 'new-password'
  placeholder?: string
}) {
  return (
    <span className="input-with-icon">
      <Icon name="lock" size={18} color="var(--icon)" />
      <input
        id={props.id}
        className="input"
        type="password"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        autoComplete={props.autoComplete}
        placeholder={props.placeholder}
        required
      />
    </span>
  )
}

// The same rules as the backend (backend/app/auth/passwords.py): at least 12 characters.
// The bars are only a hint; the backend decides.
export function PasswordStrength({ password }: { password: string }) {
  const kinds = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length
  let bars = 0
  if (password.length >= 12) bars = 2
  if (password.length >= 12 && (kinds >= 3 || password.length >= 16)) bars = 3
  if (password.length >= 16 && kinds >= 2) bars = 4
  if (password.length > 0 && password.length < 12) bars = 1
  const label = ['At least 12 characters', 'Too short: at least 12 characters', 'OK', 'Good password', 'Strong password'][bars]
  return (
    <div className="row gap-10">
      <div className="strength-bars" aria-hidden="true">
        {[1, 2, 3, 4].map((n) => (
          <span key={n} className={n <= bars ? `is-on strength-${bars}` : ''} />
        ))}
      </div>
      <span className={bars >= 3 ? 'strength-label is-good' : bars === 1 ? 'strength-label is-bad' : 'strength-label'}>
        {label}
      </span>
    </div>
  )
}

export function FormError({ message }: { message: string }) {
  if (!message) return null
  return (
    <div className="alert alert-red" role="alert">
      {message}
    </div>
  )
}
