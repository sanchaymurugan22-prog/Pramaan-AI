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
import { locale, t } from '../i18n'

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
      title: t("Every line traced to source"),
      detail: t("{linked} of {length} sentences linked to a fact", { linked: linked, length: claims.length }),
    },
    {
      state: job.consistency?.ok === false ? 'bad' : 'ok',
      title: t("Facts match across outputs"),
      detail: job.consistency?.ok === false ? t("{length} number(s) differ between outputs", { length: job.consistency.mismatches.length }) : t("Numbers, dates and names agree"),
    },
    {
      state: leaks ? 'bad' : 'ok',
      title: t("Sensitive details hidden"),
      detail: leaks ? t("{leaks} private value(s) found in an output", { leaks: leaks }) : t("{hidden} detail{n} hidden as chosen", { hidden: hidden, n: hidden === 1 ? '' : 's' }),
    },
    {
      state: job.public_check?.ok === false ? 'warn' : 'ok',
      title: t("Public-release wording"),
      detail: job.public_check?.ok === false ? t("{length} phrase(s) to soften", { length: job.public_check.problems.length }) : t("No panic wording or shouting"),
    },
    {
      state: suspicious.length > removed ? 'warn' : 'ok',
      title: t("No hidden instructions in sources"),
      detail: suspicious.length === 0 ? t("None found") : t("{length} found, {removed} removed before the AI read the source", { length: suspicious.length, removed: removed }),
    },
    {
      state: job.fact_sheet_check?.ok === false ? 'bad' : 'ok',
      title: t("Fact sheet matches the source"),
      detail: job.fact_sheet_check ? t("{found} of {total} quotes found", { found: job.fact_sheet_check.found, total: job.fact_sheet_check.total }) : '—',
    },
    { state: job.tlp ? 'ok' : 'warn', title: t("Sharing label applied"), detail: job.tlp ? t("TLP:{tlp} on every file", { tlp: job.tlp }) : t("No label chosen") },
  ]
  // Stage 8: translations keep every value, and a native speaker has read each one
  const translations = job.outputs.filter((o) => o.language !== 'en')
  if (translations.length > 0) {
    const changed = translations.filter((o) => (o.quality?.translation?.changed ?? []).length > 0)
    const checked = translations.filter((o) => o.translation?.native_check.checked)
    checks.push(
      {
        state: changed.length ? 'bad' : 'ok',
        title: t("Numbers survive translation"),
        detail: changed.length
          ? t("Changed in {n}", { n: changed.map((o) => `${o.label} (${o.language_label})`).join(', ') })
          : t("Every number, date and code is the same in {length} translation{n}", { length: translations.length, n: translations.length === 1 ? '' : 's' }),
      },
      {
        state: checked.length === translations.length ? 'ok' : 'warn',
        title: t("Checked by a native speaker"),
        detail: t("{length} of {length2} translations ticked (needed before signing)", { length: checked.length, length2: translations.length }),
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
      <h2 id="checks-title">{t("Automatic checks")}</h2>
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
          {t("{value} · Job {id} v{version}{value2}", { value: eyebrow ?? t("Review"), id: jobNo(job.id), version: job.version, value2: submitted?.by && t(" · from {by}", { by: submitted.by }) })}</div>
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
  const [mentioned, setMentioned] = useState<string[]>([]) // people named with @ in the last comment
  const [busy, setBusy] = useState(false)
  const [signing, setSigning] = useState(false)
  const [showEnglish, setShowEnglish] = useState(false) // Stage 8: a translation next to its English
  const languages = useLanguages()

  const reload = useCallback(
    () =>
      getJob(jobId)
        .then(setJob)
        .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the job."))),
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
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>
  }
  if (job.status !== 'in_review') {
    return (
      <main className="page">
        <ReviewHead job={job} />
        <div className="alert alert-yellow">
          {t("This job is not waiting for review (it is")} {job.status.replace('_', ' ')}). <a href={links.job(job.id)}>{t("Open its results")}</a> {t("or go back to the")} <a href={links.review}>{t("review queue")}</a>.
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
      const saved = await addComment(job!.id, { output_id: active.id, sentence_id: sentence.id, path: sentence.path, quote: sentence.text, text: comment })
      setComment('')
      setMentioned(saved.mentioned)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not save the comment."))
    } finally {
      setBusy(false)
    }
  }

  // Stage 8: an alert in 22 languages; the Reviewer confirms native speakers read every one (each is recorded)
  async function tickAll() {
    const ok = window.confirm(
      t("Tick “Checked by a native speaker” for all {toCheck} translations?\n\nOnly do this if a native speaker of each language has read it against the English.", { toCheck: toCheck }),
    )
    if (!ok || !job) return
    try {
      setJob(await tickAllTranslations(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not tick them."))
    }
  }

  async function takeBack(id: number) {
    try {
      await takeBackComment(job!.id, id)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not take it back."))
    }
  }

  return (
    <main className="page">
      <ReviewHead job={job}>
        {job.tlp && <TlpLabel tlp={job.tlp} />}
        {job.version > 1 && (
          <a className="btn btn-outline" href={links.compare(job.id)}>
            <Icon name="compare" size={18} strokeWidth={2} />
            {t("Compare with v")}{job.version - 1}
          </a>
        )}
        {!mine && (
          <>
            <a className="btn btn-red-outline" href={links.sendBack(job.id)}>
              <Icon name="arrowLeft" size={18} strokeWidth={2} />
              {t("Send back")}
            </a>
            <button type="button" className="btn btn-green" onClick={() => setSigning(true)}>
              <Icon name="award" size={18} strokeWidth={2} />
              {t("Approve & sign")}
            </button>
          </>
        )}
      </ReviewHead>

      {mine && (
        <div className="alert alert-yellow" role="status">
          {t("You worked on this job, so you cannot review it. Another Reviewer must check it (separation of duties).")}
        </div>
      )}
      {error && <div className="alert alert-red">{error}</div>}

      <div className="review-grid">
        <nav className="card card-pad-sm stack gap-8 review-outputs" aria-label={t("Outputs")}>
          <h2 className="notes-title">
            {t("{length} output{value}", { length: job.outputs.length, value: job.outputs.length === 1 ? '' : 's' })}</h2>
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
                  {t(o.label)}
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
                  {ok ? t("checks passed") : o.language !== 'en' && !o.translation?.native_check.checked ? t("needs a native-speaker check") : t("has notes to check")}
                </span>
              </button>
            )
          })}
          <span className="muted small">
            {job.languages.length > 1
              ? t("{length} languages · {toCheck} translation{n} to check", { length: job.languages.length, toCheck: toCheck, n: toCheck === 1 ? '' : 's' })
              : t("English")}
          </span>
          {!mine && toCheck > 1 && (
            <button type="button" className="btn btn-outline btn-xs" onClick={tickAll}>
              <Icon name="check" size={16} strokeWidth={2.2} />
              {t("Tick all")} {toCheck} {t("translations")}
            </button>
          )}
        </nav>

        <section className="card card-pad stack gap-14" aria-label={t(active.label)}>
          {active.translation && (
            <NativeCheckBox job={job} output={active} canTick={!mine} onChange={setJob} english={english}
                            showEnglish={showEnglish} onShowEnglish={setShowEnglish} />
          )}
          <TraceProvider value={{ outputId: active.id, byPath, facts, selection, select: setSelection }}>
            {active.content && showEnglish && english?.content ? (
              <div className="compare-languages">
                <div lang="en">
                  <span className="section-label">{t("English (v{version})", { version: english.version })}</span>
                  <OutputBody type={english.type} content={english.content}
                              meta={{ title: job.title, tlp: job.tlp, recordNo: null, audience: job.settings?.audience ?? '', quality: english.quality, office: job.office_name }} />
                </div>
                <div lang={active.language} dir={activeLang?.rtl ? 'rtl' : undefined}>
                  <span className="section-label">{activeLang?.native ?? active.language}</span>
                  <OutputBody type={active.type} content={active.content}
                              meta={{ title: job.title, tlp: job.tlp, recordNo: null, audience: job.settings?.audience ?? '', quality: active.quality, office: job.office_name }} />
                </div>
              </div>
            ) : active.content ? (
              <div lang={active.language} dir={activeLang?.rtl ? 'rtl' : undefined}>
                <OutputBody
                  type={active.type}
                  content={active.content}
                  meta={{ title: job.title, tlp: job.tlp, recordNo: null, audience: job.settings?.audience ?? '', quality: active.quality, office: job.office_name }}
                />
              </div>
            ) : (
              <p className="muted">{t("This output has no text.")}</p>
            )}
          </TraceProvider>

          {!mine && (
            <div className="comment-box" aria-live="polite">
              {sentence ? (
                <>
                  <span className="small muted">
                    {t("Comment on the selected line · {label} · {label2}", { label: t(active.label), label2: sentence.label })}</span>
                  <q className="comment-quote">{sentence.text}</q>
                  <label className="sr-only" htmlFor="line-comment">
                    {t("Your comment")}
                  </label>
                  <textarea
                    id="line-comment"
                    className="input textarea"
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder={t("e.g. Fine to keep as an analyst note. / This district is not in the source.")}
                  />
                  <span className="small muted">{t("Type @ and a name (e.g. @Priya) to notify someone.")}</span>
                  <div className="row gap-10">
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setSelection(NO_SELECTION)}>
                      {t("Cancel")}
                    </button>
                    <button type="button" className="btn btn-green btn-sm" onClick={send} disabled={busy || comment.trim().length < 2}>
                      {t("Add comment")}
                    </button>
                  </div>
                </>
              ) : (
                <span className="small muted">{t("Click any sentence to see its source and to comment on it.")}</span>
              )}
              {mentioned.length > 0 && (
                <span className="small" role="status">
                  <Icon name="bell" size={14} /> {t("Notified: {names}", { names: mentioned.join(', ') })}
                </span>
              )}
            </div>
          )}

          {here.length > 0 && (
            <ul className="clean-list-plain stack gap-10" aria-label={t("Comments on this output")}>
              {here.map((c) => (
                <li key={c.id} className="comment">
                  <span className="avatar avatar-sm" aria-hidden="true">
                    {(c.author ?? '?').split(' ').map((w) => w[0]).join('').slice(0, 2)}
                  </span>
                  <span className="stack gap-2 grow">
                    <span className="small">
                      <strong>{c.author_id === user.id ? t("Your comment") : c.author}</strong> · {shortTime(c.created_at)}
                    </span>
                    {c.quote && <q className="comment-quote small">{c.quote}</q>}
                    <span>{c.text}</span>
                  </span>
                  {c.author_id === user.id && (
                    <button type="button" className="btn btn-link btn-xs" onClick={() => takeBack(c.id)}>
                      {t("Take back")}<span className="sr-only"> {t("this comment")}</span>
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="stack gap-16 review-side" aria-label={t("Checks and source")}>
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
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the job.")))
  }, [jobId])

  if (!job) return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>
  const record = job.record
  if (!record) {
    return (
      <main className="page">
        <div className="alert alert-yellow">
          {t("This job is not signed.")} <a href={links.reviewJob(job.id)}>{t("Back to the review")}</a>
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
            {t("{length} file{value} signed", { length: record.files.length, value: record.files.length === 1 ? '' : 's' })}</h1>
          <p className="muted">
            {t("{title} · v{version} · signed {value}", { title: job.title, version: record.version, value: new Date(record.issued_at).toLocaleString(locale(), { dateStyle: 'medium', timeStyle: 'short' }) })}</p>
        </div>
        <div className="signed-record">
          <img src={recordQrUrl(record.record_no)} alt={t("QR code for record {record_no}", { record_no: record.record_no })} width={120} height={120} />
          <dl className="facts-table grow">
            <div>
              <dt>{t("Record")}</dt>
              <dd className="mono">{record.record_no}</dd>
            </div>
            <div>
              <dt>{t("Fingerprint")}</dt>
              <dd className="mono">SHA-256 {shortHash(record.fingerprint)}</dd>
            </div>
            <div>
              <dt>{t("Signed by")}</dt>
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
              <span className="check-title">{t("{owner} has been notified", { owner: owner })}</span>
              <span className="check-detail">{t("They can now save the signed campaign kit")}</span>
            </span>
          </li>
          <li className="check-row">
            <span className="check-dot check-ok" aria-hidden="true">
              <Icon name="check" size={16} strokeWidth={2.4} />
            </span>
            <span className="stack gap-1">
              <span className="check-title">{t("Record {record_no} added to the record book", { record_no: record.record_no })}</span>
              <span className="check-detail">{replaces ? t("It says which earlier record it replaces; the chain is intact") : t("Linked to the record before it; the chain is intact")}</span>
            </span>
          </li>
          <li className="check-row">
            <span className="check-dot check-pending" aria-hidden="true">
              <Icon name="clock" size={16} strokeWidth={2.4} />
            </span>
            <span className="stack gap-1">
              <span className="check-title">{t("Public posts stay as drafts")}</span>
              <span className="check-detail">{t("Released only by your team’s publishing process")}</span>
            </span>
          </li>
        </ul>
        <div className="row gap-10 wrap center-self">
          <a className="btn btn-lg btn-green" href={links.review}>
            <Icon name="arrowLeft" size={18} strokeWidth={2} />
            {t("Back to review queue")}
          </a>
          <a className="btn btn-lg btn-outline" href={links.records}>
            {t("Signed records")}
          </a>
          <a className="btn btn-lg btn-outline" href={links.check}>
            <Icon name="scan" size={18} />
            {t("Check a copy")}
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
      setError(e instanceof Error ? e.message : t("Could not save the check."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={check.checked ? 'notice notice-green stack gap-8' : 'notice notice-yellow stack gap-8'}>
      <span className="row gap-8">
        <Icon name={check.checked ? 'shieldCheck' : 'warning'} size={20} />
        <strong>{check.checked ? t("Checked by a native speaker") : t("Machine translated - needs a native-speaker check")}</strong>
      </span>
      <span className="small">
        {t("Translated from the English (version {value}) by {engine}. {value2}", { value: output.translation!.source_version ?? '?', engine: output.translation!.engine, value2: changed.length > 0
          ? t(" {length} part{n} changed a number or code: see the red marks.", { length: changed.length, n: changed.length === 1 ? '' : 's' })
          : t(" Every number, date and code is the same as in the English.") })}</span>
      <div className="row gap-12 wrap">
        {canTick && (
          <label className="check-row">
            <input type="checkbox" checked={check.checked} disabled={busy || job.status !== 'in_review'}
                   onChange={(e) => tick(e.target.checked)} />
            <span>{t("I have read this {language_label} text against the English: it says the same thing", { language_label: output.language_label })}</span>
          </label>
        )}
        {check.checked && check.by && <span className="small">{check.by}{check.at ? ` · ${shortTime(check.at)}` : ''}</span>}
        {english && (
          <button type="button" className="btn btn-outline btn-xs" aria-pressed={showEnglish} onClick={() => onShowEnglish(!showEnglish)}>
            <Icon name="compare" size={16} />
            {showEnglish ? t("Hide the English") : t("Show the English next to it")}
          </button>
        )}
      </div>
      {error && <div className="alert alert-red">{error}</div>}
    </div>
  )
}

