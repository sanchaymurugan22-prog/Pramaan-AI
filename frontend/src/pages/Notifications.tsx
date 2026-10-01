import { useEffect, useState } from 'react'
import { listNotifications, readAllNotifications, readNotification, type Notification, type NotificationKind } from '../api'
import { useAuth } from '../auth'
import { useCounts } from '../counts'
import { Icon, type IconName } from '../components/Icon'
import { links, navigate } from '../router'
import { dayLabel, shortTime } from './format'

// Design "40 · Notifications (all roles)": in-app only (nothing is emailed or texted; works offline).
// Each kind has its own icon, colour AND words, so nothing depends on colour alone.

type Look = { icon: IconName; tone: 'green' | 'red' | 'saffron' | 'navy'; action: string }
const LOOK: Record<NotificationKind, Look> = {
  finished: { icon: 'spinner', tone: 'navy', action: 'Open' },
  failed: { icon: 'warning', tone: 'red', action: 'Open' },
  submitted: { icon: 'eye', tone: 'navy', action: 'Review' },
  sent_back: { icon: 'arrowLeft', tone: 'red', action: 'View notes' },
  approved: { icon: 'check', tone: 'green', action: 'Open' },
  signed: { icon: 'award', tone: 'green', action: 'Open kit' },
  watch: { icon: 'folder', tone: 'saffron', action: 'Open' },
  alert: { icon: 'siren', tone: 'red', action: 'Review now' },
}

function target(note: Notification, role: string): string | null {
  if (note.job_id === null) return null
  if (note.kind === 'signed') return links.kit(note.job_id)
  if (note.kind === 'watch' && role === 'operator') return links.safety(note.job_id)
  return links.job(note.job_id)
}

export function Notifications() {
  const { user } = useAuth()
  const { refresh } = useCounts()
  const [tab, setTab] = useState<'all' | 'unread'>('all')
  const [items, setItems] = useState<Notification[] | null>(null)
  const [unread, setUnread] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    listNotifications(tab === 'unread')
      .then((body) => {
        setItems(body.items)
        setUnread(body.unread)
        setError('')
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load notifications.'))
  }, [tab])

  async function open(note: Notification) {
    if (!note.read) {
      try {
        await readNotification(note.id)
      } catch {
        // still open it
      }
      refresh()
    }
    const href = target(note, user.role)
    if (href) navigate(href)
  }

  async function readAll() {
    await readAllNotifications()
    setItems((list) => list?.map((n) => ({ ...n, read: true })) ?? null)
    setUnread(0)
    refresh()
  }

  // Grouped by day: Today, Yesterday, 28 Sep 2026 ...
  const groups: { day: string; items: Notification[] }[] = []
  for (const note of items ?? []) {
    const day = dayLabel(note.created_at)
    if (groups.at(-1)?.day !== day) groups.push({ day, items: [] })
    groups.at(-1)!.items.push(note)
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">Inbox</div>
          <h1>Notifications</h1>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-outline" onClick={readAll} disabled={unread === 0}>
          <Icon name="check" size={18} strokeWidth={2} />
          Mark all as read
        </button>
      </div>

      <div className="segmented segmented-wide" role="tablist" aria-label="Show">
        <button type="button" role="tab" aria-selected={tab === 'all'} className={tab === 'all' ? 'is-on' : ''} onClick={() => setTab('all')}>
          All
        </button>
        <button type="button" role="tab" aria-selected={tab === 'unread'} className={tab === 'unread' ? 'is-on' : ''} onClick={() => setTab('unread')}>
          Unread ({unread})
        </button>
      </div>

      {error && <div className="alert alert-red">{error}</div>}
      {items === null && !error && <p className="muted">Loading…</p>}
      {items && items.length === 0 && (
        <p className="muted">{tab === 'unread' ? 'Nothing unread.' : 'No notifications yet. You will see here when a job is ready, sent back, approved or signed.'}</p>
      )}

      {groups.map((group) => (
        <section key={group.day} className="stack gap-10" aria-label={group.day}>
          <h2 className="section-label">{group.day}</h2>
          <ul className="note-list">
            {group.items.map((note) => {
              const look = LOOK[note.kind]
              const href = target(note, user.role)
              return (
                <li key={note.id} className={note.read ? 'card note' : 'card note is-unread'}>
                  <span className="note-dot" aria-hidden="true" />
                  <span className={`note-icon tone-${look.tone}`} aria-hidden="true">
                    <Icon name={look.icon} size={20} />
                  </span>
                  <span className="stack gap-2 grow note-text">
                    <span className="note-title">
                      {!note.read && <span className="sr-only">Unread: </span>}
                      {note.title}
                    </span>
                    {note.detail && <span className="note-detail">{note.detail}</span>}
                  </span>
                  <span className="muted small nowrap">{shortTime(note.created_at)}</span>
                  {href && (
                    <button type="button" className={`btn btn-sm note-action tone-${look.tone}`} onClick={() => open(note)}>
                      {look.action}
                    </button>
                  )}
                  {!href && !note.read && (
                    <button type="button" className="btn btn-sm btn-outline" onClick={() => open(note)}>
                      Mark read
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </main>
  )
}
