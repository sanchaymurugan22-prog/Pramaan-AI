// "Is this real?" inside the app: paste a forwarded message and see whether it matches a signed record,
// was changed, or shows signs of a scam. The same check as the public verify page, on the same published
// data (backend/app/signing/messages.py). The message is not stored or logged.
import { useState, type FormEvent } from 'react'
import { checkMessage, type MessageCheck } from '../api'
import { Icon, type IconName } from '../components/Icon'
import { t } from '../i18n'

const VERDICTS: Record<MessageCheck['verdict'], { tone: string; icon: IconName; title: string; text: (r: MessageCheck) => string }> = {
  genuine: { tone: 'genuine', icon: 'check', title: 'Genuine', text: (r) => `This message matches signed record ${r.record_no} exactly.` },
  replaced: {
    tone: 'warn',
    icon: 'warning',
    title: 'Genuine, but outdated',
    text: (r) => `This matches record ${r.record_no}, but a newer version was issued: ${r.replaced_by}.`,
  },
  withdrawn: {
    tone: 'bad',
    icon: 'cross',
    title: 'Withdrawn',
    text: (r) => `This matches record ${r.record_no}, which was withdrawn. Do not rely on it or share it.`,
  },
  changed: {
    tone: 'warn',
    icon: 'warning',
    title: 'Changed',
    text: (r) => `This looks like record ${r.record_no} (${Math.round((r.similarity ?? 0) * 100)}% alike), but it was changed.`,
  },
  scam: { tone: 'bad', icon: 'cross', title: 'Not genuine', text: () => 'No signed record matches, and it shows signs of a scam. Do not click, call or reply.' },
  not_found: { tone: 'unknown', icon: 'search', title: 'Not found', text: () => 'No signed record matches this message. Treat it as unverified.' },
}

export function IsThisReal() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<MessageCheck | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setResult(await checkMessage(text))
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not check the message."))
    } finally {
      setBusy(false)
    }
  }

  const look = result ? VERDICTS[result.verdict] : null
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-4">
          <div className="eyebrow">{t("Is this real?")}</div>
          <h1>{t("Check a forwarded message")}</h1>
          <p className="muted">
            {t("Paste a message from WhatsApp, SMS or email. It is compared with the signed records (spaces, capitals, punctuation and emojis do not matter) and checked for signs of a scam. It is not stored.")}
          </p>
        </div>
      </div>
      <div className="check-grid">
        <form className="card card-pad stack gap-14" onSubmit={submit}>
          <label className="field">
            <span className="field-label">{t("Message you received")}</span>
            <textarea className="input textarea" rows={8} value={text} onChange={(e) => setText(e.target.value)} required />
          </label>
          {error && <div className="alert alert-red">{error}</div>}
          <button type="submit" className="btn btn-navy" disabled={busy || !text.trim()}>
            <Icon name="shieldCheck" size={18} strokeWidth={2} />
            {busy ? t("Checking…") : t("Check message")}
          </button>
        </form>

        {result && look && (
          <section className="stack gap-14" aria-live="polite">
            <div className={`check-result check-${look.tone}`}>
              <span className="check-result-icon">
                <Icon name={look.icon} size={28} strokeWidth={2.6} color="#fff" />
              </span>
              <span className="stack gap-2">
                <strong>{t(look.title)}</strong>
                <span>{look.text(result)}</span>
              </span>
            </div>
            {result.title && (
              <p className="muted small">
                {t("Record {record_no}: {title}", { record_no: result.record_no, title: t(result.title) })}</p>
            )}
            {result.diff && (
              <section className="card card-pad stack gap-8">
                <h2>{t("What was changed")}</h2>
                <p className="message-diff">
                  {result.diff.map((d, i) => (
                    <span key={i} className={d.kind === 'same' ? undefined : `diff-${d.kind}`}>
                      {d.text}{' '}
                    </span>
                  ))}
                </p>
                <span className="muted small">
                  <span className="diff-added">{t("red")}</span> {t("= added or changed in the message ·")} <span className="diff-removed">{t("green")}</span> {t("= in the record but missing from the message")}
                </span>
              </section>
            )}
            {result.signs.length > 0 && (
              <section className="card card-pad stack gap-10">
                <h2>{t("Signs of a scam")}</h2>
                <ul className="sign-list">
                  {result.signs.map((s) => (
                    <li key={s.kind}>
                      <Icon name="cross" size={16} strokeWidth={2.6} color="var(--red-dark)" />
                      <span>
                        <strong>{t(s.label)}:</strong> {t(s.detail)}
                        {s.note ? ` (${s.note})` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <div className="alert alert-red row gap-8">
              <Icon name="phone" size={18} />
              {result.helpline}
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
