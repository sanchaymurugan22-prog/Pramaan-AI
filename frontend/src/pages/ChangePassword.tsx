// Change password, shown on its own (forced) after signing in with a temporary password from the Admin.
// Inside the app, the password is changed on Profile & settings (Stage 9B). Other computers are signed out.
import { useState, type FormEvent } from 'react'
import { changePassword, type User } from '../api'
import { Icon } from '../components/Icon'
import { CentredLayout, FormError, PasswordInput, PasswordStrength } from './auth/AuthLayout'

function PasswordForm({ forced, onDone }: { forced: boolean; onDone: (user: User) => void }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError('The two new passwords are not the same.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const { user } = await changePassword(current, password)
      setCurrent('')
      setPassword('')
      setConfirm('')
      setDone(true)
      onDone(user)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change the password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack gap-20" onSubmit={submit}>
      <span className="auth-card-icon">
        <Icon name="key" size={26} color="var(--navy)" />
      </span>
      <div className="stack gap-6">
        <h1 className="auth-title">{forced ? 'Choose your own password' : 'Change password'}</h1>
        <p className="muted">
          {forced
            ? 'You signed in with a temporary password from your Admin. Choose a new one to continue.'
            : 'Other computers where you are signed in will be signed out.'}
        </p>
      </div>
      {done && !forced && <div className="alert alert-green">Password changed.</div>}
      <FormError message={error} />
      <div className="field">
        <label className="field-label" htmlFor="current-password">
          {forced ? 'Temporary password' : 'Current password'}
        </label>
        <PasswordInput id="current-password" value={current} onChange={setCurrent} autoComplete="current-password" />
      </div>
      <div className="field">
        <label className="field-label" htmlFor="new-password">
          New password
        </label>
        <PasswordInput id="new-password" value={password} onChange={setPassword} autoComplete="new-password" />
      </div>
      <div className="field">
        <label className="field-label" htmlFor="confirm-password">
          Confirm new password
        </label>
        <PasswordInput id="confirm-password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
      </div>
      <PasswordStrength password={password} />
      <button type="submit" className="btn btn-lg btn-navy" disabled={busy}>
        {busy ? 'Saving…' : 'Save new password'}
      </button>
    </form>
  )
}

// After a temporary password: nothing else can be used until it is changed (the backend enforces this too).
export function ForcedPasswordChange({ onDone, onSignOut }: { onDone: (user: User) => void; onSignOut: () => void }) {
  return (
    <CentredLayout>
      <PasswordForm forced onDone={onDone} />
      <button type="button" className="btn btn-link center-self" onClick={onSignOut}>
        Sign out
      </button>
    </CentredLayout>
  )
}
