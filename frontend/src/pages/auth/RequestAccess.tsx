// Design 04 · Request access, and design 06 · Request sent (pending).
// The Admin approves or rejects the request (Users & access → Access requests).
import { useEffect, useState, type FormEvent } from 'react'
import { getFormOptions, requestAccess, type AccessRequestSent, type FormOptions } from '../../api'
import { storedLanguage } from '../../localPrefs'
import { Icon } from '../../components/Icon'
import { links, navigate } from '../../router'
import { CentredLayout, FormError, PasswordInput, PasswordStrength, SplitLayout } from './AuthLayout'

const PENDING_KEY = 'pramaan.pendingRequest' // name, username and role only (nothing secret)

export function RequestAccess() {
  const [form, setForm] = useState({
    full_name: '', employee_id: '', email: '', division: 'Cyber operations', language: storedLanguage() ?? 'en',
    reason: '', role: 'operator' as 'operator' | 'reviewer',
  })
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [options, setOptions] = useState<FormOptions | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  useEffect(() => {
    getFormOptions()
      .then(setOptions)
      .catch(() => setOptions({ languages: [{ code: 'en', name: 'English' }], divisions: ['Other'] }))
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError('The two passwords are not the same.')
      return
    }
    if (!agreed) {
      setError('Please agree to the acceptable-use policy for official content.')
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
            <span className="field-label">Employee ID</span>
            <input
              className="input"
              value={form.employee_id}
              onChange={(e) => set('employee_id')(e.target.value)}
              autoCapitalize="characters"
              spellCheck={false}
              placeholder="e.g. EMP-20417"
              required
            />
          </label>
          <label className="field">
            <span className="field-label">Official email</span>
            <input
              className="input"
              type="email"
              value={form.email}
              onChange={(e) => set('email')(e.target.value)}
              autoComplete="email"
              placeholder="name@org.gov.in"
              required
            />
          </label>
          <label className="field">
            <span className="field-label">Division</span>
            <select className="input" value={form.division} onChange={(e) => set('division')(e.target.value)}>
              {(options?.divisions ?? [form.division]).map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
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
        <div className="form-grid-2">
          <label className="field">
            <span className="field-label">Preferred language</span>
            <select className="input" value={form.language} onChange={(e) => set('language')(e.target.value)}>
              {(options?.languages ?? [{ code: 'en', name: 'English' }]).map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Why do you need access? (optional)</span>
            <input
              className="input"
              value={form.reason}
              onChange={(e) => set('reason')(e.target.value)}
              placeholder="e.g. I write advisories"
            />
          </label>
        </div>
        <label className="row gap-10 agree">
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />I agree to
          the acceptable-use policy for official content
        </label>
        <button type="submit" className="btn btn-lg btn-saffron" disabled={busy}>
          {busy ? 'Sending…' : 'Request access'}
          <Icon name="send" size={18} strokeWidth={2} />
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
            This usually happens within the working day. Then sign in with the password you chose.
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
                <span className="muted small">
                  {sent?.admins?.length ? `${sent.admins.join(', ')} (Admin) can approve it` : 'Your Admin sees it under Users & access'}
                </span>
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
              {sent.employee_id && (
                <>
                  <dt>Employee ID</dt>
                  <dd className="mono">{sent.employee_id}</dd>
                </>
              )}
              <dt>Role requested</dt>
              <dd>{sent.role_label}</dd>
              {sent.division && (
                <>
                  <dt>Division</dt>
                  <dd>{sent.division}</dd>
                </>
              )}
              <dt>Sign in with</dt>
              <dd className="mono">{sent.employee_id ?? sent.username}</dd>
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
