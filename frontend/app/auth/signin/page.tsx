"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

// PKCE helper functions
function generateCodeVerifier() {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
}

async function generateCodeChallenge(verifier: string) {
  const encoder = new TextEncoder()
  const data = encoder.encode(verifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
}

export default function SignInPage() {
  const handleSignIn = async () => {
    const codeVerifier = generateCodeVerifier()
    const codeChallenge = await generateCodeChallenge(codeVerifier)

    // Store code verifier in state parameter (not secure but works for development)
    const state = `${Math.random().toString(36).substring(7)}:${codeVerifier}`

    // Also store the code_verifier in a short-lived cookie so the server
    // callback can access it for the PKCE exchange. This is safer than
    // relying solely on the state parameter which can be mangled.
    try {
      document.cookie = `pkce_verifier=${codeVerifier}; path=/; max-age=300; samesite=lax`
    } catch (e) {
      // ignore in environments without document
    }

    // Direct redirect to Keycloak with PKCE
    const keycloakUrl = `${process.env.NEXT_PUBLIC_KEYCLOAK_BROWSER_URL}/realms/${process.env.NEXT_PUBLIC_KEYCLOAK_REALM}/protocol/openid-connect/auth`
    const params = new URLSearchParams({
      client_id: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID!,
      redirect_uri: `${window.location.origin}/api/auth/callback/keycloak`,
      response_type: 'code',
      scope: 'openid email profile',
      state: state,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
    })
    window.location.href = `${keycloakUrl}?${params}`
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">SEC Filing Intelligence</CardTitle>
          <CardDescription>
            Sign in to access SEC filing insights and analysis
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={handleSignIn} className="w-full" size="lg">
            Sign In with Keycloak
          </Button>
          <div className="text-center">
            {/* Show a retry button if callback previously failed */}
            {typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('error') ? (
              <p className="text-sm text-red-400 mt-2">Sign-in failed. Please try again.</p>
            ) : null}
          </div>
          <p className="text-sm text-center text-slate-600">
            Redirecting to authentication provider...
          </p>
        </CardContent>
      </Card>
    </div>
  )
}