import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getAuthStatus, getHealth, setSignedOutHandler, signOut as apiSignOut, type Health, type Role, type User } from './api'
import { AuthContext, ROLE_TONE } from './auth'
import { CountsProvider } from './counts'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { AuditTrail } from './pages/admin/AuditTrail'
import { Users } from './pages/admin/Users'
import { AdminOverview } from './pages/admin/Overview'
import { AiModels } from './pages/admin/AiModels'
import { Templates } from './pages/admin/Templates'
import { Security } from './pages/admin/Security'
import { Backup, PublicPage } from './pages/admin/PublicPage'
import { IsThisReal } from './pages/IsThisReal'
import { RecordsPage } from './pages/RecordsPage'
import { Forgot } from './pages/auth/Forgot'
import { Pending, RequestAccess } from './pages/auth/RequestAccess'
import { Setup } from './pages/auth/Setup'
import { SignIn } from './pages/auth/SignIn'
import { LanguagePicker, Splash } from './pages/auth/Welcome'
import { storedLanguage, welcomed } from './localPrefs'
import { ForcedPasswordChange } from './pages/ChangePassword'
import { Profile } from './pages/Profile'
import { Help, NoAccess } from './pages/Help'
import { JobsList } from './pages/JobsList'
import { Notifications } from './pages/Notifications'
import { WatchFolder } from './pages/WatchFolder'
import { EmergencyAlert } from './pages/EmergencyAlert'
import { Progress } from './pages/Progress'
import { CampaignKit } from './pages/CampaignKit'
import { VersionCompare } from './pages/VersionCompare'
import { NewTransformation } from './pages/NewTransformation'
import { OperatorDashboard } from './pages/OperatorDashboard'
import { OutputsStep } from './pages/OutputsStep'
import { Results } from './pages/Results'
import { ReviewQueue } from './pages/ReviewQueue'
import { ReviewJob, Signed } from './pages/ReviewJob'
import { SendBack } from './pages/SendBack'
import { SafetyCheck } from './pages/SafetyCheck'
import { links, navigate, useRoute, type Route } from './router'
import { setLanguage, t } from './i18n'

// The pages each role may open. Anything else sends them to their home page.
// (Only for convenience: the backend refuses other roles' requests with 403.)
const ROLE_PAGES: Record<Role, Route['page'][]> = {
  operator: ['dashboard', 'new', 'safety', 'outputs', 'jobs', 'job', 'check', 'password', 'notifications', 'watch', 'emergency', 'progress', 'kit', 'compare', 'profile', 'help'],
  reviewer: ['review', 'review-job', 'send-back', 'signed', 'job', 'records', 'check', 'password', 'notifications', 'kit', 'compare', 'profile', 'help'],
  admin: ['admin-home', 'users', 'ai-models', 'templates', 'security', 'public-page', 'backup', 'audit', 'record-book', 'check', 'password', 'notifications', 'profile', 'help'],
}
const HOME: Record<Role, string> = { operator: links.dashboard, reviewer: links.review, admin: links.adminHome }
const SIGNED_OUT_PAGES: Route['page'][] = ['welcome', 'login', 'request-access', 'forgot', 'pending']

export default function App() {
  // undefined = still checking, null = backend not reachable
  const [health, setHealth] = useState<Health | null | undefined>(undefined)
  const [needsSetup, setNeedsSetup] = useState<boolean | undefined>(undefined)
  const [user, setUser] = useState<User | null>(null)
  const [notice, setNotice] = useState('') // e.g. "You were signed out after 30 minutes without activity."
  const [menuOpen, setMenuOpen] = useState(false) // the menu as a drawer (narrow screens, 200% zoom)
  const content = useRef<HTMLDivElement>(null)
  const route = useRoute()
  const routeKey = 'id' in route ? `${route.page}/${route.id}` : route.page

  // A new page: close the drawer and move keyboard focus to the page, so screen readers start there
  const firstRoute = useRef(true)
  useEffect(() => {
    setMenuOpen(false)
    if (firstRoute.current) {
      firstRoute.current = false
      return
    }
    content.current?.focus({ preventScroll: true })
  }, [routeKey])
  const closeMenu = useCallback(() => setMenuOpen(false), [])

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
    getAuthStatus()
      .then((status) => {
        setNeedsSetup(status.needs_setup)
        setUser(status.user)
      })
      .catch(() => setNeedsSetup(false))
  }, [])

  // Any request answered "not signed in" (session ended): back to Sign in, with the reason.
  useEffect(() => {
    setSignedOutHandler((message) => {
      setUser(null)
      setNotice(message)
    })
  }, [])

  const signOut = useCallback(async () => {
    try {
      await apiSignOut()
    } finally {
      setUser(null)
      setNotice(t("You have signed out."))
      navigate(links.login)
    }
  }, [])

  const signedIn = useCallback((next: User) => {
    setUser(next)
    setNotice('')
    setNeedsSetup(false)
    navigate(HOME[next.role])
  }, [])

  const auth = useMemo(() => (user ? { user, setUser, signOut } : null), [user, signOut])

  // The start address (#/) and the sign-in pages lead each role to its own home page. Any other page a
  // role may not open shows "You don't have access" (Stage 9B); the backend refuses its data anyway (403).
  useEffect(() => {
    if (!user || user.must_change_password) return
    const start = route.page === 'dashboard' && user.role !== 'operator'
    if (start || SIGNED_OUT_PAGES.includes(route.page) || route.page === 'language') navigate(HOME[user.role])
  }, [user, route.page])

  // Stage 8: the interface language: the signed-in user's (Profile, or the switch at the top right), else the one
  // chosen on the welcome screens. Set before anything is drawn; the pages are keyed by it, so a change redraws all.
  const uiLang = setLanguage(user ? user.language : storedLanguage())

  if (needsSetup === undefined) {
    return <p className="muted boot-note">{health === null ? t("The backend is not running. Start it with ./scripts/start.sh") : t("Loading…")}</p>
  }
  if (needsSetup) return <Setup onDone={signedIn} />

  if (!user || !auth) {
    // Design 01: the splash, once per browser (or at #/welcome); design 02: the language screen
    if (route.page === 'welcome' || (!welcomed() && !notice && route.page !== 'language')) return <Splash health={health} />
    if (route.page === 'language') return <LanguagePicker />
    if (route.page === 'request-access') return <RequestAccess />
    if (route.page === 'forgot') return <Forgot />
    if (route.page === 'pending') return <Pending />
    return <SignIn notice={notice} onSignedIn={signedIn} />
  }

  if (user.must_change_password) {
    return <ForcedPasswordChange onDone={(u) => signedIn(u)} onSignOut={signOut} />
  }

  const page = ROLE_PAGES[user.role].includes(route.page) && !SIGNED_OUT_PAGES.includes(route.page) ? route : null
  return (
    <AuthContext.Provider value={auth}>
      <CountsProvider key={uiLang}>
      <div
        className={[
          'app',
          `role-${ROLE_TONE[user.role]}`,
          user.prefs?.text_size && user.prefs.text_size !== 'normal' && `text-${user.prefs.text_size}`,
          user.prefs?.high_contrast && 'high-contrast',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {/* GIGW / WCAG 2.4.1: the first Tab stop jumps straight to the page, past the menu */}
        <a
          href="#/"
          className="skip-link"
          onClick={(e) => {
            e.preventDefault() // the address after "#" is the page, so do not change it
            content.current?.focus()
          }}
        >
          {t("Skip to main content")}
        </a>
        <Sidebar route={route} open={menuOpen} onClose={closeMenu} />
        <div className="main-col">
          <Topbar health={health} onMenu={() => setMenuOpen((open) => !open)} menuOpen={menuOpen} />
          <div ref={content} id="content" tabIndex={-1} className="content">
          {page?.page === 'dashboard' && <OperatorDashboard health={health} />}
          {page?.page === 'new' && <NewTransformation />}
          {page?.page === 'safety' && <SafetyCheck key={page.id} jobId={page.id} />}
          {page?.page === 'outputs' && <OutputsStep key={page.id} jobId={page.id} health={health} />}
          {page?.page === 'jobs' && <JobsList />}
          {page?.page === 'job' && <Results key={page.id} jobId={page.id} />}
          {page?.page === 'review' && <ReviewQueue />}
          {page?.page === 'review-job' && <ReviewJob key={page.id} jobId={page.id} />}
          {page?.page === 'send-back' && <SendBack key={page.id} jobId={page.id} />}
          {page?.page === 'signed' && <Signed key={page.id} jobId={page.id} />}
          {page?.page === 'admin-home' && <AdminOverview />}
          {page?.page === 'users' && <Users />}
          {page?.page === 'ai-models' && <AiModels />}
          {page?.page === 'templates' && <Templates />}
          {page?.page === 'security' && <Security />}
          {page?.page === 'public-page' && <PublicPage />}
          {page?.page === 'backup' && <Backup />}
          {page?.page === 'audit' && <AuditTrail />}
          {page?.page === 'records' && <RecordsPage admin={false} />}
          {page?.page === 'record-book' && <RecordsPage admin />}
          {(page?.page === 'password' || page?.page === 'profile') && <Profile onChanged={setUser} />}
          {page?.page === 'help' && <Help />}
          {route.page === 'not-found' && <NoAccess notFound />}
          {!page && route.page !== 'not-found' && !SIGNED_OUT_PAGES.includes(route.page) && !(route.page === 'dashboard' && user.role !== 'operator') && (
            <NoAccess />
          )}
          {page?.page === 'check' && <IsThisReal />}
          {page?.page === 'notifications' && <Notifications />}
          {page?.page === 'progress' && <Progress key={page.id} jobId={page.id} />}
          {page?.page === 'kit' && <CampaignKit key={page.id} jobId={page.id} />}
          {page?.page === 'compare' && <VersionCompare key={page.id} jobId={page.id} />}
          {page?.page === 'watch' && <WatchFolder />}
          {page?.page === 'emergency' && <EmergencyAlert />}
          </div>
        </div>
      </div>
      </CountsProvider>
    </AuthContext.Provider>
  )
}
