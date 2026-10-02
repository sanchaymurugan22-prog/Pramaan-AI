// Design 26 · Sign (dialog). Opened by "Approve & sign". Shows which key signs and how many files;
// a DSC token would also ask for its PIN (SIGNER=dsc, design only). The backend signs on approve.
import { useEffect, useState } from 'react'
import { getSignInfo, reviewJob, type JobDetail, type SignInfo } from '../api'
import { Icon } from '../components/Icon'
import { t } from '../i18n'

type Props = { job: JobDetail; notes: string; onClose: () => void; onSigned: (job: JobDetail) => void }

export function SignDialog({ job, notes, onClose, onSigned }: Props) {
  const [info, setInfo] = useState<SignInfo | null>(null)
  const [pin, setPin] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getSignInfo(job.id)
      .then(setInfo)
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not prepare signing.")))
  }, [job.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, busy])

  async function sign() {
    setBusy(true)
    setError('')
    try {
      const signed = await reviewJob(job.id, 'approve', notes, pin)
      setPin('')
      onSigned(signed)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not sign."))
    } finally {
      setBusy(false)
    }
  }

  const isTest = info?.signer.kind === 'test'
  return (
    <div className="dialog-backdrop" onClick={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <section className="card dialog" role="dialog" aria-modal="true" aria-labelledby="sign-title">
        <div className="row gap-14">
          <span className="setup-card-icon sign-icon">
            <Icon name="key" size={22} color="var(--green-dark)" />
          </span>
          <div className="stack gap-2 grow">
            <h2 id="sign-title">{isTest ? t("Sign with the test key") : t("Sign with your DSC token")}</h2>
            <span className="muted small">{t("Your signature seals every file so no one can change it unnoticed.")}</span>
          </div>
          <button type="button" className="icon-btn icon-btn-sm" aria-label={t("Close")} onClick={onClose} disabled={busy}>
            <Icon name="cross" size={18} />
          </button>
        </div>

        {info && (
          <>
            <div className={info.signer.error ? 'signer-box signer-box-bad' : 'signer-box'}>
              <Icon name={info.signer.error ? 'warning' : 'shieldCheck'} size={20} />
              <span className="stack grow">
                <strong>{t(info.signer.label)}</strong>
                <span className="small">
                  {info.signer.error ??
                    (isTest
                      ? t("For development and the demo: made on this computer, stored encrypted. Not a legal DSC.")
                      : t("Certificate read from the token."))}
                </span>
              </span>
              {!info.signer.error && (
                <span className="chip chip-green chip-xs">
                  <Icon name="check" size={12} strokeWidth={2.4} />
                  {t("Ready")}
                </span>
              )}
            </div>
            <dl className="sign-details">
              <dt>{t("Signed by")}</dt>
              <dd>{t("{signed_by} · Reviewer", { signed_by: info.signed_by })}</dd>
              <dt>{t("Certificate")}</dt>
              <dd>{info.signer.certificate_class ?? '—'}</dd>
              {info.signer.key_id && (
                <>
                  <dt>{t("Key fingerprint")}</dt>
                  <dd className="mono">{info.signer.key_id}</dd>
                </>
              )}
            </dl>
            <p className="sign-summary">
              {t("You are signing")}{' '}
              <strong>
                {t("{outputs} output{value} = {files} file{value2}", { outputs: info.outputs, value: info.outputs === 1 ? '' : 's', files: info.files, value2: info.files === 1 ? '' : 's' })}</strong>{' '}
              {t("for job #")}{info.job_id} v{info.version}{t(". Each file gets a QR code, and the job gets a numbered entry in the record book.")}
            </p>
            {info.needs_pin && (
              <label className="field">
                <span className="field-label">{t("Token PIN")}</span>
                <input className="input" type="password" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="off" />
              </label>
            )}
            <label className="row gap-10 toggle-row">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>{t("I have reviewed these outputs and approve them for release")}</span>
            </label>
          </>
        )}
        {error && <div className="alert alert-red">{error}</div>}

        <div className="row gap-10">
          <button type="button" className="btn btn-outline" onClick={onClose} disabled={busy}>
            {t("Cancel")}
          </button>
          <div className="grow" />
          <button type="button" className="btn btn-green" onClick={sign} disabled={!info || !agreed || busy || Boolean(info?.signer.error)}>
            <Icon name="shieldCheck" size={18} strokeWidth={2} />
            {busy ? t("Signing…") : t("Sign {n} file{n2}", { n: info?.files ?? '', n2: info?.files === 1 ? '' : 's' })}
          </button>
        </div>
      </section>
    </div>
  )
}
