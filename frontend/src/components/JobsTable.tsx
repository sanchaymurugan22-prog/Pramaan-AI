import type { JobSummary } from '../api'
import { outputKinds, shortTime } from '../pages/format'
import { links } from '../router'
import { StatusChip } from './StatusChip'

// The list of jobs used on the dashboard and on "My jobs". Each row opens the job's results.
export function JobsTable({ jobs }: { jobs: JobSummary[] }) {
  return (
    <div className="jobs-table" role="table" aria-label="Jobs">
      <div className="jobs-row jobs-head" role="row">
        <span role="columnheader">Job</span>
        <span role="columnheader">Status</span>
        <span role="columnheader">Outputs</span>
        <span role="columnheader">Languages</span>
        <span role="columnheader">Updated</span>
      </div>
      {jobs.map((job) => (
        <a key={job.id} href={links.job(job.id)} className="jobs-row jobs-link" role="row">
          <span role="cell" className="stack">
            <span className="job-title">{job.title}</span>
            <span className="job-kind">{outputKinds(job.output_types)}</span>
          </span>
          <span role="cell">
            <StatusChip
              status={job.status}
              progress={job.status === 'generating' ? `${job.outputs_done}/${job.outputs_total}` : undefined}
            />
          </span>
          <span role="cell">{job.outputs_total}</span>
          <span role="cell">EN</span>
          <span role="cell">{shortTime(job.updated_at)}</span>
        </a>
      ))}
    </div>
  )
}
