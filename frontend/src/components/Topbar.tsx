import type { Health } from '../api'
import { Icon } from './Icon'

type Props = {
  // undefined = still checking, null = backend not reachable
  health: Health | null | undefined
}

// Shows which AI is in use, read live from /api/health.
function ModelChip({ health }: Props) {
  if (health === undefined) return <span className="chip chip-neutral">Checking…</span>
  if (health === null)
    return (
      <span className="chip chip-red">
        <Icon name="warning" size={14} strokeWidth={2.2} />
        Backend offline
      </span>
    )
  return (
    <span className="chip chip-navy">
      <Icon name="chip" size={14} strokeWidth={2.2} />
      {health.ai_mode === 'local' ? 'Sarvam 30B · local' : 'Sarvam · cloud'}
    </span>
  )
}

export function Topbar({ health }: Props) {
  return (
    <header className="topbar">
      <label className="search">
        <span className="search-icon">
          <Icon name="search" size={18} strokeWidth={1.8} />
        </span>
        <input type="search" aria-label="Search" placeholder="Search jobs, documents, records" />
      </label>
      <div className="grow" />
      <ModelChip health={health} />
      <button type="button" className="btn btn-outline btn-sm" title="Language picker comes in Stage 8">
        <Icon name="globe" size={18} color="var(--muted)" strokeWidth={1.8} />
        English
      </button>
      <button type="button" className="icon-btn" aria-label="Notifications, 3 unread">
        <Icon name="bell" size={20} strokeWidth={1.8} />
        <span className="unread-dot" />
      </button>
    </header>
  )
}
