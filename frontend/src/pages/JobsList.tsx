import { useEffect, useState } from 'react'
import { listJobs, type JobSummary } from '../api'
import { Icon } from '../components/Icon'
import { JobsTable } from '../components/JobsTable'
import { links } from '../router'

// Design "20 · My jobs (history)". The filters are sent to the backend (GET /api/jobs?q=&status=&tlp=&days=);
// the list is shown 10 at a time. It refreshes every 5 seconds while any job is still generating.

const STATUS_TABS = [
  { label: 'All', value: '' },
  { label: 'Drafts', value: 'draft' },
  { label: 'Ready', value: 'ready,generating,failed' },
  { label: 'In review', value: 'in_review' },
  { label: 'Sent back', value: 'sent_back' },
  { label: 'Approved', value: 'approved' },
]
const PAGE_SIZE = 10

export function JobsList() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [q, setQ] = useState('') // the search text, a moment after typing stops
  const [status, setStatus] = useState('')
  const [days, setDays] = useState(30)
  const [tlp, setTlp] = useState('')
  const [page, setPage] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => setQ(text.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [text])

  useEffect(() => {
    let timer: number | undefined
    let stopped = false
    async function load() {
      try {
        const found = await listJobs({ q, status, tlp, days })
        if (stopped) return
        setJobs(found)
        setError('')
        if (found.some((job) => job.status === 'generating')) timer = window.setTimeout(load, 5000)
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : 'Could not load jobs.')
      }
    }
    load()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [q, status, tlp, days])

  useEffect(() => setPage(0), [q, status, tlp, days])

  const total = jobs?.length ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const shown = jobs?.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE) ?? []
  const filtered = q || status || tlp || days !== 30

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">History</div>
          <h1>My jobs</h1>
        </div>
        <div className="grow" />
        <a href={links.newJob} className="btn btn-saffron">
          <Icon name="plus" size={18} strokeWidth={2} />
          New transformation
        </a>
      </div>

      <div className="filter-bar" role="search" aria-label="Filter jobs">
        <div className="input-with-icon filter-search">
          <span className="search-icon" aria-hidden="true">
            <Icon name="search" size={18} strokeWidth={1.8} />
          </span>
          <label htmlFor="jobs-search" className="sr-only">
            Search by title, job number or source file
          </label>
          <input
            id="jobs-search"
            className="input input-icon"
            type="search"
            placeholder="Search by title or source"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div className="segmented" role="group" aria-label="Status">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.label}
              type="button"
              aria-pressed={status === tab.value}
              className={status === tab.value ? 'is-on' : ''}
              onClick={() => setStatus(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <label className="select-wrap">
          <Icon name="calendar" size={18} />
          <span className="sr-only">Changed in</span>
          <select className="input select-plain" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={0}>All time</option>
          </select>
        </label>
        <label className="select-wrap">
          <Icon name="filter" size={18} />
          <span className="sr-only">Sharing level</span>
          <select className="input select-plain" value={tlp} onChange={(e) => setTlp(e.target.value)}>
            <option value="">Any sharing level</option>
            <option value="RED">TLP:RED</option>
            <option value="AMBER">TLP:AMBER</option>
            <option value="GREEN">TLP:GREEN</option>
            <option value="CLEAR">TLP:CLEAR</option>
          </select>
        </label>
      </div>

      <section className="card card-pad stack gap-12" aria-label="Jobs">
        {error && <div className="alert alert-red">{error}</div>}
        {jobs === null && !error && <p className="muted">Loading…</p>}
        {jobs && jobs.length === 0 && (
          <p className="muted">
            {filtered ? 'No jobs match these filters.' : 'No jobs yet.'} <a href={links.newJob}>Start a new transformation</a>.
          </p>
        )}
        {shown.length > 0 && <JobsTable jobs={shown} full caption="My jobs" />}
        {jobs && jobs.length > 0 && (
          <div className="row gap-10 wrap">
            <span className="muted" role="status">
              Showing {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total} job{total === 1 ? '' : 's'}
            </span>
            <div className="grow" />
            <button type="button" className="btn btn-outline btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              <Icon name="chevronLeft" size={18} />
              Previous
            </button>
            <button type="button" className="btn btn-outline btn-sm" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>
              Next
              <Icon name="chevronRight" size={18} />
            </button>
          </div>
        )}
      </section>
    </main>
  )
}
