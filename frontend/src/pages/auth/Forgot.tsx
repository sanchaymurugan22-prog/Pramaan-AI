// Design 05 · Reset your password. Offline, so there is no email: the request goes to the Admin,
// who checks who you are in person and gives you a one-time password (changed at the next sign-in).
// (Recovery codes come later.)
import { useState, type FormEvent } from 'react'
import { forgotPassword } from '../../api'
import { Icon, type IconName } from '../../components/Icon'
import { links } from '../../router'
import { CentredLayout, FormError } from './AuthLayout'
import { t } from '../../i18n'

const STEPS: { icon: IconName; tone: string; text: string }[] = [
  { icon: 'send', tone: 'saffron', text: 'You send a reset request' },
  { icon: 'shieldCheck', tone: 'green', text: 'Your Admin verifies you in person' },
  { icon: 'key', tone: 'navy', text: 'You get a one-time password' },
]

export function Forgot() {
  const [username, setUsername] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setSent((await forgotPassword(username, message)).message)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not send the request."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <CentredLayout>
      <form className="stack gap-20" onSubmit={submit}>
        <span className="auth-card-icon">
          <Icon name="key" size={26} color="var(--saffron-dark)" />
        </span>
        <div className="stack gap-6">
          <h1 className="auth-title">{t("Reset your password")}</h1>
          <p className="muted">{t("Pramaan AI works offline, so passwords are reset by your Admin.")}</p>
        </div>
        {sent ? (
          <div className="alert alert-green" role="status">
            <strong>{t("Request sent.")}</strong> {sent.replace(/^Request sent\.\s*/, '')}
          </div>
        ) : (
          <>
            <FormError message={error} />
            <label className="field">
              <span className="field-label">{t("Username or employee ID")}</span>
              <span className="input-with-icon">
                <Icon name="user" size={18} color="var(--icon)" />
                <input
                  className="input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  required
                  autoFocus
                />
              </span>
            </label>
            <label className="field">
              <span className="field-label">{t("Message to Admin (optional)")}</span>
              <textarea className="input textarea" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
            </label>
            <button type="submit" className="btn btn-lg btn-navy" disabled={busy}>
              {busy ? t("Sending…") : t("Send request to Admin")}
              <Icon name="send" size={18} strokeWidth={2} />
            </button>
          </>
        )}
        <div className="forgot-steps">
          {STEPS.map((s) => (
            <div key={s.text} className="stack gap-8 center-items">
              <span className={`forgot-step-icon tone-${s.tone}`}>
                <Icon name={s.icon} size={18} />
              </span>
              <span className="muted small center">{s.text}</span>
            </div>
          ))}
        </div>
        <a href={links.login} className="row gap-6 center-self">
          <Icon name="arrowLeft" size={16} strokeWidth={2} />
          {t("Back to sign in")}
        </a>
      </form>
    </CentredLayout>
  )
}
