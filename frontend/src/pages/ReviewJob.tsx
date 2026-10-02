// Design 25 · Review a kit (checks and comments), design 26 · sign dialog, design 27 · Signed (Stage 9B).
// Click any sentence to see where it comes from (source trace, right) and to comment on it. Comments go to
// the Operator if the job is sent back (design 28, SendBack.tsx). "Approve & sign" signs every file.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { addComment, getJob, recordQrUrl, setNativeCheck, takeBackComment, tickAllTranslations, type JobDetail, type JobOutput } from '../api'
import { useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { OUTPUT_ICONS } from '../components/outputIcons'
import { TlpLabel } from '../components/TlpLabel'
import { languageByCode, useLanguages } from '../languages'
import { links, navigate } from '../router'
import { factLookup, jobNo, shortHash, shortTime } from './format'
import { OutputBody } from './OutputViews'
import { SignDialog } from './SignDialog'
import { SourcePanel } from './TracePanels'
import { TraceProvider } from './trace'
import { NO_SELECTION, sentencesByPath, type Selection } from './traceState'

// Did this output pass its checks? (no unlinked sentence, no private data, no numbers not in the source)
export function outputOk(o: JobOutput): boolean {
  const q = o.quality
  return o.status === 'done' && !(q?.unlinked?.length) && !(q?.leaks?.length) && !(q?.not_in_source?.length)
}

// Someone who worked on the job may not review it (the backend refuses too)
export function workedOn(job: JobDetail, userId: number): boolean {
  return job.owner?.id === userId || job.reviews.some((r) => (r.decision === 'submitted' || r.decision === 'reopened') && r.user_id === userId)
}

type Check = { state: 'ok' | 'warn' | 'bad'; title: string; detail: string }

// The "Automatic checks" card, worked out from what the backend already checked
export function automaticChecks(job: JobDetail): Check[] {
  const claims = job.outputs.flatMap((o) => (o.quality?.sentences ?? []).filter((s) => ['linked', 'unlinked', 'unverified'].includes(s.status)))
  const linked = claims.filter((s) => s.status === 'linked').length
  const hidden = (job.safety?.findings ?? []).filter((f) => f.choice !== 'keep').length
  const leaks = job.outputs.reduce((n, o) => n + (o.quality?.leaks?.length ?? 0), 0)
  const suspicious = job.safety?.suspicious ?? []
  const removed = suspicious.filter((x) => x.kind === 'instruction' && x.choice === 'remove').length
  const checks: Check[] = [
    {
      state: linked === claims.length ? 'ok' : 'warn',
      title: 'Every line traced to source',
      detail: `${linked} of ${claims.length} sentences linked to a fact`,
    },
    {
      state: job.consistency?.ok === false ? 'bad' : 'ok',
      title: 'Facts match across outputs',
      detail: job.consistency?.ok === false ? `${job.consistency.mismatches.length} number(s) differ between outputs` : 'Numbers, dates and names agree',
    },
    {
      state: leaks ? 'bad' : 'ok',
      title: 'Sensitive details hidden',
      detail: leaks ? `${leaks} private value(s) found in an output` : `${hidden} detail${hidden === 1 ? '' : 's'} hidden as chosen`,
    },
    {
      state: job.public_check?.ok === false ? 'warn' : 'ok',
      title: 'Public-release wording',
      detail: job.public_check?.ok === false ? `${job.public_check.problems.length} phrase(s) to soften` : 'No panic wording or shouting',
    },
    {
      state: suspicious.length > removed ? 'warn' : 'ok',
      title: 'No hidden instructions in sources',
      detail: suspicious.length === 0 ? 'None found' : `${suspicious.length} found, ${removed} removed before the AI read the source`,
    },
    {
      state: job.fact_sheet_check?.ok === false ? 'bad' : 'ok',
      title: 'Fact sheet matches the source',
      detail: job.fact_sheet_check ? `${job.fact_sheet_check.found} of ${job.fact_sheet_check.total} quotes found` : '—',
    },
    { state: job.tlp ? 'ok' : 'warn', title: 'Sharing label applied', detail: job.tlp ? `TLP:${job.tlp} on every file` : 'No label chosen' },
  ]
  // Stage 8: translations keep every value, and a native speaker has read each one
  const translations = job.outputs.filter((o) => o.language !== 'en')
  if (translations.length > 0) {
    const changed = translations.filter((o) => (o.quality?.translation?.changed ?? []).length > 0)
    const checked = translations.filter((o) => o.translation?.native_check.checked)
    checks.push(
      {
        state: changed.length ? 'bad' : 'ok',
        title: 'Numbers survive translation',
        detail: changed.length
          ? `Changed in ${changed.map((o) => `${o.label} (${o.language_label})`).join(', ')}`
          : `Every number, date and code is the same in ${translations.length} translation${translations.length === 1 ? '' : 's'}`,
      },
      {
        state: checked.length === translations.length ? 'ok' : 'warn',
        title: 'Checked by a native speaker',
        detail: `${checked.length} of ${translations.length} translations ticked (needed before signing)`,
      },
    )
  }
  return checks
}

const CHECK_ICON: Record<Check['state'], IconName> = { ok: 'check', warn: 'warning', bad: 'cross' }
const CHECK_WORD: Record<Check['state'], string> = { ok: 'Passed', warn: 'To check', bad: 'Problem' }

export function ChecksCard({ job }: { job: JobDetail }) {
  return (
    <section className="card card-pad stack gap-12" aria-labelledby="checks-title">
      <h2 id="checks-title">Automatic checks</h2>
      <ul className="clean-list-plain stack gap-12">
        {automaticChecks(job).map((c) => (
          <li key={c.title} className="check-row">
            <span className={`check-dot ${c.state === 'ok' ? 'check-ok' : c.state === 'warn' ? 'check-warn' : 'check-bad'}`}>
              <Icon name={CHECK_ICON[c.state]} size={16} strokeWidth={2.4} />
              <span className="sr-only">{CHECK_WORD[c.state]}: </span>
            </span>
            <span className="stack gap-1">
              <span className="check-title">{c.title}</span>
              <span className="check-detail">{c.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function ReviewHead({ job, children, eyebrow }: { job: JobDetail; children?: ReactNode; eyebrow?: string }) {
  const submitted = [...job.reviews].reverse().find((r) => r.decision === 'submitted')
  return (
    <div className="page-head">
      <div className="stack gap-2">
        <div className="eyebrow eyebrow-green">
          {eyebrow ?? 'Review'} · Job {jobNo(job.id)} v{job.version}
          {submitted?.by && ` · from ${submitted.by}`}
        </div>
        <h1>{job.title}</h1>
      </div>
      <div className="grow" />
      {children}
    </div>
  )
}

export function ReviewJob({ jobId }: { jobId: number }) {
  const { user } = useAuth()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  const [outputId, setOutputId] = useState<number | null>(null)
  const [selection, setSelection] = useState<Selection>(NO_SELECTION)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [signing, setSigning] = useState(false)
  const [showEnglish, setShowEnglish] = useState(false) // Stage 8: a translation next to its English
  const languages = useLanguages()

  const reload = useCallback(
    () =>
      getJob(jobId)
        .then(setJob)
        .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the job.')),
    [jobId],
  )
  useEffect(() => {
    reload()
  }, [reload])

  const facts = useMemo(() => factLookup(job?.fact_sheet ?? null), [job?.fact_sheet])
  const active = job?.outputs.find((o) => o.id === outputId) ?? job?.outputs[0]
  const byPath = useMemo(() => sentencesByPath(active?.quality?.sentences), [active?.quality])

  // Narrow screens (and 200% zoom): the source trace opens as a sheet over the bottom half of the page,
  // so bring the comment box into the top half, where it can be typed in.
  useEffect(() => {
    if (!selection.sentenceId || !window.matchMedia('(max-width: 1100px)').matches) return
    document.querySelector('.comment-box')?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [selection.sentenceId])

  if (!job || !active) {
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}</main>
  }
  if (job.status !== 'in_review') {
    return (
      <main className="page">
        <ReviewHead job={job} />
        <div className="alert alert-yellow">
          This job is not waiting for review (it is {job.status.replace('_', ' ')}). <a href={links.job(job.id)}>Open its results</a> or go
          back to the <a href={links.review}>review queue</a>.
        </div>
      </main>
    )
  }

  const mine = workedOn(job, user.id)
  // Stage 8: a translation is compared with its English output; every translation needs a native-speaker check
  const english = active.translation ? job.outputs.find((o) => o.id === active.translation!.source_output_id) : undefined
  const activeLang = languageByCode(languages, active.language)
  const toCheck = job.outputs.filter((o) => o.language !== 'en' && !o.translation?.native_check.checked).length
  const sentence =
    selection.outputId === active.id && selection.sentenceId ? active.quality?.sentences?.find((s) => s.id === selection.sentenceId) ?? null : null
  const comments = job.comments.filter((c) => c.job_version === job.version)
  const here = comments.filter((c) => c.output_id === active.id)

  async function send() {
    if (!sentence || !active) return
    setBusy(true)
    setError('')
    try {
      await addComment(job!.id, { output_id: active.id, sentence_id: sentence.id, path: sentence.path, quote: sentence.text, text: comment })
      setComment('')
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the comment.')
    } finally {
      setBusy(false)
    }
  }

  // Stage 8: an alert in 22 languages; the Reviewer confirms native speakers read every one (each is recorded)
  async function tickAll() {
    const ok = window.confirm(
      `Tick “Checked by a native speaker” for all ${toCheck} translations?\n\nOnly do this if a native speaker of each language has read it against the English.`,
    )
    if (!ok || !job) return
    try {
      setJob(await tickAllTranslations(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not tick them.')
    }
  }

  async function takeBack(id: number) {
    try {
      await takeBackComment(job!.id, id)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not take it back.')
    }
  }

  return (
    <main className="page">
      <ReviewHead job={job}>
        {job.tlp && <TlpLabel tlp={job.tlp} />}
        {job.version > 1 && (
          <a className="btn btn-outline" href={links.compare(job.id)}>
            <Icon name="compare" size={18} strokeWidth={2} />
            Compare with v{job.version - 1}
          </a>
        )}
        {!mine && (
          <>
            <a className="btn btn-red-outline" href={links.sendBack(job.id)}>
              <Icon name="arrowLeft" size={18} strokeWidth={2} />
              Send back
            </a>
            <button type="button" className="btn btn-green" onClick={() => setSigning(true)}>
              <Icon name="award" size={18} strokeWidth={2} />
              Approve &amp; sign
            </button>
          </>
        )}
      </ReviewHead>

      {mine && (
        <div className="alert alert-yellow" role="status">
          You worked on this job, so you cannot review it. Another Reviewer must check it (separation of duties).
        </div>
      )}
      {error && <div className="alert alert-red">{error}</div>}

      <div className="review-grid">
        <nav className="card card-pad-sm stack gap-8 review-outputs" aria-label="Outputs">
          <h2 className="notes-title">
            {job.outputs.length} output{job.outputs.length === 1 ? '' : 's'}
          </h2>
          {job.outputs.map((o) => {
            const ok = outputOk(o) && (o.language === 'en' || Boolean(o.translation?.native_check.checked))
            const count = comments.filter((c) => c.output_id === o.id).length
            const lang = languageByCode(languages, o.language)
            return (
              <button
                key={o.id}
                type="button"
                className={o.id === active.id ? 'review-output is-current' : 'review-output'}
                aria-current={o.id === active.id ? 'true' : undefined}
                onClick={() => {
                  setOutputId(o.id)
                  setSelection(NO_SELECTION)
                }}
              >
                <Icon name={OUTPUT_ICONS[o.type] ?? 'file'} size={18} />
                <span className="grow">
                  {o.label}
                  {o.language !== 'en' && (
                    <span className="muted" lang={o.language}>
                      {' '}
                      · {lang?.native ?? o.language}
                    </span>
                  )}
                </span>
                {count > 0 && <span className="tab-count">{count}</span>}
                <Icon name={ok ? 'check' : 'warning'} size={18} color={ok ? 'var(--green-dark)' : 'var(--saffron-dark)'} strokeWidth={2.2} />
                <span className="sr-only">
                  {ok ? 'checks passed' : o.language !== 'en' && !o.translation?.native_check.checked ? 'needs a native-speaker check' : 'has notes to check'}
                </span>
              </button>
            )
          })}
          <span className="muted small">
            {job.languages.length > 1
              ? `${job.languages.length} languages · ${toCheck} translation${toCheck === 1 ? '' : 's'} to check`
              : 'English'}
          </span>
          {!mine && toCheck > 1 && (
            <button type="button" className="btn btn-outline btn-xs" onClick={tickAll}>
              <Icon name="check" size={16} strokeWidth={2.2} />
              Tick all {toCheck} translations
            </button>
          )}
        </nav>

        <section className="card card-pad stack gap-14" aria-label={active.label}>
          {active.translation && (
            <NativeCheckBox job={job} output={active} canTick={!mine} onChange={setJob} english={english}
                            showEnglish={showEnglish} onShowEnglish={setShowEnglish} />
          )}
          <TraceProvider value={{ outputId: active.id, byPath, facts, selection, select: setSelection }}>
            {active.content && showEnglish && english?.content ? (
              <div className="compare-languages">
                <div lang="en">
                  <span className="section-label">English (v{english.version})</span>
                  <OutputBody type={english.type} content={english.content}
                              meta={{ title: job.title, tlp: job.tlp, recordNo: null, audience: job.settings?.audience ?? '', quality: english.quality }} />
                </div>
                <div lang={active.language} dir={activeLang?.rtl ? 'rtl' : undefined}>
                  <span className="section-label">{activeLang?.native ?? active.language}</span>
                  <OutputBody type={active.type} content={active.content}
                              meta={{ title: job.title, tlp: job.tlp, recordNo: null, audience: job.settings?.audience ?? '', quality: active.quality }} />
                </div>
              </div>
            ) : active.content ? (
              <div lang={active.language} dir={activeLang?.rtl ? 'rtl' : undefined}>
                <OutputBody
                  type={active.type}
                  content={active.content}
                  meta={{ title: job.title, tlp: job.tlp, recordNo: null, audience: job.settings?.audience ?? '', quality: active.quality }}
                />
              </div>
            ) : (
              <p className="muted">This output has no text.</p>
            )}
          </TraceProvider>

          {!mine && (
            <div className="comment-box" aria-live="polite">
              {sentence ? (
                <>
                  <span className="small muted">
                    Comment on the selected line · {active.label} · {sentence.label}
                  </span>
                  <q className="comment-quote">{sentence.text}</q>
                  <label className="sr-only" htmlFor="line-comment">
                    Your comment
                  </label>
                  <textarea
                    id="line-comment"
                    className="input textarea"
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="e.g. Fine to keep as an analyst note. / This district is not in the source."
                  />
                  <div className="row gap-10">
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setSelection(NO_SELECTION)}>
                      Cancel
                    </button>
                    <button type="button" className="btn btn-green btn-sm" onClick={send} disabled={busy || comment.trim().length < 2}>
                      Add comment
                    </button>
                  </div>
                </>
              ) : (
                <span className="small muted">Click any sentence to see its source and to comment on it.</span>
              )}
            </div>
          )}

          {here.length > 0 && (
            <ul className="clean-list-plain stack gap-10" aria-label="Comments on this output">
              {here.map((c) => (
                <li key={c.id} className="comment">
                  <span className="avatar avatar-sm" aria-hidden="true">
                    {(c.author ?? '?').split(' ').map((w) => w[0]).join('').slice(0, 2)}
                  </span>
                  <span className="stack gap-2 grow">
                    <span className="small">
                      <strong>{c.author_id === user.id ? 'Your comment' : c.author}</strong> · {shortTime(c.created_at)}
                    </span>
                    {c.quote && <q className="comment-quote small">{c.quote}</q>}
                    <span>{c.text}</span>
                  </span>
                  {c.author_id === user.id && (
                    <button type="button" className="btn btn-link btn-xs" onClick={() => takeBack(c.id)}>
                      Take back<span className="sr-only"> this comment</span>
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="stack gap-16 review-side" aria-label="Checks and source">
          <ChecksCard job={job} />
          <TraceProvider value={{ outputId: active.id, byPath: new Map(), facts, selection, select: setSelection }}>
            <SourcePanel
              jobId={job.id}
              facts={facts}
              selection={selection}
              sentence={sentence}
              where={sentence ? `${active.label} · ${sentence.label}` : ''}
              select={setSelection}
              onClose={() => setSelection(NO_SELECTION)}
            />
          </TraceProvider>
        </aside>
      </div>

      {signing && (
        <SignDialog
          job={job}
          notes={comments.length ? `${comments.length} line comment${comments.length === 1 ? '' : 's'} kept as notes` : ''}
          onClose={() => setSigning(false)}
          onSigned={() => navigate(links.signed(job.id))}
        />
      )}
    </main>
  )
}

// Design 27 · Signed successfully
export function Signed({ jobId }: { jobId: number }) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    getJob(jobId)
      .then(setJob)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the job.'))
  }, [jobId])

  if (!job) return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}</main>
  const record = job.record
  if (!record) {
    return (
      <main className="page">
        <div className="alert alert-yellow">
          This job is not signed. <a href={links.reviewJob(job.id)}>Back to the review</a>
        </div>
      </main>
    )
  }
  const owner = job.owner?.full_name ?? 'The Operator'
  const replaces = job.version > 1
  return (
    <main className="page signed-page">
      <section className="card signed-card stack gap-20 center-items" aria-labelledby="signed-title">
        <span className="signed-seal" aria-hidden="true">
          <Icon name="check" size={56} strokeWidth={3} />
        </span>
        <div className="stack gap-6 center">
          <h1 id="signed-title">
            {record.files.length} file{record.files.length === 1 ? '' : 's'} signed
          </h1>
          <p className="muted">
            {job.title} · v{record.version} · signed {new Date(record.issued_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
          </p>
        </div>
        <div className="signed-record">
          <img src={recordQrUrl(record.record_no)} alt={`QR code for record ${record.record_no}`} width={120} height={120} />
          <dl className="facts-table grow">
            <div>
              <dt>Record</dt>
              <dd className="mono">{record.record_no}</dd>
            </div>
            <div>
              <dt>Fingerprint</dt>
              <dd className="mono">SHA-256 {shortHash(record.fingerprint)}</dd>
            </div>
            <div>
              <dt>Signed by</dt>
              <dd>
                {record.approved_by} · {record.signer}
              </dd>
            </div>
          </dl>
        </div>
        <ul className="clean-list-plain stack gap-12 signed-list">
          <li className="check-row">
            <span className="check-dot check-ok" aria-hidden="true">
              <Icon name="check" size={16} strokeWidth={2.4} />
            </span>
            <span className="stack gap-1">
              <span className="check-title">{owner} has been notified</span>
              <span className="check-detail">They can now save the signed campaign kit</span>
            </span>
          </li>
          <li className="check-row">
            <span className="check-dot check-ok" aria-hidden="true">
              <Icon name="check" size={16} strokeWidth={2.4} />
            </span>
            <span className="stack gap-1">
              <span className="check-title">Record {record.record_no} added to the record book</span>
              <span className="check-detail">{replaces ? 'It says which earlier record it replaces; the chain is intact' : 'Linked to the record before it; the chain is intact'}</span>
            </span>
          </li>
          <li className="check-row">
            <span className="check-dot check-pending" aria-hidden="true">
              <Icon name="clock" size={16} strokeWidth={2.4} />
            </span>
            <span className="stack gap-1">
              <span className="check-title">Public posts stay as drafts</span>
              <span className="check-detail">Released only by your team’s publishing process</span>
            </span>
          </li>
        </ul>
        <div className="row gap-10 wrap center-self">
          <a className="btn btn-lg btn-green" href={links.review}>
            <Icon name="arrowLeft" size={18} strokeWidth={2} />
            Back to review queue
          </a>
          <a className="btn btn-lg btn-outline" href={links.records}>
            Signed records
          </a>
          <a className="btn btn-lg btn-outline" href={links.check}>
            <Icon name="scan" size={18} />
            Check a copy
          </a>
        </div>
      </section>
    </main>
  )
}


// Stage 8: "Checked by a native speaker" for a translated output. Until it is ticked the job cannot be signed.
function NativeCheckBox({ job, output, canTick, onChange, english, showEnglish, onShowEnglish }: {
  job: JobDetail
  output: JobOutput
  canTick: boolean
  onChange: (job: JobDetail) => void
  english: JobOutput | undefined
  showEnglish: boolean
  onShowEnglish: (on: boolean) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const check = output.translation!.native_check
  const changed = output.quality?.translation?.changed ?? []

  async function tick(on: boolean) {
    setBusy(true)
    setError('')
    try {
      onChange(await setNativeCheck(job.id, output.id, on))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the check.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={check.checked ? 'notice notice-green stack gap-8' : 'notice notice-yellow stack gap-8'}>
      <span className="row gap-8">
        <Icon name={check.checked ? 'shieldCheck' : 'warning'} size={20} />
        <strong>{check.checked ? 'Checked by a native speaker' : 'Machine translated - needs a native-speaker check'}</strong>
      </span>
      <span className="small">
        Translated from the English (version {output.translation!.source_version ?? '?'}) by {output.translation!.engine}.
        {changed.length > 0
          ? ` ${changed.length} part${changed.length === 1 ? '' : 's'} changed a number or code: see the red marks.`
          : ' Every number, date and code is the same as in the English.'}
      </span>
      <div className="row gap-12 wrap">
        {canTick && (
          <label className="check-row">
            <input type="checkbox" checked={check.checked} disabled={busy || job.status !== 'in_review'}
                   onChange={(e) => tick(e.target.checked)} />
            <span>I have read this {output.language_label} text against the English: it says the same thing</span>
          </label>
        )}
        {check.checked && check.by && <span className="small">{check.by}{check.at ? ` · ${shortTime(check.at)}` : ''}</span>}
        {english && (
          <button type="button" className="btn btn-outline btn-xs" aria-pressed={showEnglish} onClick={() => onShowEnglish(!showEnglish)}>
            <Icon name="compare" size={16} />
            {showEnglish ? 'Hide the English' : 'Show the English next to it'}
          </button>
        )}
      </div>
      {error && <div className="alert alert-red">{error}</div>}
    </div>
  )
}

