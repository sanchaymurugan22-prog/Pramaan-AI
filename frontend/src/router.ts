// A very small router: the page is chosen by the part of the address after "#".
//   #/          dashboard (Operator)
//   #/new       new transformation, step 1: add sources
//   #/new/12/safety    step 2: safety check of draft job 12
//   #/new/12/outputs   step 3: outputs and settings
//   #/jobs      my jobs
//   #/jobs/12   results of job 12 (Operators and Reviewers)
//   #/review    review queue (Reviewer)
//   #/admin/users, #/admin/audit   users & access requests, audit trail (Admin)
//   #/records   signed records (Reviewer)     #/admin/records   the record book (Admin)
//   #/password  change my password (everyone)
//   #/check     "Is this real?" message checker (everyone)
// Before signing in: #/login, #/request-access, #/forgot, #/pending
// Using "#" means the backend never has to know about these pages (works offline as plain files).
// Which role may open which page is decided in App.tsx; the backend checks every request anyway.
import { useEffect, useState } from 'react'

export type Route =
  | { page: 'dashboard' }
  | { page: 'new' }
  | { page: 'safety'; id: number }
  | { page: 'outputs'; id: number }
  | { page: 'jobs' }
  | { page: 'job'; id: number }
  | { page: 'review' }
  | { page: 'users' }
  | { page: 'audit' }
  | { page: 'records' }
  | { page: 'record-book' }
  | { page: 'password' }
  | { page: 'check' }
  | { page: 'login' }
  | { page: 'request-access' }
  | { page: 'forgot' }
  | { page: 'pending' }

export const links = {
  dashboard: '#/',
  newJob: '#/new',
  safety: (id: number) => `#/new/${id}/safety`,
  outputs: (id: number) => `#/new/${id}/outputs`,
  jobs: '#/jobs',
  job: (id: number) => `#/jobs/${id}`,
  review: '#/review',
  users: '#/admin/users',
  audit: '#/admin/audit',
  records: '#/records',
  recordBook: '#/admin/records',
  password: '#/password',
  check: '#/check',
  login: '#/login',
  requestAccess: '#/request-access',
  forgot: '#/forgot',
  pending: '#/pending',
}

const SIMPLE: Record<string, Route> = {
  '/new': { page: 'new' },
  '/jobs': { page: 'jobs' },
  '/review': { page: 'review' },
  '/admin/users': { page: 'users' },
  '/admin/audit': { page: 'audit' },
  '/records': { page: 'records' },
  '/admin/records': { page: 'record-book' },
  '/password': { page: 'password' },
  '/check': { page: 'check' },
  '/login': { page: 'login' },
  '/request-access': { page: 'request-access' },
  '/forgot': { page: 'forgot' },
  '/pending': { page: 'pending' },
}

function parse(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/'
  if (SIMPLE[path]) return SIMPLE[path]
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
