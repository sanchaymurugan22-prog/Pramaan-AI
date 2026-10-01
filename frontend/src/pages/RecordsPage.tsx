// Design 29 · Signed records (Reviewer) and design 37 · Record book (Admin).
// Every signed document set has a numbered record; each entry carries the fingerprint of the one
// before it. "Check the whole chain" asks the backend to check every entry, signature and signed file.
// Only an Admin can withdraw a record (a new, signed entry: nothing is ever changed or deleted).
import { useEffect, useState } from 'react'
import { listRecords, publicKeyUrl, verifyRecordBook, withdrawRecord, type BookCheck, type RecordBook, type RecordItem, type RecordStatus } from '../api'
import { Icon } from '../components/Icon'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { shortHash, shortTime } from './format'

const FILTERS: { key: RecordStatus | ''; label: string }[] = [
  { key: '', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'replaced', label: 'Replaced' },
  { key: 'withdrawn', label: 'Withdrawn' },
]

export function RecordsPage({ admin }: { admin: boolean }) {
  const [book, setBook] = useState<RecordBook | null>(null)
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<RecordStatus | ''>('')
  const [check, setCheck] = useState<BookCheck | null>(null)
  const [checking, setChecking] = useState(false)
  const [withdrawing, setWithdrawing] = useState<RecordItem | null>(null)
  const [error, setError] = useState('')
  const [loads, setLoads] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text), 300)
    return () => window.clearTimeout(timer)
  }, [text])

  useEffect(() => {
    let stopped = false
    listRecords(query, status)
      .then((b) => !stopped && setBook(b))
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the records.'))
    return () => {
      stopped = true
    }
  }, [query, status, loads])

  async function verify() {
    setChecking(true)
    try {
      setCheck(await verifyRecordBook())
      setLoads((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not check the record book.')
    } finally {
      setChecking(false)
    }
  }

  const counts = book?.counts ?? { active: 0, withdrawn: 0, replaced: 0 }
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-4">
          <div className={admin ? 'eyebrow eyebrow-navy' : 'eyebrow eyebrow-green'}>{admin ? 'Admin' : 'Archive'}</div>
          <h1>{admin ? 'Record book' : 'Signed records'}</h1>
          <p className="muted">
            {admin
              ? 'Every signed document is recorded here. Each entry holds the fingerprint of the one before it, so any change is exposed.'
              : 'Every document your team has signed. An Admin can withdraw a record if an advisory is withdrawn.'}
          </p>
        </div>
        <div className="grow" />
        <button type="button" className={admin ? 'btn btn-navy' : 'btn btn-green'} onClick={verify} disabled={checking}>
          <Icon name="shieldCheck" size={18} strokeWidth={2} />
          {checking ? 'Checking…' : 'Check the whole chain'}
        </button>
      </div>

      {check?.ok && (
        <div className="chain-banner" role="status">
          <span className="chain-banner-icon">
            <Icon name="check" size={24} strokeWidth={2.6} color="var(--green-dark)" />
          </span>
          <span className="stack">
            <strong>
              Chain intact · {check.checked} of {check.checked} entries verified
            </strong>
            <span className="small">
              Every hash and signature matches, and all {check.files_checked} signed files still have their fingerprints.
            </span>
          </span>
        </div>
      )}
      {check && !check.ok && (
        <div className="alert alert-red stack gap-4" role="alert">
          <strong className="row gap-8">
            <Icon name="warning" size={18} strokeWidth={2.2} />
            BROKEN at entry {check.broken.seq} ({check.broken.record_no}). The {check.checked} entries before it are intact.
          </strong>
          <span>{check.broken.reason}</span>
        </div>
      )}
      {error && <div className="alert alert-red">{error}</div>}

      <div className="stat-grid stat-grid-3">
        <Stat icon="shieldCheck" tone="green" label="Active records" value={String(counts.active)} note="Genuine when checked" />
        <Stat icon="cross" tone="red" label="Withdrawn" value={String(counts.withdrawn)} note={`${counts.replaced} replaced by a newer version`} />
        <Stat
          icon="hash"
          tone="navy"
          label="Record chain"
          value={check ? (check.ok ? 'Intact' : 'Broken') : `${book?.entries ?? 0} entries`}
          note={book?.last_check ? `Last checked ${shortTime(book.last_check.at)} by ${book.last_check.by}` : 'Not checked yet'}
        />
      </div>

      {admin && book && book.chain.length > 0 && (
        <section className="card card-pad stack gap-14">
          <div className="row">
            <h2>Latest entries</h2>
            <div className="grow" />
            <span className="muted small">
              Showing {book.chain.length} of {book.entries}
            </span>
          </div>
          <div className="chain-cards">
            {book.chain.map((entry, i) => (
              <div key={entry.seq} className="row chain-card-wrap">
                {i > 0 && <Icon name="hash" size={20} color="var(--green-dark)" />}
                <article className={i === book.chain.length - 1 ? 'chain-card is-latest' : 'chain-card'}>
                  <div className="row">
                    <strong className="mono">#{entry.seq}</strong>
                    <div className="grow" />
                    {i === book.chain.length - 1 && <span className="chip chip-green chip-xs">Latest</span>}
                  </div>
                  <span className="chain-card-title">{entry.kind === 'withdraw' ? `Withdrawal of ${entry.record_no}` : entry.title}</span>
                  <span className="muted small">
                    {entry.record_no} · {shortTime(entry.created_at)}
                  </span>
                  <span className="muted small">Fingerprint</span>
                  <span className="mono small">{shortHash(entry.entry_hash)}</span>
                  <span className="muted small">Previous</span>
                  <span className="mono small">{shortHash(entry.prev_hash)}</span>
                </article>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="card card-pad stack gap-14">
        <div className="row gap-12 wrap">
          <label className="search audit-search">
            <span className="search-icon">
              <Icon name="search" size={18} strokeWidth={1.8} />
            </span>
            <input type="search" aria-label="Search by title or record number" placeholder="Search by title or record number" value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          <div className="grow" />
          <div className="segmented">
            {FILTERS.map((f) => (
              <button key={f.key} type="button" className={status === f.key ? 'is-on' : ''} onClick={() => setStatus(f.key)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Record</th>
              <th>Title</th>
              <th>Signed by</th>
              <th>Date</th>
              <th>Files</th>
              <th>Sharing</th>
              <th>Status</th>
              {admin && <th aria-label="Actions" />}
            </tr>
          </thead>
          <tbody>
            {book?.records.map((r) => (
              <tr key={r.record_no}>
                <td className="mono nowrap">
                  <a href={r.verify_url} target="_blank" rel="noreferrer" title="Open on the verify page">
                    {r.record_no}
                  </a>
                </td>
                <td>
                  {r.job_id ? <a href={links.job(r.job_id)}>{r.title}</a> : r.title}
                  {r.job_version && r.job_version > 1 && <span className="muted"> · v{r.job_version}</span>}
                </td>
                <td>{r.approved_by}</td>
                <td className="nowrap">{shortTime(r.issued_at)}</td>
                <td>{r.files_count}</td>
                <td>{r.tlp && <TlpLabel tlp={r.tlp} />}</td>
                <td>
                  {r.status === 'active' && (
                    <span className="chip chip-green chip-xs">
                      <Icon name="check" size={12} strokeWidth={2.4} />
                      Active
                    </span>
                  )}
                  {r.status === 'replaced' && <span className="chip chip-yellow chip-xs">Replaced by {r.replaced_by}</span>}
                  {r.status === 'withdrawn' && (
                    <span className="chip chip-red chip-xs" title={r.withdrawn?.reason}>
                      <Icon name="cross" size={12} strokeWidth={2.4} />
                      Withdrawn
                    </span>
                  )}
                </td>
                {admin && (
                  <td className="right">
                    {!r.withdrawn && (
                      <button type="button" className="btn btn-link btn-xs withdraw-link" onClick={() => setWithdrawing(r)}>
                        Withdraw
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {book && book.records.length === 0 && <p className="muted">No records yet. A record is made when a Reviewer approves and signs a job.</p>}
      </section>

      {admin && (
        <section className="card card-pad stack gap-12 narrow-card">
          <h2>Public key</h2>
          <p className="muted">
            Verification pages and phones use this to check signatures, even offline. It contains no secret information.
          </p>
          <a className="btn btn-navy-outline" href={publicKeyUrl} download>
            <Icon name="download" size={18} strokeWidth={2} />
            Download public key
          </a>
        </section>
      )}

      {withdrawing && (
        <WithdrawDialog
          record={withdrawing}
          onClose={() => setWithdrawing(null)}
          onDone={() => {
            setWithdrawing(null)
            setLoads((n) => n + 1)
          }}
        />
      )}
    </main>
  )
}

function Stat(props: { icon: 'shieldCheck' | 'cross' | 'hash'; tone: string; label: string; value: string; note: string }) {
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

function WithdrawDialog({ record, onClose, onDone }: { record: RecordItem; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    setBusy(true)
    setError('')
    try {
      await withdrawRecord(record.record_no, reason)
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not withdraw it.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="dialog-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <section className="card dialog" role="dialog" aria-modal="true" aria-labelledby="withdraw-title">
        <div className="stack gap-4">
          <h2 id="withdraw-title">Withdraw {record.record_no}?</h2>
          <span className="muted">{record.title}</span>
        </div>
        <p className="muted">
          The record is not deleted: a signed “withdrawn” entry is added to the record book. Anyone who checks it on the
          verify page then sees it is withdrawn, and why
          {record.tlp === 'RED' || record.tlp === 'AMBER' ? ' (for a TLP:RED / AMBER record only “Withdrawn by the issuing office”)' : ''}.
        </p>
        <label className="field">
          <span className="field-label">Reason</span>
          <textarea className="input textarea" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
        </label>
        {error && <div className="alert alert-red">{error}</div>}
        <div className="row gap-10">
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancel
          </button>
          <div className="grow" />
          <button type="button" className="btn btn-red-outline" onClick={submit} disabled={busy || reason.trim().length < 5}>
            <Icon name="cross" size={18} strokeWidth={2} />
            Withdraw record
          </button>
        </div>
      </section>
    </div>
  )
}
