// A very small router: the page is chosen by the part of the address after "#".
//   #/          dashboard (Operator)
//   #/new       new transformation, step 1: add sources
//   #/new/12/safety    step 2: safety check of draft job 12
//   #/new/12/outputs   step 3: outputs and settings
//   #/jobs      my jobs
//   #/jobs/12   results of job 12 (Operators and Reviewers)
//   #/jobs/12/progress   live progress while the AI writes (Stage 9A)
//   #/jobs/12/kit        campaign kit: choose and download the files
//   #/jobs/12/compare    version compare (v1 against v2)
//   #/watch     watch folder     #/emergency   emergency alert     #/notifications   notifications (everyone)
//   #/review    review queue (Reviewer); #/review/12 review job 12, /send-back, /signed (Stage 9B)
//   #/admin/users, #/admin/audit   users & access requests, audit trail (Admin)
//   #/records   signed records (Reviewer)     #/admin/records   the record book (Admin)
//   #/password  change my password (everyone)
//   #/check     "Is this real?" message checker (everyone)
// Before signing in: #/welcome (splash), #/language, #/login, #/request-access, #/forgot, #/pending
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
  | { page: 'progress'; id: number }
  | { page: 'kit'; id: number }
  | { page: 'compare'; id: number }
  | { page: 'watch' }
  | { page: 'emergency' }
  | { page: 'notifications' }
  | { page: 'review' }
  | { page: 'review-job'; id: number }
  | { page: 'send-back'; id: number }
  | { page: 'signed'; id: number }
  | { page: 'users' }
  | { page: 'audit' }
  | { page: 'records' }
  | { page: 'record-book' }
  | { page: 'password' }
  | { page: 'profile' }
  | { page: 'help' }
  | { page: 'check' }
  | { page: 'welcome' }
  | { page: 'language' }
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
  progress: (id: number) => `#/jobs/${id}/progress`,
  kit: (id: number) => `#/jobs/${id}/kit`,
  compare: (id: number) => `#/jobs/${id}/compare`,
  watch: '#/watch',
  emergency: '#/emergency',
  notifications: '#/notifications',
  review: '#/review',
  reviewJob: (id: number) => `#/review/${id}`,
  sendBack: (id: number) => `#/review/${id}/send-back`,
  signed: (id: number) => `#/review/${id}/signed`,
  users: '#/admin/users',
  audit: '#/admin/audit',
  records: '#/records',
  recordBook: '#/admin/records',
  password: '#/password',
  profile: '#/profile',
  help: '#/help',
  check: '#/check',
  welcome: '#/welcome',
  language: '#/language',
  login: '#/login',
  requestAccess: '#/request-access',
  forgot: '#/forgot',
  pending: '#/pending',
}

const SIMPLE: Record<string, Route> = {
  '/new': { page: 'new' },
  '/jobs': { page: 'jobs' },
  '/watch': { page: 'watch' },
  '/emergency': { page: 'emergency' },
  '/notifications': { page: 'notifications' },
  '/review': { page: 'review' },
  '/admin/users': { page: 'users' },
  '/admin/audit': { page: 'audit' },
  '/records': { page: 'records' },
  '/admin/records': { page: 'record-book' },
  '/password': { page: 'password' },
  '/profile': { page: 'profile' },
  '/help': { page: 'help' },
  '/check': { page: 'check' },
  '/welcome': { page: 'welcome' },
  '/language': { page: 'language' },
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
  const review = path.match(/^\/review\/(\d+)(?:\/(send-back|signed))?$/)
  if (review) return review[2] ? { page: review[2] as 'send-back' | 'signed', id: Number(review[1]) } : { page: 'review-job', id: Number(review[1]) }
  const sub = path.match(/^\/jobs\/(\d+)\/(progress|kit|compare)$/)
  if (sub) return { page: sub[2] as 'progress' | 'kit' | 'compare', id: Number(sub[1]) }
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
