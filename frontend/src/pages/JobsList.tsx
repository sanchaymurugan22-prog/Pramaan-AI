import { useEffect, useState } from 'react'
import { listJobs, type JobSummary } from '../api'
import { Icon } from '../components/Icon'
import { JobsTable } from '../components/JobsTable'
import { links } from '../router'

// "My jobs": every job, newest first. Refreshes every 5 seconds while any job is still generating.
export function JobsList() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let timer: number | undefined
    let stopped = false
    async function load() {
      try {
        const all = await listJobs()
        if (stopped) return
        setJobs(all)
        setError('')
        if (all.some((job) => job.status === 'generating')) timer = window.setTimeout(load, 5000)
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : 'Could not load jobs.')
      }
    }
    load()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [])

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
      <section className="card card-pad stack gap-12">
        {error && <div className="alert alert-red">{error}</div>}
        {jobs === null && !error && <p className="muted">Loading…</p>}
        {jobs && jobs.length === 0 && (
          <p className="muted">
            No jobs yet. <a href={links.newJob}>Start a new transformation</a>.
          </p>
        )}
        {jobs && jobs.length > 0 && <JobsTable jobs={jobs} />}
      </section>
    </main>
  )
}
