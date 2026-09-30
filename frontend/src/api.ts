// Small helpers for calling the FastAPI backend.
// In development, Vite forwards /api/... to http://localhost:8000 (see vite.config.ts).
// Signing in sets an HttpOnly session cookie: the browser sends it with every request by itself,
// and this code never sees it (so page scripts cannot steal it).

// ---- accounts (Stage 6B) ------------------------------------------------------------------

export type Role = 'operator' | 'reviewer' | 'admin'

export type User = {
  id: number
  username: string
  full_name: string
  role: Role
  role_label: string
  must_change_password: boolean
}

export type Health = { status: string; ai_mode: 'local' | 'cloud' | 'mock' }

export type AiPing =
  | { ok: true; reply: string; ai_mode: string; model: string; base_url: string }
  | { ok: false; error: string; ai_mode: string; model: string; base_url: string }

// ---- jobs -------------------------------------------------------------------------------

export type JobStatus = 'draft' | 'generating' | 'ready' | 'failed' | 'in_review' | 'sent_back' | 'approved'
export type OutputStatus = 'queued' | 'generating' | 'done' | 'failed'

export type OutputTypeInfo = { key: string; label: string; description: string; public: boolean }

export type JobSettings = {
  audience: string
  tone: string
  objective: string
  style: string
  detail_level: string
}

export type Options = {
  output_types: OutputTypeInfo[]
  settings: Record<keyof JobSettings, string[]>
  default_settings: JobSettings
}

export type QuoteFound = 'exact' | 'close' | 'no'

// Where a fact sheet item was found in the source. start/end are character positions in that
// page's text (counted in Unicode characters, as Python does), or null if it was not found.
export type SourceTrace = {
  source_id: string
  page: number
  quote: string
  quote_found: QuoteFound
  start?: number | null
  end?: number | null
}

export type Fact = SourceTrace & { id: string; text: string }
export type Action = Partial<SourceTrace> & { id: string; text: string }
export type DateItem = Partial<SourceTrace> & { id?: string; date: string; event: string }

export type FactSheet = {
  summary: string
  severity: string
  key_facts: Fact[]
  dates: DateItem[]
  entities: { name: string; type: string }[]
  indicators: { cves: string[]; ips: string[]; hashes: string[] }
  recommended_actions: Action[]
  parts: number
  truncated: boolean
  seconds: number
}

// ---- checks (Stage 5, see backend/app/pipeline/checks.py) --------------------------------

export type Path = (string | number)[]

export type NotInSource = { kind: string; label: string; text: string }

// ---- safety (Stage 6A, see backend/app/safety/) ------------------------------------------------

export type Tlp = 'RED' | 'AMBER' | 'GREEN' | 'CLEAR'
export type SafetyChoice = 'hide_public' | 'hide_all' | 'keep'
export type Risk = 'high' | 'medium' | 'low'

export type Occurrence = { source_id: string; page: number; start: number; end: number; text: string }

// One private value (or attack indicator), found once or more in the sources
export type Finding = {
  id: string // P1, P2 ... private data; I1, I2 ... attack indicators
  kind: string // aadhaar, phone, email, private_ip, password, classification, attacker_ip, cve ...
  label: string // "Phone number"
  group: 'personal' | 'location' | 'network' | 'secret' | 'marking' | 'indicator'
  risk: Risk
  text: string // as first written in the source
  value: string
  placeholder: string // what the AI sees instead: PHONE-1
  redaction: string // what readers of public outputs see: [phone number]
  choice: SafetyChoice
  count: number
  occurrences: Occurrence[]
}

// Something in the source that speaks to the AI, or that a person cannot see
export type Suspicious = {
  id: string // X1, X2 ...
  kind: 'instruction' | 'hidden_characters' | 'hidden_text'
  label: string
  source_id: string
  page: number
  start: number | null
  end: number | null
  spans?: [number, number][]
  text: string
  detail: string
  // instructions only: cut the sentence out of what the AI reads (default), or keep it
  choice?: InstructionChoice
  remove?: [number, number]
}

export type InstructionChoice = 'remove' | 'keep'

export type SafetyReport = {
  checked: { sources: number; pages: number }
  findings: Finding[]
  indicators: Finding[]
  suspicious: Suspicious[]
  kinds_found: number
  suggested_tlp: Tlp
  tlp_reason: string
  switched_off: Record<string, string> // public outputs the label switched off when the job started
}

export type SafetyDecision = {
  id: number
  actor: string
  user_id: number | null
  action: 'scan' | 'choice' | 'instruction' | 'tlp' | 'confirm' | 'start'
  item: string | null
  value: string | null
  detail: string
  created_at: string | null
}

// A hidden value found in a finished output: the output is blocked until it is edited out
export type Leak = { finding_id: string; kind: string; label: string; found: string; where: string; choice: SafetyChoice }

export type Sentence = {
  id: string // "s3", unique within one output
  path: Path // which text field it is in, e.g. ["tweets", 1, "text"]
  label: string // e.g. "Post 2"
  text: string
  // linked / unlinked: a claim; unverified: linked only to facts whose quotes are not in the source;
  // heading: a title (not linked); plain: only hashtags or links
  status: 'linked' | 'unlinked' | 'unverified' | 'heading' | 'plain'
  fact_ids: string[]
  matched_by: 'model' | 'words' | null // words = linked by matching words, the AI did not cite it
  closest: string | null // unlinked only: the fact that fits best
  not_in_source: NotInSource[]
}

export type ScorePart = {
  label: string
  points: number
  max: number
  done?: number
  total?: number
  close?: number
  problems?: number
}

export type Quality = {
  score?: number
  score_parts?: { linked: ScorePart; quotes: ScorePart; values: ScorePart; format: ScorePart }
  explanation?: string
  sentences?: Sentence[]
  facts_used?: string[]
  not_in_source?: (NotInSource & { sentence_id: string })[]
  format_rules?: { rule: string; ok: boolean; detail: string }[]
  parts: number
  linked: number
  unlinked: string[]
  unverified?: string[]
  capped?: boolean // score capped at 50: the fact sheet does not match the source
  unknown_fact_ids: string[]
  warnings: string[]
  leaks?: Leak[] // Stage 6A leak check
}

export type Consistency = {
  ok: boolean
  checked: number
  outputs: number
  mismatches: {
    fact_id: string
    what: string
    expected: string[]
    found: string
    output_id: number
    output_type: string
    output_label: string
    sentence_id: string
    sentence: string
  }[]
  agreed: { fact_id: string; value: string; outputs: string[] }[]
}

export type Origin = 'ai' | 'human' | 'regenerated'

export type VersionSummary = {
  version: number
  origin: Origin
  origin_label: string
  quality_score: number | null
  created_at: string | null
}

export type VersionDetail = VersionSummary & { content: Record<string, unknown>; quality: Quality | null }

export type JobOutput = {
  id: number
  type: string
  label: string
  // File types this output can be downloaded as, e.g. ['pdf', 'docx']
  formats: string[]
  language: string
  status: OutputStatus
  // The shape depends on the output type (see backend/app/pipeline/output_types.py)
  content: Record<string, unknown> | null // always the latest version
  version: number
  origin: Origin
  origin_label: string // "Written by AI", "Edited by human", "Regenerated by AI"
  quality: Quality | null
  quality_score: number | null
  fields: { path: Path; label: string; text: string }[] // the text the operator can edit
  error: string | null
  truncated: boolean
  seconds: number | null
  tokens: number | null
  started_at: string | null
  finished_at: string | null
}

export type JobSummary = {
  id: number
  title: string
  owner: { id: number; full_name: string } | null // the Operator who created it
  status: JobStatus
  step: string
  error: string | null
  outputs_done: number
  outputs_total: number
  output_types: string[]
  created_at: string
  updated_at: string
}

export type ReviewEvent = {
  decision: 'submitted' | 'approved' | 'sent_back'
  by: string | null
  user_id: number
  notes: string
  version: number
  created_at: string
}

export type JobDetail = JobSummary & {
  tlp: Tlp | null
  reviews: ReviewEvent[] // oldest first
  safety: SafetyReport | null // null for jobs made before Stage 6A
  safety_decisions: SafetyDecision[]
  switched_off: Record<string, string> // output type -> why the TLP label does not allow it
  version: number
  settings: JobSettings
  quality_score: number | null
  consistency: Consistency | null
  sources: { id: string; filename: string; kind: string; pages: number; chars: number; sha256: string }[]
  fact_sheet: FactSheet | null
  // How many fact sheet quotes were found in the source; ok = false -> "Do not publish" banner
  fact_sheet_check: { ok: boolean; found: number; total: number } | null
  outputs: JobOutput[]
}

// ---- requests ---------------------------------------------------------------------------

// Called when the backend says "not signed in" (401): the session ended (8 hours, 30 idle minutes,
// signed out elsewhere). App.tsx shows the Sign in page with the message.
let onSignedOut: (message: string) => void = () => {}
export function setSignedOutHandler(handler: (message: string) => void) {
  onSignedOut = handler
}

// An error from the backend, with its HTTP status (401 not signed in, 403 not allowed, 409 not now ...)
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', ...init })
  if (!response.ok) {
    // FastAPI sends errors as {"detail": "..."}; show that message if there is one.
    let message = `${path} returned ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // not JSON; keep the default message
    }
    // A wrong password on the Sign in page is also a 401, but that is not "signed out".
    if (response.status === 401 && !path.startsWith('/api/auth/')) onSignedOut(message)
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

export const getHealth = () => request<Health>('/api/health')
export const pingAi = () => request<AiPing>('/api/ai/ping')
export const getOptions = () => request<Options>('/api/options')
export const listJobs = () => request<JobSummary[]>('/api/jobs')
export const getJob = (id: number) => request<JobDetail>(`/api/jobs/${id}`)
export const retryJob = (id: number) => request<JobDetail>(`/api/jobs/${id}/retry`, { method: 'POST' })

export type SourceText = { id: string; filename: string; kind: string; pages: string[] }
export const getSource = (jobId: number, sourceId: string) => request<SourceText>(`/api/jobs/${jobId}/sources/${sourceId}`)

// ---- edit, regenerate and versions of one output --------------------------------------------

const outputPath = (jobId: number, outputId: number) => `/api/jobs/${jobId}/outputs/${outputId}`

// Saves the changed fields as a new version ("Edited by human"); the backend re-runs every check.
export const editOutput = (jobId: number, outputId: number, fields: { path: Path; text: string }[]) =>
  request<JobDetail>(outputPath(jobId, outputId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields }),
  })

export const regenerateOutput = (jobId: number, outputId: number) =>
  request<JobDetail>(`${outputPath(jobId, outputId)}/regenerate`, { method: 'POST' })

export const listVersions = (jobId: number, outputId: number) =>
  request<VersionSummary[]>(`${outputPath(jobId, outputId)}/versions`)

export const getVersion = (jobId: number, outputId: number, version: number) =>
  request<VersionDetail>(`${outputPath(jobId, outputId)}/versions/${version}`)

// Step 1 of a new transformation. form: title, text and/or files. The job comes back as a "draft"
// with its safety report.
export const createJob = (form: FormData) => request<JobDetail>('/api/jobs', { method: 'POST', body: form })

const sendJson = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// Step 2: the operator's choice for each finding (only the changed ones need to be sent) and the TLP label
export const saveSafety = (jobId: number, update: { tlp?: Tlp; choices?: Record<string, SafetyChoice | InstructionChoice> }) =>
  request<JobDetail>(`/api/jobs/${jobId}/safety`, sendJson('PUT', update))

// Step 3: the outputs and settings; starts the AI
export const startJob = (jobId: number, outputs: string[], settings: JobSettings) =>
  request<JobDetail>(`/api/jobs/${jobId}/start`, sendJson('POST', { outputs, settings }))

// ---- downloads (real files made from finished outputs; plain links, the browser saves them) ----

// inline=true asks the browser to show the file instead of saving it (used for the infographic preview)
export const downloadUrl = (jobId: number, outputId: number, format: string, inline = false) =>
  `/api/jobs/${jobId}/outputs/${outputId}/download?format=${format}${inline ? '&inline=true' : ''}`

export const kitUrl = (jobId: number) => `/api/jobs/${jobId}/kit.zip`

// ---- sign-in pages (Stage 6B, backend/app/routes/auth.py) --------------------------------------

export type AuthStatus = { needs_setup: boolean; user: User | null }

export const getAuthStatus = () => request<AuthStatus>('/api/auth/status')
export const signIn = (username: string, password: string) =>
  request<{ user: User }>('/api/auth/login', sendJson('POST', { username, password }))
export const signOut = () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' })
export const firstTimeSetup = (form: { username: string; full_name: string; password: string }) =>
  request<{ user: User }>('/api/auth/setup', sendJson('POST', form))
export const changePassword = (current_password: string, new_password: string) =>
  request<{ user: User }>('/api/auth/change-password', sendJson('POST', { current_password, new_password }))

export type AccessRequestForm = { username: string; full_name: string; role: 'operator' | 'reviewer'; reason: string; password: string }
export type AccessRequestSent = { username: string; full_name: string; role: Role; role_label: string; created_at: string }
export const requestAccess = (form: AccessRequestForm) =>
  request<AccessRequestSent>('/api/auth/request-access', sendJson('POST', form))
export const forgotPassword = (username: string, message: string) =>
  request<{ ok: true; message: string }>('/api/auth/forgot', sendJson('POST', { username, message }))

// ---- review (Stage 6B, backend/app/routes/review.py) -------------------------------------------

export type QueueItem = {
  id: number
  title: string
  tlp: Tlp | null
  version: number
  owner: string | null
  submitted_by: string | null
  submitted_at: string | null
  submit_notes: string
  outputs: string[]
  quality_score: number | null
  warnings: number
  numbers_match: boolean
  fact_sheet_ok: boolean
  can_review: boolean
  why_not: string | null
}

export type ReviewQueue = {
  waiting: QueueItem[]
  recent: (ReviewEvent & { job_id: number; job_title: string })[]
}

export const getReviewQueue = () => request<ReviewQueue>('/api/review/queue')
export const submitForReview = (jobId: number, notes: string) =>
  request<JobDetail>(`/api/jobs/${jobId}/submit`, sendJson('POST', { notes }))
export const reviewJob = (jobId: number, decision: 'approve' | 'send_back', notes: string) =>
  request<JobDetail>(`/api/jobs/${jobId}/review`, sendJson('POST', { decision, notes }))

// ---- admin (Stage 6B, backend/app/routes/admin.py) ---------------------------------------------

export type AdminUser = {
  id: number
  username: string
  full_name: string
  role: Role
  role_label: string
  is_active: boolean
  locked: boolean
  must_change_password: boolean
  failed_attempts: number
  created_at: string
  last_login: string | null
}

export type AccountRequest = {
  id: number
  kind: 'access' | 'reset'
  username: string
  full_name: string
  role: Role | null
  role_label: string
  reason: string
  status: 'pending' | 'approved' | 'rejected' | 'done'
  user_exists: boolean
  created_at: string
  decided_at: string | null
  decided_by: string | null
}

export const listUsers = () => request<AdminUser[]>('/api/admin/users')
export const addUser = (form: { username: string; full_name: string; role: Role }) =>
  request<{ user: AdminUser; temporary_password: string }>('/api/admin/users', sendJson('POST', form))
export const changeUser = (id: number, change: { full_name?: string; role?: Role; is_active?: boolean; unlock?: boolean }) =>
  request<AdminUser>(`/api/admin/users/${id}`, sendJson('PUT', change))
export const resetUserPassword = (id: number) =>
  request<{ user: AdminUser; temporary_password: string }>(`/api/admin/users/${id}/reset-password`, { method: 'POST' })
export const listAccountRequests = () => request<AccountRequest[]>('/api/admin/requests')
export const approveAccountRequest = (id: number, role?: Role) =>
  request<{ request: AccountRequest; user: AdminUser }>(`/api/admin/requests/${id}/approve`, sendJson('POST', { role }))
export const rejectAccountRequest = (id: number) =>
  request<{ request: AccountRequest }>(`/api/admin/requests/${id}/reject`, { method: 'POST' })

export type AuditCategory = 'security' | 'users' | 'content' | 'review' | 'system'
export type AuditEntry = {
  seq: number
  created_at: string
  actor: string
  actor_id: number | null
  category: AuditCategory
  action: string
  target: string
  detail: string
  prev_hash: string
  entry_hash: string
}
export type AuditPage = { entries: AuditEntry[]; total: number; actors: string[] }
export type ChainCheck =
  | { ok: true; checked: number; last_hash: string }
  | { ok: false; checked: number; broken: { seq: number; reason: string; entry: AuditEntry } }

export const getAudit = (filters: { category?: string; q?: string; actor?: string; days?: number; offset?: number; limit?: number }) => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== '') params.set(key, String(value))
  return request<AuditPage>(`/api/admin/audit?${params}`)
}
export const verifyAuditChain = () => request<ChainCheck>('/api/admin/audit/verify', { method: 'POST' })
