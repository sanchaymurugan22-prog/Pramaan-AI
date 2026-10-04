// Design 03 · Sign in. Username + password; the backend sets an HttpOnly session cookie.
// Stage 9B: the username, the employee ID or the official email can be typed in the same box.
import { useState, type FormEvent } from 'react'
import { signIn, type User } from '../../api'
import { Icon } from '../../components/Icon'
import { links } from '../../router'
import { FormError, PasswordInput, SplitLayout } from './AuthLayout'
import { t } from '../../i18n'

export function SignIn({ notice, onSignedIn }: { notice: string; onSignedIn: (user: User) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { user } = await signIn(username, password)
      setPassword('')
      onSignedIn(user)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not sign in."))
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SplitLayout tone="saffron">
      <form className="auth-form" onSubmit={submit}>
        <div className="stack gap-6">
          <h1 className="auth-title">{t("Welcome back")}</h1>
          <p className="muted">{t("Sign in with the account your Admin created for you.")}</p>
        </div>
        <div style={{
          background: 'var(--saffron-light, #FFF4E8)',
          border: '1px solid var(--saffron-mid, #FFDDB8)',
          borderRadius: '12px',
          padding: '14px 16px',
          margin: '12px 0'
        }}>
          <div style={{ fontWeight: 600, color: 'var(--saffron-dark, #A34A00)', marginBottom: '4px', fontSize: '0.92rem' }}>
            🏛️ SIH Judge Evaluation Demo Access
          </div>
          <p style={{ fontSize: '0.83rem', color: 'var(--ink, #1B1D26)', marginBottom: '10px', lineHeight: 1.4 }}>
            Select a role to auto-fill credentials:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-sm btn-navy"
              style={{ padding: '6px 10px', fontSize: '0.8rem', height: 'auto', minHeight: '34px', justifyContent: 'center' }}
              onClick={() => { setUsername('admin'); setPassword('AdminPassword123!'); }}
            >
              Fill Admin
            </button>
            <button
              type="button"
              className="btn btn-sm btn-saffron"
              style={{ padding: '6px 10px', fontSize: '0.8rem', height: 'auto', minHeight: '34px', justifyContent: 'center' }}
              onClick={() => { setUsername('operator'); setPassword('OperatorPassword123!'); }}
            >
              Fill Operator
            </button>
            <button
              type="button"
              className="btn btn-sm btn-green"
              style={{ padding: '6px 10px', fontSize: '0.8rem', height: 'auto', minHeight: '34px', justifyContent: 'center' }}
              onClick={() => { setUsername('reviewer.demo'); setPassword('ReviewerPassword123!'); }}
            >
              Fill Reviewer
            </button>
          </div>
        </div>
        {notice && !error && (
          <div className="hint" role="status">
            {notice}
          </div>
        )}
        <FormError message={error} />
        <label className="field">
          <span className="field-label">{t("Username, employee ID or official email")}</span>
          <span className="input-with-icon">
            <Icon name="user" size={18} color="var(--icon)" />
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              placeholder={t("e.g. priya.sharma or EMP-20311")}
              required
              autoFocus
            />
          </span>
        </label>
        <div className="field">
          <div className="row">
            <label className="field-label" htmlFor="password">
              {t("Password")}
            </label>
            <div className="grow" />
            <a href={links.forgot} className="small">
              {t("Forgot password?")}
            </a>
          </div>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </div>
        <button type="submit" className="btn btn-lg btn-navy" disabled={busy}>
          {busy ? t("Signing in…") : t("Sign in")}
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </button>
        <p className="muted center">
          <a href={links.language} className="small">
            {t("Language: change")}
          </a>
        </p>
        <p className="muted center">
          {t("New to Pramaan AI?")} <a href={links.requestAccess} className="link-saffron">{t("Request access")}</a>
        </p>
        <p className="row gap-8 secure-note">
          <Icon name="bolt" size={16} color="var(--saffron-dark)" />
          {t("Online · Sarvam AI | Secure web application")}
        </p>
      </form>
    </SplitLayout>
  )
}
