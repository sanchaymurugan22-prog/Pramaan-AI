// Design 41 · Profile and settings (all roles), Stage 9B. Everyone changes their own language and
// preferences here; name, employee ID, email, division and role are changed by an Admin (so nobody can
// give themselves another identity). Text size and high contrast apply to the whole app at once.
import { useEffect, useState, type FormEvent } from 'react'
import { changePassword, getProfile, saveProfile, type Language, type Prefs, type User } from '../api'
import { initials, useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { Mandala } from '../components/Mandala'
import { Toggle } from '../components/Toggle'
import { languageByCode, useLanguages } from '../languages'
import { FormError, PasswordInput, PasswordStrength } from './auth/AuthLayout'

function CardHead({ icon, tone, title }: { icon: IconName; tone: string; title: string }) {
  return (
    <div className="row gap-12">
      <span className={`stat-icon tone-${tone}`} aria-hidden="true">
        <Icon name={icon} size={20} />
      </span>
      <h2>{title}</h2>
    </div>
  )
}

const SIZES: { value: NonNullable<Prefs['text_size']>; label: string }[] = [
  { value: 'normal', label: 'Normal' },
  { value: 'large', label: 'Large' },
  { value: 'xlarge', label: 'Extra large' },
]

export function Profile({ onChanged }: { onChanged: (user: User) => void }) {
  const { user, signOut } = useAuth()
  const [languages, setLanguages] = useState<Language[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getProfile()
      .then((p) => setLanguages(p.languages))
      .catch(() => setError('Could not load the language list.'))
  }, [])

  async function save(change: { language?: string; prefs?: Prefs }, done: string) {
    setError('')
    try {
      onChanged((await saveProfile(change)).user)
      setMessage(done)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save.')
    }
  }

  const prefs = user.prefs ?? {}
  const languageInfo = useLanguages()
  const voice = languageByCode(languageInfo, user.language || 'en')?.voice ?? null
  const outputs = prefs.output_languages ?? [user.language || 'en']
  const name = (code: string) => languages.find((l) => l.code === code)?.name ?? code
  const since = user.created_at ? new Date(user.created_at).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }) : '—'

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">Account</div>
          <h1>Profile &amp; settings</h1>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-red-outline" onClick={() => signOut()}>
          <Icon name="signOut" size={18} />
          Sign out
        </button>
      </div>
      {error && <div className="alert alert-red" role="alert">{error}</div>}
      <p className="sr-only" role="status">{message}</p>

      <div className="profile-grid">
        <section className="card profile-card" aria-label="Your details">
          <div className="profile-banner" aria-hidden="true">
            <Mandala size={200} petals={12} color="var(--role)" opacity={0.4} />
          </div>
          <div className="stack gap-12 profile-body">
            <span className="avatar profile-avatar" aria-hidden="true">
              {initials(user.full_name)}
            </span>
            <div className="stack gap-2">
              <h2 className="profile-name">{user.full_name}</h2>
              <span className="muted">
                {user.role_label}
                {user.division && ` · ${user.division}`}
              </span>
            </div>
            <dl className="facts-table">
              <div>
                <dt>Employee ID</dt>
                <dd className="mono">{user.employee_id ?? '—'}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{user.email ?? '—'}</dd>
              </div>
              <div>
                <dt>Username</dt>
                <dd className="mono">{user.username}</dd>
              </div>
              <div>
                <dt>Member since</dt>
                <dd>{since}</dd>
              </div>
              {user.role === 'reviewer' && (
                <div>
                  <dt>DSC token</dt>
                  <dd>{user.dsc_holder ? 'Class 3 holder' : 'None'}</dd>
                </div>
              )}
            </dl>
            <p className="muted small">Your Admin changes these details (Users &amp; access).</p>
          </div>
        </section>

        <div className="stack gap-20">
          <section className="card card-pad stack gap-14" aria-label="Language">
            <CardHead icon="globe" tone="saffron" title="Language" />
            <div className="form-grid-2">
              <label className="field">
                <span className="field-label">App language</span>
                <select className="input" value={user.language || 'en'} onChange={(e) => save({ language: e.target.value }, 'Language saved.')}>
                  {languages.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.name}
                    </option>
                  ))}
                </select>
                <span className="field-help">Saved now; the app’s own words are in English until Stage 8.</span>
              </label>
              <div className="field">
                <span className="field-label">Voice for audio</span>
                <span className="input input-static">{voice ?? 'No voice for this language on this computer'}</span>
                <span className="field-help">Offline voices: Hindi, Telugu, Malayalam, Urdu (Piper) and Indian English.</span>
              </div>
            </div>
            <div className="field">
              <span className="field-label" id="output-languages">
                Default output languages
              </span>
              <div className="row gap-8 wrap" role="group" aria-labelledby="output-languages">
                {outputs.map((code) => (
                  <span key={code} className="pill is-on">
                    <Icon name="check" size={16} strokeWidth={2.4} />
                    {name(code)}
                    {outputs.length > 1 && (
                      <button
                        type="button"
                        className="pill-remove"
                        aria-label={`Remove ${name(code)}`}
                        onClick={() => save({ prefs: { output_languages: outputs.filter((c) => c !== code) } }, 'Output languages saved.')}
                      >
                        <Icon name="cross" size={12} strokeWidth={2.6} />
                      </button>
                    )}
                  </span>
                ))}
                <label className="sr-only" htmlFor="add-language">
                  Add an output language
                </label>
                <select
                  id="add-language"
                  className="input select-sm add-language"
                  value=""
                  onChange={(e) => e.target.value && save({ prefs: { output_languages: [...outputs, e.target.value] } }, 'Output languages saved.')}
                >
                  <option value="">+ Add</option>
                  {languages
                    .filter((l) => !outputs.includes(l.code))
                    .map((l) => (
                      <option key={l.code} value={l.code}>
                        {l.name}
                      </option>
                    ))}
                </select>
              </div>
              <span className="field-help">Ticked in advance on “Outputs and settings” for every new job. English is always made.</span>
            </div>
          </section>

          <div className="form-grid-2 profile-pair">
            <section className="card card-pad stack gap-14" aria-label="Accessibility">
              <CardHead icon="eye" tone="navy" title="Accessibility" />
              <div className="field">
                <span className="field-label" id="text-size">
                  Text size
                </span>
                <div className="segmented" role="group" aria-labelledby="text-size">
                  {SIZES.map((s) => (
                    <button
                      key={s.value}
                      type="button"
                      aria-pressed={(prefs.text_size ?? 'normal') === s.value}
                      className={(prefs.text_size ?? 'normal') === s.value ? 'is-on' : ''}
                      onClick={() => save({ prefs: { text_size: s.value } }, `Text size: ${s.label}.`)}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
              <Toggle
                label="High contrast"
                detail="Darker text and borders"
                on={Boolean(prefs.high_contrast)}
                onChange={(on) => save({ prefs: { high_contrast: on } }, on ? 'High contrast on.' : 'High contrast off.')}
              />
              <Toggle
                label="Read results aloud"
                detail="A “Listen” button on each output, in its own language"
                on={Boolean(prefs.read_aloud)}
                onChange={(on) => save({ prefs: { read_aloud: on } }, on ? 'Read aloud on.' : 'Read aloud off.')}
              />
            </section>

            <section className="card card-pad stack gap-14" aria-label="Notifications">
              <CardHead icon="bell" tone="green" title="Notifications" />
              <Toggle
                label="When outputs are ready"
                on={prefs.notify_ready !== false}
                onChange={(on) => save({ prefs: { notify_ready: on } }, 'Saved.')}
              />
              <Toggle
                label="When a reviewer sends something back"
                on={prefs.notify_sent_back !== false}
                onChange={(on) => save({ prefs: { notify_sent_back: on } }, 'Saved.')}
              />
              {user.role === 'operator' && (
                <Toggle label="Watch folder drafts" on={prefs.notify_watch !== false} onChange={(on) => save({ prefs: { notify_watch: on } }, 'Saved.')} />
              )}
              <p className="muted small">Approvals, signatures and emergency alerts are always shown. Nothing is emailed: in the app only.</p>
            </section>
          </div>

          <PasswordCard onDone={(u) => onChanged(u)} />
        </div>
      </div>
    </main>
  )
}

function PasswordCard({ onDone }: { onDone: (user: User) => void }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setDone(false)
    try {
      const { user } = await changePassword(current, password)
      setCurrent('')
      setPassword('')
      setDone(true)
      onDone(user)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change the password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card card-pad stack gap-14" aria-label="Password" id="password">
      <CardHead icon="lock" tone="red" title="Password" />
      <form className="stack gap-14" onSubmit={submit}>
        <FormError message={error} />
        {done && (
          <div className="alert alert-green" role="status">
            Password changed. Other computers where you were signed in are signed out.
          </div>
        )}
        <div className="form-grid-2">
          <div className="field">
            <label className="field-label" htmlFor="profile-current">
              Current password
            </label>
            <PasswordInput id="profile-current" value={current} onChange={setCurrent} autoComplete="current-password" />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="profile-new">
              New password
            </label>
            <PasswordInput id="profile-new" value={password} onChange={setPassword} autoComplete="new-password" placeholder="At least 12 characters" />
          </div>
        </div>
        <PasswordStrength password={password} />
        <div className="row gap-10 wrap">
          <button type="submit" className="btn btn-navy-outline" disabled={busy || !current || !password}>
            {busy ? 'Changing…' : 'Change password'}
          </button>
          <span className="grow" />
          <span className="muted small">Signed in on this computer only</span>
        </div>
      </form>
    </section>
  )
}
