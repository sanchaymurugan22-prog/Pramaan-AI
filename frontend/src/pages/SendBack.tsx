// Design 28 · Send back with notes (Stage 9B). Reasons, the line comments made on the review page (each
// with what the source says), a note to the Operator. The Operator sees all of it on their job.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { addComment, getJob, getReviewQueue, reviewJob, takeBackComment, type JobDetail, type ReviewComment } from '../api'
import { firstName, useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { links, navigate } from '../router'
import { factLookup } from './format'
import { ReviewHead, workedOn } from './ReviewJob'

export function SendBack({ jobId }: { jobId: number }) {
  const { user } = useAuth()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [reasons, setReasons] = useState<string[]>([])
  const [allReasons, setAllReasons] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [extra, setExtra] = useState<string | null>(null) // a comment about the whole job, being written
  const [chosen, setChosen] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const reload = useCallback(
    () =>
      getJob(jobId)
        .then(setJob)
        .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the job.')),
    [jobId],
  )
  useEffect(() => {
    reload()
    getReviewQueue()
      .then((q) => setAllReasons(q.reasons))
      .catch(() => setAllReasons(['Facts need checking', 'Language quality', 'Tone', 'Sensitive detail', 'Formatting']))
  }, [reload])

  const facts = useMemo(() => factLookup(job?.fact_sheet ?? null), [job?.fact_sheet])
  if (!job) return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}</main>

  const comments = job.comments.filter((c) => c.job_version === job.version)
  const owner = job.owner ? firstName(job.owner.full_name) : 'the Operator'
  const selected = comments.find((c) => c.id === chosen) ?? comments[0]
  const ready = job.status === 'in_review' && !workedOn(job, user.id)

  // What the source says for a comment's sentence: the quotes of the facts it uses
  function sourceFor(c: ReviewComment): string[] {
    const output = job!.outputs.find((o) => o.id === c.output_id)
    const sentence = output?.quality?.sentences?.find((s) => s.id === c.sentence_id)
    const ids = sentence ? (sentence.fact_ids.length ? sentence.fact_ids : sentence.closest ? [sentence.closest] : []) : []
    return ids.map((id) => facts.get(id)?.quote).filter((q): q is string => Boolean(q))
  }

  async function send() {
    setBusy(true)
    setError('')
    try {
      await reviewJob(job!.id, 'send_back', note, '', reasons)
      navigate(links.review)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send it back.')
      setBusy(false)
    }
  }

  async function saveExtra() {
    if (!extra?.trim()) return
    try {
      await addComment(job!.id, { text: extra.trim() })
      setExtra(null)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not add the comment.')
    }
  }

  return (
    <main className="page">
      <ReviewHead job={job} eyebrow="Send back">
        <a className="btn btn-outline" href={links.reviewJob(job.id)}>
          Cancel
        </a>
      </ReviewHead>
      {!ready && (
        <div className="alert alert-yellow">
          This job cannot be sent back by you now. <a href={links.review}>Back to the review queue</a>
        </div>
      )}
      {error && <div className="alert alert-red" role="alert">{error}</div>}

      <div className="sendback-grid">
        <section className="card card-pad stack gap-16" aria-labelledby="why-title">
          <h2 id="why-title">Why are you sending it back?</h2>
          <div className="row gap-8 wrap" role="group" aria-label="Reasons">
            {allReasons.map((reason) => {
              const on = reasons.includes(reason)
              return (
                <button
                  key={reason}
                  type="button"
                  className={on ? 'pill pill-red is-on' : 'pill'}
                  aria-pressed={on}
                  onClick={() => setReasons(on ? reasons.filter((r) => r !== reason) : [...reasons, reason])}
                >
                  {on && <Icon name="check" size={16} strokeWidth={2.4} />}
                  {reason}
                </button>
              )
            })}
          </div>

          <div className="row gap-10">
            <h3 className="grow">Line comments ({comments.length})</h3>
            <button type="button" className="btn btn-link btn-xs link-red" onClick={() => setExtra(extra === null ? '' : null)} aria-expanded={extra !== null}>
              <Icon name="plus" size={16} strokeWidth={2} />
              Add comment
            </button>
          </div>
          {extra !== null && (
            <div className="stack gap-8">
              <label className="sr-only" htmlFor="job-comment">
                A comment about the whole job
              </label>
              <textarea id="job-comment" className="input textarea" rows={2} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="A comment about the whole job" />
              <div className="row gap-8">
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setExtra(null)}>
                  Cancel
                </button>
                <button type="button" className="btn btn-sm btn-red" onClick={saveExtra} disabled={!extra.trim()}>
                  Add
                </button>
              </div>
              <span className="small muted">
                To comment on one sentence, click it on the <a href={links.reviewJob(job.id)}>review page</a>.
              </span>
            </div>
          )}
          {comments.length === 0 && extra === null && (
            <p className="muted small">No line comments. Click sentences on the review page to comment on them, or write a note below.</p>
          )}
          <ul className="clean-list-plain stack gap-10">
            {comments.map((c) => (
              <li key={c.id} className={c.id === selected?.id ? 'comment comment-card is-current' : 'comment comment-card'}>
                <span className="comment-icon" aria-hidden="true">
                  <Icon name={c.output_id ? 'file' : 'summary'} size={18} />
                </span>
                <button type="button" className="stack gap-2 grow comment-open" onClick={() => setChosen(c.id)}>
                  <span className="small muted">{c.output_label ?? 'Whole job'} · English</span>
                  {c.quote && <q className="comment-quote">{c.quote}</q>}
                  <span>{c.text}</span>
                </button>
                {c.author_id === user.id && (
                  <button
                    type="button"
                    className="icon-btn icon-btn-sm"
                    aria-label="Take back this comment"
                    onClick={async () => {
                      await takeBackComment(job.id, c.id)
                      await reload()
                    }}
                  >
                    <Icon name="cross" size={16} />
                  </button>
                )}
              </li>
            ))}
          </ul>

          <label className="field">
            <span className="field-label">Note to {owner}</span>
            <textarea
              className="input textarea"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Good structure overall. Please fix the district names and match the source wording, then resend."
            />
          </label>
          <div className="row gap-10 wrap">
            <span className="muted small grow">{owner} will see this on their dashboard and next to each line.</span>
            <button
              type="button"
              className="btn btn-lg btn-red"
              onClick={send}
              disabled={busy || !ready || (note.trim().length < 5 && comments.length === 0)}
            >
              <Icon name="send" size={18} strokeWidth={2} />
              {busy ? 'Sending…' : `Send back to ${owner}`}
            </button>
          </div>
        </section>

        <aside className="card card-pad stack gap-12" aria-label="The selected comment and its source">
          {selected ? (
            <>
              <div className="row gap-10">
                <h2 className="grow">{selected.output_label ?? 'Whole job'}</h2>
                <span className="chip chip-neutral chip-xs">Selected comment</span>
              </div>
              {selected.quote ? <p className="lead">“{selected.quote}”</p> : <p className="muted">A comment about the whole job.</p>}
              {selected.quote && (
                <>
                  <div className="divider" />
                  <h3>Source says</h3>
                  {sourceFor(selected).length ? (
                    sourceFor(selected).map((q) => (
                      <p key={q} className="source-quote">
                        “{q}”
                      </p>
                    ))
                  ) : (
                    <p className="muted small">This line is not linked to any fact in the source.</p>
                  )}
                </>
              )}
            </>
          ) : (
            <p className="muted">Pick a comment to see the line next to what the source says.</p>
          )}
        </aside>
      </div>
    </main>
  )
}
