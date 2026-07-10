import type { MeResponse } from './main'
import type { Affirmation } from './views/appView'

export type AuthResult = { ok: true } | { ok: false; status: number }

export async function getMe(): Promise<MeResponse | null> {
  const response = await fetch('/auth/me', { credentials: 'same-origin' })
  if (response.status === 401) {
    return null
  }
  if (!response.ok) {
    throw new Error(`getMe failed: ${response.status}`)
  }
  return (await response.json()) as MeResponse
}

export async function login(username: string, password: string): Promise<AuthResult> {
  const response = await fetch('/auth/login', {
    credentials: 'same-origin',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  return response.ok ? { ok: true } : { ok: false, status: response.status }
}

export async function register(
  joinCode: string,
  username: string,
  displayName: string,
  password: string,
): Promise<AuthResult> {
  const response = await fetch('/auth/register', {
    credentials: 'same-origin',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ join_code: joinCode, username, display_name: displayName, password }),
  })
  return response.ok ? { ok: true } : { ok: false, status: response.status }
}

export async function logout(): Promise<void> {
  await fetch('/auth/logout', { credentials: 'same-origin', method: 'POST' })
}

// The backend affirmation record (sharedvoice.models.Affirmation) has fields
// `id`, `title`, `body_text` -- there is no `text` field. The frontend
// contract (sv-lds.8) pins `Affirmation { id, text }`, so this is the seam
// that adapts backend shape to frontend contract: prefer body_text, fall
// back to title if body_text is empty.
interface BackendAffirmation {
  id: string
  title: string
  body_text?: string
}

export async function getAffirmations(): Promise<Affirmation[]> {
  const response = await fetch('/affirmations', { credentials: 'same-origin' })
  if (!response.ok) {
    throw new Error(`getAffirmations failed: ${response.status}`)
  }
  const data = (await response.json()) as BackendAffirmation[]
  return data.map((a) => ({
    id: a.id,
    text: a.body_text && a.body_text.length > 0 ? a.body_text : a.title,
  }))
}
