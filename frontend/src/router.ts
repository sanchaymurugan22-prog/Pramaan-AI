// A very small router: the page is chosen by the part of the address after "#".
//   #/          dashboard
//   #/new       new transformation, step 1: add sources
//   #/new/12/safety    step 2: safety check of draft job 12
//   #/new/12/outputs   step 3: outputs and settings
//   #/jobs      my jobs
//   #/jobs/12   results of job 12
// Using "#" means the backend never has to know about these pages (works offline as plain files).
import { useEffect, useState } from 'react'

export type Route =
  | { page: 'dashboard' }
  | { page: 'new' }
  | { page: 'safety'; id: number }
  | { page: 'outputs'; id: number }
  | { page: 'jobs' }
  | { page: 'job'; id: number }

export const links = {
  dashboard: '#/',
  newJob: '#/new',
  safety: (id: number) => `#/new/${id}/safety`,
  outputs: (id: number) => `#/new/${id}/outputs`,
  jobs: '#/jobs',
  job: (id: number) => `#/jobs/${id}`,
}

function parse(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/'
  if (path === '/new') return { page: 'new' }
  if (path === '/jobs') return { page: 'jobs' }
  const step = path.match(/^\/new\/(\d+)\/(safety|outputs)$/)
  if (step) return { page: step[2] as 'safety' | 'outputs', id: Number(step[1]) }
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
