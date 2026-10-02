// Design 34 · AI models and performance (Stage 9B). Which AI writes (AI_MODE in .env), the models of the
// plan with what is really installed, and speeds MEASURED from real runs on this computer (not samples).
import { useEffect, useState } from 'react'
import { getAiInfo, runSpeedTest, type AiInfo } from '../../api'
import { Icon } from '../../components/Icon'
import { duration, shortTime } from '../format'
import { t } from '../../i18n'

const STATUS: Record<string, { label: string; className: string }> = {
  in_use: { label: 'In use', className: 'chip chip-green chip-xs' },
  standby: { label: 'Set up, not in use', className: 'chip chip-neutral chip-xs' },
  off: { label: 'Off', className: 'chip chip-neutral chip-xs' },
  missing: { label: 'Not installed', className: 'chip chip-yellow chip-xs' },
}

export function AiModels() {
  const [info, setInfo] = useState<AiInfo | null>(null)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState('')

  const load = () =>
    getAiInfo()
      .then(setInfo)
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the AI information.")))
  useEffect(() => {
    load()
  }, [])

  async function test() {
    setTesting(true)
    setError('')
    try {
      await runSpeedTest()
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("The speed test did not run."))
    } finally {
      setTesting(false)
    }
  }

  const current = info?.performance.find((p) => p.ai_mode === info.ai_mode)
  const speed = info?.speed_test
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-navy">{t("Admin")}</div>
          <h1>{t("AI models & performance")}</h1>
          <p className="muted page-lead">{t("All models are Indian and run on this computer. Speeds below are measured from real jobs here.")}</p>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-navy" onClick={test} disabled={testing || !info}>
          <Icon name="bolt" size={18} strokeWidth={2} />
          {testing ? t("Testing… (the local model can take a minute)") : t("Run a speed test")}
        </button>
      </div>
      {error && <div className="alert alert-red">{error}</div>}

      {info && (
        <>
          <div className="mode-grid">
            {(['local', 'mock', 'cloud'] as const).map((mode) => (
              <section key={mode} className={info.ai_mode === mode ? 'card card-pad mode-card is-on' : 'card card-pad mode-card'} aria-label={t("{mode} mode", { mode: mode })}>
                <div className="row gap-12 align-start">
                  <span className="setup-card-icon" aria-hidden="true">
                    <Icon name={mode === 'local' ? 'chip' : mode === 'mock' ? 'code' : 'globe'} size={22} color="var(--navy)" />
                  </span>
                  <span className="stack gap-4 grow">
                    <strong className="mode-title">
                      {{ local: 'Full mode · Sarvam 30B', mock: 'Mock AI · for tests', cloud: 'Sarvam hosted · development only' }[mode]}
                    </strong>
                    <span className="muted small">
                      {{
                        local: 'Writes every output on this computer, offline. Best quality; slow on this laptop.',
                        mock: 'No model: answers built from the source by rules. Instant; for tests and demos.',
                        cloud: 'Uses the internet. Never for real or sensitive data.',
                      }[mode]}
                    </span>
                  </span>
                  {info.ai_mode === mode && (
                    <span className="chip chip-navy chip-xs">
                      <Icon name="check" size={12} strokeWidth={2.4} />
                      {t("In use")}
                    </span>
                  )}
                </div>
              </section>
            ))}
          </div>
          <p className="muted small">
            {t("The mode is set with")} <code className="mono">AI_MODE</code> {t("in")} <code className="mono">.env</code> {t("(then restart the app), so it cannot be changed from a web page. Model:")} <span className="mono">{info.model || '—'}</span>
            {info.base_url && (
              <>
                {' '}
                {t("at")} <span className="mono">{info.base_url}</span>
              </>
            )}
            .
          </p>

          <div className="admin-two">
            <section className="card card-pad stack gap-12" aria-labelledby="models-title">
              <h2 id="models-title">{t("Models")}</h2>
              <div className="table-scroll">
                <table className="data-table">
                  <caption className="sr-only">{t("Models of the plan and their status")}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{t("Model")}</th>
                      <th scope="col">{t("Job")}</th>
                      <th scope="col">{t("Made by")}</th>
                      <th scope="col">{t("Status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {info.models.map((m) => (
                      <tr key={m.name}>
                        <td>
                          <strong>{m.name}</strong>
                          <div className="muted small">{m.runtime}</div>
                        </td>
                        <td>{m.job}</td>
                        <td>{m.made_by}</td>
                        <td>
                          <span className={(STATUS[m.status] ?? STATUS.off).className}>{t((STATUS[m.status] ?? STATUS.off).label)}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="stack gap-20">
              <section className="card card-pad stack gap-12" aria-labelledby="speed-title">
                <h2 id="speed-title">{t("Measured speed · {label}", { label: t(info.label) })}</h2>
                {!current && <p className="muted small">{t("No jobs have run with this AI yet.")}</p>}
                {current && (
                  <dl className="facts-table">
                    <div>
                      <dt>{t("Outputs written")}</dt>
                      <dd>{current.outputs}</dd>
                    </div>
                    <div>
                      <dt>{t("Average per output")}</dt>
                      <dd>{current.average_output_seconds === null ? '—' : duration(current.average_output_seconds)}</dd>
                    </div>
                    <div>
                      <dt>{t("Average fact sheet")}</dt>
                      <dd>{current.average_fact_sheet_seconds === null ? '—' : duration(current.average_fact_sheet_seconds)}</dd>
                    </div>
                    <div>
                      <dt>{t("Writing speed")}</dt>
                      <dd>{current.tokens_per_second === null ? '—' : `${current.tokens_per_second} tokens/s`}</dd>
                    </div>
                  </dl>
                )}
                {current && current.by_type.length > 0 && (
                  <ul className="clean-list-plain small stack gap-4">
                    {current.by_type.map((speed) => (
                      <li key={speed.type} className="row">
                        <span className="grow">{t(speed.label)}</span>
                        <span className="muted">
                          {t("{count}× · {average_seconds} each", { count: speed.count, average_seconds: duration(speed.average_seconds) })}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="card card-pad stack gap-10" aria-labelledby="test-title" aria-live="polite">
                <h2 id="test-title">{t("Last speed test")}</h2>
                {!speed?.at && <p className="muted small">{t("Not run yet.")}</p>}
                {speed?.at && (
                  <p className={speed.ok ? '' : 'over-limit'}>
                    {speed.ok
                      ? t("{words} words in {seconds} s{n}", { words: speed.words, seconds: speed.seconds, n: speed.words_per_second ? ` (${speed.words_per_second} words/s)` : '' })
                      : `Failed: ${speed.error}`}
                    <span className="muted small"> · {speed.ai_mode} · {shortTime(speed.at)}</span>
                  </p>
                )}
              </section>

              <section className="card card-pad stack gap-8" aria-labelledby="saving-title">
                <h2 id="saving-title">{t("How Pramaan saves time")}</h2>
                <ul className="clean-list small">
                  <li>{t("The source is read once into a fact sheet, reused for every output.")}</li>
                  <li>{t("Short outputs are written first, so the first results appear sooner.")}</li>
                  <li>{t("Local answers are streamed: the progress page shows them being written.")}</li>
                  <li>{t("Each answer has a word limit per output type (MAX_TOKENS_… in .env).")}</li>
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </main>
  )
}
