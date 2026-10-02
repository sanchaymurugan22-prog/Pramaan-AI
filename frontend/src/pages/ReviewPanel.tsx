// The review box at the top of the Results page (Stage 6B, signing added in Stage 7).
//   Operator: "Submit for review" when the job is finished (or was sent back), the reviewer's notes,
//             and "Start a new version" once it is approved and signed.
//   Reviewer: a link to the review page (Stage 9B, ReviewJob.tsx), where they comment, approve and sign,
//             or send back.
//   Approved: the signed record (QR code, record number, fingerprint).
// The backend checks everything again (role, job state, separation of duties); this only shows it.
import { useState } from 'react'
import { newVersion, submitForReview, type JobDetail } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { shortTime } from './format'
import { links } from '../router'
import { SignedRecord } from './SignedRecord'
import { t } from '../i18n'

export function ReviewPanel({ job, onChange }: { job: JobDetail; onChange: (job: JobDetail) => void }) {
  const { user } = useAuth()
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lastSentBack = [...job.reviews].reverse().find((r) => r.decision === 'sent_back')
  const lastSubmitted = [...job.reviews].reverse().find((r) => r.decision === 'submitted')

  async function run(action: () => Promise<JobDetail>) {
    setBusy(true)
    setError('')
    try {
      onChange(await action())
      setNotes('')
    } catch (e) {
      setError(e instanceof Error ? e.message : t("That did not work."))
    } finally {
      setBusy(false)
    }
  }

  const record = job.record
  const recordBox = record && <SignedRecord job={job} record={record} justSigned={false} />

  const sentBackNote = job.status === 'sent_back' && lastSentBack && (
    <div className="alert alert-red stack gap-4" role="status">
      <strong className="row gap-8">
        <Icon name="arrowLeft" size={18} strokeWidth={2.2} />
        {t("Sent back by")} {lastSentBack.by} · {shortTime(lastSentBack.created_at)}
      </strong>
      <span className="pre-line">{lastSentBack.notes}</span>
    </div>
  )

  if (job.status === 'approved') {
    return (
      <>
        {recordBox}
        {user.role === 'operator' && (
          <section className="card card-pad-sm review-panel">
            <div className="stack gap-4 grow">
              <strong>{t("Need to change it?")}</strong>
              <span className="muted small">
                {t("Signed files cannot be changed. A new version needs a new review and a new signature; the new record says which one it replaces.")}
              </span>
              {error && <span className="form-error">{error}</span>}
            </div>
            <button
              type="button"
              className="btn btn-saffron-outline"
              disabled={busy}
              onClick={() => {
                if (window.confirm(t("Start version {n} of this job? It will need a new review and signature.", { n: job.version + 1 })))
                  run(() => newVersion(job.id))
              }}
            >
              <Icon name="pencil" size={18} strokeWidth={2} />
              {t("Start a new version")}
            </button>
          </section>
        )}
      </>
    )
  }

  // ---- Operator ----
  if (user.role === 'operator') {
    if (job.status === 'in_review') {
      return (
        <div className="hint row gap-8" role="status">
          <Icon name="eye" size={18} />
          {lastSubmitted ? t("Submitted for review by {by} · {n}.", { by: lastSubmitted.by, n: shortTime(lastSubmitted.created_at) }) : t("Submitted for review.")}{' '}{t("It cannot be changed until a Reviewer approves it or sends it back.")}
        </div>
      )
    }
    if (job.status !== 'ready' && job.status !== 'sent_back') return recordBox || null
    return (
      <>
        {sentBackNote}
        {recordBox}
        <section className="card card-pad-sm review-panel">
          <div className="stack gap-4 grow">
            <strong>{job.status === 'sent_back' ? t("Made the changes?") : t("Finished checking?")}</strong>
            <span className="muted small">
              {t("A Reviewer checks the job and approves and signs it, or sends it back with notes. It is locked while it is with them.")}
            </span>
            <input
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("Note for the reviewer (optional)")}
              aria-label={t("Note for the reviewer")}
            />
            {error && <span className="form-error">{error}</span>}
          </div>
          <button type="button" className="btn btn-saffron" disabled={busy} onClick={() => run(() => submitForReview(job.id, notes))}>
            <Icon name="arrowRight" size={18} strokeWidth={2} />
            {job.status === 'sent_back' ? t("Submit again (v{n})", { n: job.version + 1 }) : t("Submit for review")}
          </button>
        </section>
      </>
    )
  }

  // ---- Reviewer: the review itself happens on the review page (design 25) ----
  if (user.role === 'reviewer' && job.status === 'in_review') {
    return (
      <section className="card card-pad-sm review-panel">
        <div className="stack gap-4 grow">
          <strong>{t("Waiting for review (version {version})", { version: job.version })}</strong>
          <span className="muted small">
            {t("{value}Comment on lines, approve and sign, or send it back on the review page.", { value: lastSubmitted ? t("Submitted by {by} · {n}. ", { by: lastSubmitted.by, n: shortTime(lastSubmitted.created_at) }) : '' })}</span>
        </div>
        <a className="btn btn-green" href={links.reviewJob(job.id)}>
          {t("Open the review")}
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </a>
      </section>
    )
  }
  return (
    <>
      {sentBackNote}
      {recordBox}
    </>
  )
}
