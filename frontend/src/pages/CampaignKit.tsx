import { useEffect, useState } from 'react'
import { getKitInfo, kitUrl, type KitInfo } from '../api'
import { Icon } from '../components/Icon'
import { OUTPUT_ICONS } from '../components/outputIcons'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { fileSize, jobNo } from './format'

// Design "19 · Campaign kit download". Tick the outputs to put in the .zip. Once a Reviewer has signed
// the job, every file in it is the signed one, with its QR code and record number; before that, files
// say "AI-assisted · pending human approval" and the QR code box is empty.
// The browser saves the .zip (to the Downloads folder, or wherever it asks): nothing is sent anywhere.

export function CampaignKit({ jobId }: { jobId: number }) {
  const [kit, setKit] = useState<KitInfo | null>(null)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState<string[] | null>(null) // null = not loaded yet

  useEffect(() => {
    getKitInfo(jobId)
      .then((info) => {
        setKit(info)
        setPicked(info.outputs.filter((o) => !o.blocked).map((o) => o.type))
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the kit.'))
  }, [jobId])

  if (!kit || !picked) {
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">Loading…</p>}</main>
  }

  const usable = kit.outputs.filter((o) => !o.blocked)
  const chosen = usable.filter((o) => picked.includes(o.type))
  const files = chosen.flatMap((o) => o.files)
  const known = files.every((f) => f.bytes !== null)
  const bytes = files.reduce((sum, f) => sum + (f.bytes ?? 0), 0)
  const allPicked = chosen.length === usable.length
  const record = kit.record
  const signed = Boolean(record && record.current && !record.withdrawn)
  const href = kitUrl(kit.job_id, allPicked ? [] : chosen.map((o) => o.type))

  function toggle(type: string) {
    setPicked((now) => (now!.includes(type) ? now!.filter((t) => t !== type) : [...now!, type]))
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">Job {jobNo(kit.job_id)} · Campaign kit</div>
          <h1>{signed ? 'Download the signed kit' : 'Download the campaign kit'}</h1>
          <p className="muted page-lead">
            {signed
              ? 'Every approved file in one package, each with its own QR code.'
              : 'Every finished file in one package. QR codes and the record number are added when a Reviewer signs it.'}
          </p>
        </div>
        <div className="grow" />
        <a className="btn btn-outline" href={links.job(kit.job_id)}>
          <Icon name="arrowLeft" size={18} strokeWidth={2} />
          Back to results
        </a>
      </div>

      {signed && record ? (
        <section className="kit-banner kit-banner-green" aria-label="Signature">
          <span className="kit-banner-icon" aria-hidden="true">
            <Icon name="award" size={24} />
          </span>
          <span className="stack gap-2 grow">
            <strong className="kit-banner-title">Approved and signed by {record.approved_by}</strong>
            <span className="small">
              {new Date(record.issued_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })} · {record.signer} · Record{' '}
              {record.record_no}
            </span>
          </span>
          <span className="chip chip-green">
            <Icon name="check" size={14} strokeWidth={2.4} />
            {record.files.length} files signed
          </span>
        </section>
      ) : (
        <section className="kit-banner kit-banner-yellow" aria-label="Not signed yet">
          <span className="kit-banner-icon" aria-hidden="true">
            <Icon name="warning" size={24} />
          </span>
          <span className="stack gap-2 grow">
            <strong className="kit-banner-title">Not signed yet</strong>
            <span className="small">
              {record?.withdrawn
                ? `Record ${record.record_no} was withdrawn. These files are not signed.`
                : 'Use these files for checking only. Send the job for review: when a Reviewer approves it, the kit holds the signed files.'}
            </span>
          </span>
        </section>
      )}

      <div className="kit-grid">
        <section className="card card-pad stack gap-12" aria-labelledby="inside-title">
          <div className="row gap-10">
            <h2 id="inside-title" className="grow">
              What is inside
            </h2>
            <label className="check-pill">
              <input
                type="checkbox"
                checked={allPicked}
                onChange={() => setPicked(allPicked ? [] : usable.map((o) => o.type))}
              />
              Select all
            </label>
          </div>
          <div className="table-scroll">
            <table className="jobs-table">
              <caption className="sr-only">Outputs in the kit</caption>
              <thead>
                <tr>
                  <th scope="col">
                    <span className="sr-only">Put in the kit</span>
                  </th>
                  <th scope="col">Output</th>
                  <th scope="col">Formats</th>
                  <th scope="col">Language</th>
                  <th scope="col">Size</th>
                </tr>
              </thead>
              <tbody>
                {kit.outputs.map((o) => {
                  const size = o.files.every((f) => f.bytes !== null) ? fileSize(o.files.reduce((s, f) => s + (f.bytes ?? 0), 0)) : 'Made on download'
                  return (
                    <tr key={o.output_id}>
                      <td>
                        <input
                          type="checkbox"
                          className="kit-check"
                          aria-label={`Put the ${o.label} in the kit`}
                          checked={picked.includes(o.type)}
                          disabled={o.blocked}
                          onChange={() => toggle(o.type)}
                        />
                      </td>
                      <td>
                        <span className="row gap-10">
                          <span className="progress-icon" aria-hidden="true">
                            <Icon name={OUTPUT_ICONS[o.type] ?? 'file'} size={18} />
                          </span>
                          <span className="stack">
                            <strong>{o.label}</strong>
                            {o.blocked && <span className="small over-limit">Left out: private data found in it</span>}
                          </span>
                        </span>
                      </td>
                      <td>{o.files.map((f) => f.format.toUpperCase()).join(', ')}</td>
                      <td>
                        <span className="chip chip-green chip-xs">
                          <Icon name="check" size={12} strokeWidth={2.4} />
                          EN
                        </span>
                      </td>
                      <td className="nowrap">{size}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card card-pad stack gap-14" aria-labelledby="package-title">
          <h2 id="package-title">Package</h2>
          <p className="kit-count">
            <span className="kit-number">{files.length}</span> file{files.length === 1 ? '' : 's'}
            {known && files.length > 0 && ` · about ${fileSize(bytes)}`}
          </p>
          <ul className="clean-list-plain stack gap-10">
            <li className="check-row">
              <span className={`check-dot ${signed ? 'check-ok' : 'check-pending'}`} aria-hidden="true">
                <Icon name={signed ? 'check' : 'clock'} size={16} strokeWidth={2.4} />
              </span>
              <span className="stack gap-1">
                <span className="check-title">{signed ? 'Signed ZIP package' : 'Not signed yet'}</span>
                <span className="check-detail">
                  {signed ? 'Any change to a file changes its fingerprint' : 'README.txt lists every file’s SHA-256 fingerprint'}
                </span>
              </span>
            </li>
            <li className="check-row">
              <span className={`check-dot ${signed ? 'check-ok' : 'check-pending'}`} aria-hidden="true">
                <Icon name={signed ? 'check' : 'clock'} size={16} strokeWidth={2.4} />
              </span>
              <span className="check-title">{signed ? 'QR code on every document' : 'QR codes added when signed'}</span>
            </li>
            <li className="check-row">
              <span className="check-dot check-ok" aria-hidden="true">
                <Icon name="check" size={16} strokeWidth={2.4} />
              </span>
              <span className="check-title row gap-8">
                Sharing label: {kit.tlp ? <TlpLabel tlp={kit.tlp} /> : 'not chosen'}
              </span>
            </li>
          </ul>
          <div className="divider" />
          <h3 className="notes-title">Save to</h3>
          <div className="save-option">
            <Icon name="download" size={20} />
            <span className="stack">
              <strong>This computer</strong>
              <span className="muted small">Your browser saves it (usually the Downloads folder). Copy it to a USB drive from there.</span>
            </span>
          </div>
          {files.length > 0 ? (
            <a className="btn btn-lg btn-green" href={href} download>
              <Icon name="download" size={18} strokeWidth={2} />
              {signed ? 'Save signed kit' : 'Save kit (.zip)'}
            </a>
          ) : (
            <button type="button" className="btn btn-lg btn-green" disabled>
              Tick at least one output
            </button>
          )}
        </section>
      </div>
    </main>
  )
}
