"use client"

import { useCallback } from "react"
import { useAuth } from "@/lib/auth"
import { apiFetch, buildUrl } from "./fetcher"

// Small helper to wait until a condition is false with timeout
function waitFor(predicate: () => boolean, timeout = 5000, interval = 50) {
  return new Promise<void>((resolve, reject) => {
    const start = Date.now()
    const iv = setInterval(() => {
      if (predicate()) {
        clearInterval(iv)
        resolve()
      } else if (Date.now() - start > timeout) {
        clearInterval(iv)
        reject(new Error('Timeout waiting for condition'))
      }
    }, interval)
  })
}

export function useApiFetch() {
  const { accessToken, isLoading, signOut } = useAuth()
  // Small cooldown after page load/callback to avoid racing signout flows.
  // During the first `cooldownMs` milliseconds we will not dispatch session:invalidated
  // so the AuthProvider has a chance to initialize and perform refresh.
  const cooldownMs = 2000
  const pageLoadTs = Date.now()

  const fetchWithAuth = useCallback(async (path: string, init: RequestInit = {}) => {
    // Wait for auth to finish initialization (so accessToken is available or confirmed absent)
    if (isLoading) {
      try {
        await waitFor(() => !isLoading, 5000)
      } catch (e) {
        throw new Error('Auth initialization timed out')
      }
    }

    const url = path.startsWith('http') ? path : buildUrl(path)
    let res = await apiFetch(url, init, accessToken || undefined)

    // If the server responds 401, try a token refresh once, then retry the request
    if (res.status === 401) {
      console.warn('[useApiFetch] received 401 for', url)
      try {
        // Call the frontend refresh endpoint (relative path) so the session cookie is available
        console.log('[useApiFetch] attempting refresh')
  const refreshRes = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin' })
        console.log('[useApiFetch] refresh response status', refreshRes.status)
        if (refreshRes.ok) {
          // Ask the frontend auth provider to refresh its in-memory session
          try {
            window?.dispatchEvent?.(new CustomEvent('session:updated'))
          } catch (e) {}

          // Read the updated session directly so we can retry with the new access token
          try {
            const sessionRes = await fetch('/api/auth/session', { credentials: 'same-origin' })
            console.log('[useApiFetch] session fetch status', sessionRes.status)
            if (sessionRes.ok) {
              const data = await sessionRes.json()
              const newAccessToken = data?.session?.accessToken
              console.log('[useApiFetch] newAccessToken present=', !!newAccessToken)
              if (newAccessToken) {
                // retry original request with new token
                res = await apiFetch(url, init, newAccessToken)
                return res
              }
            }
          } catch (e) {
            console.error('[useApiFetch] failed to fetch session after refresh', e)
            // if fetching session failed, fall through to sign out
          }
        }
      } catch (e) {
        console.error('[useApiFetch] refresh attempt failed', e)
        // continue to sign out below
      }

      // If refresh failed, do not auto-signout or dispatch global invalidation.
      // Returning the original 401 allows calling components to decide how to
      // handle authorization failures (for example, showing a login prompt).
      console.warn('[useApiFetch] refresh failed; returning 401 to caller')
    }

    return res
  }, [accessToken, isLoading, signOut])

  return { fetchWithAuth, buildUrl }
}

export default useApiFetch
