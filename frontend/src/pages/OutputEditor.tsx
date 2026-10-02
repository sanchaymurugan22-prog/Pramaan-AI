// "Edit" on an output: one text box per text field. Saving makes a new version ("Edited by human")
// and the backend runs every check again (no AI call). The old version is kept and can be viewed.
import { useState } from 'react'
import { editOutput, type JobDetail, type JobOutput } from '../api'
import { Icon } from '../components/Icon'
import { pathKey } from './traceState'
import { t } from '../i18n'

type Props = {
  jobId: number
  output: JobOutput
  onSaved: (job: JobDetail) => void
  onCancel: () => void
}

export function OutputEditor({ jobId, output, onSaved, onCancel }: Props) {
  const [texts, setTexts] = useState<Record<string, string>>(() =>
    Object.fromEntries(output.fields.map((f) => [pathKey(f.path), f.text])),
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const changed = output.fields.filter((f) => texts[pathKey(f.path)] !== f.text)

  async function save() {
    setSaving(true)
    setError('')
    try {
      const job = await editOutput(
        jobId,
        output.id,
        changed.map((f) => ({ path: f.path, text: texts[pathKey(f.path)] })),
      )
      onSaved(job)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not save."))
      setSaving(false)
    }
  }

  return (
    <div className="stack gap-14">
      <p className="hint">
        {t("Change any text below, then")} <strong>{t("Save and re-check")}</strong>{t(". The checks run again straight away (no AI). The current text is kept as version")} {output.version}{t(". Empty a box to remove that post, point or step.")}
      </p>
      <div className="edit-fields">
        {output.fields.map((f) => {
          const key = pathKey(f.path)
          const value = texts[key] ?? ''
          const limit = output.type === 'x_thread' && f.path[0] === 'tweets' ? 280 : null
          return (
            <label key={key} className="field">
              <span className="row gap-8">
                <span className="field-label grow">{t(f.label)}</span>
                {limit && <span className={value.length > limit ? 'small over-limit' : 'small muted'}>{value.length}/{limit}</span>}
              </span>
              <textarea
                className={value !== f.text ? 'input textarea is-changed' : 'input textarea'}
                rows={Math.min(8, Math.max(1, Math.ceil(value.length / 80)))}
                value={value}
                onChange={(e) => setTexts({ ...texts, [key]: e.target.value })}
              />
            </label>
          )
        })}
      </div>
      {error && <div className="alert alert-red">{error}</div>}
      <div className="row gap-10 wrap edit-actions">
        <button type="button" className="btn btn-saffron" disabled={saving || changed.length === 0} onClick={save}>
          <Icon name="check" size={18} strokeWidth={2.2} />
          {saving ? t("Saving…") : t("Save and re-check")}
        </button>
        <button type="button" className="btn btn-outline" disabled={saving} onClick={onCancel}>
          {t("Cancel")}
        </button>
        <span className="muted small">
          {changed.length === 0 ? t("No changes yet.") : t("{length} field{n} changed.", { length: changed.length, n: changed.length === 1 ? '' : 's' })}
        </span>
      </div>
    </div>
  )
}
