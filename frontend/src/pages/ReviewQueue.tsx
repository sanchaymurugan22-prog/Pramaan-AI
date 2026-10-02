// Design 24 · Reviewer dashboard (review queue). Jobs waiting for review, emergency alerts first, then
// oldest first. "Review" opens the review page (design 25), where the Reviewer comments on lines,
// approves and signs, or sends the job back with notes.
import { useEffect, useState } from 'react'
import { getReviewQueue, type QueueItem, type ReviewQueue as Queue } from '../api'
import { firstName, useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { Mandala } from '../components/Mandala'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { jobNo, LANGUAGE_LABELS, todayLabel } from './format'
import { t } from '../i18n'

function waitingFor(iso: string | null, now: number): string {
  if (!iso) return ''
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.round(minutes / 60)
  return hours < 48 ? `${hours} hour${hours === 1 ? '' : 's'}` : `${Math.round(hours / 24)} days`
}

// What the automatic checks found, in one chip (icon + words)
function checksChip(item: QueueItem) {
  const notes = item.warnings + item.leaks + item.public_problems + (item.numbers_match ? 0 : 1) + (item.fact_sheet_ok ? 0 : 1)
  if (notes === 0)
    return (
      <span className="chip chip-green chip-xs">
        <Icon name="check" size={12} strokeWidth={2.4} />
        {t("All checks passed")}
      </span>
    )
  return (
    <span className="chip chip-yellow chip-xs">
      <Icon name="warning" size={12} strokeWidth={2.4} />
      {notes} {t("note")}{notes === 1 ? '' : 's'} {t("to check")}
    </span>
  )
}

function Stat({ icon, tone, label, value, note }: { icon: IconName; tone: string; label: string; value: string; note: string }) {
  return (
    <section className="card stat-card" aria-label={label}>
      <div className={`stat-icon tone-${tone}`} aria-hidden="true">
        <Icon name={icon} size={22} />
      </div>
      <div className="stack gap-2">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        <span className="stat-note">{note}</span>
      </div>
    </section>
  )
}

export function ReviewQueue() {
  const { user } = useAuth()
  const [queue, setQueue] = useState<Queue | null>(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<'all' | 'emergency' | 'kits'>('all')
  const [now, setNow] = useState(0) // when the queue was loaded, for "Waiting 8 min"

  useEffect(() => {
    let timer: number | undefined
    const load = () =>
      getReviewQueue()
        .then((q) => {
          setNow(Date.now())
          setQueue(q)
          setError('')
        })
        .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the review queue.")))
        .finally(() => {
          timer = window.setTimeout(load, 30000) // new submissions appear by themselves
        })
    load()
    return () => window.clearTimeout(timer)
  }, [])

  const waiting = queue?.waiting ?? []
  const emergencies = waiting.filter((w) => w.fast_track).length
  const shown = waiting.filter((w) => filter === 'all' || (filter === 'emergency') === w.fast_track)
  const s = queue?.stats

  return (
    <main className="page">
      <section className="hero hero-green">
        <div className="hero-mandala-big" aria-hidden="true">
          <Mandala size={340} petals={16} color="var(--green)" opacity={0.4} />
        </div>
        <div className="hero-body">
          <div className="eyebrow eyebrow-green">{todayLabel()}</div>
          <h1>{t("Namaste, {full_name}", { full_name: firstName(user.full_name) })}</h1>
          <p>
            {queue === null
              ? t("Loading the review queue…")
              : waiting.length === 0
                ? t("Nothing is waiting for review.")
                : `${waiting.length} kit${waiting.length === 1 ? ' is' : 's are'} waiting for you` +
                  (emergencies ? `, including ${emergencies} emergency alert${emergencies === 1 ? '' : 's'} on fast track.` : '.')}
          </p>
          {queue && (
            <div className="row gap-8 wrap">
              <span className={queue.signer.ready ? 'chip chip-green' : 'chip chip-red'}>
                <Icon name="usb" size={14} strokeWidth={2.2} />
                {queue.signer.ready ? (queue.signer.kind === 'test' ? t("Test signing key ready") : t("DSC token connected")) : t("Signing key not ready")}
              </span>
              {user.emergency_duty && (
                <span className="chip chip-saffron">
                  <Icon name="siren" size={14} strokeWidth={2.2} />
                  {t("On duty for emergencies")}
                </span>
              )}
            </div>
          )}
        </div>
      </section>

      <div className="stat-grid">
        <Stat
          icon="history"
          tone="green"
          label={t("Waiting for you")}
          value={s ? String(s.waiting) : '–'}
          note={s?.oldest_submitted_at ? `Oldest: ${waitingFor(s.oldest_submitted_at, now)}` : 'All clear'}
        />
        <Stat
          icon="award"
          tone="navy"
          label={t("Signed today")}
          value={s ? String(s.signed_today) : '–'}
          note={s?.signed_today ? `${s.files_in_last_kit} files in the last kit` : 'None yet'}
        />
        <Stat
          icon="clock"
          tone="saffron"
          label={t("Average review time")}
          value={s?.average_review_minutes !== null && s ? `${s.average_review_minutes} min` : '–'}
          note="This week"
        />
        <Stat icon="arrowLeft" tone="red" label={t("Sent back this week")} value={s ? String(s.sent_back_this_week) : '–'} note="With notes to operators" />
      </div>

      {error && <div className="alert alert-red">{error}</div>}

      <div className="dash-grid">
        <section className="card card-pad stack gap-14" aria-labelledby="queue-title">
          <div className="row gap-10 wrap">
            <h2 id="queue-title" className="grow">
              {t("Review queue")}
            </h2>
            <div className="segmented" role="group" aria-label={t("Show")}>
              {(['all', 'emergency', 'kits'] as const).map((f) => (
                <button key={f} type="button" aria-pressed={filter === f} className={filter === f ? 'is-on' : ''} onClick={() => setFilter(f)}>
                  {{ all: 'All', emergency: 'Emergency', kits: 'Kits' }[f]}
                </button>
              ))}
            </div>
          </div>
          {queue && shown.length === 0 && <p className="muted">{t("Nothing here. New jobs appear by themselves.")}</p>}
          <ul className="clean-list-plain stack gap-10">
            {shown.map((item) => (
              <li key={item.id} className={item.fast_track ? 'queue-item is-emergency' : 'queue-item'}>
                <div className="stack gap-6 grow queue-text">
                  <div className="row gap-8 wrap">
                    {item.fast_track ? (
                      <span className="chip chip-red chip-xs">
                        <Icon name="bolt" size={12} strokeWidth={2.4} />
                        {t("Emergency")}
                      </span>
                    ) : (
                      item.tlp && <TlpLabel tlp={item.tlp} />
                    )}
                    <strong className="queue-title">
                      {t(item.title)}
                      {item.version > 1 && ` · v${item.version}`}
                    </strong>
                  </div>
                  <div className="row gap-10 wrap small muted">
                    <span>{t("From {value}", { value: item.submitted_by ?? item.owner ?? t("an Operator") })}</span>
                    <span>
                      {t("{length} output{value} × {value2}", { length: item.outputs.length, value: item.outputs.length === 1 ? '' : 's', value2: item.languages.map((l) => LANGUAGE_LABELS[l] ?? l).join(' · ') })}</span>
                    <span className="mono">{jobNo(item.id)}</span>
                    {checksChip(item)}
                  </div>
                  {item.submit_notes && <span className="small">“{item.submit_notes}”</span>}
                  {!item.can_review && <span className="small over-limit">{t("You worked on this job: another Reviewer must check it.")}</span>}
                </div>
                <div className="stack gap-6 end-items">
                  <span className="small muted">{t("Waiting {submitted_at}", { submitted_at: waitingFor(item.submitted_at, now) })}</span>
                  {item.can_review ? (
                    <a href={links.reviewJob(item.id)} className={item.fast_track ? 'btn btn-sm btn-red' : 'btn btn-sm btn-green-outline'}>
                      {t("Review")}<span className="sr-only"> {t(item.title)}</span>
                      <Icon name="arrowRight" size={16} strokeWidth={2} />
                    </a>
                  ) : (
                    <a href={links.job(item.id)} className="btn btn-sm btn-outline">
                      {t("View")}<span className="sr-only"> {t(item.title)}</span>
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <div className="stack gap-20">
          {queue && (
            <section className="card card-pad stack gap-12" aria-labelledby="key-title">
              <div className="row gap-12">
                <span className="stat-icon tone-green" aria-hidden="true">
                  <Icon name="usb" size={20} />
                </span>
                <span className="stack grow">
                  <h2 id="key-title">{queue.signer.kind === 'test' ? t("Signing key") : t("DSC token")}</h2>
                  <span className="muted small">{t(queue.signer.label)} · {queue.signer.holder}</span>
                </span>
                <span className={queue.signer.ready ? 'chip chip-green chip-xs' : 'chip chip-red chip-xs'}>{queue.signer.ready ? t("Ready") : t("Not ready")}</span>
              </div>
              <dl className="facts-table">
                {queue.signer.key_id && (
                  <div>
                    <dt>{t("Key fingerprint")}</dt>
                    <dd className="mono">{queue.signer.key_id}</dd>
                  </div>
                )}
                <div>
                  <dt>{t("Signing count today")}</dt>
                  <dd>{t("{signed_today} kits", { signed_today: queue.stats.signed_today })}</dd>
                </div>
              </dl>
              {queue.signer.error && <p className="small over-limit">{queue.signer.error}</p>}
            </section>
          )}
          <section className="card card-pad stack gap-12" aria-labelledby="today-title">
            <div className="row">
              <h2 id="today-title" className="grow">
                {t("Signed today")}
              </h2>
              <a href={links.records} className="btn btn-link">
                {t("All records")}
                <Icon name="arrowRight" size={16} strokeWidth={2} />
              </a>
            </div>
            {queue && queue.signed_today.length === 0 && <p className="muted small">{t("Nothing signed yet today.")}</p>}
            <ul className="clean-list-plain">
              {queue?.signed_today.map((r) => (
                <li key={r.record_no} className="signed-row">
                  <Icon name="award" size={18} color="var(--green-dark)" />
                  <span className="grow">{r.title}</span>
                  <span className="mono small muted">{r.record_no}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </main>
  )
}
