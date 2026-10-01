// Design 33 · Audit trail. Admin only. Every row carries the SHA-256 of the row before it;
// "Verify chain" works every hash out again and shows the first row that was changed or deleted.
import { useEffect, useState } from 'react'
import { getAudit, verifyAuditChain, type AuditCategory, type AuditEntry,
  type AuditPage, type ChainCheck } from '../../api'
import { Icon, type IconName } from '../../components/Icon'

const PAGE_SIZE = 50
const CATEGORIES: { key: AuditCategory | ''; label: string }[] = [
  { key: '', label: 'All' },
  { key: 'content', label: 'Content' },
  { key: 'review', label: 'Review' },
  { key: 'security', label: 'Security' },
  { key: 'users', label: 'Users' },
  { key: 'system', label: 'System' },
]
const ICONS: Record<AuditCategory, { icon: IconName; tone: string }> = {
  content: { icon: 'pencil', tone: 'saffron' },
  review: { icon: 'shieldCheck', tone: 'green' },
  security: { icon: 'lock', tone: 'red' },
  users: { icon: 'user', tone: 'navy' },
  system: { icon: 'chip', tone: 'neutral' },
}

function when(iso: string): { time: string; date: string } {
  const d = new Date(iso)
  return {
    time: d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
    date: d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
  }
}

export function AuditTrail() {
  const [category, setCategory] = useState<AuditCategory | ''>('')
  const [text, setText] = useState('')
  const [query, setQuery] = useState('') // the search text, applied after typing stops
  const [actor, setActor] = useState('')
  const [days, setDays] = useState(0)
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<AuditPage | null>(null)
  const [check, setCheck] = useState<ChainCheck | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text), 300)
    return () => window.clearTimeout(timer)
  }, [text])

  useEffect(() => {
    getAudit({ category, q: query, actor, days, offset, limit: PAGE_SIZE })
      .then((p) => {
        setPage(p)
        setError('')
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the audit trail.'))
  }, [category, query, actor, days, offset, reloadCount])

  function filter(change: () => void) {
    change()
    setOffset(0)
  }

  async function verify() {
    setChecking(true)
    try {
      setCheck(await verifyAuditChain())
      setReloadCount((n) => n + 1) // the check itself is logged: show it
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not check the chain.')
    } finally {
      setChecking(false)
    }
  }

  const total = page?.total ?? 0
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-4">
          <div className="eyebrow eyebrow-navy">Admin</div>
          <h1>Audit trail</h1>
          <p className="muted">A permanent record of every action. Entries cannot be edited or deleted.</p>
        </div>
        <div className="grow" />
        {page && page.entries.length > 0 && (
          <a className="btn btn-outline" href={csvHref(page.entries)} download="pramaan-audit-log.csv">
            <Icon name="download" size={18} strokeWidth={2} />
            Export log with hashes
          </a>
        )}
        <button type="button" className="btn btn-navy" onClick={verify} disabled={checking}>
          <Icon name="shieldCheck" size={18} strokeWidth={2} />
          {checking ? 'Checking…' : 'Verify chain'}
        </button>
      </div>

      {check?.ok && (
        <div className="alert alert-green row gap-8" role="status">
          <Icon name="check" size={18} strokeWidth={2.4} />
          Chain intact: all {check.checked} rows checked, every hash matches. Last hash{' '}
          <span className="mono">{check.last_hash.slice(0, 16)}…</span>
        </div>
      )}
      {check && !check.ok && (
        <div className="alert alert-red stack gap-6" role="alert">
          <strong className="row gap-8">
            <Icon name="warning" size={18} strokeWidth={2.2} />
            Chain BROKEN at row {check.broken.seq}. The {check.checked} rows before it are intact.
          </strong>
          <span>{check.broken.reason}</span>
          <span className="small">
            Row {check.broken.seq} now says: {check.broken.entry.actor} · {check.broken.entry.detail} ({check.broken.entry.created_at})
          </span>
        </div>
      )}
      {error && <div className="alert alert-red">{error}</div>}

      <div className="row gap-12 wrap">
        <label className="search audit-search">
          <span className="search-icon">
            <Icon name="search" size={18} strokeWidth={1.8} />
          </span>
          <input type="search" aria-label="Search actions or people" placeholder="Search actions or people" value={text} onChange={(e) => filter(() => setText(e.target.value))} />
        </label>
        <div className="segmented">
          {CATEGORIES.map((c) => (
            <button key={c.key} type="button" className={category === c.key ? 'is-on' : ''} onClick={() => filter(() => setCategory(c.key))}>
              {c.label}
            </button>
          ))}
        </div>
        <div className="grow" />
        <select className="input input-sm" aria-label="When" value={days} onChange={(e) => filter(() => setDays(Number(e.target.value)))}>
          <option value={0}>All time</option>
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
        <select className="input input-sm" aria-label="Who" value={actor} onChange={(e) => filter(() => setActor(e.target.value))}>
          <option value="">Everyone</option>
          {page?.actors.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <section className="card card-pad stack gap-14">
        <table className="data-table audit-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Time</th>
              <th aria-label="Kind" />
              <th>Who</th>
              <th>Action</th>
              <th>Entry hash</th>
            </tr>
          </thead>
          <tbody>
            {page?.entries.map((e) => {
              const t = when(e.created_at)
              const look = ICONS[e.category]
              const broken = check && !check.ok && check.broken.seq === e.seq
              return (
                <tr key={e.seq} className={broken ? 'is-broken' : undefined}>
                  <td className="mono muted">{e.seq}</td>
                  <td className="nowrap">
                    <span className="mono">{t.time}</span> <span className="muted small">{t.date}</span>
                  </td>
                  <td>
                    <span className={`audit-icon tone-${look.tone}`} title={e.category}>
                      <Icon name={look.icon} size={16} />
                    </span>
                  </td>
                  <td>
                    <strong>{e.actor}</strong>
                  </td>
                  <td>{e.detail}</td>
                  <td className="mono muted nowrap" title={`This row: ${e.entry_hash}\nRow before: ${e.prev_hash}`}>
                    {e.entry_hash.slice(0, 4)}…{e.entry_hash.slice(-4)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {page && page.entries.length === 0 && <p className="muted">Nothing matches these filters.</p>}
        <div className="row gap-10">
          <span className="row gap-8 small chain-note">
            <Icon name="hash" size={16} color="var(--green-dark)" />
            Each entry carries the hash of the entry before it.
          </span>
          <div className="grow" />
          <span className="muted small">
            {total === 0 ? '0' : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)}`} of {total}
          </span>
          <button type="button" className="btn btn-outline btn-xs" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            <Icon name="arrowLeft" size={14} strokeWidth={2} />
            Newer
          </button>
          <button type="button" className="btn btn-outline btn-xs" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Older
            <Icon name="arrowRight" size={14} strokeWidth={2} />
          </button>
        </div>
      </section>
    </main>
  )
}

// Stage 9B (design 33): the rows on screen as a CSV file, with each row's hash and the hash before it,
// so the chain can be checked again outside the app. Made in the browser.
function csvHref(entries: AuditEntry[]): string {
  const cell = (value: string | number | null) => `"${String(value ?? '').replace(/"/g, '""')}"`
  const rows = [
    ['Row', 'Time (UTC)', 'Who', 'Category', 'Action', 'Target', 'Detail', 'Previous hash', 'Entry hash'],
    ...entries.map((e) => [e.seq, e.created_at, e.actor, e.category, e.action, e.target, e.detail, e.prev_hash, e.entry_hash]),
  ]
  return `data:text/csv;charset=utf-8,${encodeURIComponent(rows.map((row) => row.map(cell).join(',')).join('\n'))}`
}

