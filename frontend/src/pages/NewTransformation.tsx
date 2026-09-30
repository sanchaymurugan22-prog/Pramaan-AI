import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { createJob, getOptions, type Health, type JobSettings, type Options } from '../api'
import { Icon } from '../components/Icon'
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

export function NewTransformation({ health }: { health: Health | null | undefined }) {
  const [options, setOptions] = useState<Options | null>(null)
  const [loadError, setLoadError] = useState('')

  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [selected, setSelected] = useState<string[]>(QUICK_OUTPUTS)
  const [settings, setSettings] = useState<JobSettings | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getOptions()
      .then((o) => {
        setOptions(o)
        setSettings(o.default_settings)
      })
      .catch(() => setLoadError('Could not reach the backend. Is it running? (scripts/start.sh)'))
  }, [])

  function toggleOutput(key: string) {
    setSelected((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]))
  }

  // Only these file types can be read by the backend
  const ALLOWED = ['.txt', '.pdf', '.docx']

  function addFiles(list: FileList | null) {
    if (!list || list.length === 0) return
    // Copy the files NOW. Safari empties the FileList as soon as the input is cleared,
    // so reading it later (inside the state update) would add nothing.
    const picked = Array.from(list)
    if (fileInput.current) fileInput.current.value = '' // so the same file can be picked again

    const good = picked.filter((file) => ALLOWED.some((ext) => file.name.toLowerCase().endsWith(ext)))
    const skipped = picked.length - good.length
    if (good.length > 0) {
      setFiles((current) => {
        // ignore a file that is already in the list (same name and size)
        const fresh = good.filter((f) => !current.some((c) => c.name === f.name && c.size === f.size))
        return [...current, ...fresh]
      })
    }
    setError(skipped > 0 ? `Skipped ${skipped} file(s). Only .txt, .pdf and .docx are supported.` : '')
  }

  // Drag and drop files onto the Source card
  const [dragging, setDragging] = useState(false)
  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    addFiles(event.dataTransfer.files)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!settings) return
    if (!text.trim() && files.length === 0) return setError('Paste some text or add a file.')
    if (selected.length === 0) return setError('Tick at least one output.')

    const form = new FormData()
    form.append('title', title)
    form.append('text', text)
    files.forEach((file) => form.append('files', file))
    selected.forEach((key) => form.append('outputs', key))
    Object.entries(settings).forEach(([key, value]) => form.append(key, value))

    setSubmitting(true)
    setError('')
    try {
      const job = await createJob(form)
      navigate(links.job(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
      setSubmitting(false)
    }
  }

  if (loadError) {
    return (
      <main className="page">
        <div className="alert alert-red">{loadError}</div>
      </main>
    )
  }
  if (!options || !settings) {
    return (
      <main className="page">
        <p className="muted">Loading…</p>
      </main>
    )
  }

  const allSelected = selected.length === options.output_types.length

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">New transformation</div>
          <h1>Add a source and choose outputs</h1>
        </div>
      </div>

      <form className="new-grid" onSubmit={submit}>
        <div className="stack gap-20">
          {/* ---- 1. Source ---- */}
          <section
            className={dragging ? 'card card-pad stack gap-14 is-dragging' : 'card card-pad stack gap-14'}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <h2>1. Source</h2>
            <label className="field">
              <span className="field-label">Title (optional)</span>
              <input
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="We will use the document's heading if you leave this empty"
              />
            </label>
            <label className="field">
              <span className="field-label">Paste text</span>
              <textarea
                className="input textarea"
                value={text}
                onChange={(e) => {
                  setText(e.target.value)
                  if (error) setError('')
                }}
                placeholder="Paste a report, advisory or notice here…"
                rows={9}
              />
            </label>
            <div className="field">
              <span className="field-label">…or add files (.txt, .pdf, .docx)</span>
              <div className="row gap-10 wrap">
                <button type="button" className="btn btn-outline" onClick={() => fileInput.current?.click()}>
                  <Icon name="upload" size={18} strokeWidth={2} />
                  Choose files
                </button>
                <span className="muted small">or drag files here · Tip: try samples/sample-ransomware-report.txt</span>
              </div>
              <input
                ref={fileInput}
                type="file"
                multiple
                accept=".txt,.pdf,.docx"
                hidden
                onChange={(e) => addFiles(e.target.files)}
              />
              {files.length > 0 && (
                <ul className="file-list">
                  {files.map((file, index) => (
                    <li key={`${file.name}-${index}`}>
                      <Icon name="file" size={18} color="var(--muted)" />
                      <span className="grow">{file.name}</span>
                      <span className="chip chip-green chip-xs">Added</span>
                      <span className="muted small">{Math.ceil(file.size / 1024)} KB</span>
                      <button
                        type="button"
                        className="icon-btn icon-btn-sm"
                        aria-label={`Remove ${file.name}`}
                        onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
                      >
                        <Icon name="cross" size={16} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          {/* ---- 2. Outputs ---- */}
          <section className="card card-pad stack gap-14">
            <div className="row gap-12">
              <h2>2. Outputs</h2>
              <div className="grow" />
              <span className="muted small">{selected.length} selected</span>
              <button
                type="button"
                className="btn btn-link"
                onClick={() => setSelected(allSelected ? [] : options.output_types.map((o) => o.key))}
              >
                {allSelected ? 'Clear all' : 'Select all'}
              </button>
            </div>
            <div className="output-grid">
              {options.output_types.map((type) => {
                const checked = selected.includes(type.key)
                return (
                  <label key={type.key} className={checked ? 'output-option is-checked' : 'output-option'}>
                    <input type="checkbox" checked={checked} onChange={() => toggleOutput(type.key)} />
                    <span className="stack gap-2 grow">
                      <span className="row gap-10 wrap">
                        <span className="output-option-title">{type.label}</span>
                        {type.public && <span className="chip chip-saffron chip-xs">Public</span>}
                      </span>
                      <span className="output-option-desc">{type.description}</span>
                    </span>
                  </label>
                )
              })}
            </div>
            {health?.ai_mode === 'local' && (
              <p className="hint">
                The local AI is slow on this laptop (about 1 word a second). The fact sheet takes about
                10 minutes and each short output about 5–7 minutes. Try 2 short outputs first.
              </p>
            )}
          </section>

          {/* ---- 3. Settings ---- */}
          <section className="card card-pad stack gap-14">
            <h2>3. Settings</h2>
            <div className="settings-grid">
              {SETTING_FIELDS.map(({ key, label }) => (
                <label key={key} className="field">
                  <span className="field-label">{label}</span>
                  <select
                    className="input"
                    value={settings[key]}
                    onChange={(e) => setSettings({ ...settings, [key]: e.target.value })}
                  >
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

        {/* ---- summary + Generate ---- */}
        <aside className="card card-pad stack gap-14 new-summary">
          <h2>Your kit</h2>
          <div className="row gap-10 kit-count">
            <span className="kit-number">{selected.length}</span>
            <span className="muted">output{selected.length === 1 ? '' : 's'}</span>
          </div>
          <p className="muted small">
            All written from one fact sheet, so every output says the same thing. Short outputs are
            written first.
          </p>
          {error && <div className="alert alert-red">{error}</div>}
          <button type="submit" className="btn btn-lg btn-saffron" disabled={submitting}>
            {submitting ? 'Starting…' : 'Generate'}
          </button>
        </aside>
      </form>
    </main>
  )
}
