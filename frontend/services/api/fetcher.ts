// services/api/fetcher.ts
export async function apiFetch(input: RequestInfo, init: RequestInit = {}, accessToken?: string) {
  const headers = new Headers(init.headers || {})
  headers.set('Content-Type', headers.get('Content-Type') || 'application/json')
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  // Diagnostic log: show which URL and whether an Authorization header was attached
  try {
    console.log('[apiFetch] fetching', typeof input === 'string' ? input : String(input), 'withAuth=', !!accessToken)
  } catch (e) {
    // ignore logging errors in environments without console
  }

  const res = await fetch(input, { ...init, headers })

  // Diagnostic log: response status for quick tracing
  try {
    console.log('[apiFetch] response', typeof input === 'string' ? input : String(input), 'status=', res.status)
  } catch (e) {}

  return res
}

export function buildUrl(path: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
  return `${base}${path}`
}
