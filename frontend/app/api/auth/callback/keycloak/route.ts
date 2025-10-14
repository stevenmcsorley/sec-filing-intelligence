import { NextRequest, NextResponse } from 'next/server'

function safeTruncate(s?: string, n = 40) {
  if (!s) return null
  return s.length > n ? `${s.substring(0, n)}...` : s
}

export async function GET(request: NextRequest) {
  console.log('=== OAUTH CALLBACK STARTED ===')
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const error = searchParams.get('error')

  console.log('OAuth callback received:', {
    code: safeTruncate(code ?? undefined),
    state: safeTruncate(state ?? undefined),
    error,
    origin: request.nextUrl.origin,
  })

  if (error) {
    return NextResponse.redirect(new URL('/auth/signin?error=' + error, request.url))
  }

  if (!code) {
    return NextResponse.redirect(new URL('/auth/signin?error=no_code', request.url))
  }

  if (!state) {
    return NextResponse.redirect(new URL('/auth/signin?error=no_state', request.url))
  }

  // Extract code_verifier from state parameter (format: random:code_verifier)
  // Prefer pkce_verifier cookie (set by the browser prior to redirect), then fallback to state
  let codeVerifier: string | null = null
  try {
    const cookieHeader = request.headers.get('cookie') || ''
    const cookies = Object.fromEntries(cookieHeader.split(';').map(c => {
      const [k, ...v] = c.trim().split('=')
      return [k, decodeURIComponent(v.join('='))]
    }).filter(Boolean))
    if (cookies['pkce_verifier']) {
      codeVerifier = cookies['pkce_verifier']
    }
  } catch (e) {
    // ignore
  }

  if (!codeVerifier) {
    const decodedState = decodeURIComponent(state)
    const stateParts = decodedState.split(':')
    if (stateParts.length !== 2) {
      return NextResponse.redirect(new URL('/auth/signin?error=invalid_state', request.url))
    }
    codeVerifier = stateParts[1]
  }

  try {
    const redirectUri = `${request.nextUrl.origin}/api/auth/callback/keycloak`
    const tokenEndpoint = `${process.env.NEXT_PUBLIC_KEYCLOAK_URL}/realms/${process.env.NEXT_PUBLIC_KEYCLOAK_REALM}/protocol/openid-connect/token`

    console.log('Token exchange attempt', {
      tokenEndpoint,
      redirectUri,
      clientId: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID,
      hasCode: !!code,
      hasCodeVerifier: !!codeVerifier,
    })

    const tokenParams = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID!,
      code: code!,
      redirect_uri: redirectUri,
      code_verifier: codeVerifier,
    })

    // Token exchange: call the container-accessible Keycloak directly
    console.log('POST', tokenEndpoint)
    const tokenResponse = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: tokenParams.toString(),
    })

    const tokenText = await tokenResponse.text()
    if (!tokenResponse.ok) {
      console.error('Token exchange HTTP error', { status: tokenResponse.status, text: tokenText.substring(0, 200) })
      throw new Error(`Failed to exchange code for tokens: ${tokenResponse.status}`)
    }

    let tokens: any
    try {
      tokens = JSON.parse(tokenText)
    } catch (parseErr) {
      console.error('Failed to parse token response', { parseErr, text: tokenText.substring(0, 200) })
      throw parseErr
    }

    console.log('Received tokens', { accessTokenSnippet: safeTruncate(tokens.access_token) })

    // Get user info
    try {
      const userInfoEndpoint = `${process.env.NEXT_PUBLIC_KEYCLOAK_URL}/realms/${process.env.NEXT_PUBLIC_KEYCLOAK_REALM}/protocol/openid-connect/userinfo`
      const userResponse = await fetch(userInfoEndpoint, {
        headers: {
          Authorization: `Bearer ${tokens.access_token}`,
        },
      })

      let user: any = null
      if (userResponse.ok) {
        try {
          user = await userResponse.json()
        } catch (e) {
          console.error('Failed to parse userinfo JSON', e)
        }
      } else {
        const txt = await userResponse.text()
        console.error('Failed to fetch userinfo', { status: userResponse.status, text: txt.substring(0, 200) })
      }

      // Fallback: if userinfo failed or returned empty, decode id_token JWT
      if (!user || Object.keys(user).length === 0) {
        try {
          const idToken = tokens.id_token
          if (idToken) {
            const parts = idToken.split('.')
            if (parts.length >= 2) {
              const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'))
              user = payload
              console.log('Extracted user from id_token', { sub: user.sub, email: user.email, name: user.name })
            }
          }
        } catch (e) {
          console.error('Failed to decode id_token', e)
        }
      }

      if (!user) {
        throw new Error('Failed to obtain user info')
      }

      const sessionData = {
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        user: {
          id: user.sub,
          name: user.name,
          email: user.email,
          roles: user.realm_access?.roles || user.realm_access?.roles || [],
        },
      }

      // Redirect to an intermediate page that will warm up the client session
      const response = NextResponse.redirect(new URL('/auth/complete', request.url))
      // Persist session cookie for 7 days; backend refresh will renew tokens
      response.cookies.set('session', JSON.stringify(sessionData), {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 60 * 24 * 7, // 7 days
      })
      return response
    } catch (err) {
      console.error('Userinfo/token handling error', err)
      throw err
    }
  } catch (err) {
    console.error('OAuth callback error:', err)
    return NextResponse.redirect(new URL('/auth/signin?error=callback_failed', request.url))
  }
}