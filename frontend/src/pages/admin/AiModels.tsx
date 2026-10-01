// Design 34 · AI models and performance (Stage 9B). Which AI writes (AI_MODE in .env), the models of the
// plan with what is really installed, and speeds MEASURED from real runs on this computer (not samples).
import { useEffect, useState } from 'react'
import { getAiInfo, runSpeedTest, type AiInfo } from '../../api'
import { Icon } from '../../components/Icon'
import { duration, shortTime } from '../format'

const STATUS: Record<string, { label: string; className: string }> = {
  in_use: { label: 'In use', className: 'chip chip-green chip-xs' },
  standby: { label: 'Set up, not in use', className: 'chip chip-neutral chip-xs' },
  off: { label: 'Off', className: 'chip chip-neutral chip-xs' },
  planned: { label: 'Stage 8', className: 'chip chip-yellow chip-xs' },
}

export function AiModels() {
  const [info, setInfo] = useState<AiInfo | null>(null)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState('')

  const load = () =>
    getAiInfo()
      .then(setInfo)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the AI information.'))
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
      setError(e instanceof Error ? e.message : 'The speed test did not run.')
    } finally {
      setTesting(false)
    }
  }

  const current = info?.performance.find((p) => p.ai_mode === info.ai_mode)
  const t = info?.speed_test
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-navy">Admin</div>
          <h1>AI models &amp; performance</h1>
          <p className="muted page-lead">All models are Indian and run on this computer. Speeds below are measured from real jobs here.</p>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-navy" onClick={test} disabled={testing || !info}>
          <Icon name="bolt" size={18} strokeWidth={2} />
          {testing ? 'Testing… (the local model can take a minute)' : 'Run a speed test'}
        </button>
      </div>
      {error && <div className="alert alert-red">{error}</div>}

      {info && (
        <>
          <div className="mode-grid">
            {(['local', 'mock', 'cloud'] as const).map((mode) => (
              <section key={mode} className={info.ai_mode === mode ? 'card card-pad mode-card is-on' : 'card card-pad mode-card'} aria-label={`${mode} mode`}>
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
                      In use
                    </span>
                  )}
                </div>
              </section>
            ))}
          </div>
          <p className="muted small">
            The mode is set with <code className="mono">AI_MODE</code> in <code className="mono">.env</code> (then restart the app), so it cannot be
            changed from a web page. Model: <span className="mono">{info.model || '—'}</span>
            {info.base_url && (
              <>
                {' '}
                at <span className="mono">{info.base_url}</span>
              </>
            )}
            .
          </p>

          <div className="admin-two">
            <section className="card card-pad stack gap-12" aria-labelledby="models-title">
              <h2 id="models-title">Models</h2>
              <div className="table-scroll">
                <table className="data-table">
                  <caption className="sr-only">Models of the plan and their status</caption>
                  <thead>
                    <tr>
                      <th scope="col">Model</th>
                      <th scope="col">Job</th>
                      <th scope="col">Made by</th>
                      <th scope="col">Status</th>
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
                          <span className={STATUS[m.status].className}>{STATUS[m.status].label}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="stack gap-20">
              <section className="card card-pad stack gap-12" aria-labelledby="speed-title">
                <h2 id="speed-title">Measured speed · {info.label}</h2>
                {!current && <p className="muted small">No jobs have run with this AI yet.</p>}
                {current && (
                  <dl className="facts-table">
                    <div>
                      <dt>Outputs written</dt>
                      <dd>{current.outputs}</dd>
                    </div>
                    <div>
                      <dt>Average per output</dt>
                      <dd>{current.average_output_seconds === null ? '—' : duration(current.average_output_seconds)}</dd>
                    </div>
                    <div>
                      <dt>Average fact sheet</dt>
                      <dd>{current.average_fact_sheet_seconds === null ? '—' : duration(current.average_fact_sheet_seconds)}</dd>
                    </div>
                    <div>
                      <dt>Writing speed</dt>
                      <dd>{current.tokens_per_second === null ? '—' : `${current.tokens_per_second} tokens/s`}</dd>
                    </div>
                  </dl>
                )}
                {current && current.by_type.length > 0 && (
                  <ul className="clean-list-plain small stack gap-4">
                    {current.by_type.map((t) => (
                      <li key={t.type} className="row">
                        <span className="grow">{t.label}</span>
                        <span className="muted">
                          {t.count}× · {duration(t.average_seconds)} each
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="card card-pad stack gap-10" aria-labelledby="test-title" aria-live="polite">
                <h2 id="test-title">Last speed test</h2>
                {!t?.at && <p className="muted small">Not run yet.</p>}
                {t?.at && (
                  <p className={t.ok ? '' : 'over-limit'}>
                    {t.ok
                      ? `${t.words} words in ${t.seconds} s${t.words_per_second ? ` (${t.words_per_second} words/s)` : ''}`
                      : `Failed: ${t.error}`}
                    <span className="muted small"> · {t.ai_mode} · {shortTime(t.at)}</span>
                  </p>
                )}
              </section>

              <section className="card card-pad stack gap-8" aria-labelledby="saving-title">
                <h2 id="saving-title">How Pramaan saves time</h2>
                <ul className="clean-list small">
                  <li>The source is read once into a fact sheet, reused for every output.</li>
                  <li>Short outputs are written first, so the first results appear sooner.</li>
                  <li>Local answers are streamed: the progress page shows them being written.</li>
                  <li>Each answer has a word limit per output type (MAX_TOKENS_… in .env).</li>
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </main>
  )
}
