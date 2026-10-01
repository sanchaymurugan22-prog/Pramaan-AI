// Design 30 · Admin overview (Stage 9B). Real numbers from GET /api/admin/overview. Admins do not see job
// content: only counts, the computer, account requests and security events.
import { useEffect, useState } from 'react'
import { approveAccountRequest, getAdminOverview, rejectAccountRequest, type AdminOverview } from '../../api'
import { firstName, initials, useAuth } from '../../auth'
import { Icon, type IconName } from '../../components/Icon'
import { Mandala } from '../../components/Mandala'
import { useCounts } from '../../counts'
import { links } from '../../router'
import { fileSize, shortTime, todayLabel } from '../format'

function greeting(): string {
  const hour = new Date().getHours()
  return hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
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

function Meter({ label, value, percent, tone }: { label: string; value: string; percent: number | null; tone: string }) {
  return (
    <div className="stack gap-6">
      <div className="row">
        <span className="grow">{label}</span>
        <strong>{value}</strong>
      </div>
      {percent !== null && (
        <div className="bar" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)}>
          <div className={`bar-fill fill-${tone}`} style={{ width: `${Math.min(100, Math.max(2, percent))}%` }} />
        </div>
      )}
    </div>
  )
}

const EVENT_ICON: Record<string, IconName> = { locked: 'lock', sign_in_failed: 'lock', review_refused: 'shield', policy_changed: 'shield' }

export function AdminOverview() {
  const { user } = useAuth()
  const { refresh } = useCounts()
  const [data, setData] = useState<AdminOverview | null>(null)
  const [error, setError] = useState('')

  const load = () =>
    getAdminOverview()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the overview.'))
  useEffect(() => {
    load()
  }, [])

  async function act(action: () => Promise<unknown>) {
    try {
      await action()
      await load()
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.')
    }
  }

  const c = data?.computer
  const access = data?.requests.filter((r) => r.kind === 'access') ?? []
  const change = data ? data.jobs.this_month - data.jobs.last_month : 0
  const fakes = data ? data.checker.scam + data.checker.changed : 0
  const usedDisk = c ? ((c.disk_total_bytes - c.disk_free_bytes) / c.disk_total_bytes) * 100 : null
  return (
    <main className="page">
      <section className="hero hero-navy" aria-labelledby="admin-hello">
        <div className="hero-mandala-big" aria-hidden="true">
          <Mandala size={340} petals={16} color="var(--navy)" opacity={0.35} />
        </div>
        <div className="hero-body">
          <div className="eyebrow eyebrow-navy">System overview · {todayLabel()}</div>
          <h1 id="admin-hello">
            {greeting()}, {firstName(user.full_name)}
          </h1>
          <p>
            {data === null
              ? 'Loading…'
              : `${c?.encrypted ? 'Everything is healthy.' : 'The database is NOT encrypted.'} ${
                  data.requests.length === 0
                    ? 'No requests are waiting.'
                    : `${data.requests.length} request${data.requests.length === 1 ? ' is' : 's are'} waiting for you.`
                }`}
          </p>
          <div className="row gap-10 mt-8 wrap">
            <a href={links.users} className="btn btn-lg btn-navy">
              <Icon name="user" size={18} strokeWidth={2} />
              Review requests
            </a>
            <a href={links.recordBook} className="btn btn-lg btn-navy-outline">
              <Icon name="hash" size={18} strokeWidth={2} />
              Check record book
            </a>
          </div>
        </div>
      </section>

      {error && <div className="alert alert-red">{error}</div>}

      <div className="stat-grid">
        <Stat
          icon="user"
          tone="navy"
          label="Active users"
          value={data ? String(data.users.total) : '–'}
          note={data ? `${data.users.operator} operators · ${data.users.reviewer} reviewers · ${data.users.admin} admin` : ''}
        />
        <Stat
          icon="history"
          tone="saffron"
          label="Jobs this month"
          value={data ? String(data.jobs.this_month) : '–'}
          note={data ? `${change >= 0 ? '+' : ''}${change} from last month` : ''}
        />
        <Stat icon="award" tone="green" label="Documents signed" value={data ? String(data.records.issued) : '–'} note="All verifiable by QR" />
        <Stat
          icon="shield"
          tone="red"
          label="Fake or edited caught"
          value={data ? String(fakes) : '–'}
          note={data ? `Of ${data.checker.checks} “Is this real?” checks in the app` : ''}
        />
      </div>

      <div className="admin-grid">
        <section className="card card-pad stack gap-14" aria-labelledby="computer-title">
          <div className="row gap-10">
            <h2 id="computer-title" className="grow">
              This computer
            </h2>
            {c && (
              <span className={c.encrypted ? 'chip chip-green chip-xs' : 'chip chip-red chip-xs'}>
                <Icon name={c.encrypted ? 'check' : 'warning'} size={12} strokeWidth={2.4} />
                {c.encrypted ? 'Healthy' : 'Not encrypted'}
              </span>
            )}
          </div>
          {c && (
            <>
              <Meter label="Processor load" value={c.load_percent === null ? '—' : `${c.load_percent}%`} percent={c.load_percent} tone="navy" />
              <Meter label="Memory" value={c.memory_bytes ? `${fileSize(c.memory_bytes)} installed` : 'Unknown'} percent={null} tone="fair" />
              <Meter label="Disk space" value={`${fileSize(c.disk_free_bytes)} free`} percent={usedDisk} tone="good" />
              <p className="row gap-8 small count-ok">
                <Icon name="chip" size={16} />
                AI: {c.ai_label}
              </p>
              <p className="row gap-8 small count-ok">
                <Icon name="wifiOff" size={16} />
                No internet needed · {c.encrypted ? 'database and files encrypted' : 'encryption missing'}
              </p>
            </>
          )}
        </section>

        <section className="card card-pad stack gap-12" aria-labelledby="requests-title">
          <div className="row gap-10">
            <h2 id="requests-title" className="grow">
              Access requests
            </h2>
            {data && data.requests.length > 0 && <span className="chip chip-saffron chip-xs">{data.requests.length} waiting</span>}
          </div>
          {data && data.requests.length === 0 && <p className="muted small">Nobody is waiting.</p>}
          <ul className="clean-list-plain">
            {access.slice(0, 4).map((r) => (
              <li key={r.id} className="request-mini">
                <span className="avatar avatar-sm" aria-hidden="true">
                  {initials(r.full_name)}
                </span>
                <span className="stack grow">
                  <strong>{r.full_name}</strong>
                  <span className="muted small">
                    {[r.role_label, r.division, r.employee_id].filter(Boolean).join(' · ')}
                  </span>
                </span>
                <span className="row gap-6">
                  <button type="button" className="btn btn-green btn-xs" onClick={() => act(() => approveAccountRequest(r.id))}>
                    Approve<span className="sr-only"> {r.full_name}</span>
                  </button>
                  <button type="button" className="btn btn-outline btn-xs" onClick={() => act(() => rejectAccountRequest(r.id))}>
                    Deny<span className="sr-only"> {r.full_name}</span>
                  </button>
                </span>
              </li>
            ))}
          </ul>
          {data && data.requests.length > access.length && (
            <a href={links.users} className="small">
              {data.requests.length - access.length} forgot-password request(s): open Users &amp; access
            </a>
          )}
        </section>

        <section className="card card-pad stack gap-12" aria-labelledby="events-title">
          <div className="row">
            <h2 id="events-title" className="grow">
              Security events
            </h2>
            <a href={links.audit} className="btn btn-link">
              Audit trail
              <Icon name="arrowRight" size={16} strokeWidth={2} />
            </a>
          </div>
          {data && data.security_events.length === 0 && <p className="muted small">No security events.</p>}
          <ul className="clean-list-plain">
            {data?.security_events.map((e) => (
              <li key={e.seq} className="request-mini">
                <span className="note-icon tone-red" aria-hidden="true">
                  <Icon name={EVENT_ICON[e.action] ?? 'shield'} size={18} />
                </span>
                <span className="stack grow">
                  <strong className="small">{e.detail}</strong>
                  <span className="muted small">
                    {shortTime(e.created_at)} · {e.actor}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}
