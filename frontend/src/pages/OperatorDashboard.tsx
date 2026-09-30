import { useEffect, useState, type ReactNode } from 'react'
import { listJobs, pingAi, type AiPing, type Health, type JobSummary } from '../api'
import { firstName, useAuth } from '../auth'
import { Icon, type IconName } from '../components/Icon'
import { Mandala } from '../components/Mandala'
import { JobsTable } from '../components/JobsTable'
import { links } from '../router'
import { aiLabel, todayLabel } from './format'
import { SAMPLE_ATTENTION, SAMPLE_STATS } from './sampleData'

function Hero() {
  const { user } = useAuth()
  return (
    <section className="hero">
      <div className="hero-mandala-big">
        <Mandala size={340} petals={16} color="var(--saffron)" opacity={0.45} />
      </div>
      <div className="hero-mandala-small">
        <Mandala size={220} petals={12} color="var(--green)" opacity={0.35} />
      </div>
      <div className="hero-body">
        <div className="eyebrow">{todayLabel()}</div>
        <h1>Namaste, {firstName(user.full_name)}</h1>
        <p>2 items need your attention. Your ransomware advisory kit was approved at 10:21.</p>
        <div className="row gap-10 mt-8">
          <a href={links.newJob} className="btn btn-lg btn-saffron">
            <Icon name="plus" size={18} strokeWidth={2} />
            New transformation
          </a>
          <button type="button" className="btn btn-lg btn-red-outline">
            <Icon name="siren" size={18} strokeWidth={2} />
            Emergency alert
          </button>
        </div>
      </div>
    </section>
  )
}

function StatCards() {
  return (
    <div className="stat-grid">
      {SAMPLE_STATS.map((s) => (
        <section key={s.label} className="card stat-card">
          <div className={`stat-icon tone-${s.tone}`}>
            <Icon name={s.icon} size={22} />
          </div>
          <div className="stack gap-2">
            <span className="stat-label">{s.label}</span>
            <span className="stat-value">{s.value}</span>
            <span className="stat-note">{s.note}</span>
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
      .then((all) => setJobs(all.slice(0, 5)))
      .catch(() => setJobs(null))
  }, [])

  return (
    <section className="card card-pad stack gap-12">
      <div className="row gap-12">
        <h2>Recent jobs</h2>
        <div className="grow" />
        <a href={links.jobs} className="btn btn-link">
          View all
          <Icon name="arrowRight" size={18} strokeWidth={2} />
        </a>
      </div>
      {jobs === undefined && <p className="muted">Loading…</p>}
      {jobs === null && <p className="muted">Could not load jobs. Is the backend running?</p>}
      {jobs && jobs.length === 0 && (
        <p className="muted">
          No jobs yet. <a href={links.newJob}>Start a new transformation</a>.
        </p>
      )}
      {jobs && jobs.length > 0 && <JobsTable jobs={jobs} />}
    </section>
  )
}

function NeedsAttention() {
  return (
    <section className="card card-pad stack gap-14">
      <h2>Needs your attention</h2>
      <div className="stack gap-10">
        {SAMPLE_ATTENTION.map((item) => (
          <a key={item.title} href="#" className={`attention tone-${item.tone}`} onClick={(e) => e.preventDefault()}>
            <div className="attention-icon">
              <Icon name={item.icon} size={19} />
            </div>
            <span className="stack gap-2 grow">
              <span className="attention-title">{item.title}</span>
              <span className="attention-detail">{item.detail}</span>
            </span>
            <Icon name="chevronRight" size={18} color="var(--muted)" strokeWidth={1.8} />
          </a>
        ))}
      </div>
    </section>
  )
}

type CheckState = 'ok' | 'bad' | 'pending'

function CheckRow({ state, title, detail, children }: { state: CheckState; title: string; detail: string; children?: ReactNode }) {
  const icon: IconName = state === 'ok' ? 'check' : state === 'bad' ? 'cross' : 'clock'
  return (
    <div className="check-row">
      <span className={`check-dot check-${state}`}>
        <Icon name={icon} size={16} strokeWidth={2.4} />
      </span>
      <span className="stack gap-1">
        <span className="check-title">{title}</span>
        <span className="check-detail">{detail}</span>
        {children}
      </span>
    </div>
  )
}

// "This computer" shows LIVE status: backend health and a button to test the AI.
function ThisComputer({ health }: { health: Health | null | undefined }) {
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
    <section className="card card-pad stack gap-14">
      <h2>This computer</h2>
      <div className="stack gap-12">
        <CheckRow
          state={backendState}
          title={health ? 'Backend running' : health === null ? 'Backend not running' : 'Checking backend…'}
          detail={health ? `AI mode: ${health.ai_mode}` : 'Start it with scripts/start.sh'}
        />
        <CheckRow
          state={aiState}
          title={ping?.ok ? `${modelName} ready` : modelName}
          detail={
            pinging ? 'Asking the model to say namaste… (can take a minute)'
            : ping === null ? 'Not tested yet'
            : ping.ok ? `Reply: “${ping.reply}”`
            : ping.error
          }
        >
          <button type="button" className="btn btn-outline btn-sm mt-8" onClick={testAi} disabled={pinging || !health}>
            {pinging ? 'Testing…' : 'Test AI'}
          </button>
        </CheckRow>
        <CheckRow state="pending" title="Encrypted storage" detail="Added in Stage 6" />
      </div>
    </section>
  )
}

export function OperatorDashboard({ health }: { health: Health | null | undefined }) {
  return (
    <main className="page">
      <Hero />
      <StatCards />
      <div className="dash-grid">
        <RecentJobs />
        <div className="stack gap-20">
          <NeedsAttention />
          <ThisComputer health={health} />
        </div>
      </div>
    </main>
  )
}
