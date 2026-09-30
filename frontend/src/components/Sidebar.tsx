import type { Route } from '../router'
import { links } from '../router'
import { Icon, type IconName } from './Icon'
import { Logo } from './Logo'
import { TricolourStrip } from './TricolourStrip'

// href = a page that exists; items without one are built in later stages and do nothing yet.
type NavItem = { label: string; icon: IconName; badge?: number; href?: string; pages?: Route['page'][] }

const MAIN_NAV: NavItem[] = [
  { label: 'Dashboard', icon: 'home', href: links.dashboard, pages: ['dashboard'] },
  { label: 'New transformation', icon: 'plus', href: links.newJob, pages: ['new', 'safety', 'outputs'] },
  { label: 'My jobs', icon: 'history', href: links.jobs, pages: ['jobs', 'job'] },
  { label: 'Emergency alert', icon: 'siren' },
  { label: 'Watch folder', icon: 'folder', badge: 2 },
  { label: 'Is this real?', icon: 'scan' },
]

const ACCOUNT_NAV: NavItem[] = [
  { label: 'Notifications', icon: 'bell', badge: 3 },
  { label: 'Profile & settings', icon: 'sliders' },
]

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
      <Icon name={item.icon} color={current ? 'var(--saffron)' : 'var(--icon)'} />
      {item.label}
      {item.badge !== undefined && <span className="nav-badge">{item.badge}</span>}
    </a>
  )
}

export function Sidebar({ route }: { route: Route }) {
  return (
    <nav className="sidebar" aria-label="Main">
      <TricolourStrip />
      <div className="sidebar-inner">
        <Logo />

        <div className="workspace-pill">
          <span className="dot" />
          Operator workspace
        </div>

        <div className="nav-group">
          {MAIN_NAV.map((item) => (
            <NavLink key={item.label} item={item} route={route} />
          ))}
        </div>

        <div className="divider" />

        <div className="nav-group">
          {ACCOUNT_NAV.map((item) => (
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

        {/* Placeholder user until login is built in Stage 6 */}
        <div className="user-row">
          <div className="avatar">PS</div>
          <div className="stack grow">
            <span className="user-name">Priya Sharma</span>
            <span className="user-role">Operator</span>
          </div>
          <a href="#" className="icon-link" aria-label="Sign out" onClick={(e) => e.preventDefault()}>
            <Icon name="signOut" size={19} strokeWidth={1.8} />
          </a>
        </div>
      </div>
    </nav>
  )
}
