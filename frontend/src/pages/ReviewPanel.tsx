// The review box at the top of the Results page (Stage 6B).
//   Operator: "Submit for review" when the job is finished (or was sent back), and the reviewer's notes.
//   Reviewer: "Approve" or "Send back" with notes, while the job is waiting for review.
// The backend checks everything again (role, job state, separation of duties); this only shows it.
import { useState } from 'react'
import { reviewJob, submitForReview, type JobDetail } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { shortTime } from './format'

export function ReviewPanel({ job, onChange }: { job: JobDetail; onChange: (job: JobDetail) => void }) {
  const { user } = useAuth()
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const last = job.reviews[job.reviews.length - 1]
  const lastSentBack = [...job.reviews].reverse().find((r) => r.decision === 'sent_back')
  const lastSubmitted = [...job.reviews].reverse().find((r) => r.decision === 'submitted')

  async function run(action: () => Promise<JobDetail>) {
    setBusy(true)
    setError('')
    try {
      onChange(await action())
      setNotes('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.')
    } finally {
      setBusy(false)
    }
  }

  const sentBackNote = job.status === 'sent_back' && lastSentBack && (
    <div className="alert alert-red stack gap-4" role="status">
      <strong className="row gap-8">
        <Icon name="arrowLeft" size={18} strokeWidth={2.2} />
        Sent back by {lastSentBack.by} · {shortTime(lastSentBack.created_at)}
      </strong>
      <span className="pre-line">{lastSentBack.notes}</span>
    </div>
  )

  if (job.status === 'approved' && last) {
    return (
      <div className="alert alert-green stack gap-4" role="status">
        <strong className="row gap-8">
          <Icon name="check" size={18} strokeWidth={2.4} />
          Approved by {last.by} · {shortTime(last.created_at)} · version {job.version}
        </strong>
        {last.notes && <span className="pre-line">{last.notes}</span>}
        <span className="small">It can no longer be changed. Signing the files comes in Stage 7.</span>
      </div>
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
    if (job.status !== 'ready' && job.status !== 'sent_back') return null
    return (
      <>
        {sentBackNote}
        <section className="card card-pad-sm review-panel">
          <div className="stack gap-4 grow">
            <strong>{job.status === 'sent_back' ? 'Made the changes?' : 'Finished checking?'}</strong>
            <span className="muted small">
              A Reviewer checks the job and approves it or sends it back with notes. It is locked while it is with them.
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
    const ownJob = job.owner?.id === user.id || job.reviews.some((r) => r.decision === 'submitted' && r.user_id === user.id)
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
                  notes.trim().length < 5
                    ? setError('Write a note for the Operator: what should be changed?')
                    : run(() => reviewJob(job.id, 'send_back', notes))
                }
              >
                <Icon name="arrowLeft" size={18} strokeWidth={2} />
                Send back with notes
              </button>
              <div className="grow" />
              <button type="button" className="btn btn-green" disabled={busy} onClick={() => run(() => reviewJob(job.id, 'approve', notes))}>
                <Icon name="check" size={18} strokeWidth={2.4} />
                Approve
              </button>
            </div>
          </>
        )}
      </section>
    )
  }
  return sentBackNote || null
}
