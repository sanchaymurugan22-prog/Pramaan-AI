// Design 38 · Public verification page and design 39 · Updates and backup (Stage 9B).
import { useEffect, useState } from 'react'
import { backupUrl, getPublicPageInfo, listBackups, makeBackup, verifyBundleUrl, type Backups, type PublicPageInfo } from '../../api'
import { Icon } from '../../components/Icon'
import { dateTime, fileSize } from '../format'

const CONTAINS = ['The public key that checks signatures', 'The list of signed and withdrawn records (titles only for TLP:GREEN and CLEAR)', 'The fake-message checking rules']
const NEVER = ['Any document or report', 'Names, emails or user accounts', 'AI models, the database or private keys']
const RULES = [
  'Look-alike or unofficial links',
  'Requests for OTP, PIN or password',
  'Pressure words like “act within 1 hour”',
  'Phone numbers not in any signed record',
  'Shows the cyber-crime helpline 1930 on every fake result',
]

export function PublicPage() {
  const [info, setInfo] = useState<PublicPageInfo | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    getPublicPageInfo()
      .then(setInfo)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load.'))
  }, [])

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-navy">Admin</div>
          <h1>Public verification page</h1>
          <p className="muted page-lead">A small public website where anyone can check a document. It holds no documents and no secrets.</p>
        </div>
        <div className="grow" />
        {info && (
          <a className="btn btn-outline" href={info.address} target="_blank" rel="noreferrer">
            <Icon name="eye" size={18} />
            Open public page
          </a>
        )}
      </div>
      {error && <div className="alert alert-red">{error}</div>}
      {info && (
        <>
          <section className="kit-banner kit-banner-navy" aria-label="Address">
            <span className="kit-banner-icon" aria-hidden="true">
              <Icon name="globe" size={24} />
            </span>
            <span className="stack gap-2 grow">
              <strong className="mono">{info.address}</strong>
              <span className="small">
                Issued by “{info.issuer}” · last update exported {info.last_export ? dateTime(info.last_export) : 'never'}
              </span>
            </span>
          </section>

          <div className="stat-grid stat-grid-3">
            <section className="card stat-card">
              <div className="stat-icon tone-green" aria-hidden="true">
                <Icon name="check" size={22} />
              </div>
              <div className="stack gap-2">
                <span className="stat-label">Records on the page</span>
                <span className="stat-value">{info.records.issued}</span>
                <span className="stat-note">Each can be checked by QR</span>
              </div>
            </section>
            <section className="card stat-card">
              <div className="stat-icon tone-red" aria-hidden="true">
                <Icon name="cross" size={22} />
              </div>
              <div className="stack gap-2">
                <span className="stat-label">Fake or edited caught</span>
                <span className="stat-value">{info.checker.scam + info.checker.changed}</span>
                <span className="stat-note">By “Is this real?” in the app (the public page keeps no counts)</span>
              </div>
            </section>
            <section className="card stat-card">
              <div className="stat-icon tone-saffron" aria-hidden="true">
                <Icon name="warning" size={22} />
              </div>
              <div className="stack gap-2">
                <span className="stat-label">Withdrawn records</span>
                <span className="stat-value">{info.records.withdrawn}</span>
                <span className="stat-note">Shown as withdrawn when checked</span>
              </div>
            </section>
          </div>

          <div className="admin-two">
            <section className="card card-pad stack gap-14" aria-labelledby="update-title">
              <div className="row gap-10 wrap">
                <h2 id="update-title" className="grow">
                  Update the public page
                </h2>
                <span className="chip chip-navy chip-xs">One-way: office → public</span>
              </div>
              <ol className="steps-list">
                <li>
                  <strong>Export the update file</strong>
                  <span className="muted small">The public key and the records list. No documents, no personal data.</span>
                  <a className="btn btn-navy btn-sm mt-8" href={verifyBundleUrl} download>
                    <Icon name="download" size={16} strokeWidth={2} />
                    Export update file
                  </a>
                </li>
                <li>
                  <strong>Copy it to a USB drive</strong>
                  <span className="muted small">This computer never connects to the internet, so the file travels by hand.</span>
                </li>
                <li>
                  <strong>Upload it on the public server</strong>
                  <span className="muted small">Unzip it into the website folder. The page checks every record’s signature before using it.</span>
                </li>
              </ol>
              <p className="row gap-8 small count-ok">
                <Icon name="shieldCheck" size={16} />
                Nothing from the internet can ever reach this computer.
              </p>
            </section>

            <div className="stack gap-20">
              <section className="card card-pad stack gap-12" aria-labelledby="holds-title">
                <h2 id="holds-title">What the public page holds</h2>
                <div className="form-grid-2">
                  <div className="stack gap-6">
                    <span className="small count-ok">Contains</span>
                    <ul className="clean-list-plain stack gap-6 small">
                      {CONTAINS.map((c) => (
                        <li key={c} className="row gap-6 align-start">
                          <Icon name="check" size={16} color="var(--green-dark)" strokeWidth={2.4} />
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="stack gap-6">
                    <span className="small over-limit">Never contains</span>
                    <ul className="clean-list-plain stack gap-6 small">
                      {NEVER.map((c) => (
                        <li key={c} className="row gap-6 align-start">
                          <Icon name="cross" size={16} color="var(--red-dark)" strokeWidth={2.4} />
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </section>
              <section className="card card-pad stack gap-10" aria-labelledby="rules-title">
                <h2 id="rules-title">Fake-message rules</h2>
                <p className="muted small">Run inside the visitor’s browser. No message is uploaded.</p>
                <ul className="clean-list-plain stack gap-8">
                  {RULES.map((r) => (
                    <li key={r} className="row gap-8">
                      <Icon name="check" size={16} color="var(--green-dark)" strokeWidth={2.4} />
                      {r}
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </main>
  )
}

export function Backup() {
  const [data, setData] = useState<Backups | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    listBackups()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load.'))
  }, [])

  async function backUp() {
    setBusy(true)
    setError('')
    try {
      setData(await makeBackup())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The backup failed.')
    } finally {
      setBusy(false)
    }
  }

  const last = data?.backups[0]
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow eyebrow-navy">Admin</div>
          <h1>Updates &amp; backup</h1>
          <p className="muted page-lead">Back up everything without internet. Updates arrive as a package on USB.</p>
        </div>
      </div>
      {error && <div className="alert alert-red" role="alert">{error}</div>}
      {data && (
        <>
          <section className="card card-pad row gap-14" aria-label="Version">
            <span aria-hidden="true">
              <Icon name="shieldCheck" size={36} color="var(--navy)" />
            </span>
            <span className="stack">
              <strong className="mode-title">Pramaan AI {data.version}</strong>
              <span className="muted small">Stage 9 build · AI: {data.ai_mode}</span>
            </span>
          </section>
          <div className="admin-two">
            <section className="card card-pad stack gap-12" aria-labelledby="update-title">
              <div className="row gap-12">
                <span className="stat-icon tone-navy" aria-hidden="true">
                  <Icon name="usb" size={20} />
                </span>
                <h2 id="update-title">Install an update</h2>
              </div>
              <p className="muted">
                No update package found. Installing signed update packages from USB is planned for the submission build (Stage 10). Until
                then, update by copying the new project folder and running <code className="mono">./scripts/start.sh</code>; make a
                backup first.
              </p>
            </section>
            <section className="card card-pad stack gap-12" aria-labelledby="backup-title">
              <div className="row gap-12">
                <span className="stat-icon tone-saffron" aria-hidden="true">
                  <Icon name="box" size={20} />
                </span>
                <h2 id="backup-title">Backup</h2>
              </div>
              <dl className="facts-table">
                <div>
                  <dt>Last backup</dt>
                  <dd>{last ? dateTime(last.created_at) : 'Never'}</dd>
                </div>
                <div>
                  <dt>Size</dt>
                  <dd>{last ? `${fileSize(last.bytes)} · encrypted` : '—'}</dd>
                </div>
                <div>
                  <dt>Kept in</dt>
                  <dd className="mono small break-all">{data.folder}</dd>
                </div>
              </dl>
              <div className="row gap-10 wrap">
                <button type="button" className="btn btn-navy-outline" onClick={backUp} disabled={busy}>
                  <Icon name="upload" size={18} />
                  {busy ? 'Backing up…' : 'Back up now'}
                </button>
              </div>
              <p className="row gap-8 small count-ok align-start">
                <Icon name="lock" size={16} />
                Backups are encrypted with DB_KEY from .env, which is not in the backup: keep a copy of .env somewhere safe. The README inside says how
                to restore.
              </p>
              {data.backups.length > 0 && (
                <ul className="clean-list-plain stack gap-6">
                  {data.backups.slice(0, 8).map((b) => (
                    <li key={b.name} className="row gap-10 small">
                      <span className="grow mono">{b.name}</span>
                      <span className="muted">{fileSize(b.bytes)}</span>
                      <a href={backupUrl(b.name)} download>
                        Download<span className="sr-only"> {b.name}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  )
}
