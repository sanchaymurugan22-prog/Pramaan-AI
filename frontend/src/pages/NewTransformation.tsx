import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import { createJob } from '../api'
import { Icon } from '../components/Icon'
import { Stepper } from '../components/Stepper'
import { useLanguages } from '../languages'
import { links, navigate } from '../router'

// Only these file types can be read by the backend
const DOCUMENTS = ['.txt', '.pdf', '.docx']
// Stage 8: recordings, turned into text by speech-to-text on this computer
const RECORDINGS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.mp4', '.m4v', '.mov', '.webm']
const ALLOWED = [...DOCUMENTS, ...RECORDINGS]
const isRecording = (file: File) => RECORDINGS.some((ext) => file.name.toLowerCase().endsWith(ext))

// New transformation, step 1 of 3: add sources. "Next" reads the sources and runs the safety scan
// (no AI, a few seconds), then opens step 2, the Safety check.
export function NewTransformation() {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [spoken, setSpoken] = useState('hi') // the language spoken in a recording
  const languages = useLanguages()
  const sttLanguages = languages?.languages.filter((l) => l.speech_to_text) ?? []
  const fileInput = useRef<HTMLInputElement>(null)

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
    setError(skipped > 0 ? `Skipped ${skipped} file(s). Use .txt, .pdf or .docx files, or a recording (.mp3, .wav, .m4a, .mp4 …).` : '')
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
    if (!text.trim() && files.length === 0) return setError('Paste some text or add a file.')

    const form = new FormData()
    form.append('title', title)
    form.append('text', text)
    files.forEach((file) => form.append('files', file))
    form.append('audio_language', spoken)

    setSubmitting(true)
    setError('')
    try {
      const job = await createJob(form)
      navigate(links.safety(job.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
      setSubmitting(false)
    }
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">New transformation</div>
          <h1>Add sources</h1>
        </div>
        <div className="grow" />
        <a className="btn btn-outline" href={links.dashboard}>
          Cancel
        </a>
      </div>
      <Stepper current={1} />

      <form className="new-grid" onSubmit={submit}>
        <section
          className={dragging ? 'card card-pad stack gap-14 is-dragging' : 'card card-pad stack gap-14'}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <h2>Source</h2>
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
              rows={11}
            />
          </label>
          <div className="field">
            <span className="field-label">…or add files (.txt, .pdf, .docx) or a recording (.mp3, .wav, .m4a, .mp4)</span>
            <div className="row gap-10 wrap">
              <button type="button" className="btn btn-outline" onClick={() => fileInput.current?.click()}>
                <Icon name="upload" size={18} strokeWidth={2} />
                Choose files
              </button>
              <span className="muted small">or drag files here · Try the files in the samples folder</span>
            </div>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept={ALLOWED.join(',')}
              aria-label="Choose source files (.txt, .pdf, .docx) or recordings"
              hidden
              onChange={(e) => addFiles(e.target.files)}
            />
            {files.length > 0 && (
              <ul className="file-list">
                {files.map((file, index) => (
                  <li key={`${file.name}-${index}`}>
                    <Icon name={isRecording(file) ? 'volume' : 'file'} size={18} color="var(--muted)" />
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
            {files.some(isRecording) && (
              <label className="field">
                <span className="field-label">Language spoken in the recording</span>
                <select className="input" value={spoken} onChange={(e) => setSpoken(e.target.value)}>
                  {(sttLanguages.length ? sttLanguages : []).map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.native === l.name ? l.name : `${l.native} (${l.name})`}
                    </option>
                  ))}
                </select>
                <span className="field-help">
                  The recording is turned into text on this computer (IndicConformer for Hindi and Tamil, Whisper for
                  English). A 10-minute recording takes a few minutes. The text is then checked like any other source.
                </span>
              </label>
            )}
          </div>
        </section>

        <aside className="card card-pad stack gap-14 new-summary">
          <h2>Next: safety check</h2>
          <p className="muted small">
            Before any AI reads your sources, Pramaan looks for private data (Aadhaar, PAN, phone numbers,
            passwords, internal addresses…), classification markings and hidden instructions aimed at the AI.
            You then decide what to hide. This takes a few seconds and never leaves this computer.
          </p>
          {error && <div className="alert alert-red">{error}</div>}
          <button type="submit" className="btn btn-lg btn-saffron" disabled={submitting}>
            {submitting ? (files.some(isRecording) ? 'Turning speech into text…' : 'Checking…') : 'Next: safety check'}
            {!submitting && <Icon name="arrowRight" size={18} strokeWidth={2} />}
          </button>
        </aside>
      </form>
    </main>
  )
}
