import type { Role } from '../api'
import { initials, useAuth } from '../auth'
import type { Route } from '../router'
import { links } from '../router'
import { Icon, type IconName } from './Icon'
import { Logo } from './Logo'
import { TricolourStrip } from './TricolourStrip'

// href = a page that exists; items without one are built in later stages and do nothing yet.
type NavItem = { label: string; icon: IconName; badge?: number; href?: string; pages?: Route['page'][] }

// Each role sees its own menu (the backend refuses the other roles' pages anyway).
const MAIN_NAV: Record<Role, NavItem[]> = {
  operator: [
    { label: 'Dashboard', icon: 'home', href: links.dashboard, pages: ['dashboard'] },
    { label: 'New transformation', icon: 'plus', href: links.newJob, pages: ['new', 'safety', 'outputs'] },
    { label: 'My jobs', icon: 'history', href: links.jobs, pages: ['jobs', 'job'] },
    { label: 'Emergency alert', icon: 'siren' },
    { label: 'Watch folder', icon: 'folder' },
    { label: 'Is this real?', icon: 'scan' },
  ],
  reviewer: [
    { label: 'Review queue', icon: 'history', href: links.review, pages: ['review', 'job'] },
    { label: 'Signed records', icon: 'shieldCheck', href: links.records, pages: ['records'] },
    { label: 'Is this real?', icon: 'scan' },
  ],
  admin: [
    { label: 'Users & access', icon: 'user', href: links.users, pages: ['users'] },
    { label: 'Audit trail', icon: 'hash', href: links.audit, pages: ['audit'] },
    { label: 'AI models', icon: 'chip' },
    { label: 'Security & policies', icon: 'shield' },
    { label: 'Record book', icon: 'box', href: links.recordBook, pages: ['record-book'] },
  ],
}

const WORKSPACE: Record<Role, string> = {
  operator: 'Operator workspace',
  reviewer: 'Reviewer workspace',
  admin: 'Admin workspace',
}

function NavLink({ item, route }: { item: NavItem; route: Route }) {
  const current = item.pages?.includes(route.page) ?? false
  return (
    <a
      href={item.href ?? '#'}
      className={current ? 'nav-link is-current' : 'nav-link'}
      aria-current={current ? 'page' : undefined}
      title={item.href ? undefined : 'Coming in a later stage'}
      onClick={item.href ? undefined : (e) => e.preventDefault()}
    >
      {current && <span className="nav-marker" />}
      <Icon name={item.icon} color={current ? 'var(--role)' : 'var(--icon)'} />
      {item.label}
      {item.badge !== undefined && <span className="nav-badge">{item.badge}</span>}
    </a>
  )
}

export function Sidebar({ route }: { route: Route }) {
  const { user, signOut } = useAuth()
  const account: NavItem[] = [{ label: 'Change password', icon: 'key', href: links.password, pages: ['password'] }]
  return (
    <nav className="sidebar" aria-label="Main">
      <TricolourStrip />
      <div className="sidebar-inner">
        <Logo />

        <div className="workspace-pill">
          <span className="dot" />
          {WORKSPACE[user.role]}
        </div>

        <div className="nav-group">
          {MAIN_NAV[user.role].map((item) => (
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
          <div className="avatar">{initials(user.full_name)}</div>
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
  )
}
