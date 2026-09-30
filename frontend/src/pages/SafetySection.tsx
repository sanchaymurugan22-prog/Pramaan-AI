import { useState } from 'react'
import type { JobDetail, JobOutput } from '../api'
import { Icon } from '../components/Icon'
import { TlpLabel } from '../components/TlpLabel'
import { choiceLabel, TLP_LEVELS } from './safety'
import { outputKinds, shortTime } from './format'

// The small "Safety" section of the Results page (Stage 6A): the sharing label, what was hidden,
// outputs the label switched off, suspicious instructions, and every safety decision (who, when, what).
export function SafetySection({ job }: { job: JobDetail }) {
  const [open, setOpen] = useState(false)
  const safety = job.safety
  if (!safety) return null // jobs from before Stage 6A

  const counts = { hide_public: 0, hide_all: 0, keep: 0 }
  safety.findings.forEach((f) => (counts[f.choice] += 1))
  const off = Object.keys(safety.switched_off)
  const level = TLP_LEVELS.find((l) => l.tlp === job.tlp)
  const blocked = job.outputs.filter((o) => (o.quality?.leaks ?? []).length > 0)

  return (
    <section className="card card-pad-sm stack gap-10 safety-section">
      <div className="row gap-12 wrap">
        <span className="section-label">Safety</span>
        {job.tlp && <TlpLabel tlp={job.tlp} />}
        {level && <span className="small">{level.title}</span>}
        <span className="muted small">·</span>
        <span className="small">
          {safety.findings.length === 0
            ? 'No private data found'
            : `${counts.hide_public} hidden in public outputs, ${counts.hide_all} hidden everywhere, ${counts.keep} kept`}
        </span>
        {safety.indicators.length > 0 && (
          <span className="small muted">· {safety.indicators.length} attack indicator{safety.indicators.length === 1 ? '' : 's'}</span>
        )}
        {safety.suspicious.length > 0 && (
          <span className="chip chip-red chip-xs">
            {safety.suspicious.length} suspicious instruction{safety.suspicious.length === 1 ? '' : 's'}
          </span>
        )}
        <div className="grow" />
        <button type="button" className="btn btn-outline btn-xs" onClick={() => setOpen(!open)} aria-expanded={open}>
          <Icon name="shield" size={16} />
          {open ? 'Hide details' : `Decisions (${job.safety_decisions.length})`}
        </button>
      </div>
      {off.length > 0 && (
        <p className="small muted">
          <Icon name="lock" size={14} /> Switched off by TLP:{job.tlp}: {outputKinds(off)}. {safety.switched_off[off[0]]}
        </p>
      )}
      {blocked.length > 0 && (
        <div className="alert alert-red small">
          Private data found in: {blocked.map((o) => o.label).join(', ')}. These cannot be downloaded until it is edited out.
        </div>
      )}
      {open && (
        <div className="stack gap-10">
          {safety.findings.length + safety.indicators.length > 0 && (
            <ul className="decision-list">
              {[...safety.findings, ...safety.indicators].map((f) => (
                <li key={f.id}>
                  <span className="mono muted">{f.id}</span> {f.label} <span className="muted">({f.count}×)</span> →{' '}
                  <strong>{choiceLabel(f.choice)}</strong>
                </li>
              ))}
            </ul>
          )}
          <span className="section-label">Decision log</span>
          <ol className="decision-list">
            {job.safety_decisions.map((d) => (
              <li key={d.id}>
                <span className="muted">{d.created_at ? shortTime(d.created_at) : ''}</span> <strong>{d.actor}</strong> ·{' '}
                {d.detail}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}

// The red box on an output the leak check blocked
export function LeakAlert({ output }: { output: JobOutput }) {
  const leaks = output.quality?.leaks ?? []
  if (leaks.length === 0) return null
  return (
    <div className="alert alert-red stack gap-6" role="alert">
      <strong className="row gap-8">
        <Icon name="warning" size={18} strokeWidth={2.2} />
        Private data found
      </strong>
      <span>
        This output contains values you chose to hide. It cannot be downloaded until you edit them out (Edit, then
        remove or replace them).
      </span>
      <ul className="clean-list">
        {leaks.map((leak, i) => (
          <li key={i}>
            {leak.label} “{leak.found}” in <strong>{leak.where}</strong>{' '}
            <span className="muted">({choiceLabel(leak.choice)})</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
