// Small helpers for calling the FastAPI backend.
// In development, Vite forwards /api/... to http://localhost:8000 (see vite.config.ts).
// Signing in sets an HttpOnly session cookie: the browser sends it with every request by itself,
// and this code never sees it (so page scripts cannot steal it).

// ---- accounts (Stage 6B) ------------------------------------------------------------------

export type Role = 'operator' | 'reviewer' | 'admin'

export type Prefs = {
  text_size?: 'normal' | 'large' | 'xlarge'
  high_contrast?: boolean
  output_languages?: string[]
  read_aloud?: boolean // Stage 8: a "Listen" button on each output
  notify_ready?: boolean
  notify_sent_back?: boolean
  notify_watch?: boolean
}

export type User = {
  id: number
  username: string
  full_name: string
  role: Role
  role_label: string
  must_change_password: boolean
  // Stage 9B
  employee_id: string | null
  email: string | null
  division: string
  language: string
  dsc_holder: boolean
  emergency_duty: boolean
  prefs: Prefs
  created_at: string | null
}

export type Language = { code: string; name: string }
export type FormOptions = { languages: Language[]; divisions: string[] }
export type ComputerCheck = {
  memory_bytes: number | null
  processors: number | null
  disk_free_bytes: number
  ai: { ai_mode: string; model: string; base_url: string; label: string }
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
  matched_by: 'model' | 'words' | 'translation' | null // words = linked by matching words, the AI did not cite it
  closest: string | null // unlinked only: the fact that fits best
  not_in_source: NotInSource[]
  english?: string // Stage 8: a translated field's English text
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
  // Stage 8: a translation's own check against its English (values that changed, per field)
  translation?: { language: string; values_checked: number; changed: { label: string; missing: string[]; extra: string[] }[] }
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

export type Origin = 'ai' | 'human' | 'regenerated' | 'translated' | 'retranslated'

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
  // Stage 8: outputs in Indian languages, translated from the English output of the same type
  language_label: string // "English", "हिन्दी (Hindi)"
  translation: Translation | null // null for English
}

export type Translation = {
  source_output_id: number
  source_version: number | null // the English version it was translated from
  engine: string // "IndicTrans2 (AI4Bharat)"
  stale: boolean // the English changed since (it is being translated again)
  native_check: { checked: boolean; by: string | null; at: string | null }
}

// Stage 8: GET /api/languages (backend/app/routes/languages.py)
export type LanguageInfo = {
  code: string
  name: string // "Hindi"
  native: string // "हिन्दी"
  script: string // "Deva"
  rtl: boolean
  sms_limit: number // 160 for English, 70 for Indian scripts
  translate: boolean // can be translated into on this computer
  voice: string | null // the voice that reads it aloud, or null: "audio not available"
  speech_to_text: boolean // a recording in this language can be a source
}
export type LanguagesInfo = { translation: { engine: string; ready: boolean; detail: string }; languages: LanguageInfo[] }

export type AiMode = 'local' | 'cloud' | 'mock'
export type CreatedVia = 'manual' | 'watch' | 'emergency'
export type AlertInfo = { type: string; severity: string; area: string; message: string; chars: number; sms_parts: number }

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
  // Stage 9A
  tlp: Tlp | null
  version: number
  ai_mode: AiMode | null // which AI wrote it; null until the AI starts
  quality_score: number | null
  created_via: CreatedVia
  suggested_outputs: string[] | null // watch folder: the kit ticked in advance on step 3
  alert: AlertInfo | null // emergency alert form
  record_no: string | null
  languages: string[]
  sources_count: number
}

export type ReviewEvent = {
  decision: 'submitted' | 'approved' | 'sent_back' | 'reopened'
  by: string | null
  user_id: number
  notes: string
  version: number
  created_at: string
}

// The latest signed record of a job (Stage 7, backend/app/routes/jobs.py record_summary)
export type JobRecord = {
  record_no: string // PRM-2026-000001
  issued_at: string
  version: number
  approved_by: string
  signer: string
  key_id: string
  files: { name: string; sha256: string; bytes: number }[]
  texts: number
  fingerprint: string // this record's entry hash in the record book
  verify_url: string // what the QR code holds
  withdrawn: { reason: string; at: string } | null
  current: boolean // false once the job was reopened as a new version
}

export type PublicProblem = { kind: string; label: string; text: string; where?: string }
export type PublicCheck = { ok: boolean; problems: PublicProblem[] }

export type JobDetail = JobSummary & {
  office_name: string // v1.2: the letterhead's office name (shown as the author of the social post previews)
  record: JobRecord | null
  reviews: ReviewEvent[] // oldest first
  safety: SafetyReport | null // null for jobs made before Stage 6A
  safety_decisions: SafetyDecision[]
  switched_off: Record<string, string> // output type -> why the TLP label does not allow it
  settings: JobSettings
  public_check: PublicCheck // Stage 9A: panic wording or shouting in the public outputs
  comments: ReviewComment[] // Stage 9B: the Reviewers' line comments, every version
  quality_score: number | null
  consistency: Consistency | null
  sources: {
    id: string
    filename: string
    kind: string // text | txt | pdf | docx | audio (Stage 8)
    pages: number
    chars: number
    sha256: string
    transcript: { model: string; language: string; seconds: number } | null // a recording turned into text
  }[]
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
export type JobFilters = { q?: string; status?: string; tlp?: string; days?: number }
export const listJobs = (filters: JobFilters = {}) => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== '' && value !== 0) params.set(key, String(value))
  const query = params.toString()
  return request<JobSummary[]>(`/api/jobs${query ? `?${query}` : ''}`)
}
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

// "Shorter" / "More formal" / "Simpler": the AI rewrites the current English text with that one change
export type RewriteChange = 'shorter' | 'formal' | 'simpler'
export const rewriteOutput = (jobId: number, outputId: number, change: RewriteChange) =>
  request<JobDetail>(`${outputPath(jobId, outputId)}/rewrite`, sendJson('POST', { change }))

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
export const startJob = (jobId: number, outputs: string[], settings: JobSettings, languages: string[] = []) =>
  request<JobDetail>(`/api/jobs/${jobId}/start`, sendJson('POST', { outputs, settings, languages }))

// ---- Stage 8: languages ----
export const getLanguages = () => request<LanguagesInfo>('/api/languages')
export const addLanguages = (jobId: number, languages: string[]) =>
  request<JobDetail>(`/api/jobs/${jobId}/languages`, sendJson('POST', { languages }))
export const setNativeCheck = (jobId: number, outputId: number, checked: boolean) =>
  request<JobDetail>(`/api/jobs/${jobId}/outputs/${outputId}/native-check`, sendJson('POST', { checked }))

// ---- downloads (real files made from finished outputs; plain links, the browser saves them) ----

// inline=true asks the browser to show the file instead of saving it (used for the infographic preview)
// Stage 8: an output's text read aloud (MP3), for "Read results aloud"
export const listenUrl = (jobId: number, outputId: number, version: number) =>
  `/api/jobs/${jobId}/outputs/${outputId}/listen?v=${version}`

export const downloadUrl = (jobId: number, outputId: number, format: string, inline = false) =>
  `/api/jobs/${jobId}/outputs/${outputId}/download?format=${format}${inline ? '&inline=true' : ''}`

// outputs: only these output types (Stage 9A "What is inside" ticks); empty = all
export const kitUrl = (jobId: number, outputs: string[] = []) =>
  `/api/jobs/${jobId}/kit.zip${outputs.length ? `?outputs=${outputs.join(',')}` : ''}`

export type KitInfo = {
  job_id: number
  title: string
  tlp: Tlp | null
  status: JobStatus
  record: JobRecord | null
  outputs: {
    output_id: number
    type: string
    label: string
    language: string
    blocked: boolean
    files: { format: string; name: string; bytes: number | null }[]
  }[]
}
export const getKitInfo = (jobId: number) => request<KitInfo>(`/api/jobs/${jobId}/kit-info`)

// ---- version compare (Stage 9A, backend/app/pipeline/compare.py) -------------------------------

export type DiffPiece = { text: string; kind: 'same' | 'added' | 'removed' }
export type CompareVersion = { key: number; label: string; status: string; at: string | null }
export type Comparison = {
  job_id: number
  versions: CompareVersion[]
  left: CompareVersion
  right: CompareVersion
  outputs: {
    output_id: number
    type: string
    label: string
    changed: boolean
    left: { version: number | null; quality_score: number | null }
    right: { version: number | null; quality_score: number | null }
    fields: { label: string; path: Path; changed: boolean; left: DiffPiece[]; right: DiffPiece[] }[]
  }[]
  summary: {
    outputs_changed: number
    outputs: number
    words_added: number
    words_removed: number
    numbers: { label: string; before: string; after: string }[]
    lists: { label: string; before: number; after: number; output: string }[]
  }
}
export const compareVersions = (jobId: number, left?: number, right?: number) => {
  const params = new URLSearchParams()
  if (left !== undefined) params.set('left', String(left))
  if (right !== undefined) params.set('right', String(right))
  return request<Comparison>(`/api/jobs/${jobId}/compare?${params}`)
}

// ---- sign-in pages (Stage 6B, backend/app/routes/auth.py) --------------------------------------

export type AuthStatus = { needs_setup: boolean; user: User | null }

export const getAuthStatus = () => request<AuthStatus>('/api/auth/status')
export const signIn = (username: string, password: string) =>
  request<{ user: User }>('/api/auth/login', sendJson('POST', { username, password }))
export const signOut = () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' })
export const getFormOptions = () => request<FormOptions>('/api/auth/options')
export const checkComputer = () => request<ComputerCheck>('/api/auth/computer')
export const getProfile = () => request<{ user: User } & FormOptions>('/api/profile')
export const saveProfile = (change: { language?: string; prefs?: Prefs }) =>
  request<{ user: User }>('/api/profile', sendJson('PUT', change))
export const firstTimeSetup = (form: { username: string; full_name: string; password: string; employee_id?: string; email?: string }) =>
  request<{ user: User }>('/api/auth/setup', sendJson('POST', form))
export const changePassword = (current_password: string, new_password: string) =>
  request<{ user: User }>('/api/auth/change-password', sendJson('POST', { current_password, new_password }))

export type AccessRequestForm = {
  username?: string
  employee_id: string
  email: string
  division: string
  language: string
  full_name: string
  role: 'operator' | 'reviewer'
  reason: string
  password: string
}
export type AccessRequestSent = {
  username: string
  full_name: string
  role: Role
  role_label: string
  created_at: string
  employee_id?: string | null
  division?: string
}
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
  fast_track: boolean // Stage 9A emergency alert: reviewed first
  leaks: number
  public_problems: number
  languages: string[]
  alert: AlertInfo | null
  can_review: boolean
  why_not: string | null
}

export type ReviewQueue = {
  waiting: QueueItem[]
  recent: (ReviewEvent & { job_id: number; job_title: string })[]
  // Stage 9B (design 24)
  stats: {
    waiting: number
    oldest_submitted_at: string | null
    signed_today: number
    files_in_last_kit: number
    average_review_minutes: number | null
    sent_back_this_week: number
  }
  signed_today: { record_no: string; title: string; job_id: number | null }[]
  signer: { ready: boolean; kind: string; label: string; error?: string; key_id?: string; certificate_class?: string; holder: string; dsc_holder: boolean }
  reasons: string[]
}

// ---- line comments (Stage 9B, backend/app/routes/comments.py) -----------------------------------

export type ReviewComment = {
  id: number
  job_version: number
  output_id: number | null
  output_label: string | null
  sentence_id: string | null
  path: Path | null
  quote: string
  text: string
  author: string | null
  author_id: number
  created_at: string
}
export const addComment = (jobId: number, comment: { output_id?: number | null; sentence_id?: string | null; path?: Path | null; quote?: string; text: string }) =>
  request<ReviewComment & { mentioned: string[] }>(`/api/jobs/${jobId}/comments`, sendJson('POST', comment))
export const takeBackComment = (jobId: number, commentId: number) =>
  request<{ ok: true }>(`/api/jobs/${jobId}/comments/${commentId}`, { method: 'DELETE' })

export const getReviewQueue = () => request<ReviewQueue>('/api/review/queue')
export const submitForReview = (jobId: number, notes: string) =>
  request<JobDetail>(`/api/jobs/${jobId}/submit`, sendJson('POST', { notes }))
// Approve also signs (Stage 7). pin: only for a DSC token.
export const reviewJob = (jobId: number, decision: 'approve' | 'send_back', notes: string, pin = '', reasons: string[] = []) =>
  request<JobDetail>(`/api/jobs/${jobId}/review`, sendJson('POST', { decision, notes, pin, reasons }))

// ---- signing (Stage 7) ----------------------------------------------------------------------

export type SignInfo = {
  job_id: number
  version: number
  outputs: number
  files: number
  signer: { kind: 'test' | 'dsc'; label: string; certificate_class?: string; key_id?: string; error?: string }
  needs_pin: boolean
  signed_by: string
}
export const getSignInfo = (jobId: number) => request<SignInfo>(`/api/jobs/${jobId}/sign-info`)
export const newVersion = (jobId: number) => request<JobDetail>(`/api/jobs/${jobId}/new-version`, { method: 'POST' })
export const recordQrUrl = (recordNo: string) => `/api/records/${recordNo}/qr.png`

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
  employee_id: string | null
  email: string | null
  division: string
  dsc_holder: boolean
  emergency_duty: boolean
}

export type AccountRequest = {
  id: number
  kind: 'access' | 'reset'
  username: string
  full_name: string
  role: Role | null
  role_label: string
  reason: string
  employee_id: string | null
  email: string | null
  division: string
  status: 'pending' | 'approved' | 'rejected' | 'done'
  user_exists: boolean
  created_at: string
  decided_at: string | null
  decided_by: string | null
}

export const listUsers = () => request<AdminUser[]>('/api/admin/users')
export type UserForm = {
  username?: string
  full_name: string
  role: Role
  employee_id?: string
  email?: string
  division?: string
  dsc_holder?: boolean
  emergency_duty?: boolean
}
export const addUser = (form: UserForm) =>
  request<{ user: AdminUser; temporary_password: string }>('/api/admin/users', sendJson('POST', form))
export const changeUser = (id: number, change: Partial<UserForm> & { is_active?: boolean; unlock?: boolean }) =>
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

// ---- record book (Stage 7, backend/app/routes/records.py) ---------------------------------------

export type RecordStatus = 'active' | 'withdrawn' | 'replaced'
export type RecordItem = {
  seq: number
  record_no: string
  job_id: number | null
  job_version: number | null
  title: string
  tlp: Tlp | null
  issued_at: string
  issuing_office: string
  approved_by: string
  replaces: string | null
  replaced_by: string | null
  status: RecordStatus
  files_count: number
  texts_count: number
  verify_url: string
  fingerprint: string
  withdrawn: { reason: string; at: string } | null
}
export type ChainEntry = {
  seq: number
  kind: 'issue' | 'withdraw'
  record_no: string
  created_at: string
  entry_hash: string
  prev_hash: string
  title: string | null
}
export type RecordBook = {
  records: RecordItem[]
  counts: Record<RecordStatus, number>
  entries: number
  last_check: { at: string; by: string; detail: string } | null
  chain: ChainEntry[]
}
export type BookCheck =
  | { ok: true; checked: number; files_checked: number; last_hash: string }
  | { ok: false; checked: number; files_checked: number; broken: { seq: number; record_no: string; kind: string; reason: string } }

export const listRecords = (q = '', status = '') =>
  request<RecordBook>(`/api/records?${new URLSearchParams({ q, status })}`)
export const verifyRecordBook = () => request<BookCheck>('/api/records/verify', { method: 'POST' })
export const withdrawRecord = (recordNo: string, reason: string) =>
  request<RecordItem>(`/api/admin/records/${recordNo}/withdraw`, sendJson('POST', { reason }))
export const publicKeyUrl = '/api/records/public-key.pem'
// The public verify site + latest records.json + public key, for one-way (USB) transfer to the public web server
export const verifyBundleUrl = '/api/admin/records/verify-bundle.zip'

// ---- "Is this real?" message checker (Stage 7, backend/app/signing/messages.py) -------------------

export type ScamSign = { kind: string; label: string; detail: string; note?: string }
export type MessageCheck = {
  verdict: 'genuine' | 'replaced' | 'withdrawn' | 'changed' | 'scam' | 'not_found'
  record_no: string | null
  replaced_by?: string | null
  title?: string | null
  record_status?: 'genuine' | 'replaced' | 'withdrawn'
  similarity?: number
  label?: string
  diff?: { text: string; kind: 'same' | 'added' | 'removed' }[]
  signs: ScamSign[]
  helpline: string
  sha256: string
}
export const checkMessage = (text: string) => request<MessageCheck>('/api/check-message', sendJson('POST', { text }))

// ---- notifications, search, dashboard (Stage 9A) ------------------------------------------------

export type NotificationKind = 'finished' | 'failed' | 'submitted' | 'sent_back' | 'approved' | 'signed' | 'watch' | 'alert' | 'mention'
export type Notification = {
  id: number
  kind: NotificationKind
  title: string
  detail: string
  job_id: number | null
  created_at: string
  read: boolean
}
export type Counts = { unread: number; watch_drafts: number; requests: number }

export const listNotifications = (show: 'all' | 'unread' | 'mentions' = 'all') =>
  request<{ items: Notification[]; unread: number }>(`/api/notifications${show === 'all' ? '' : `?${show}=true`}`)
export const getCounts = () => request<Counts>('/api/notifications/count')
export const readNotification = (id: number) => request<{ unread: number }>(`/api/notifications/${id}/read`, { method: 'POST' })
export const readAllNotifications = () => request<{ unread: number }>('/api/notifications/read-all', { method: 'POST' })

export type SearchResults = {
  jobs: { id: number; title: string; status: JobStatus; tlp: Tlp | null; version: number }[]
  sources: { job_id: number; job_title: string; id: string; filename: string; kind: string; pages: number }[]
  records: { record_no: string; title: string; job_id: number | null; tlp: Tlp | null; withdrawn: boolean }[]
}
export const search = (q: string) => request<SearchResults>(`/api/search?q=${encodeURIComponent(q)}`)

export type AttentionItem = {
  kind: 'sent_back' | 'leak' | 'failed' | 'unlinked' | 'watch' | 'ready'
  job_id: number | null
  title: string
  detail: string
}
export type Dashboard = {
  stats: {
    jobs_this_week: number
    jobs_last_week: number
    outputs_approved: number
    formats_approved: number
    hours_saved: number
    languages: string[]
  }
  attention: AttentionItem[]
  watch_drafts: number
  latest_approval: { id: number; title: string; at: string } | null
  encrypted: boolean
}
export const getDashboard = () => request<Dashboard>('/api/dashboard')

// ---- watch folder (Stage 9A, backend/app/routes/watch.py) ---------------------------------------

export type WatchActivity = {
  id: number
  filename: string
  folder: string
  status: 'drafted' | 'skipped' | 'failed'
  detail: string
  job_id: number | null
  job_status: JobStatus | null
  bytes: number
  found_at: string
}
export type WatchState = {
  enabled: boolean
  folder: string
  outputs: string[]
  skip_duplicates: boolean
  notify: boolean
  last_check: string | null
  interval_seconds: number
  root: string
  folders: string[]
  activity: WatchActivity[]
  new?: number
}
export type WatchUpdate = Partial<Pick<WatchState, 'enabled' | 'folder' | 'outputs' | 'skip_duplicates' | 'notify'>>
export const getWatch = () => request<WatchState>('/api/watch')
export const updateWatch = (change: WatchUpdate) => request<WatchState>('/api/watch', sendJson('PUT', change))
export const makeWatchFolder = (name: string) =>
  request<{ folder: string; folders: string[] }>('/api/watch/folders', sendJson('POST', { name }))
export const checkWatchNow = () => request<WatchState>('/api/watch/check', { method: 'POST' })

// ---- emergency alert (Stage 9A, backend/app/routes/alerts.py) -----------------------------------

export type AlertCheck = PublicCheck & { chars: number; sms_parts: number; max_chars: number; fits_one_sms: boolean }
export type NewAlert = {
  type: string
  severity: string
  area: string
  message: string
  outputs: string[]
  languages: string[] // Stage 8: the SMS and every output in these languages too
  voice: boolean // Stage 8: a voice announcement in every language that has a voice
}
export const checkAlert = (message: string) => request<AlertCheck>('/api/alerts/check', sendJson('POST', { message }))
export const createAlert = (alert: NewAlert) => request<JobDetail>('/api/alerts', sendJson('POST', alert))
// Stage 8: the alert in each language, for the preview cards
export type AlertPreview = {
  code: string
  name: string
  native: string
  rtl: boolean
  text: string
  chars: number
  limit: number // 160 for English, 70 for Indian scripts
  sms_parts: number
  changed: string[] // numbers or codes that did not survive the translation
  voice: string | null
}
export const previewAlert = (message: string, languages: string[]) =>
  request<{ languages: AlertPreview[] }>('/api/alerts/preview', sendJson('POST', { message, languages }))
export const tickAllTranslations = (jobId: number) =>
  request<JobDetail>(`/api/jobs/${jobId}/native-check-all`, sendJson('POST', {}))

// ---- Admin system pages (Stage 9B, backend/app/routes/admin_system.py and admin_files.py) --------

export type ComputerInfo = {
  processors: number
  load_percent: number | null
  memory_bytes: number | null
  disk_total_bytes: number
  disk_free_bytes: number
  encrypted: boolean
  ai_mode: string
  ai_label: string
}
export type CheckerCounts = { checks: number; genuine: number; changed: number; scam: number; withdrawn: number; not_found: number }
export type AdminOverview = {
  users: { operator: number; reviewer: number; admin: number; total: number }
  jobs: { this_month: number; last_month: number }
  records: { issued: number; withdrawn: number }
  checker: CheckerCounts
  computer: ComputerInfo
  requests: { id: number; kind: 'access' | 'reset'; full_name: string; username: string; role: Role | null; role_label: string; employee_id: string | null; division: string; created_at: string }[]
  security_events: { seq: number; action: string; detail: string; actor: string; created_at: string }[]
}
export const getAdminOverview = () => request<AdminOverview>('/api/admin/overview')

export type SpeedTest = { at?: string; ai_mode?: string; ok?: boolean; error?: string | null; seconds?: number; words?: number; words_per_second?: number | null }
export type AiInfo = {
  ai_mode: string
  label: string
  model: string
  base_url: string
  timeout_seconds: number
  models: { name: string; job: string; made_by: string; runtime: string; status: 'in_use' | 'standby' | 'off' | 'missing'; detail: string }[]
  performance: {
    ai_mode: string
    label: string
    outputs: number
    average_output_seconds: number | null
    tokens_per_second: number | null
    fact_sheets: number
    average_fact_sheet_seconds: number | null
    by_type: { type: string; label: string; count: number; average_seconds: number }[]
  }[]
  speed_test: SpeedTest
}
export const getAiInfo = () => request<AiInfo>('/api/admin/ai')
export const runSpeedTest = () => request<SpeedTest>('/api/admin/ai/speed-test', { method: 'POST' })

export type SecurityState = {
  scanner: { key: string; label: string; on: boolean }[]
  classification_words: string[]
  built_in_words: string[]
  idle_minutes: number
  idle_choices: number[]
  lock_after: number
  lock_choices: number[]
  tlp: { level: Tlp; title: string; description: string; public_allowed: boolean }[]
  public_outputs: string[]
  encryption: { database: boolean; files: boolean; key_place: string }
  signer: { kind: string; label: string; key_id?: string; error?: string }
  reviewers: { name: string; dsc_holder: boolean }[]
  max_session_hours: number
}
export type SecurityChange = { scanner?: Record<string, boolean>; classification_words?: string[]; idle_minutes?: number; lock_after?: number }
export const getSecurity = () => request<SecurityState>('/api/admin/security')
export const saveSecurity = (change: SecurityChange) => request<SecurityState>('/api/admin/security', sendJson('PUT', change))

export type Letterhead = { office_name: string; effective_name: string; default_name: string; has_logo: boolean }
export const getLetterhead = () => request<Letterhead>('/api/admin/letterhead')
export const saveLetterhead = (office_name: string) => request<Letterhead>('/api/admin/letterhead', sendJson('PUT', { office_name }))
export const uploadLogo = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<Letterhead>('/api/admin/letterhead/logo', { method: 'POST', body: form })
}
export const removeLogo = () => request<Letterhead>('/api/admin/letterhead/logo', { method: 'DELETE' })
export const logoUrl = '/api/letterhead/logo.png'

export type PublicPageInfo = { address: string; issuer: string; records: { issued: number; withdrawn: number }; last_export: string | null; checker: CheckerCounts }
export const getPublicPageInfo = () => request<PublicPageInfo>('/api/admin/public-page')

export type Backups = { version: string; ai_mode?: string; folder: string; made?: string; backups: { name: string; bytes: number; created_at: string }[] }
export const listBackups = () => request<Backups>('/api/admin/backups')
export const makeBackup = () => request<Backups>('/api/admin/backups', { method: 'POST' })
export const backupUrl = (name: string) => `/api/admin/backups/${encodeURIComponent(name)}`

