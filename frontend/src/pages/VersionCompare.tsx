import { useEffect, useState } from 'react'
import { compareVersions, type Comparison, type DiffPiece } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { OUTPUT_ICONS } from '../components/outputIcons'
import { links } from '../router'
import { jobNo, shortTime } from './format'
import { ScoreBadge } from './TracePanels'
import { t } from '../i18n'

// Design "21 · Version compare (v1 vs v2)". Two versions of a job side by side, word by word
// (backend/app/pipeline/compare.py). Added words are green, bold and underlined; removed words are red
// and struck through; screen readers hear "added" / "removed" (<ins> and <del>), so nothing depends on colour.

function Pieces({ pieces, side }: { pieces: DiffPiece[]; side: 'left' | 'right' }) {
  if (pieces.length === 0) return <span className="muted">{side === 'left' ? t("(not in this version)") : t("(removed)")}</span>
  return (
    <>
      {pieces.map((p, i) =>
        p.kind === 'same' ? (
          <span key={i}>{p.text}</span>
        ) : p.kind === 'added' ? (
          <ins key={i} className="diff-add">
            <span className="sr-only">{t("[added:")} </span>
            {p.text}
            <span className="sr-only">]</span>
          </ins>
        ) : (
          <del key={i} className="diff-del">
            <span className="sr-only">{t("[removed:")} </span>
            {p.text}
            <span className="sr-only">]</span>
          </del>
        ),
      )}
    </>
  )
}

export function VersionCompare({ jobId }: { jobId: number }) {
  const { user } = useAuth()
  const [data, setData] = useState<Comparison | null>(null)
  const [left, setLeft] = useState<number | undefined>(undefined)
  const [right, setRight] = useState<number | undefined>(undefined)
  const [outputId, setOutputId] = useState<number | null>(null)
  const [onlyChanged, setOnlyChanged] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    compareVersions(jobId, left, right)
      .then((found) => {
        setData(found)
        setError('')
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not compare the versions.")))
  }, [jobId, left, right])

  if (!data) {
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>
  }
  const s = data.summary
  const output = data.outputs.find((o) => o.output_id === outputId) ?? data.outputs.find((o) => o.changed) ?? data.outputs[0]
  const fields = output ? output.fields.filter((f) => !onlyChanged || f.changed) : []
  const latest = data.right.key === data.versions.at(-1)?.key

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">{t("Job {job_id} · Version compare", { job_id: jobNo(data.job_id) })}</div>
          <h1>
            {t("{label} vs {value}", { label: data.right.label, value: data.left.key === 0 ? t("the first AI draft") : data.left.label.toLowerCase() })}</h1>
          <p className="muted page-lead">
            {s.outputs_changed === 0
              ? t("Nothing changed between these versions.")
              : t("{outputs_changed} of {outputs} outputs changed · {words_added} words added, {words_removed} removed.", { outputs_changed: s.outputs_changed, outputs: s.outputs, words_added: s.words_added, words_removed: s.words_removed })}
          </p>
        </div>
        <div className="grow" />
        <a className="btn btn-outline" href={links.job(data.job_id)}>
          <Icon name="arrowLeft" size={18} strokeWidth={2} />
          {t("Back to results")}
        </a>
        {user.role === 'operator' && latest && (data.right.status === 'draft' || data.right.status === 'sent back') && (
          <a className="btn btn-saffron" href={links.job(data.job_id)}>
            {t("Send")} {data.right.label.replace('Version ', 'v')} {t("for review")}
            <Icon name="send" size={18} strokeWidth={2} />
          </a>
        )}
      </div>

      <div className="filter-bar">
        <label className="select-wrap">
          <span className="small">{t("Old")}</span>
          <select className="input select-plain" value={data.left.key} onChange={(e) => setLeft(Number(e.target.value))}>
            {data.versions.map((v) => (
              <option key={v.key} value={v.key}>
                {v.label} · {v.status}
              </option>
            ))}
          </select>
        </label>
        <Icon name="arrowRight" size={18} color="var(--muted)" />
        <label className="select-wrap">
          <span className="small">{t("New")}</span>
          <select className="input select-plain" value={data.right.key} onChange={(e) => setRight(Number(e.target.value))}>
            {data.versions.map((v) => (
              <option key={v.key} value={v.key}>
                {v.label} · {v.status}
              </option>
            ))}
          </select>
        </label>
      </div>

      {(s.numbers.length > 0 || s.lists.length > 0) && (
        <div className="stat-grid" aria-label={t("What changed")}>
          {s.numbers.slice(0, 4).map((n) => (
            <section key={n.label} className="change-card tone-saffron">
              <span className="small muted">{n.label}</span>
              <span className="change-value">
                {n.before} <span aria-hidden="true">→</span>
                <span className="sr-only"> {t("changed to")} </span> {n.after}
              </span>
            </section>
          ))}
          {s.lists.slice(0, 4 - Math.min(4, s.numbers.length)).map((l) => (
            <section key={`${l.output}-${l.label}`} className={l.after > l.before ? 'change-card tone-green' : 'change-card tone-red'}>
              <span className="small muted">
                {l.label} · {l.output}
              </span>
              <span className="change-value">
                {l.after > l.before ? '+' : '−'}
                {Math.abs(l.after - l.before)} {Math.abs(l.after - l.before) === 1 ? t("item") : t("items")}
              </span>
            </section>
          ))}
        </div>
      )}

      <div className="row gap-14 wrap small">
        <ins className="diff-add">{t("Added")}</ins>
        <del className="diff-del">{t("Removed")}</del>
        <label className="row gap-6">
          <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} />
          {t("Show only the parts that changed")}
        </label>
      </div>

      <div className="tab-bar" role="group" aria-label={t("Output")}>
        {data.outputs.map((o) => (
          <button
            key={o.output_id}
            type="button"
            className={o.output_id === output?.output_id ? 'output-tab is-current' : 'output-tab'}
            aria-pressed={o.output_id === output?.output_id}
            onClick={() => setOutputId(o.output_id)}
          >
            <Icon name={OUTPUT_ICONS[o.type] ?? 'file'} size={18} />
            {o.label}
            <span className={o.changed ? 'tab-count tab-changed' : 'tab-count'}>{o.changed ? t("Changed") : t("Same")}</span>
          </button>
        ))}
      </div>

      {output && (
        <div className="compare-grid">
          {(['left', 'right'] as const).map((side) => {
            const version = side === 'left' ? data.left : data.right
            const info = output[side]
            return (
              <section key={side} className="card card-pad stack gap-14" aria-label={`${version.label}, ${output.label}`}>
                <div className="row gap-10 wrap compare-head">
                  <h2 className="grow">{version.label}</h2>
                  <ScoreBadge score={info.quality_score} />
                  <span className={side === 'left' ? 'chip chip-neutral' : 'chip chip-saffron'}>
                    {version.at ? `${shortTime(version.at)} · ` : ''}
                    {version.status}
                  </span>
                </div>
                {info.version === null && <p className="muted">{t("This output did not exist in this version.")}</p>}
                {fields.length === 0 && info.version !== null && <p className="muted">{t("No changes in the {label}.", { label: output.label })}</p>}
                {fields.map((f) => (
                  <div key={f.path.join('.')} className="compare-field">
                    <span className="section-label">{f.label}</span>
                    <p className="compare-text">
                      <Pieces pieces={f[side]} side={side} />
                    </p>
                  </div>
                ))}
              </section>
            )
          })}
        </div>
      )}
    </main>
  )
}
