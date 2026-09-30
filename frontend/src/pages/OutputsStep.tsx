import { useEffect, useState } from 'react'
import { getJob, getOptions, startJob, type Health, type JobDetail, type JobSettings, type Options } from '../api'
import { Icon } from '../components/Icon'
import { Stepper } from '../components/Stepper'
import { TlpLabel } from '../components/TlpLabel'
import { links, navigate } from '../router'

// Labels for the setting dropdowns, in the order they are shown
const SETTING_FIELDS: { key: keyof JobSettings; label: string }[] = [
  { key: 'audience', label: 'Audience' },
  { key: 'tone', label: 'Tone' },
  { key: 'objective', label: 'Objective' },
  { key: 'style', label: 'Style' },
]

const DETAIL_LEVELS = [
  { value: 'short', label: 'Short' },
  { value: 'medium', label: 'Medium' },
  { value: 'detailed', label: 'Detailed' },
]

// Short outputs we suggest ticking first when the slow local model is in use
const QUICK_OUTPUTS = ['x_thread', 'linkedin_post']

// New transformation, step 3 of 3: outputs and settings. Public outputs that the TLP label does
// not allow (RED, AMBER) are switched off, with the reason. "Generate" starts the AI.
export function OutputsStep({ jobId, health }: { jobId: number; health: Health | null | undefined }) {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [options, setOptions] = useState<Options | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [settings, setSettings] = useState<JobSettings | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getJob(jobId), getOptions()])
      .then(([loadedJob, loadedOptions]) => {
        setJob(loadedJob)
        setOptions(loadedOptions)
        setSettings(loadedOptions.default_settings)
        const allowed = loadedOptions.output_types.map((o) => o.key).filter((k) => !loadedJob.switched_off[k])
        const quick = QUICK_OUTPUTS.filter((k) => allowed.includes(k))
        setSelected(quick.length > 0 ? quick : allowed.slice(0, 2))
      })
      .catch(() => setError('Could not reach the backend. Is it running? (scripts/start.sh)'))
  }, [jobId])

  if (!job || !options || !settings) {
    return (
      <main className="page">
        {error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}
      </main>
    )
  }
  if (job.status !== 'draft') {
    return (
      <main className="page">
        <div className="alert alert-yellow">
          This job has already started. <a href={links.job(job.id)}>Open its results</a>.
        </div>
      </main>
    )
  }
  if (!job.tlp) {
    return (
      <main className="page">
        <div className="alert alert-yellow">
          Finish the safety check first. <a href={links.safety(job.id)}>Go to the Safety check</a>.
        </div>
      </main>
    )
  }

  const off = job.switched_off
  const allowedKeys = options.output_types.map((o) => o.key).filter((k) => !off[k])
  const allSelected = allowedKeys.every((k) => selected.includes(k))
  const offReason = Object.values(off)[0]

  function toggleOutput(key: string) {
    if (off[key]) return
    setSelected((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]))
  }

  async function generate() {
    if (!job || !settings) return
    if (selected.length === 0) return setError('Tick at least one output.')
    setSubmitting(true)
    setError('')
    try {
      await startJob(job.id, selected, settings)
      navigate(links.job(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
      setSubmitting(false)
    }
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">New transformation · {job.title}</div>
          <h1>Outputs and settings</h1>
        </div>
        <div className="grow" />
        <a className="btn btn-outline" href={links.dashboard}>
          Cancel
        </a>
      </div>
      <Stepper current={3} />

      <div className="new-grid">
        <div className="stack gap-20">
          <section className="card card-pad stack gap-14">
            <div className="row gap-12 wrap">
              <h2>Outputs</h2>
              <TlpLabel tlp={job.tlp} />
              <div className="grow" />
              <span className="muted small">{selected.length} selected</span>
              <button type="button" className="btn btn-link" onClick={() => setSelected(allSelected ? [] : allowedKeys)}>
                {allSelected ? 'Clear all' : 'Select all'}
              </button>
            </div>
            {offReason && (
              <div className="alert alert-yellow row gap-10">
                <Icon name="lock" size={18} />
                <span>{offReason} Go back to the Safety check to choose TLP:GREEN or TLP:CLEAR if this is meant for the public.</span>
              </div>
            )}
            <div className="output-grid">
              {options.output_types.map((type) => {
                const disabled = Boolean(off[type.key])
                const checked = !disabled && selected.includes(type.key)
                return (
                  <label
                    key={type.key}
                    className={['output-option', checked && 'is-checked', disabled && 'is-off'].filter(Boolean).join(' ')}
                    title={disabled ? off[type.key] : undefined}
                  >
                    <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggleOutput(type.key)} />
                    <span className="stack gap-2 grow">
                      <span className="row gap-10 wrap">
                        <span className="output-option-title">{type.label}</span>
                        {type.public && <span className="chip chip-saffron chip-xs">Public</span>}
                        {disabled && <span className="chip chip-neutral chip-xs">Off · TLP:{job.tlp}</span>}
                      </span>
                      <span className="output-option-desc">{disabled ? 'Switched off by the sharing label' : type.description}</span>
                    </span>
                  </label>
                )
              })}
            </div>
            {health?.ai_mode === 'local' && (
              <p className="hint">
                The local AI is slow on this laptop (about 1 word a second). The fact sheet takes about 10 minutes and
                each short output about 5–7 minutes. Try 2 short outputs first.
              </p>
            )}
          </section>

          <section className="card card-pad stack gap-14">
            <h2>Settings</h2>
            <div className="settings-grid">
              {SETTING_FIELDS.map(({ key, label }) => (
                <label key={key} className="field">
                  <span className="field-label">{label}</span>
                  <select className="input" value={settings[key]} onChange={(e) => setSettings({ ...settings, [key]: e.target.value })}>
                    {options.settings[key].map((choice) => (
                      <option key={choice}>{choice}</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className="field">
              <span className="field-label">Level of detail</span>
              <div className="segmented" role="radiogroup" aria-label="Level of detail">
                {DETAIL_LEVELS.map((level) => (
                  <button
                    key={level.value}
                    type="button"
                    role="radio"
                    aria-checked={settings.detail_level === level.value}
                    className={settings.detail_level === level.value ? 'is-on' : ''}
                    onClick={() => setSettings({ ...settings, detail_level: level.value })}
                  >
                    {level.label}
                  </button>
                ))}
              </div>
            </div>
            <p className="muted small">English only for now. Indian languages come in Stage 8.</p>
          </section>
        </div>

        <aside className="card card-pad stack gap-14 new-summary">
          <h2>Your kit</h2>
          <div className="row gap-10 kit-count">
            <span className="kit-number">{selected.length}</span>
            <span className="muted">output{selected.length === 1 ? '' : 's'}</span>
          </div>
          <p className="muted small">
            All written from one fact sheet, so every output says the same thing. Hidden values are replaced by
            placeholders before the AI reads anything.
          </p>
          {error && <div className="alert alert-red">{error}</div>}
          <button type="button" className="btn btn-lg btn-saffron" disabled={submitting} onClick={generate}>
            {submitting ? 'Starting…' : 'Generate'}
          </button>
          <a className="btn btn-outline" href={links.safety(job.id)}>
            <Icon name="arrowLeft" size={18} strokeWidth={2} />
            Back to safety check
          </a>
        </aside>
      </div>
    </main>
  )
}
