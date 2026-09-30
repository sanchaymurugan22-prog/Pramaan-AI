// Small helpers for calling the FastAPI backend.
// In development, Vite forwards /api/... to http://localhost:8000 (see vite.config.ts).

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
}

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
  action: 'scan' | 'choice' | 'tlp' | 'confirm' | 'start'
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
  // linked / unlinked: a claim; heading: a title (not linked); plain: only hashtags or links
  status: 'linked' | 'unlinked' | 'heading' | 'plain'
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
  status: JobStatus
  step: string
  error: string | null
  outputs_done: number
  outputs_total: number
  output_types: string[]
  created_at: string
  updated_at: string
}

export type JobDetail = JobSummary & {
  tlp: Tlp | null
  safety: SafetyReport | null // null for jobs made before Stage 6A
  safety_decisions: SafetyDecision[]
  switched_off: Record<string, string> // output type -> why the TLP label does not allow it
  version: number
  settings: JobSettings
  quality_score: number | null
  consistency: Consistency | null
  sources: { id: string; filename: string; kind: string; pages: number; chars: number; sha256: string }[]
  fact_sheet: FactSheet | null
  outputs: JobOutput[]
}

// ---- requests ---------------------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    // FastAPI sends errors as {"detail": "..."}; show that message if there is one.
    let message = `${path} returned ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // not JSON; keep the default message
    }
    throw new Error(message)
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
export const saveSafety = (jobId: number, update: { tlp?: Tlp; choices?: Record<string, SafetyChoice> }) =>
  request<JobDetail>(`/api/jobs/${jobId}/safety`, sendJson('PUT', update))

// Step 3: the outputs and settings; starts the AI
export const startJob = (jobId: number, outputs: string[], settings: JobSettings) =>
  request<JobDetail>(`/api/jobs/${jobId}/start`, sendJson('POST', { outputs, settings }))

// ---- downloads (real files made from finished outputs; plain links, the browser saves them) ----

// inline=true asks the browser to show the file instead of saving it (used for the infographic preview)
export const downloadUrl = (jobId: number, outputId: number, format: string, inline = false) =>
  `/api/jobs/${jobId}/outputs/${outputId}/download?format=${format}${inline ? '&inline=true' : ''}`

export const kitUrl = (jobId: number) => `/api/jobs/${jobId}/kit.zip`
