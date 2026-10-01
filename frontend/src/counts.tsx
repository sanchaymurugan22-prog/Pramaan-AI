// The small numbers shown on the menu and the bell (Stage 9A): unread notifications and watch-folder
// drafts waiting at the Safety check. Asked from the backend every 20 seconds, and again whenever a page
// calls refresh() (for example after "Mark all as read").
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { getCounts, type Counts } from './api'

const POLL_MS = 20000

type CountsState = { counts: Counts; refresh: () => void }

const CountsContext = createContext<CountsState>({ counts: { unread: 0, watch_drafts: 0 }, refresh: () => {} })

export function CountsProvider({ children }: { children: ReactNode }) {
  const [counts, setCounts] = useState<Counts>({ unread: 0, watch_drafts: 0 })
  const refresh = useCallback(() => {
    getCounts()
      .then(setCounts)
      .catch(() => {}) // the backend may be restarting: keep the last numbers
  }, [])

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, POLL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])

  return <CountsContext.Provider value={{ counts, refresh }}>{children}</CountsContext.Provider>
}

export function useCounts(): CountsState {
  return useContext(CountsContext)
}
