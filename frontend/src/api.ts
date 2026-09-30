// Small helpers for calling the FastAPI backend.
// In development, Vite forwards /api/... to http://localhost:8000 (see vite.config.ts).

export type Health = { status: string; ai_mode: 'local' | 'cloud' }

export type AiPing =
  | { ok: true; reply: string; ai_mode: string; model: string; base_url: string }
  | { ok: false; error: string; ai_mode: string; model: string; base_url: string }

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${path} returned ${response.status}`)
  return response.json() as Promise<T>
}

export const getHealth = () => getJson<Health>('/api/health')
export const pingAi = () => getJson<AiPing>('/api/ai/ping')
