import type { JobStatus } from '../api'
import { Icon, type IconName } from './Icon'

// Colour + icon + label for each job status, as in the design.
const STATUS: Record<JobStatus, { label: string; icon: IconName; className: string }> = {
  approved: { label: 'Approved', icon: 'check', className: 'chip-green' },
  ready: { label: 'Ready', icon: 'check', className: 'chip-green' },
  failed: { label: 'Failed', icon: 'warning', className: 'chip-red' },
  in_review: { label: 'In review', icon: 'eye', className: 'chip-navy' },
  sent_back: { label: 'Sent back', icon: 'arrowLeft', className: 'chip-red' },
  generating: { label: 'Generating', icon: 'spinner', className: 'chip-saffron' },
  draft: { label: 'Draft', icon: 'pencil', className: 'chip-neutral' },
}

export function StatusChip({ status, progress }: { status: JobStatus; progress?: string }) {
  const s = STATUS[status]
  return (
    <span className={`chip ${s.className}`}>
      <Icon name={s.icon} size={14} strokeWidth={2.2} />
      {s.label}
      {progress !== undefined && ` ${progress}`}
    </span>
  )
}
