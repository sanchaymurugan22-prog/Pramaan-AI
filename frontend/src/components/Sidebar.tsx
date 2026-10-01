import { useCallback, useEffect, useRef } from 'react'
import type { Role } from '../api'
import { initials, useAuth } from '../auth'
import { useCounts } from '../counts'
import type { Route } from '../router'
import { links } from '../router'
import { Icon, type IconName } from './Icon'
import { Logo } from './Logo'
import { TricolourStrip } from './TricolourStrip'

// badge: the number shown on the right, with words for screen readers ("2 drafts waiting")
type NavItem = { label: string; icon: IconName; href: string; pages: Route['page'][]; badge?: number; badgeLabel?: string }

const WORKSPACE: Record<Role, string> = {
  operator: 'Operator workspace',
  reviewer: 'Reviewer workspace',
  admin: 'Admin workspace',
}

// Each role sees its own menu (the backend refuses the other roles' pages anyway).
function mainNav(role: Role, watchDrafts: number, requests: number): NavItem[] {
  const check: NavItem = { label: 'Is this real?', icon: 'scan', href: links.check, pages: ['check'] }
  if (role === 'operator') {
    return [
      { label: 'Dashboard', icon: 'home', href: links.dashboard, pages: ['dashboard'] },
      { label: 'New transformation', icon: 'plus', href: links.newJob, pages: ['new', 'safety', 'outputs', 'progress'] },
      { label: 'My jobs', icon: 'history', href: links.jobs, pages: ['jobs', 'job', 'kit', 'compare'] },
      { label: 'Emergency alert', icon: 'siren', href: links.emergency, pages: ['emergency'] },
      {
        label: 'Watch folder', icon: 'folder', href: links.watch, pages: ['watch'],
        badge: watchDrafts || undefined, badgeLabel: `${watchDrafts} draft${watchDrafts === 1 ? '' : 's'} waiting`,
      },
      check,
    ]
  }
  if (role === 'reviewer') {
    return [
      { label: 'Review queue', icon: 'history', href: links.review, pages: ['review', 'review-job', 'send-back', 'signed', 'job', 'compare', 'kit'] },
      { label: 'Signed records', icon: 'shieldCheck', href: links.records, pages: ['records'] },
      check,
    ]
  }
  return [
    { label: 'Overview', icon: 'home', href: links.adminHome, pages: ['admin-home'] },
    {
      label: 'Users & access', icon: 'user', href: links.users, pages: ['users'],
      badge: requests || undefined, badgeLabel: `${requests} request${requests === 1 ? '' : 's'} waiting`,
    },
    { label: 'Audit trail', icon: 'hash', href: links.audit, pages: ['audit'] },
    { label: 'AI models', icon: 'chip', href: links.aiModels, pages: ['ai-models'] },
    { label: 'Templates', icon: 'summary', href: links.templates, pages: ['templates'] },
    { label: 'Security & policies', icon: 'shield', href: links.security, pages: ['security'] },
    { label: 'Record book', icon: 'box', href: links.recordBook, pages: ['record-book'] },
    { label: 'Public verify page', icon: 'globe', href: links.publicPage, pages: ['public-page'] },
    { label: 'Updates & backup', icon: 'refresh', href: links.backup, pages: ['backup'] },
    check,
  ]
}

function NavLink({ item, route }: { item: NavItem; route: Route }) {
  const current = item.pages.includes(route.page)
  return (
    <a href={item.href} className={current ? 'nav-link is-current' : 'nav-link'} aria-current={current ? 'page' : undefined}>
      {current && <span className="nav-marker" />}
      <Icon name={item.icon} color={current ? 'var(--role-dark)' : 'var(--icon)'} />
      {item.label}
      {item.badge !== undefined && (
        <span className="nav-badge">
          <span aria-hidden="true">{item.badge}</span>
          <span className="sr-only">{item.badgeLabel}</span>
        </span>
      )}
    </a>
  )
}

type Props = {
  route: Route
  open: boolean // narrow screens / 200% zoom: shown as a drawer over the page
  onClose: () => void
}

export function Sidebar({ route, open, onClose }: Props) {
  const { user, signOut } = useAuth()
  const { counts } = useCounts()
  const panel = useRef<HTMLElement>(null)

  // The drawer: focus moves into it when it opens; Escape, the close button or a click outside close
  // it and put focus back on the Menu button
  const close = useCallback(() => {
    onClose()
    document.querySelector<HTMLElement>('.menu-btn')?.focus()
  }, [onClose])
  useEffect(() => {
    if (!open) return
    panel.current?.querySelector<HTMLElement>('a, button')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, close])

  const account: NavItem[] = [
    {
      label: 'Notifications', icon: 'bell', href: links.notifications, pages: ['notifications'],
      badge: counts.unread || undefined, badgeLabel: `${counts.unread} unread`,
    },
    { label: 'Profile & settings', icon: 'sliders', href: links.profile, pages: ['profile', 'password'] },
    { label: 'Help', icon: 'summary', href: links.help, pages: ['help'] },
  ]
  return (
    <>
      {open && <div className="drawer-backdrop" onClick={close} aria-hidden="true" />}
      <nav ref={panel} id="main-menu" className={open ? 'sidebar is-open' : 'sidebar'} aria-label="Main">
        <TricolourStrip />
        <div className="sidebar-inner">
          <div className="row">
            <Logo />
            <button type="button" className="icon-btn drawer-close" aria-label="Close menu" onClick={close}>
              <Icon name="cross" size={18} />
            </button>
          </div>

          <div className="workspace-pill">
            <span className="dot" aria-hidden="true" />
            {WORKSPACE[user.role]}
          </div>

          <div className="nav-group">
            {mainNav(user.role, counts.watch_drafts, counts.requests).map((item) => (
              <NavLink key={item.label} item={item} route={route} />
            ))}
          </div>

          <div className="divider" />

          <div className="nav-group">
            {account.map((item) => (
              <NavLink key={item.label} item={item} route={route} />
            ))}
          </div>

          <div className="grow" />

          <div className="offline-box">
            <Icon name="wifiOff" size={18} color="var(--green-dark)" strokeWidth={2} />
            <span className="stack">
              <span className="offline-title">Fully offline</span>
              <span className="offline-sub">Nothing leaves this computer</span>
            </span>
          </div>

          <div className="user-row">
            <div className="avatar" aria-hidden="true">{initials(user.full_name)}</div>
            <div className="stack grow">
              <span className="user-name">{user.full_name}</span>
              <span className="user-role">{user.role_label}</span>
            </div>
            <button type="button" className="icon-link" aria-label="Sign out" title="Sign out" onClick={() => signOut()}>
              <Icon name="signOut" size={19} strokeWidth={1.8} />
            </button>
          </div>
        </div>
      </nav>
    </>
  )
}
