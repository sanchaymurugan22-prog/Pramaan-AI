// A very small router: the page is chosen by the part of the address after "#".
//   #/          dashboard
//   #/new       new transformation
//   #/jobs      my jobs
//   #/jobs/12   results of job 12
// Using "#" means the backend never has to know about these pages (works offline as plain files).
import { useEffect, useState } from 'react'

export type Route =
  | { page: 'dashboard' }
  | { page: 'new' }
  | { page: 'jobs' }
  | { page: 'job'; id: number }

export const links = {
  dashboard: '#/',
  newJob: '#/new',
  jobs: '#/jobs',
  job: (id: number) => `#/jobs/${id}`,
}

function parse(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/'
  if (path === '/new') return { page: 'new' }
  if (path === '/jobs') return { page: 'jobs' }
  const match = path.match(/^\/jobs\/(\d+)$/)
  if (match) return { page: 'job', id: Number(match[1]) }
  return { page: 'dashboard' }
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      setRoute(parse(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function navigate(href: string) {
  window.location.hash = href.replace(/^#/, '')
}
