import { StoredAuth } from './types'

const AUTH_STORAGE_KEY = 'jansahayak_auth_v1'

export function getStoredAuth(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as StoredAuth
  } catch {
    return null
  }
}

export function saveStoredAuth(auth: StoredAuth): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth))
}

export function clearStoredAuth(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY)
}

export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const auth = getStoredAuth()
  const headers = new Headers(init.headers || {})
  if (auth?.token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${auth.token}`)
  }
  return fetch(input, { ...init, headers })
}

export async function downloadAuthenticatedFile(url: string, fallbackFilename: string): Promise<void> {
  const resp = await apiFetch(url)
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || 'Download failed')
  }
  const blob = await resp.blob()
  const cd = resp.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/i)
  const filename = match?.[1] || fallbackFilename

  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 2000)
}
