// Design 24 · Reviewer dashboard (review queue). Jobs waiting for review, oldest first. "Review" opens
// the job's Results page, where the Reviewer approves it or sends it back with notes.
// (Signing and the DSC token come in Stage 7.)
import { useEffect, useState } from 'react'
import { getReviewQueue, type QueueItem, type ReviewQueue as Queue } from '../api'
import { firstName, useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { Mandala } from '../components/Mandala'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { shortTime, todayLabel } from './format'

function waitingFor(iso: string | null, now: number): string {
  if (!iso) return ''
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.round(minutes / 60)
  return hours < 48 ? `${hours} hour${hours === 1 ? '' : 's'}` : `${Math.round(hours / 24)} days`
}

export function ReviewQueue() {
  const { user } = useAuth()
  const [queue, setQueue] = useState<Queue | null>(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(0) // when the queue was loaded, for "Waiting 8 min"

  useEffect(() => {
    getReviewQueue()
      .then((q) => {
        setNow(Date.now())
        setQueue(q)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the review queue.'))
  }, [])

  const waiting = queue?.waiting ?? []
  const sentBack = queue?.recent.filter((r) => r.decision === 'sent_back').length ?? 0
  const approved = queue?.recent.filter((r) => r.decision === 'approved').length ?? 0

  return (
    <main className="page">
      <section className="hero hero-green">
        <div className="hero-mandala-big">
          <Mandala size={340} petals={16} color="var(--green)" opacity={0.4} />
        </div>
        <div className="hero-body">
          <div className="eyebrow">{todayLabel()}</div>
          <h1>Namaste, {firstName(user.full_name)}</h1>
          <p>
            {queue === null
              ? 'Loading the review queue…'
              : waiting.length === 0
                ? 'Nothing is waiting for review.'
                : `${waiting.length} job${waiting.length === 1 ? ' is' : 's are'} waiting for you.`}
          </p>
        </div>
      </section>

      <div className="stat-grid stat-grid-3">
        <Stat icon="history" tone="green" label="Waiting for you" value={waiting.length} note={waiting[0] ? `Oldest: ${waitingFor(waiting[0].submitted_at, now)}` : 'All clear'} />
        <Stat icon="check" tone="navy" label="Approved recently" value={approved} note="Last 10 decisions" />
        <Stat icon="arrowLeft" tone="red" label="Sent back recently" value={sentBack} note="With notes to operators" />
      </div>

      {error && <div className="alert alert-red">{error}</div>}

      <div className="dash-grid">
        <section className="card card-pad stack gap-14">
          <h2>Review queue</h2>
          {queue && waiting.length === 0 && <p className="muted">No jobs are waiting. Submitted jobs appear here.</p>}
          {waiting.map((item) => (
            <QueueRow key={item.id} item={item} now={now} />
          ))}
        </section>
        <section className="card card-pad stack gap-12">
          <h2>Recent decisions</h2>
          {queue && queue.recent.length === 0 && <p className="muted small">No decisions yet.</p>}
          {queue?.recent.map((r, i) => (
            <a key={i} href={links.job(r.job_id)} className="recent-row">
              <Icon
                name={r.decision === 'approved' ? 'check' : 'arrowLeft'}
                size={16}
                strokeWidth={2.2}
                color={r.decision === 'approved' ? 'var(--green-dark)' : 'var(--red-dark)'}
              />
              <span className="stack grow">
                <span className="recent-title">{r.job_title}</span>
                <span className="muted small">
                  {r.decision === 'approved' ? 'Approved' : 'Sent back'} by {r.by} · {shortTime(r.created_at)}
                </span>
              </span>
              <span className="mono muted">#{r.job_id}</span>
            </a>
          ))}
        </section>
      </div>
    </main>
  )
}

function Stat(props: { icon: 'history' | 'check' | 'arrowLeft'; tone: string; label: string; value: number; note: string }) {
  return (
    <section className="card stat-card">
      <div className={`stat-icon tone-${props.tone}`}>
        <Icon name={props.icon} size={22} />
      </div>
      <div className="stack gap-2">
        <span className="stat-label">{props.label}</span>
        <span className="stat-value">{props.value}</span>
        <span className="stat-note">{props.note}</span>
      </div>
    </section>
  )
}

function QueueRow({ item, now }: { item: QueueItem; now: number }) {
  const problems = [
    !item.fact_sheet_ok && 'Fact sheet does not match the source',
    !item.numbers_match && 'Numbers differ between outputs',
    item.warnings > 0 && `${item.warnings} sentence${item.warnings === 1 ? '' : 's'} not linked to the source`,
  ].filter(Boolean) as string[]
  return (
    <article className="queue-row">
      <div className="stack gap-6 grow">
        <div className="row gap-10 wrap">
          {item.tlp && <TlpLabel tlp={item.tlp} />}
          <strong className="queue-title">
            {item.title}
            {item.version > 1 && ` · v${item.version}`}
          </strong>
        </div>
        <div className="row gap-12 wrap muted small">
          <span>From {item.submitted_by ?? item.owner ?? 'unknown'}</span>
          <span>
            {item.outputs.length} output{item.outputs.length === 1 ? '' : 's'}
          </span>
          {item.quality_score !== null && <span>Quality {item.quality_score}/100</span>}
          {problems.length === 0 ? (
            <span className="chip chip-green chip-xs">
              <Icon name="check" size={12} strokeWidth={2.4} />
              All checks passed
            </span>
          ) : (
            <span className="chip chip-yellow chip-xs" title={problems.join('\n')}>
              <Icon name="warning" size={12} strokeWidth={2.4} />
              {problems.length} to check
            </span>
          )}
        </div>
        {item.submit_notes && <p className="muted small">“{item.submit_notes}”</p>}
        {!item.can_review && <p className="small queue-own">{item.why_not}</p>}
      </div>
      <div className="stack gap-6 end-items">
        <span className="muted small">Waiting {waitingFor(item.submitted_at, now)}</span>
        <a href={links.job(item.id)} className="btn btn-green-outline btn-sm">
          {item.can_review ? 'Review' : 'View'}
          <Icon name="arrowRight" size={16} strokeWidth={2} />
        </a>
      </div>
    </article>
  )
}
