// Design 27 · Signed successfully: the record box (QR code, record number, fingerprint, signer),
// shown at the top of an approved job's Results page.
import { recordQrUrl, type JobDetail, type JobRecord } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { links } from '../router'
import { shortHash, shortTime } from './format'

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
            {files} file{files === 1 ? '' : 's'} signed
          </h2>
          <span className="muted">
            {job.title} · v{record.version} · signed {shortTime(record.issued_at)}
          </span>
        </div>
      )}
      {record.withdrawn && (
        <div className="alert alert-red" role="status">
          <strong>Withdrawn {shortTime(record.withdrawn.at)}.</strong> {record.withdrawn.reason} The verify page now shows it as
          withdrawn.
        </div>
      )}
      {!record.current && !record.withdrawn && (
        <div className="hint">This job was reopened as a new version. Record {record.record_no} stays valid until the new version is signed.</div>
      )}
      <div className="record-box">
        <img className="record-qr" src={recordQrUrl(record.record_no)} alt={`QR code for record ${record.record_no}`} width={128} height={128} />
        <dl className="record-details">
          <dt>Record</dt>
          <dd className="mono">{record.record_no}</dd>
          <dt>Fingerprint</dt>
          <dd className="mono" title={record.fingerprint}>
            SHA-256 {shortHash(record.fingerprint)}
          </dd>
          <dt>Signed by</dt>
          <dd>
            {record.approved_by} · {record.signer.replace(/ - NOT TESTED$/, '')}
          </dd>
          <dt>Files</dt>
          <dd>
            {files} file{files === 1 ? '' : 's'} and {record.texts} text fingerprint{record.texts === 1 ? '' : 's'}
          </dd>
        </dl>
      </div>
      {justSigned && (
        <ul className="signed-steps">
          <li>
            <Icon name="check" size={16} strokeWidth={2.4} color="var(--green-dark)" />
            <span>
              <strong>{job.owner?.full_name ?? 'The Operator'}</strong> can now download the signed files and kit
            </span>
          </li>
          <li>
            <Icon name="check" size={16} strokeWidth={2.4} color="var(--green-dark)" />
            <span>
              <strong>Record {record.record_no}</strong> added to the record book (hash-chained)
            </span>
          </li>
          <li>
            <Icon name="clock" size={16} color="var(--muted)" />
            <span>
              <strong>Public posts stay as drafts:</strong> they are released by your team's publishing process
            </span>
          </li>
        </ul>
      )}
      <div className="row gap-10 wrap">
        {user.role === 'reviewer' && (
          <a href={links.review} className="btn btn-green">
            <Icon name="arrowLeft" size={18} strokeWidth={2} />
            Back to review queue
          </a>
        )}
        <a href={record.verify_url} target="_blank" rel="noreferrer" className="btn btn-outline">
          <Icon name="scan" size={18} />
          Check a copy (verify page)
        </a>
      </div>
    </section>
  )
}
