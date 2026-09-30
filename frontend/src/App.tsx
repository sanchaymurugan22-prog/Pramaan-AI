import { useEffect, useState } from 'react'
import { getHealth, type Health } from './api'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { OperatorDashboard } from './pages/OperatorDashboard'

export default function App() {
  // undefined = still checking, null = backend not reachable
  const [health, setHealth] = useState<Health | null | undefined>(undefined)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  return (
    <div className="app">
      <Sidebar />
      <div className="main-col">
        <Topbar health={health} />
        <OperatorDashboard health={health} />
      </div>
    </div>
  )
}
