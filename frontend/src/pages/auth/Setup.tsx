// Design 07 · First-time setup. Shown only while there are no accounts at all: it makes the first
// Admin (there are no built-in or default accounts). Stage 9B: the computer check shows real numbers
// from this computer (GET /api/auth/computer), and the AI that is set up in .env.
import { useEffect, useState, type FormEvent } from 'react'
import { checkComputer, firstTimeSetup, type ComputerCheck, type User } from '../../api'
import { Icon } from '../../components/Icon'
import { TricolourStrip } from '../../components/TricolourStrip'
import { BrandMark, FormError, PasswordInput, PasswordStrength } from './AuthLayout'

const STEPS = ['Check this computer', 'Install AI models', 'Create Admin account', 'Organisation details', 'Signing certificate', 'Ready to use']
const CURRENT = 2

export function Setup({ onDone }: { onDone: (user: User) => void }) {
  const [form, setForm] = useState({ full_name: '', username: '', employee_id: '', email: '' })
  const [computer, setComputer] = useState<ComputerCheck | null>(null)

  useEffect(() => {
    checkComputer()
      .then(setComputer)
      .catch(() => setComputer(null))
  }, [])
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError('The two passwords are not the same.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const { user } = await firstTimeSetup({ ...form, password })
      onDone(user)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the Admin account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="setup-page">
      <TricolourStrip />
      <header className="setup-head">
        <BrandMark />
        <span className="muted">· First-time setup</span>
        <div className="grow" />
        <span className="chip chip-green">
          <Icon name="wifiOff" size={14} strokeWidth={2.2} />
          Offline
        </span>
      </header>
      <div className="setup-body">
        <aside className="stack gap-20">
          <div className="stack gap-8">
            <h1 className="setup-title">Set up Pramaan AI on this computer</h1>
            <p className="muted">You only do this once.</p>
          </div>
          <ol className="setup-steps">
            {STEPS.map((step, i) => (
              <li key={step} className={i < CURRENT ? 'is-done' : i === CURRENT ? 'is-current' : ''}>
                <span className="setup-step-dot">{i < CURRENT ? <Icon name="check" size={16} strokeWidth={3} /> : i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </aside>
        <form className="stack gap-20" onSubmit={submit}>
          <ComputerCard computer={computer} />
          <section className="card card-pad stack gap-20">
            <div className="row gap-14">
              <span className="setup-card-icon">
                <Icon name="user" size={22} color="var(--navy)" />
              </span>
              <div className="stack gap-2">
                <h2>Create the first Admin account</h2>
                <span className="muted small">This person manages users, templates and security, and reads the audit trail.</span>
              </div>
            </div>
            <FormError message={error} />
            <div className="form-grid-2">
              <label className="field">
                <span className="field-label">Full name</span>
                <input
                  className="input"
                  value={form.full_name}
                  onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                  autoComplete="name"
                  required
                  autoFocus
                />
              </label>
              <label className="field">
                <span className="field-label">Employee ID</span>
                <input
                  className="input"
                  value={form.employee_id}
                  onChange={(e) => setForm((f) => ({ ...f, employee_id: e.target.value }))}
                  autoCapitalize="characters"
                  spellCheck={false}
                  placeholder="e.g. EMP-10001"
                  required
                />
              </label>
              <label className="field">
                <span className="field-label">Username (optional)</span>
                <input
                  className="input"
                  value={form.username}
                  onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  placeholder="e.g. kavya.nair (else the employee ID)"
                />
              </label>
              <label className="field">
                <span className="field-label">Official email (optional)</span>
                <input
                  className="input"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  autoComplete="email"
                />
              </label>
              <div className="field">
                <label className="field-label" htmlFor="setup-password">
                  Password
                </label>
                <PasswordInput id="setup-password" value={password} onChange={setPassword} autoComplete="new-password" />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="setup-confirm">
                  Confirm password
                </label>
                <PasswordInput id="setup-confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
              </div>
            </div>
            <PasswordStrength password={password} />
            <p className="row gap-8 muted small">
              <Icon name="lock" size={16} color="var(--navy)" />
              Keep this password safe. There is no email reset: another Admin can reset it, so consider making a
              second Admin later.
            </p>
          </section>
          <div className="row">
            <div className="grow" />
            <button type="submit" className="btn btn-lg btn-navy" disabled={busy}>
              {busy ? 'Creating…' : 'Create Admin and continue'}
              <Icon name="arrowRight" size={18} strokeWidth={2} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const gb = (bytes: number | null) => (bytes === null ? 'Unknown' : `${Math.round(bytes / 1024 ** 3)} GB`)

// "This computer is ready" (design 07), with the real numbers of this computer and the AI from .env
function ComputerCard({ computer }: { computer: ComputerCheck | null }) {
  const enough = computer && (computer.memory_bytes ?? 0) >= 15 * 1024 ** 3
  const tiles: { icon: 'chip' | 'bolt' | 'box'; label: string; value: string }[] = computer
    ? [
        { icon: 'chip', label: 'Memory', value: `${gb(computer.memory_bytes)} RAM` },
        { icon: 'bolt', label: 'Processors', value: `${computer.processors ?? '?'} cores` },
        { icon: 'box', label: 'Free disk space', value: gb(computer.disk_free_bytes) },
      ]
    : []
  return (
    <section className="card card-pad stack gap-16" aria-labelledby="computer-title">
      <div className="row gap-10">
        <h2 id="computer-title" className="grow">
          This computer
        </h2>
        {computer && (
          <span className={enough ? 'chip chip-green' : 'chip chip-yellow'}>
            <Icon name={enough ? 'check' : 'warning'} size={14} strokeWidth={2.4} />
            {enough ? 'Checked' : 'Less than 16 GB memory: the local AI will be slow'}
          </span>
        )}
      </div>
      {!computer && <p className="muted small">Checking…</p>}
      <div className="setup-tiles">
        {tiles.map((t) => (
          <div key={t.label} className="setup-tile">
            <span className="setup-tile-icon" aria-hidden="true">
              <Icon name={t.icon} size={20} />
            </span>
            <span className="stack">
              <span className="small muted">{t.label}</span>
              <strong>{t.value}</strong>
            </span>
          </div>
        ))}
      </div>
      {computer && (
        <p className="row gap-8 small">
          <Icon name="chip" size={16} color="var(--navy)" />
          AI: <strong>{computer.ai.label}</strong>
          <span className="muted">(set with AI_MODE in .env; more models arrive in Stage 8)</span>
        </p>
      )}
    </section>
  )
}

