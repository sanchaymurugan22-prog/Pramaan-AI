import { useEffect, useState } from 'react'
import { checkAlert, createAlert, previewAlert, type AlertCheck, type AlertPreview } from '../api'
import { Icon } from '../components/Icon'
import { LanguagePicker } from '../components/LanguagePicker'
import { Toggle } from '../components/Toggle'
import { useLanguages } from '../languages'
import { links, navigate } from '../router'
import { t } from '../i18n'

// Design "22 · Emergency alert". The operator writes a short public alert; the app checks it (no panic
// wording, no private data, SMS length) as they type. "Send for fast-track approval" makes a TLP:CLEAR
// job whose source is this message, the AI writes the public outputs, and the job goes to the Reviewers
// by itself, first in their queue. Nothing is published until a Reviewer approves and signs it.
// (backend/app/routes/alerts.py) Stage 8: the alert in every chosen language (IndicTrans2, on this computer), each
// within the SMS length (160 characters in English, 70 in Indian scripts), with a voice announcement where a voice
// exists. The SMS itself is an output of the job: translated, checked, ticked by a native speaker and signed.

const TYPES = ['Cyber fraud', 'Flood', 'Cyclone', 'Heatwave', 'Health', 'Other']
const SEVERITIES = ['Advisory', 'Warning', 'Emergency']
const OUTPUTS = [
  { key: 'x_thread', label: 'X thread' },
  { key: 'infographic', label: 'Infographic (poster)' },
  { key: 'linkedin_post', label: 'LinkedIn post' },
]
const SMS = 160

export function EmergencyAlert() {
  const [type, setType] = useState('Cyber fraud')
  const [severity, setSeverity] = useState('Warning')
  const [area, setArea] = useState('All states and union territories')
  const [message, setMessage] = useState('')
  const [outputs, setOutputs] = useState(['x_thread', 'infographic'])
  const [check, setCheck] = useState<AlertCheck | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const info = useLanguages()
  const [chosen, setChosen] = useState<string[] | null>(null) // null: every language (the default)
  const allIndian = info?.languages.filter((l) => l.code !== 'en').map((l) => l.code) ?? []
  const languages = info?.translation.ready ? (chosen ?? allIndian) : []
  const [voice, setVoice] = useState(true)
  const [preview, setPreview] = useState<AlertPreview[] | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const voices = info?.languages.filter((l) => l.voice).map((l) => l.native) ?? []

  async function showPreview() {
    setPreviewing(true)
    setError('')
    try {
      setPreview((await previewAlert(message, languages)).languages)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not translate the preview."))
    } finally {
      setPreviewing(false)
    }
  }

  // The public-release check, a moment after typing stops
  useEffect(() => {
    if (message.trim().length < 5) {
      setCheck(null)
      return
    }
    const timer = window.setTimeout(() => {
      checkAlert(message)
        .then(setCheck)
        .catch(() => setCheck(null))
    }, 400)
    return () => window.clearTimeout(timer)
  }, [message])

  const chars = message.trim().length
  const tooShort = chars < 20
  const ready = !tooShort && check?.ok && outputs.length > 0 && chars <= (check?.max_chars ?? 480)

  async function send() {
    setSending(true)
    setError('')
    try {
      const job = await createAlert({ type, severity, area, message, outputs, languages, voice })
      navigate(links.progress(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not send the alert."))
      setSending(false)
    }
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-red">{t("Emergency mode")}</div>
          <h1>{t("Urgent public alert")}</h1>
          <p className="muted page-lead">{t("Short alerts in all 22 languages with voice announcements. Goes to fast-track review.")}</p>
        </div>
        <div className="grow" />
        <span className="chip chip-red">
          <Icon name="bolt" size={14} strokeWidth={2.2} />
          {t("Fast-track review")}
        </span>
        <a className="btn btn-outline" href={links.dashboard}>
          {t("Cancel")}
        </a>
      </div>

      <div className="alert-grid">
        <section className="card card-pad stack gap-16" aria-labelledby="write-title">
          <h2 id="write-title">{t("Write the alert")}</h2>

          <fieldset className="fieldset">
            <legend className="field-label">{t("Alert type")}</legend>
            <div className="row gap-8 wrap">
              {TYPES.map((kind) => (
                <label key={kind} className={type === kind ? 'pill pill-red is-on' : 'pill'}>
                  <input type="radio" name="alert-type" className="sr-only" checked={type === kind} onChange={() => setType(kind)} />
                  {type === kind && <Icon name="check" size={16} strokeWidth={2.4} />}
                  {t(kind)}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="alert-row">
            <fieldset className="fieldset">
              <legend className="field-label">{t("Severity")}</legend>
              <div className="segmented">
                {SEVERITIES.map((s) => (
                  <label key={s} className={severity === s ? 'segment is-on is-red' : 'segment'}>
                    <input type="radio" name="severity" className="sr-only" checked={severity === s} onChange={() => setSeverity(s)} />
                    {t(s)}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="field grow">
              <label className="field-label" htmlFor="alert-area">{t("Area")}</label>
              <input id="alert-area" className="input" value={area} onChange={(e) => setArea(e.target.value)} maxLength={120} />
            </div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="alert-message">{t("Message in English")}</label>
            <textarea
              id="alert-message"
              className="input textarea"
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t("Cyber alert: Do not open unknown links about hospital bills. Report fraud by calling 1930.")}
              aria-describedby="alert-count alert-tip"
            />
            <div className="row gap-10 wrap">
              <span id="alert-count" className={chars > SMS ? 'small over-limit' : 'small count-ok'} aria-live="polite">
                {t("{chars} / {SMS} characters · {value}", { chars: chars, SMS: SMS, value: chars <= SMS ? t("fits one SMS") : t("{n} SMS parts", { n: check?.sms_parts ?? Math.ceil(chars / 153) }) })}</span>
              <div className="grow" />
              <span id="alert-tip" className="muted small">{t("Plain words, no panic. Name the helpline (1930 for cyber fraud).")}</span>
            </div>
          </div>

          <fieldset className="fieldset">
            <legend className="field-label">{t("Outputs to prepare")}</legend>
            <div className="row gap-8 wrap">
              {OUTPUTS.map((o) => (
                <label key={o.key} className="check-pill">
                  <input
                    type="checkbox"
                    checked={outputs.includes(o.key)}
                    onChange={() => setOutputs((now) => (now.includes(o.key) ? now.filter((k) => k !== o.key) : [...now, o.key]))}
                  />
                  {t(o.label)}
                </label>
              ))}
            </div>
          </fieldset>

          <LanguagePicker
            info={info}
            selected={languages}
            onChange={(codes) => {
              setChosen(codes)
              setPreview(null)
            }}
            label={t("Languages")}
            showVoices
          />
          <Toggle
            label={t("Add voice announcement")}
            detail={
              voices.length
                ? t("Indian voices on this computer: {n}. Other languages: text only.", { n: voices.join(', ') })
                : t("No voices on this computer: text only.")
            }
            on={voice}
            onChange={setVoice}
          />
          <div className="toggle-row">
            <span className="stack gap-1 grow">
              <span className="toggle-label">{t("QR code for verification")}</span>
              <span className="toggle-detail">{t("Added to every file when a Reviewer signs it")}</span>
            </span>
            <span className="chip chip-green">
              <Icon name="check" size={14} strokeWidth={2.4} />
              {t("Always")}
            </span>
          </div>

          <PublicCheck check={check} tooShort={tooShort} empty={chars === 0} />
        </section>

        <section className="card card-pad stack gap-14 preview-card" aria-labelledby="preview-title">
          <div className="row gap-10 wrap">
            <h2 id="preview-title">{t("Preview in every language")}</h2>
            <div className="grow" />
            <span className="chip chip-neutral">
              {preview ? t("{n} of {n2} ready", { n: preview.length + 1, n2: languages.length + 1 }) : t("English · {length} more to translate", { length: languages.length })}
            </span>
          </div>
          <article className="lang-card" lang="en">
            <div className="row gap-8">
              <strong className="lang-name">{t("English")}</strong>
              <span className="muted small">{type} · {severity} · {area}</span>
            </div>
            <p className="lang-text">{message.trim() || t("Your message appears here as people will read it.")}</p>
          </article>
          {languages.length > 0 && (
            <button type="button" className="btn btn-outline" onClick={showPreview} disabled={previewing || chars < 20}>
              <Icon name="globe" size={18} strokeWidth={2} />
              {previewing ? t("Translating…") : preview ? t("Translate the preview again") : t("Show it in {length} languages", { length: languages.length })}
            </button>
          )}
          {preview && (
            <div className="stack gap-10 lang-cards" aria-live="polite">
              {preview.map((p) => (
                <article key={p.code} className="lang-card" lang={p.code} dir={p.rtl ? 'rtl' : undefined}>
                  <div className="row gap-8 wrap" dir="ltr">
                    <strong className="lang-name">{p.native}</strong>
                    <span className="muted small" lang="en">
                      {p.name}
                    </span>
                    <div className="grow" />
                    <span className={p.sms_parts > 1 ? 'small over-limit' : 'small count-ok'} lang="en">
                      {p.chars} / {p.limit} · {p.sms_parts === 1 ? t("one SMS") : `${p.sms_parts} SMS`}
                    </span>
                    {voice &&
                      (p.voice ? (
                        <span className="chip chip-green chip-xs" title={`Voice: ${p.voice}`} lang="en">
                          <Icon name="volume" size={12} />
                          {t("Voice")}
                        </span>
                      ) : (
                        <span className="chip chip-neutral chip-xs" lang="en">
                          {t("Text only")}
                        </span>
                      ))}
                  </div>
                  <p className="lang-text">{p.text}</p>
                  {p.changed.length > 0 && (
                    <span className="small over-limit" dir="ltr" lang="en">
                      {t("Changed in translation: {value}. Check it before sending.", { value: p.changed.join(', ') })}</span>
                  )}
                </article>
              ))}
            </div>
          )}
          <p className="muted small">
            {t("Machine translated on this computer (IndicTrans2). A Reviewer ticks “Checked by a native speaker” for every language before the alert can be signed.")}
          </p>
        </section>
      </div>

      {error && <div className="alert alert-red" role="alert">{error}</div>}

      <section className="send-bar" aria-label={t("Send")}>
        <Icon name="bolt" size={22} color="var(--red-dark)" />
        <span className="grow">{t("Any on-duty Reviewer can approve this within minutes. Nothing is sent until it is signed.")}</span>
        <button type="button" className="btn btn-lg btn-red" onClick={send} disabled={!ready || sending}>
          {sending ? t("Sending…") : t("Send for fast-track approval")}
          <Icon name="send" size={18} strokeWidth={2} />
        </button>
      </section>
    </main>
  )
}

function PublicCheck({ check, tooShort, empty }: { check: AlertCheck | null; tooShort: boolean; empty: boolean }) {
  if (empty) return null
  if (tooShort || !check) {
    return <p className="muted small">{t("The public-release check runs when the message is at least 20 characters.")}</p>
  }
  if (check.ok) {
    return (
      <div className="check-row" role="status">
        <span className="check-dot check-ok" aria-hidden="true">
          <Icon name="check" size={16} strokeWidth={2.4} />
        </span>
        <span className="stack gap-1">
          <span className="check-title">{t("Public-release safety check passed")}</span>
          <span className="check-detail">{t("No panic wording, no shouting, no private data")}</span>
        </span>
      </div>
    )
  }
  return (
    <div className="alert alert-red stack gap-6" role="alert">
      <strong className="row gap-8">
        <Icon name="warning" size={18} strokeWidth={2.2} />
        {t("Public-release check: change the message before sending")}
      </strong>
      <ul className="clean-list">
        {check.problems.map((p, i) => (
          <li key={i}>
            {t(p.label)}: “{p.text}”
          </li>
        ))}
      </ul>
    </div>
  )
}
