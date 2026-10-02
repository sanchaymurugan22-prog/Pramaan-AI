// Design 35 · Templates and letterheads (Stage 9B). Every exported file uses the built-in template of
// its output type, with the office's letterhead: the office name and logo set here are printed on every
// PDF, Word, PowerPoint, PNG and text file, and the name is "Issued by" on the public verify page.
// (Choosing between several templates per output comes later; today each output has one.)
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { getLetterhead, logoUrl, removeLogo, saveLetterhead, uploadLogo, type Letterhead } from '../../api'
import { Icon } from '../../components/Icon'
import { LogoSeal } from '../../components/Logo'
import { t } from '../../i18n'

type Kind = 'all' | 'documents' | 'slides' | 'infographics' | 'letterheads'
const TEMPLATES: { name: string; output: string; kind: Exclude<Kind, 'all'>; art: 'doc' | 'slides' | 'poster' | 'text' }[] = [
  { name: 'CERT-In style advisory', output: 'Advisory · PDF and Word', kind: 'documents', art: 'doc' },
  { name: 'Executive brief', output: 'Executive summary · PDF and Word', kind: 'documents', art: 'doc' },
  { name: 'Script and storyboard', output: 'Video package · Word and subtitles', kind: 'documents', art: 'doc' },
  { name: 'Tricolour slides', output: 'Presentation · PowerPoint', kind: 'slides', art: 'slides' },
  { name: 'Tricolour poster', output: 'Infographic · PNG (steps, big numbers, timeline)', kind: 'infographics', art: 'poster' },
  { name: 'Post text', output: 'LinkedIn post and X thread · text', kind: 'documents', art: 'text' },
]

export function Templates() {
  const [kind, setKind] = useState<Kind>('all')
  const [letterhead, setLetterhead] = useState<Letterhead | null>(null)
  const [name, setName] = useState('')
  const [version, setVersion] = useState(0) // changes the logo address, so the new one is shown
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getLetterhead()
      .then((l) => {
        setLetterhead(l)
        setName(l.office_name)
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the letterhead.")))
  }, [])

  async function run(action: () => Promise<Letterhead>, done: string) {
    setError('')
    setMessage('')
    try {
      const l = await action()
      setLetterhead(l)
      setName(l.office_name)
      setVersion((v) => v + 1)
      setMessage(done)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("That did not work."))
    }
  }

  function chooseLogo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) run(() => uploadLogo(file), 'Logo saved. It is on every file made from now on.')
    event.target.value = ''
  }

  const shown = TEMPLATES.filter((template) => kind === 'all' || template.kind === kind)
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-navy">{t("Admin")}</div>
          <h1>{t("Templates")}</h1>
          <p className="muted page-lead">{t("The look of every output. Your letterhead is printed on all of them.")}</p>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-navy" onClick={() => fileInput.current?.click()}>
          <Icon name="upload" size={18} strokeWidth={2} />
          {t("Upload logo")}
        </button>
        <input ref={fileInput} type="file" accept="image/png,image/jpeg" hidden aria-label={t("Choose a logo (PNG or JPEG)")} onChange={chooseLogo} />
      </div>

      <div className="segmented segmented-wide" role="group" aria-label={t("Show")}>
        {(['all', 'documents', 'slides', 'infographics', 'letterheads'] as const).map((k) => (
          <button key={k} type="button" aria-pressed={kind === k} className={kind === k ? 'is-on' : ''} onClick={() => setKind(k)}>
            {k[0].toUpperCase() + k.slice(1)}
          </button>
        ))}
      </div>
      {error && <div className="alert alert-red" role="alert">{error}</div>}
      <p className="sr-only" role="status">{message}</p>
      {message && <div className="alert alert-green">{message}</div>}

      {(kind === 'all' || kind === 'letterheads') && letterhead && (
        <section className="card card-pad letterhead-card" aria-labelledby="letterhead-title">
          <div className="stack gap-14 grow">
            <h2 id="letterhead-title">{t("Your letterhead")}</h2>
            <label className="field">
              <span className="field-label">{t("Office name")}</span>
              <input
                className="input"
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
                placeholder={letterhead.default_name}
              />
              <span className="field-help">
                {t("Printed on every exported file and shown as “Issued by” when someone checks a document. Empty = “{default_name}” (ISSUING_OFFICE in .env).", { default_name: letterhead.default_name })}</span>
            </label>
            <div className="row gap-10 wrap">
              <button type="button" className="btn btn-navy" onClick={() => run(() => saveLetterhead(name), 'Office name saved.')} disabled={name === letterhead.office_name}>
                <Icon name="check" size={18} strokeWidth={2.4} />
                {t("Save office name")}
              </button>
              <button type="button" className="btn btn-outline" onClick={() => fileInput.current?.click()}>
                <Icon name="upload" size={18} />
                {letterhead.has_logo ? t("Change logo") : t("Upload logo")}
              </button>
              {letterhead.has_logo && (
                <button type="button" className="btn btn-red-outline" onClick={() => run(removeLogo, 'Logo removed.')}>
                  {t("Remove logo")}
                </button>
              )}
            </div>
            <span className="field-help">{t("Logo: PNG or JPEG, up to 2 MB. It is made at most 600 pixels wide and stored encrypted.")}</span>
          </div>
          <figure className="letterhead-preview" aria-label={t("Preview of the top of a page")}>
            <div className="slide-strip" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div className="row gap-10 letterhead-preview-head">
              {letterhead.has_logo ? (
                <img src={`${logoUrl}?v=${version}`} alt={t("Your logo")} height={36} />
              ) : (
                <LogoSeal size={32} />
              )}
              <strong>{letterhead.effective_name}</strong>
              <span className="muted small">{t("· Advisory")}</span>
            </div>
            <div className="letterhead-lines" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <figcaption className="muted small">{t("Preview of the top of every page")}</figcaption>
          </figure>
        </section>
      )}

      {kind !== 'letterheads' && (
        <div className="template-grid">
          {shown.map((template) => (
            <section key={template.name} className="card template-card" aria-label={template.name}>
              <div className={`template-art art-${template.art}`} aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
              <div className="row gap-8 align-start">
                <span className="stack grow">
                  <strong>{template.name}</strong>
                  <span className="muted small">{template.output}</span>
                </span>
                <span className="chip chip-navy chip-xs">
                  <Icon name="check" size={12} strokeWidth={2.4} />
                  {t("In use")}
                </span>
              </div>
            </section>
          ))}
        </div>
      )}
    </main>
  )
}
