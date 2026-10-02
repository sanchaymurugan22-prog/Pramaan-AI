import { useEffect, useState, type ReactNode } from 'react'
import { getDashboard, listJobs, pingAi, type AiPing, type AttentionItem, type Dashboard, type Health, type JobSummary } from '../api'
import { firstName, useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { JobsTable } from '../components/JobsTable'
import { Mandala } from '../components/Mandala'
import { links } from '../router'
import { aiLabel, LANGUAGE_LABELS, shortTime, todayLabel } from './format'
import { t } from '../i18n'

// Design "08 · Operator dashboard". Every number is real (GET /api/dashboard); "hours saved" is an
// estimate and says so.

function Hero({ data }: { data: Dashboard | null }) {
  const { user } = useAuth()
  const count = data?.attention.length ?? 0
  const latest = data?.latest_approval
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-mandala-big" aria-hidden="true">
        <Mandala size={340} petals={16} color="var(--saffron)" opacity={0.45} />
      </div>
      <div className="hero-mandala-small" aria-hidden="true">
        <Mandala size={220} petals={12} color="var(--green)" opacity={0.35} />
      </div>
      <div className="hero-body">
        <div className="eyebrow">{todayLabel()}</div>
        <h1 id="hero-title">{t("Namaste, {full_name}", { full_name: firstName(user.full_name) })}</h1>
        <p>
          {data === null
            ? t("Loading your day…")
            : count === 0
              ? t("Nothing needs your attention right now.")
              : count === 1
                ? t("1 item needs your attention.")
                : t("{count} items need your attention.", { count })}
          {latest && t(" “{title}” was approved at {n}.", { title: latest.title, n: shortTime(latest.at) })}
        </p>
        <div className="row gap-10 mt-8 wrap">
          <a href={links.newJob} className="btn btn-lg btn-saffron">
            <Icon name="plus" size={18} strokeWidth={2} />
            {t("New transformation")}
          </a>
          <a href={links.emergency} className="btn btn-lg btn-red-outline">
            <Icon name="siren" size={18} strokeWidth={2} />
            {t("Emergency alert")}
          </a>
        </div>
      </div>
    </section>
  )
}

function StatCards({ data }: { data: Dashboard | null }) {
  const s = data?.stats
  const change = s ? s.jobs_this_week - s.jobs_last_week : 0
  const languageNames = s?.languages.map((l) => (l === 'en' ? 'English' : LANGUAGE_LABELS[l] ?? l)).join(', ')
  const stats: { label: string; value: string; note: string; icon: IconName; tone: string }[] = [
    {
      label: t("Jobs this week"), value: s ? String(s.jobs_this_week) : '–', icon: 'history', tone: 'saffron',
      note: s ? t("{n}{change} from last week", { n: change >= 0 ? '+' : '', change: change }) : '',
    },
    {
      label: t("Outputs approved"), value: s ? String(s.outputs_approved) : '–', icon: 'shieldCheck', tone: 'green',
      note: s ? t("Across {formats_approved} format{n}", { formats_approved: s.formats_approved, n: s.formats_approved === 1 ? '' : 's' }) : '',
    },
    { label: t("Hours saved (est.)"), value: s ? String(s.hours_saved) : '–', note: t("Compared with manual writing"), icon: 'clock', tone: 'navy' },
    { label: t("Languages used"), value: s ? String(s.languages.length) : '–', note: languageNames ?? '', icon: 'globe', tone: 'saffron' },
  ]
  return (
    <div className="stat-grid">
      {stats.map((stat) => (
        <section key={stat.label} className="card stat-card" aria-label={t(stat.label)}>
          <div className={`stat-icon tone-${stat.tone}`} aria-hidden="true">
            <Icon name={stat.icon} size={22} />
          </div>
          <div className="stack gap-2">
            <span className="stat-label">{t(stat.label)}</span>
            <span className="stat-value">{stat.value}</span>
            <span className="stat-note">{stat.note}</span>
          </div>
        </section>
      ))}
    </div>
  )
}

function RecentJobs() {
  // undefined = loading, null = could not load
  const [jobs, setJobs] = useState<JobSummary[] | null | undefined>(undefined)
  useEffect(() => {
    listJobs()
      .then((all) => setJobs(all.slice(0, 6)))
      .catch(() => setJobs(null))
  }, [])

  return (
    <section className="card card-pad stack gap-12" aria-labelledby="recent-title">
      <div className="row gap-12">
        <h2 id="recent-title">{t("Recent jobs")}</h2>
        <div className="grow" />
        <a href={links.jobs} className="btn btn-link">
          {t("View all")}
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </a>
      </div>
      {jobs === undefined && <p className="muted">{t("Loading…")}</p>}
      {jobs === null && <p className="muted">{t("Could not load jobs. Is the backend running?")}</p>}
      {jobs && jobs.length === 0 && (
        <p className="muted">
          {t("No jobs yet.")} <a href={links.newJob}>{t("Start a new transformation")}</a>.
        </p>
      )}
      {jobs && jobs.length > 0 && <JobsTable jobs={jobs} caption={t("Recent jobs")} />}
    </section>
  )
}

const ATTENTION_LOOK: Record<AttentionItem['kind'], { tone: string; icon: IconName }> = {
  sent_back: { tone: 'red', icon: 'arrowLeft' },
  leak: { tone: 'red', icon: 'lock' },
  failed: { tone: 'red', icon: 'warning' },
  unlinked: { tone: 'yellow', icon: 'warning' },
  watch: { tone: 'saffron', icon: 'folder' },
  ready: { tone: 'green', icon: 'send' },
}

function attentionHref(item: AttentionItem): string {
  if (item.kind === 'watch') return item.job_id ? links.safety(item.job_id) : links.watch
  return item.job_id ? links.job(item.job_id) : links.jobs
}

function NeedsAttention({ data }: { data: Dashboard | null }) {
  return (
    <section className="card card-pad stack gap-14" aria-labelledby="attention-title">
      <h2 id="attention-title">{t("Needs your attention")}</h2>
      {data === null && <p className="muted">{t("Loading…")}</p>}
      {data && data.attention.length === 0 && <p className="muted">{t("All clear. Nothing is waiting for you.")}</p>}
      <ul className="clean-list-plain stack gap-10">
        {data?.attention.map((item) => {
          const look = ATTENTION_LOOK[item.kind]
          return (
            <li key={`${item.kind}-${item.job_id}`}>
              <a href={attentionHref(item)} className={`attention tone-${look.tone}`}>
                <span className="attention-icon" aria-hidden="true">
                  <Icon name={look.icon} size={19} />
                </span>
                <span className="stack gap-2 grow">
                  <span className="attention-title">{t(item.title)}</span>
                  <span className="attention-detail">{t(item.detail)}</span>
                </span>
                <Icon name="chevronRight" size={18} color="var(--muted)" strokeWidth={1.8} />
              </a>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

type CheckState = 'ok' | 'bad' | 'pending'

function CheckRow({ state, title, detail, children }: { state: CheckState; title: string; detail: string; children?: ReactNode }) {
  const icon: IconName = state === 'ok' ? 'check' : state === 'bad' ? 'cross' : 'clock'
  const word = state === 'ok' ? 'OK' : state === 'bad' ? t("Problem") : t("Not checked")
  return (
    <div className="check-row">
      <span className={`check-dot check-${state}`}>
        <Icon name={icon} size={16} strokeWidth={2.4} />
        <span className="sr-only">{word}: </span>
      </span>
      <span className="stack gap-1">
        <span className="check-title">{title}</span>
        <span className="check-detail">{detail}</span>
        {children}
      </span>
    </div>
  )
}

// "This computer" shows LIVE status: backend health, a button to test the AI, and the encryption.
function ThisComputer({ health, data }: { health: Health | null | undefined; data: Dashboard | null }) {
  const [ping, setPing] = useState<AiPing | null>(null)
  const [pinging, setPinging] = useState(false)

  async function testAi() {
    setPinging(true)
    setPing(null)
    try {
      setPing(await pingAi())
    } catch {
      setPing({ ok: false, error: 'Could not reach the backend.', ai_mode: '', model: '', base_url: '' })
    } finally {
      setPinging(false)
    }
  }

  const backendState: CheckState = health === undefined ? 'pending' : health ? 'ok' : 'bad'
  const aiState: CheckState = ping === null ? 'pending' : ping.ok ? 'ok' : 'bad'
  const modelName = aiLabel(health?.ai_mode)

  return (
    <section className="card card-pad stack gap-14" aria-labelledby="computer-title">
      <h2 id="computer-title">{t("This computer")}</h2>
      <div className="stack gap-12">
        <CheckRow
          state={backendState}
          title={health ? t("Fully offline") : health === null ? t("Backend not running") : t("Checking backend…")}
          detail={health ? t("No internet connection needed") : t("Start it with scripts/start.sh")}
        />
        <CheckRow
          state={aiState}
          title={ping?.ok ? t("{modelName} ready", { modelName: modelName }) : modelName}
          detail={
            pinging ? t("Asking the model to say namaste… (can take a minute)")
            : ping === null ? t("Not tested yet")
            : ping.ok ? t("Reply: “{reply}”", { reply: ping.reply })
            : ping.error
          }
        >
          <button type="button" className="btn btn-outline btn-sm mt-8" onClick={testAi} disabled={pinging || !health}>
            {pinging ? t("Testing…") : t("Test AI")}
          </button>
        </CheckRow>
        <CheckRow
          state={data === null ? 'pending' : data.encrypted ? 'ok' : 'bad'}
          title={t("Encrypted storage")}
          detail={data === null ? t("Checking…") : data.encrypted ? t("Database and files locked") : t("The database is NOT encrypted")}
        />
      </div>
    </section>
  )
}

export function OperatorDashboard({ health }: { health: Health | null | undefined }) {
  const [data, setData] = useState<Dashboard | null>(null)
  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(() => setData(null))
  }, [])

  return (
    <main className="page">
      <Hero data={data} />
      <StatCards data={data} />
      <div className="dash-grid">
        <RecentJobs />
        <div className="stack gap-20">
          <NeedsAttention data={data} />
          <ThisComputer health={health} data={data} />
        </div>
      </div>
    </main>
  )
}
