// The review box at the top of the Results page (Stage 6B, signing added in Stage 7).
//   Operator: "Submit for review" when the job is finished (or was sent back), the reviewer's notes,
//             and "Start a new version" once it is approved and signed.
//   Reviewer: "Approve & sign" (opens the sign dialog) or "Send back" with reasons and notes.
//   Approved: the signed record (QR code, record number, fingerprint).
// The backend checks everything again (role, job state, separation of duties); this only shows it.
import { useState } from 'react'
import { newVersion, reviewJob, submitForReview, type JobDetail } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { shortTime } from './format'
import { SignDialog } from './SignDialog'
import { SignedRecord } from './SignedRecord'

// Design 28 · Send back: quick reasons, added to the start of the note
const REASONS = ['Facts need checking', 'Language quality', 'Tone', 'Sensitive detail', 'Formatting']

export function ReviewPanel({ job, onChange }: { job: JobDetail; onChange: (job: JobDetail) => void }) {
  const { user } = useAuth()
  const [notes, setNotes] = useState('')
  const [reasons, setReasons] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [signing, setSigning] = useState(false)
  const [justSigned, setJustSigned] = useState(false)
  const lastSentBack = [...job.reviews].reverse().find((r) => r.decision === 'sent_back')
  const lastSubmitted = [...job.reviews].reverse().find((r) => r.decision === 'submitted')

  async function run(action: () => Promise<JobDetail>) {
    setBusy(true)
    setError('')
    try {
      onChange(await action())
      setNotes('')
      setReasons([])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.')
    } finally {
      setBusy(false)
    }
  }

  const record = job.record
  const recordBox = record && <SignedRecord job={job} record={record} justSigned={justSigned} />

  const sentBackNote = job.status === 'sent_back' && lastSentBack && (
    <div className="alert alert-red stack gap-4" role="status">
      <strong className="row gap-8">
        <Icon name="arrowLeft" size={18} strokeWidth={2.2} />
        Sent back by {lastSentBack.by} · {shortTime(lastSentBack.created_at)}
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
              <strong>Need to change it?</strong>
              <span className="muted small">
                Signed files cannot be changed. A new version needs a new review and a new signature; the new record says
                which one it replaces.
              </span>
              {error && <span className="form-error">{error}</span>}
            </div>
            <button
              type="button"
              className="btn btn-saffron-outline"
              disabled={busy}
              onClick={() => {
                if (window.confirm(`Start version ${job.version + 1} of this job? It will need a new review and signature.`))
                  run(() => newVersion(job.id))
              }}
            >
              <Icon name="pencil" size={18} strokeWidth={2} />
              Start a new version
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
          Submitted for review{lastSubmitted ? ` by ${lastSubmitted.by} · ${shortTime(lastSubmitted.created_at)}` : ''}. It cannot be
          changed until a Reviewer approves it or sends it back.
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
            <strong>{job.status === 'sent_back' ? 'Made the changes?' : 'Finished checking?'}</strong>
            <span className="muted small">
              A Reviewer checks the job and approves and signs it, or sends it back with notes. It is locked while it is
              with them.
            </span>
            <input
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Note for the reviewer (optional)"
              aria-label="Note for the reviewer"
            />
            {error && <span className="form-error">{error}</span>}
          </div>
          <button type="button" className="btn btn-saffron" disabled={busy} onClick={() => run(() => submitForReview(job.id, notes))}>
            <Icon name="arrowRight" size={18} strokeWidth={2} />
            {job.status === 'sent_back' ? `Submit again (v${job.version + 1})` : 'Submit for review'}
          </button>
        </section>
      </>
    )
  }

  // ---- Reviewer ----
  if (user.role === 'reviewer' && job.status === 'in_review') {
    const ownJob =
      job.owner?.id === user.id || job.reviews.some((r) => (r.decision === 'submitted' || r.decision === 'reopened') && r.user_id === user.id)
    const fullNote = () => [reasons.length ? `Reasons: ${reasons.join(', ')}.` : '', notes.trim()].filter(Boolean).join('\n')
    return (
      <section className="card card-pad review-panel-reviewer stack gap-12">
        <div className="row gap-10 wrap">
          <h2>Your review</h2>
          <span className="chip chip-navy">Version {job.version}</span>
          {lastSubmitted && (
            <span className="muted small">
              Submitted by {lastSubmitted.by} · {shortTime(lastSubmitted.created_at)}
            </span>
          )}
        </div>
        {lastSubmitted?.notes && <p className="muted">“{lastSubmitted.notes}”</p>}
        {ownJob ? (
          <div className="alert alert-yellow">
            You worked on this job, so you cannot review it. Another Reviewer must check it (separation of duties).
          </div>
        ) : (
          <>
            <div className="row gap-8 wrap" role="group" aria-label="Reasons to send back">
              {REASONS.map((reason) => {
                const on = reasons.includes(reason)
                return (
                  <button
                    key={reason}
                    type="button"
                    className={on ? 'reason-chip is-on' : 'reason-chip'}
                    aria-pressed={on}
                    onClick={() => setReasons(on ? reasons.filter((r) => r !== reason) : [...reasons, reason])}
                  >
                    {on && <Icon name="check" size={14} strokeWidth={2.4} />}
                    {reason}
                  </button>
                )
              })}
            </div>
            <textarea
              className="input textarea"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notes for the Operator (needed to send back; optional to approve)"
              aria-label="Review notes"
            />
            {error && <span className="form-error">{error}</span>}
            <div className="row gap-10">
              <button
                type="button"
                className="btn btn-red-outline"
                disabled={busy}
                onClick={() =>
                  fullNote().length < 5
                    ? setError('Pick a reason or write a note for the Operator: what should be changed?')
                    : run(() => reviewJob(job.id, 'send_back', fullNote()))
                }
              >
                <Icon name="arrowLeft" size={18} strokeWidth={2} />
                Send back with notes
              </button>
              <div className="grow" />
              <button type="button" className="btn btn-green" disabled={busy} onClick={() => setSigning(true)}>
                <Icon name="shieldCheck" size={18} strokeWidth={2} />
                Approve &amp; sign
              </button>
            </div>
          </>
        )}
        {signing && (
          <SignDialog
            job={job}
            notes={notes}
            onClose={() => setSigning(false)}
            onSigned={(signed) => {
              setSigning(false)
              setJustSigned(true)
              setNotes('')
              onChange(signed)
              window.scrollTo(0, 0)
            }}
          />
        )}
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
