import type { JobSummary } from '../api'
import { aiShort, jobNo, LANGUAGE_LABELS, outputKinds, shortTime } from '../pages/format'
import { ScoreBadge } from '../pages/TracePanels'
import { links } from '../router'
import { Icon } from './Icon'
import { StatusChip } from './StatusChip'
import { TlpLabel } from './TlpLabel'

// Where a row leads: a draft opens its Safety check (where the operator left off), a job being
// written opens its live progress, anything else its results.
export function jobHref(job: JobSummary): string {
  if (job.status === 'draft') return links.safety(job.id)
  if (job.status === 'generating' && job.outputs_done === 0) return links.progress(job.id)
  return links.job(job.id)
}

// "Watch folder" / "Emergency" badge: how the job was made (icon + words, not colour alone)
export function OriginBadge({ job }: { job: JobSummary }) {
  if (job.created_via === 'watch')
    return (
      <span className="chip chip-saffron chip-xs">
        <Icon name="folder" size={12} strokeWidth={2.2} />
        Watch folder
      </span>
    )
  if (job.created_via === 'emergency')
    return (
      <span className="chip chip-red chip-xs">
        <Icon name="siren" size={12} strokeWidth={2.2} />
        Emergency
      </span>
    )
  return null
}

function languages(job: JobSummary): string {
  return job.languages.map((l) => LANGUAGE_LABELS[l] ?? l.toUpperCase()).join(' · ')
}

// The list of jobs on the dashboard (compact, as in design 08) and on "My jobs" (full, design 20).
// A real table: each title is a link, and the whole row can be clicked too.
export function JobsTable({ jobs, full = false, caption }: { jobs: JobSummary[]; full?: boolean; caption: string }) {
  return (
    <div className="table-scroll">
      <table className={full ? 'jobs-table jobs-table-full' : 'jobs-table'}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Job</th>
            {full && <th scope="col">Ver.</th>}
            <th scope="col">Status</th>
            {full && <th scope="col">Sharing</th>}
            {full && <th scope="col">AI used</th>}
            {full && <th scope="col">Quality</th>}
            <th scope="col">Outputs</th>
            {!full && <th scope="col">Languages</th>}
            <th scope="col">Updated</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="jobs-tr">
              <td>
                <span className="stack gap-2">
                  <a href={jobHref(job)} className="row-link job-title">
                    <span className="job-no">{jobNo(job.id)}</span> {job.title}
                  </a>
                  <span className="row gap-6 wrap">
                    <span className="job-kind">{job.output_types.length ? outputKinds(job.output_types) : 'Waiting at the Safety check'}</span>
                    <OriginBadge job={job} />
                  </span>
                </span>
              </td>
              {full && <td className="mono job-ver">v{job.version}</td>}
              <td>
                <StatusChip
                  status={job.status}
                  progress={job.status === 'generating' ? `${job.outputs_done}/${job.outputs_total}` : undefined}
                />
              </td>
              {full && <td>{job.tlp ? <TlpLabel tlp={job.tlp} /> : <span className="muted small">Not chosen</span>}</td>}
              {full && <td className="small">{aiShort(job.ai_mode)}</td>}
              {full && (
                <td>
                  {job.quality_score !== null ? <ScoreBadge score={job.quality_score} /> : <span className="muted small">—</span>}
                </td>
              )}
              <td>{job.outputs_total || '—'}</td>
              {!full && <td>{languages(job)}</td>}
              <td className="nowrap">{shortTime(job.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
