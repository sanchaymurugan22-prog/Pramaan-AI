import { useCallback, useEffect, useMemo, useState } from 'react'
import { getAuthStatus, getHealth, setSignedOutHandler, signOut as apiSignOut, type Health, type Role, type User } from './api'
import { AuthContext, ROLE_TONE } from './auth'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { AuditTrail } from './pages/admin/AuditTrail'
import { Users } from './pages/admin/Users'
import { Forgot } from './pages/auth/Forgot'
import { Pending, RequestAccess } from './pages/auth/RequestAccess'
import { Setup } from './pages/auth/Setup'
import { SignIn } from './pages/auth/SignIn'
import { ChangePasswordPage, ForcedPasswordChange } from './pages/ChangePassword'
import { JobsList } from './pages/JobsList'
import { NewTransformation } from './pages/NewTransformation'
import { OperatorDashboard } from './pages/OperatorDashboard'
import { OutputsStep } from './pages/OutputsStep'
import { Results } from './pages/Results'
import { ReviewQueue } from './pages/ReviewQueue'
import { SafetyCheck } from './pages/SafetyCheck'
import { links, navigate, useRoute, type Route } from './router'

// The pages each role may open. Anything else sends them to their home page.
// (Only for convenience: the backend refuses other roles' requests with 403.)
const ROLE_PAGES: Record<Role, Route['page'][]> = {
  operator: ['dashboard', 'new', 'safety', 'outputs', 'jobs', 'job', 'password'],
  reviewer: ['review', 'job', 'password'],
  admin: ['users', 'audit', 'password'],
}
const HOME: Record<Role, string> = { operator: links.dashboard, reviewer: links.review, admin: links.users }
const SIGNED_OUT_PAGES: Route['page'][] = ['login', 'request-access', 'forgot', 'pending']

export default function App() {
  // undefined = still checking, null = backend not reachable
  const [health, setHealth] = useState<Health | null | undefined>(undefined)
  const [needsSetup, setNeedsSetup] = useState<boolean | undefined>(undefined)
  const [user, setUser] = useState<User | null>(null)
  const [notice, setNotice] = useState('') // e.g. "You were signed out after 30 minutes without activity."
  const route = useRoute()

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
      setNotice('You have signed out.')
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

  // Send each role to a page it may see.
  useEffect(() => {
    if (user && !user.must_change_password && !ROLE_PAGES[user.role].includes(route.page)) navigate(HOME[user.role])
  }, [user, route.page])

  if (needsSetup === undefined) {
    return <p className="muted boot-note">{health === null ? 'The backend is not running. Start it with ./scripts/start.sh' : 'Loading…'}</p>
  }
  if (needsSetup) return <Setup onDone={signedIn} />

  if (!user || !auth) {
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
      <div className={`app role-${ROLE_TONE[user.role]}`}>
        <Sidebar route={route} />
        <div className="main-col">
          <Topbar health={health} />
          {page?.page === 'dashboard' && <OperatorDashboard health={health} />}
          {page?.page === 'new' && <NewTransformation />}
          {page?.page === 'safety' && <SafetyCheck key={page.id} jobId={page.id} />}
          {page?.page === 'outputs' && <OutputsStep key={page.id} jobId={page.id} health={health} />}
          {page?.page === 'jobs' && <JobsList />}
          {page?.page === 'job' && <Results key={page.id} jobId={page.id} />}
          {page?.page === 'review' && <ReviewQueue />}
          {page?.page === 'users' && <Users />}
          {page?.page === 'audit' && <AuditTrail />}
          {page?.page === 'password' && <ChangePasswordPage onDone={setUser} />}
        </div>
      </div>
    </AuthContext.Provider>
  )
}
