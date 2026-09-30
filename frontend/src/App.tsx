import { useEffect, useState } from 'react'
import { getHealth, type Health } from './api'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { JobsList } from './pages/JobsList'
import { NewTransformation } from './pages/NewTransformation'
import { OperatorDashboard } from './pages/OperatorDashboard'
import { OutputsStep } from './pages/OutputsStep'
import { Results } from './pages/Results'
import { SafetyCheck } from './pages/SafetyCheck'
import { useRoute } from './router'

export default function App() {
  // undefined = still checking, null = backend not reachable
  const [health, setHealth] = useState<Health | null | undefined>(undefined)
  const route = useRoute()

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  return (
    <div className="app">
      <Sidebar route={route} />
      <div className="main-col">
        <Topbar health={health} />
        {route.page === 'dashboard' && <OperatorDashboard health={health} />}
        {route.page === 'new' && <NewTransformation />}
        {route.page === 'safety' && <SafetyCheck key={route.id} jobId={route.id} />}
        {route.page === 'outputs' && <OutputsStep key={route.id} jobId={route.id} health={health} />}
        {route.page === 'jobs' && <JobsList />}
        {route.page === 'job' && <Results key={route.id} jobId={route.id} />}
      </div>
    </div>
  )
}
