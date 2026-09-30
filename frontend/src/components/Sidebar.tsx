import { Icon, type IconName } from './Icon'
import { Logo } from './Logo'
import { TricolourStrip } from './TricolourStrip'

type NavItem = { label: string; icon: IconName; badge?: number; current?: boolean }

// Only the Dashboard exists in Stage 2. The other pages are built in later stages,
// so their links are shown (to match the design) but do nothing yet.
const MAIN_NAV: NavItem[] = [
  { label: 'Dashboard', icon: 'home', current: true },
  { label: 'New transformation', icon: 'plus' },
  { label: 'My jobs', icon: 'history' },
  { label: 'Emergency alert', icon: 'siren' },
  { label: 'Watch folder', icon: 'folder', badge: 2 },
  { label: 'Is this real?', icon: 'scan' },
]

const ACCOUNT_NAV: NavItem[] = [
  { label: 'Notifications', icon: 'bell', badge: 3 },
  { label: 'Profile & settings', icon: 'sliders' },
]

function NavLink({ item }: { item: NavItem }) {
  return (
    <a
      href="#"
      className={item.current ? 'nav-link is-current' : 'nav-link'}
      aria-current={item.current ? 'page' : undefined}
      title={item.current ? undefined : 'Coming in a later stage'}
      onClick={(e) => e.preventDefault()}
    >
      {item.current && <span className="nav-marker" />}
      <Icon name={item.icon} color={item.current ? 'var(--saffron)' : 'var(--icon)'} />
      {item.label}
      {item.badge !== undefined && <span className="nav-badge">{item.badge}</span>}
    </a>
  )
}

export function Sidebar() {
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
            <NavLink key={item.label} item={item} />
          ))}
        </div>

        <div className="divider" />

        <div className="nav-group">
          {ACCOUNT_NAV.map((item) => (
            <NavLink key={item.label} item={item} />
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
