// Design 27 · Signed successfully: the record box (QR code, record number, fingerprint, signer),
// shown at the top of an approved job's Results page.
import { recordQrUrl, type JobDetail, type JobRecord } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { links } from '../router'
import { shortHash, shortTime } from './format'
import { t } from '../i18n'

export function SignedRecord({ job, record, justSigned }: { job: JobDetail; record: JobRecord; justSigned: boolean }) {
  const { user } = useAuth()
  const files = record.files.length
  return (
    <section className="card card-pad signed-card stack gap-16">
      {justSigned && (
        <div className="stack gap-6 center-items center">
          <span className="signed-tick">
            <Icon name="check" size={40} strokeWidth={3} color="#fff" />
          </span>
          <h2 className="signed-title">
            {t("{files} file{value} signed", { files: files, value: files === 1 ? '' : 's' })}</h2>
          <span className="muted">
            {t("{title} · v{version} · signed {issued_at}", { title: job.title, version: record.version, issued_at: shortTime(record.issued_at) })}</span>
        </div>
      )}
      {record.withdrawn && (
        <div className="alert alert-red" role="status">
          <strong>{t("Withdrawn {at}.", { at: shortTime(record.withdrawn.at) })}</strong> {record.withdrawn.reason} {t("The verify page now shows it as withdrawn.")}
        </div>
      )}
      {!record.current && !record.withdrawn && (
        <div className="hint">{t("This job was reopened as a new version. Record {record_no} stays valid until the new version is signed.", { record_no: record.record_no })}</div>
      )}
      <div className="record-box">
        <img className="record-qr" src={recordQrUrl(record.record_no)} alt={t("QR code for record {record_no}", { record_no: record.record_no })} width={128} height={128} />
        <dl className="record-details">
          <dt>{t("Record")}</dt>
          <dd className="mono">{record.record_no}</dd>
          <dt>{t("Fingerprint")}</dt>
          <dd className="mono" title={record.fingerprint}>
            SHA-256 {shortHash(record.fingerprint)}
          </dd>
          <dt>{t("Signed by")}</dt>
          <dd>
            {record.approved_by} · {record.signer.replace(/ - NOT TESTED$/, '')}
          </dd>
          <dt>{t("Files")}</dt>
          <dd>
            {t("{files} file{value} and {texts} text fingerprint{value2}", { files: files, value: files === 1 ? '' : 's', texts: record.texts, value2: record.texts === 1 ? '' : 's' })}</dd>
        </dl>
      </div>
      {justSigned && (
        <ul className="signed-steps">
          <li>
            <Icon name="check" size={16} strokeWidth={2.4} color="var(--green-dark)" />
            <span>
              <strong>{job.owner?.full_name ?? t("The Operator")}</strong> {t("can now download the signed files and kit")}
            </span>
          </li>
          <li>
            <Icon name="check" size={16} strokeWidth={2.4} color="var(--green-dark)" />
            <span>
              <strong>{t("Record {record_no}", { record_no: record.record_no })}</strong> {t("added to the record book (hash-chained)")}
            </span>
          </li>
          <li>
            <Icon name="clock" size={16} color="var(--muted)" />
            <span>
              <strong>{t("Public posts stay as drafts:")}</strong> {t("they are released by your team's publishing process")}
            </span>
          </li>
        </ul>
      )}
      <div className="row gap-10 wrap">
        {user.role === 'reviewer' && (
          <a href={links.review} className="btn btn-green">
            <Icon name="arrowLeft" size={18} strokeWidth={2} />
            {t("Back to review queue")}
          </a>
        )}
        <a href={record.verify_url} target="_blank" rel="noreferrer" className="btn btn-outline">
          <Icon name="scan" size={18} />
          {t("Check a copy (verify page)")}
        </a>
      </div>
    </section>
  )
}
