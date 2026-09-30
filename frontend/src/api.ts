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

export type Fact = {
  id: string
  text: string
  source_id: string
  page: number
  quote: string
  quote_found: 'exact' | 'close' | 'no'
}

export type FactSheet = {
  summary: string
  severity: string
  key_facts: Fact[]
  dates: { date: string; event: string }[]
  entities: { name: string; type: string }[]
  indicators: { cves: string[]; ips: string[]; hashes: string[] }
  recommended_actions: { id: string; text: string }[]
  parts: number
  truncated: boolean
  seconds: number
}

export type Quality = {
  parts: number
  linked: number
  unlinked: string[]
  unknown_fact_ids: string[]
  warnings: string[]
}

export type JobOutput = {
  id: number
  type: string
  label: string
  language: string
  status: OutputStatus
  // The shape depends on the output type (see backend/app/pipeline/output_types.py)
  content: Record<string, unknown> | null
  quality: Quality | null
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
  tlp: string | null
  version: number
  settings: JobSettings
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

// form: text and/or files, outputs (one entry per ticked output), and the settings
export const createJob = (form: FormData) => request<JobDetail>('/api/jobs', { method: 'POST', body: form })
