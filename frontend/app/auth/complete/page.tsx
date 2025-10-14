"use client"

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function AuthComplete() {
  const router = useRouter()

  useEffect(() => {
    // After the server sets the cookie, ask the client to refresh its session
    // then navigate to home. This avoids race conditions where components
    // immediately call protected APIs before the client knows it is authenticated.
    const run = async () => {
      try {
        // Poll /api/auth/session until the server-set cookie is visible to the
        // server endpoint (same-origin credentials must be sent).
        const start = Date.now()
        while (Date.now() - start < 5000) {
          try {
            const res = await fetch('/api/auth/session', { credentials: 'same-origin' })
            if (res.ok) {
              const data = await res.json()
              if (data?.authenticated) break
            }
          } catch (e) {
            // ignore transient errors
          }
          await new Promise(r => setTimeout(r, 250))
        }
      } catch (e) {}
      router.replace('/')
    }

    run()
  }, [router])

  return <div>Signing you in…</div>
}
