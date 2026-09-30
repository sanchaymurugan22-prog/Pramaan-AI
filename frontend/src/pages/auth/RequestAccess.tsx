// Design 04 · Request access, and design 06 · Request sent (pending).
// The Admin approves or rejects the request (Users & access → Access requests).
import { useState, type FormEvent } from 'react'
import { requestAccess, type AccessRequestSent } from '../../api'
import { Icon } from '../../components/Icon'
import { links, navigate } from '../../router'
import { CentredLayout, FormError, PasswordInput, PasswordStrength, SplitLayout } from './AuthLayout'

const PENDING_KEY = 'pramaan.pendingRequest' // name, username and role only (nothing secret)

export function RequestAccess() {
  const [form, setForm] = useState({ full_name: '', username: '', reason: '', role: 'operator' as 'operator' | 'reviewer' })
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError('The two passwords are not the same.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const sent = await requestAccess({ ...form, password })
      try {
        sessionStorage.setItem(PENDING_KEY, JSON.stringify(sent))
      } catch {
        // private browsing: the Request sent page just shows less detail
      }
      navigate(links.pending)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send the request.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SplitLayout tone="green">
      <form className="auth-form" onSubmit={submit}>
        <div className="stack gap-6">
          <h1 className="auth-title">Request access</h1>
          <p className="muted">Your Admin approves every new account before it can be used.</p>
        </div>
        <FormError message={error} />
        <div className="form-grid-2">
          <label className="field">
            <span className="field-label">Full name</span>
            <input className="input" value={form.full_name} onChange={(e) => set('full_name')(e.target.value)} autoComplete="name" required />
          </label>
          <label className="field">
            <span className="field-label">Username</span>
            <input
              className="input"
              value={form.username}
              onChange={(e) => set('username')(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              placeholder="e.g. rahul.kumar or EMP-20417"
              required
            />
          </label>
        </div>
        <fieldset className="field role-fieldset">
          <legend className="field-label">Role you need</legend>
          <div className="form-grid-2">
            <RoleOption
              role="operator"
              title="Operator"
              note="Create content from reports"
              icon="pencil"
              checked={form.role === 'operator'}
              onChoose={() => set('role')('operator')}
            />
            <RoleOption
              role="reviewer"
              title="Reviewer"
              note="Check and approve content"
              icon="shieldCheck"
              checked={form.role === 'reviewer'}
              onChoose={() => set('role')('reviewer')}
            />
          </div>
          <span className="muted small">Admin accounts are created only by an existing Admin.</span>
        </fieldset>
        <label className="field">
          <span className="field-label">Why do you need access?</span>
          <textarea
            className="input textarea"
            rows={2}
            value={form.reason}
            onChange={(e) => set('reason')(e.target.value)}
            placeholder="e.g. I write advisories for the cyber operations team"
            required
          />
        </label>
        <div className="form-grid-2">
          <div className="field">
            <label className="field-label" htmlFor="new-password">
              Create password
            </label>
            <PasswordInput id="new-password" value={password} onChange={setPassword} autoComplete="new-password" />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="confirm-password">
              Confirm password
            </label>
            <PasswordInput id="confirm-password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          </div>
        </div>
        <PasswordStrength password={password} />
        <button type="submit" className="btn btn-lg btn-saffron" disabled={busy}>
          {busy ? 'Sending…' : 'Request access'}
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </button>
        <p className="muted center">
          Already have an account? <a href={links.login}>Sign in</a>
        </p>
      </form>
    </SplitLayout>
  )
}

function RoleOption(props: {
  role: string
  title: string
  note: string
  icon: 'pencil' | 'shieldCheck'
  checked: boolean
  onChoose: () => void
}) {
  return (
    <label className={`role-option role-${props.role}${props.checked ? ' is-checked' : ''}`}>
      <input type="radio" name="role" value={props.role} checked={props.checked} onChange={props.onChoose} />
      <span className="role-option-icon">
        <Icon name={props.icon} size={18} />
      </span>
      <span className="stack">
        <strong>{props.title}</strong>
        <span className="muted small">{props.note}</span>
      </span>
    </label>
  )
}

// Design 06 · Request sent
export function Pending() {
  let sent: AccessRequestSent | null = null
  try {
    sent = JSON.parse(sessionStorage.getItem(PENDING_KEY) ?? 'null')
  } catch {
    sent = null
  }
  return (
    <CentredLayout wide>
      <div className="stack gap-20 center-items">
        <div className="pending-clock">
          <Icon name="clock" size={40} color="var(--navy)" strokeWidth={1.8} />
        </div>
        <div className="stack gap-6 center">
          <h1 className="auth-title">Request sent</h1>
          <p className="muted">
            Your Admin will check your details and approve your account.
            <br />
            You can sign in with the password you chose once it is approved.
          </p>
        </div>
        <div className="pending-grid">
          <ol className="pending-steps">
            <li className="is-done">
              <span className="pending-dot">
                <Icon name="check" size={14} strokeWidth={3} />
              </span>
              <span className="stack">
                <strong>Request submitted</strong>
                <span className="muted small">
                  {sent ? new Date(sent.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'Just now'}
                </span>
              </span>
            </li>
            <li className="is-current">
              <span className="pending-dot" />
              <span className="stack">
                <strong>Admin approval</strong>
                <span className="muted small">Your Admin sees it under Users &amp; access</span>
              </span>
            </li>
            <li>
              <span className="pending-dot" />
              <span className="stack">
                <strong>Account ready</strong>
                <span className="muted small">You can sign in once approved</span>
              </span>
            </li>
          </ol>
          {sent && (
            <dl className="pending-details">
              <dt>Name</dt>
              <dd>{sent.full_name}</dd>
              <dt>Username</dt>
              <dd className="mono">{sent.username}</dd>
              <dt>Role requested</dt>
              <dd>{sent.role_label}</dd>
            </dl>
          )}
        </div>
        <a href={links.login} className="btn btn-navy-outline">
          <Icon name="arrowLeft" size={18} strokeWidth={2} />
          Back to sign in
        </a>
      </div>
    </CentredLayout>
  )
}
