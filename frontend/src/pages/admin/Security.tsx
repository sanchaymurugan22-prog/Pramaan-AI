// Design 36 · Security and policies (Stage 9B). The switches here really change what the app does
// (backend/app/app_settings.py): which private data the scanner looks for, extra classification words,
// sign-out after inactivity, and lockout after wrong passwords. Every change goes into the audit trail.
import { useEffect, useState } from 'react'
import { getSecurity, saveSecurity, isWebMode, type SecurityChange, type SecurityState } from '../../api'
import { Icon, type IconName } from '../../components/Icon'
import { TlpLabel } from '../../components/TlpLabel'
import { Toggle } from '../../components/Toggle'
import { t } from '../../i18n'

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

export function Security() {
  const [state, setState] = useState<SecurityState | null>(null)
  const [draft, setDraft] = useState<SecurityChange>({})
  const [newWord, setNewWord] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getSecurity()
      .then(setState)
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the security settings.")))
  }, [])

  if (!state) return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>

  // What is on screen: the saved state with the unsaved changes on top
  const scannerOn = (key: string) => draft.scanner?.[key] ?? state.scanner.find((s) => s.key === key)!.on
  const words = draft.classification_words ?? state.classification_words
  const idle = draft.idle_minutes ?? state.idle_minutes
  const lock = draft.lock_after ?? state.lock_after
  const changed = Object.keys(draft).length > 0
  const switchedOff = state.scanner.filter((s) => !scannerOn(s.key))

  async function save() {
    if (switchedOff.length && !window.confirm(t("Private data of these kinds will NOT be found any more: {n}. Continue?", { n: switchedOff.map((s) => s.label).join(', ') }))) return
    setError('')
    try {
      setState(await saveSecurity(draft))
      setDraft({})
      setMessage(t("Saved. The change is in the audit trail."))
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not save."))
    }
  }

  function addWord() {
    const word = newWord.trim().toUpperCase()
    if (word && !words.includes(word)) setDraft((d) => ({ ...d, classification_words: [...words, word] }))
    setNewWord('')
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-navy">{t("Admin")}</div>
          <h1>{t("Security & policies")}</h1>
          <p className="muted page-lead">{t("Rules that protect sensitive information. Changes are recorded in the audit trail.")}</p>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-navy" onClick={save} disabled={!changed}>
          <Icon name="check" size={18} strokeWidth={2.4} />
          {t("Save changes")}
        </button>
      </div>
      {error && <div className="alert alert-red" role="alert">{error}</div>}
      <p className="sr-only" role="status">{message}</p>
      {message && !changed && <div className="alert alert-green">{message}</div>}
      {changed && <div className="alert alert-yellow">{t("You have unsaved changes.")}</div>}

      <div className="admin-two">
        <div className="stack gap-20">
          <section className="card card-pad stack gap-14" aria-label={t("Sensitive information scanner")}>
            <CardHead icon="eyeOff" tone="saffron" title={t("Sensitive information scanner")} />
            <p className="muted small">{t("What the Safety check looks for in every source before any AI reads it.")}</p>
            <div className="toggle-grid">
              {state.scanner.map((s) => (
                <Toggle
                  key={s.key}
                  label={t(s.label)}
                  on={scannerOn(s.key)}
                  onChange={(on) => setDraft((d) => ({ ...d, scanner: { ...(d.scanner ?? {}), [s.key]: on } }))}
                />
              ))}
            </div>
            {switchedOff.length > 0 && (
              <div className="alert alert-yellow small">
                {t("Switched off: {value}. These will not be found or hidden.", { value: switchedOff.map((s) => s.label).join(', ') })}</div>
            )}
            <h3 className="field-label">{t("Classification words")}</h3>
            <div className="row gap-8 wrap">
              {state.built_in_words.map((w) => (
                <span key={w} className="word-chip is-fixed" title={t("Built in: always found")}>
                  {w}
                </span>
              ))}
              {words.map((w) => (
                <span key={w} className="word-chip">
                  {w}
                  <button
                    type="button"
                    aria-label={t("Remove {w}", { w: w })}
                    onClick={() => setDraft((d) => ({ ...d, classification_words: words.filter((x) => x !== w) }))}
                  >
                    <Icon name="cross" size={12} strokeWidth={2.6} />
                  </button>
                </span>
              ))}
            </div>
            <div className="row gap-8">
              <label className="sr-only" htmlFor="new-word">
                {t("Add a classification word")}
              </label>
              <input
                id="new-word"
                className="input grow"
                value={newWord}
                onChange={(e) => setNewWord(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addWord()}
                placeholder={t("e.g. INTERNAL ONLY")}
                maxLength={40}
              />
              <button type="button" className="btn btn-outline" onClick={addWord} disabled={!newWord.trim()}>
                <Icon name="plus" size={16} strokeWidth={2} />
                {t("Add word")}
              </button>
            </div>
          </section>

          <section className="card card-pad stack gap-12" aria-label={t("Hidden-instruction shield")}>
            <CardHead icon="shield" tone="red" title={t("Hidden-instruction shield")} />
            <p className="muted small">
              {t("Always on: text inside uploaded files that tries to give the AI orders, hidden characters and hidden text are found, shown to the operator, and removed from what the AI reads unless the operator keeps them.")}
            </p>
          </section>

          <section className="card card-pad stack gap-12" aria-label={t("Signing certificates")}>
            <CardHead icon="usb" tone="green" title={t("Signing")} />
            <dl className="facts-table">
              <div>
                <dt>{t("Signing key in use")}</dt>
                <dd>{state.signer.error ? <span className="over-limit">{state.signer.error}</span> : state.signer.label}</dd>
              </div>
              {state.signer.key_id && (
                <div>
                  <dt>{t("Key fingerprint")}</dt>
                  <dd className="mono">{state.signer.key_id}</dd>
                </div>
              )}
              {state.reviewers.map((r) => (
                <div key={r.name}>
                  <dt>{t("{name} · Reviewer", { name: r.name })}</dt>
                  <dd>{r.dsc_holder ? t("Holds a Class 3 DSC token") : t("No DSC token")}</dd>
                </div>
              ))}
            </dl>
            <p className="muted small">{t("The public key is shared with the verify page so anyone can check documents offline. SIGNER in .env picks the key.")}</p>
          </section>
        </div>

        <div className="stack gap-20">
          <section className="card card-pad stack gap-12" aria-label={t("Sharing rules (TLP)")}>
            <CardHead icon="summary" tone="navy" title={t("Sharing rules (TLP)")} />
            <div className="table-scroll">
              <table className="data-table">
                <caption className="sr-only">{t("What each sharing label allows")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("Level")}</th>
                    <th scope="col">{t("Internal documents")}</th>
                    <th scope="col">{t("Public posts, infographic, video")}</th>
                  </tr>
                </thead>
                <tbody>
                  {state.tlp.map((level_) => (
                    <tr key={level_.level}>
                      <td>
                        <TlpLabel tlp={level_.level} />
                      </td>
                      <td>
                        <span className="chip chip-green chip-xs">{t("Allowed")}</span>
                      </td>
                      <td>
                        {level_.public_allowed ? (
                          <span className={level_.level === 'CLEAR' ? 'chip chip-green chip-xs' : 'chip chip-saffron chip-xs'}>
                            {level_.level === 'CLEAR' ? t("Allowed") : t("Details hidden")}
                          </span>
                        ) : (
                          <span className="chip chip-red chip-xs">{t("Blocked")}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card card-pad stack gap-12" aria-label={t("Encryption and storage")}>
            <CardHead icon="lock" tone="green" title={t("Encryption and storage")} />
            <ul className="clean-list-plain stack gap-10">
              <li className="check-row">
                <span className={state.encryption.database ? 'check-dot check-ok' : 'check-dot check-bad'} aria-hidden="true">
                  <Icon name={state.encryption.database ? 'check' : 'cross'} size={16} strokeWidth={2.4} />
                </span>
                <span className="stack">
                  <span className="check-title">{t("Database {value}", { value: state.encryption.database ? t("encrypted") : t("NOT encrypted") })}</span>
                  <span className="check-detail">{t("SQLCipher · AES-256")}</span>
                </span>
              </li>
              <li className="check-row">
                <span className="check-dot check-ok" aria-hidden="true">
                  <Icon name="check" size={16} strokeWidth={2.4} />
                </span>
                <span className="stack">
                  <span className="check-title">{t("Uploaded and generated files encrypted")}</span>
                  <span className="check-detail">{t("AES-256-GCM · key in {key_place}", { key_place: state.encryption.key_place })}</span>
                </span>
              </li>
            </ul>
          </section>

          <section className="card card-pad stack gap-12" aria-label={t("Sign-in and sessions")}>
            <CardHead icon="clock" tone="navy" title={t("Sign-in and sessions")} />
            <div className="form-grid-2">
              <label className="field">
                <span className="field-label">{t("Sign out after inactivity")}</span>
                <select className="input" value={idle} onChange={(e) => setDraft((d) => ({ ...d, idle_minutes: Number(e.target.value) }))}>
                  {state.idle_choices.map((m) => (
                    <option key={m} value={m}>
                      {t("{m} minutes", { m: m })}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">{t("Lock account after")}</span>
                <select className="input" value={lock} onChange={(e) => setDraft((d) => ({ ...d, lock_after: Number(e.target.value) }))}>
                  {state.lock_choices.map((n) => (
                    <option key={n} value={n}>
                      {t("{n} failed sign-ins", { n: n })}</option>
                  ))}
                </select>
              </label>
            </div>
            <p className="row gap-8 small count-ok">
              <Icon name={isWebMode ? "wifi" : "wifiOff"} size={16} />
              {isWebMode
                ? t("Every session also ends after {hours} hours. Secured via Sarvam Cloud backend.", { hours: state.max_session_hours })
                : t("Every session also ends after {hours} hours. Internet access: offline only.", { hours: state.max_session_hours })}
            </p>
          </section>
        </div>
      </div>
    </main>
  )
}
