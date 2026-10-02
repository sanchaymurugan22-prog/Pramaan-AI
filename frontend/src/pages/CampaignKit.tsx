import { useEffect, useState } from 'react'
import { getKitInfo, kitUrl, type KitInfo } from '../api'
import { Icon } from '../components/Icon'
import { OUTPUT_ICONS } from '../components/outputIcons'
import { TlpLabel } from '../components/TlpLabel'
import { links } from '../router'
import { fileSize, jobNo } from './format'
import { locale, t } from '../i18n'

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
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load the kit.")))
  }, [jobId])

  if (!kit || !picked) {
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>
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
          <div className="eyebrow">{t("Job {job_id} · Campaign kit", { job_id: jobNo(kit.job_id) })}</div>
          <h1>{signed ? t("Download the signed kit") : t("Download the campaign kit")}</h1>
          <p className="muted page-lead">
            {signed
              ? t("Every approved file in one package, each with its own QR code.")
              : t("Every finished file in one package. QR codes and the record number are added when a Reviewer signs it.")}
          </p>
        </div>
        <div className="grow" />
        <a className="btn btn-outline" href={links.job(kit.job_id)}>
          <Icon name="arrowLeft" size={18} strokeWidth={2} />
          {t("Back to results")}
        </a>
      </div>

      {signed && record ? (
        <section className="kit-banner kit-banner-green" aria-label={t("Signature")}>
          <span className="kit-banner-icon" aria-hidden="true">
            <Icon name="award" size={24} />
          </span>
          <span className="stack gap-2 grow">
            <strong className="kit-banner-title">{t("Approved and signed by {approved_by}", { approved_by: record.approved_by })}</strong>
            <span className="small">
              {t("{value} · {signer} · Record {record_no}", { value: new Date(record.issued_at).toLocaleString(locale(), { dateStyle: 'medium', timeStyle: 'short' }), signer: record.signer, record_no: record.record_no })}</span>
          </span>
          <span className="chip chip-green">
            <Icon name="check" size={14} strokeWidth={2.4} />
            {record.files.length} {t("files signed")}
          </span>
        </section>
      ) : (
        <section className="kit-banner kit-banner-yellow" aria-label={t("Not signed yet")}>
          <span className="kit-banner-icon" aria-hidden="true">
            <Icon name="warning" size={24} />
          </span>
          <span className="stack gap-2 grow">
            <strong className="kit-banner-title">{t("Not signed yet")}</strong>
            <span className="small">
              {record?.withdrawn
                ? t("Record {record_no} was withdrawn. These files are not signed.", { record_no: record.record_no })
                : t("Use these files for checking only. Send the job for review: when a Reviewer approves it, the kit holds the signed files.")}
            </span>
          </span>
        </section>
      )}

      <div className="kit-grid">
        <section className="card card-pad stack gap-12" aria-labelledby="inside-title">
          <div className="row gap-10">
            <h2 id="inside-title" className="grow">
              {t("What is inside")}
            </h2>
            <label className="check-pill">
              <input
                type="checkbox"
                checked={allPicked}
                onChange={() => setPicked(allPicked ? [] : usable.map((o) => o.type))}
              />
              {t("Select all")}
            </label>
          </div>
          <div className="table-scroll">
            <table className="jobs-table">
              <caption className="sr-only">{t("Outputs in the kit")}</caption>
              <thead>
                <tr>
                  <th scope="col">
                    <span className="sr-only">{t("Put in the kit")}</span>
                  </th>
                  <th scope="col">{t("Output")}</th>
                  <th scope="col">{t("Formats")}</th>
                  <th scope="col">{t("Language")}</th>
                  <th scope="col">{t("Size")}</th>
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
                          aria-label={t("Put the {label} in the kit", { label: o.label })}
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
                            <strong>{t(o.label)}</strong>
                            {o.blocked && <span className="small over-limit">{t("Left out: private data found in it")}</span>}
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
          <h2 id="package-title">{t("Package")}</h2>
          <p className="kit-count">
            <span className="kit-number">{files.length}</span> {t("file")}{files.length === 1 ? '' : 's'}
            {known && files.length > 0 && t(" · about {n}", { n: fileSize(bytes) })}
          </p>
          <ul className="clean-list-plain stack gap-10">
            <li className="check-row">
              <span className={`check-dot ${signed ? 'check-ok' : 'check-pending'}`} aria-hidden="true">
                <Icon name={signed ? 'check' : 'clock'} size={16} strokeWidth={2.4} />
              </span>
              <span className="stack gap-1">
                <span className="check-title">{signed ? t("Signed ZIP package") : t("Not signed yet")}</span>
                <span className="check-detail">
                  {signed ? t("Any change to a file changes its fingerprint") : t("README.txt lists every file’s SHA-256 fingerprint")}
                </span>
              </span>
            </li>
            <li className="check-row">
              <span className={`check-dot ${signed ? 'check-ok' : 'check-pending'}`} aria-hidden="true">
                <Icon name={signed ? 'check' : 'clock'} size={16} strokeWidth={2.4} />
              </span>
              <span className="check-title">{signed ? t("QR code on every document") : t("QR codes added when signed")}</span>
            </li>
            <li className="check-row">
              <span className="check-dot check-ok" aria-hidden="true">
                <Icon name="check" size={16} strokeWidth={2.4} />
              </span>
              <span className="check-title row gap-8">
                {t("Sharing label:")} {kit.tlp ? <TlpLabel tlp={kit.tlp} /> : t("not chosen")}
              </span>
            </li>
          </ul>
          <div className="divider" />
          <h3 className="notes-title">{t("Save to")}</h3>
          <div className="save-option">
            <Icon name="download" size={20} />
            <span className="stack">
              <strong>{t("This computer")}</strong>
              <span className="muted small">{t("Your browser saves it (usually the Downloads folder). Copy it to a USB drive from there.")}</span>
            </span>
          </div>
          {files.length > 0 ? (
            <a className="btn btn-lg btn-green" href={href} download>
              <Icon name="download" size={18} strokeWidth={2} />
              {signed ? t("Save signed kit") : t("Save kit (.zip)")}
            </a>
          ) : (
            <button type="button" className="btn btn-lg btn-green" disabled>
              {t("Tick at least one output")}
            </button>
          )}
        </section>
      </div>
    </main>
  )
}
