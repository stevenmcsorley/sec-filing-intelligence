import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    console.log('[auth/refresh] refresh called')
    const cookieHeader = request.headers.get('cookie') || ''
    const cookies = Object.fromEntries(cookieHeader.split(';').map(c => {
      const [k, ...v] = c.trim().split('=')
      return [k, decodeURIComponent(v.join('='))]
    }).filter(Boolean))

    if (!cookies.session) {
      console.log('[auth/refresh] no session cookie')
      return NextResponse.json({ ok: false, message: 'no session' }, { status: 401 })
    }

    let session: any
    try {
      session = JSON.parse(cookies.session)
    } catch (e) {
      return NextResponse.json({ ok: false, message: 'invalid session' }, { status: 401 })
    }

    const refreshToken = session.refreshToken
    if (!refreshToken) {
      console.log('[auth/refresh] no refresh token')
      return NextResponse.json({ ok: false, message: 'no refresh token' }, { status: 401 })
    }

    const tokenEndpoint = `${process.env.NEXT_PUBLIC_KEYCLOAK_URL}/realms/${process.env.NEXT_PUBLIC_KEYCLOAK_REALM}/protocol/openid-connect/token`
    const tokenParams = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID!,
      refresh_token: refreshToken,
    })

    const tokenRes = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: tokenParams.toString(),
    })

    const text = await tokenRes.text()
    if (!tokenRes.ok) {
      console.error('[auth/refresh] Refresh token failed', { status: tokenRes.status, text: text.substring(0, 400) })
      return NextResponse.json({ ok: false, message: 'refresh_failed' }, { status: 401 })
    }

    let tokens: any
    try {
      tokens = JSON.parse(text)
    } catch (e) {
      console.error('Failed to parse refresh response', e)
      return NextResponse.json({ ok: false, message: 'invalid_token_response' }, { status: 500 })
    }

    // Update session with new tokens; keep existing user/roles if present
    const newSession = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token || session.refreshToken,
      user: session.user || null,
      roles: session.roles || (session.user?.roles || []),
    }

  console.log('[auth/refresh] refresh success, updating session cookie')
  const response = NextResponse.json({ ok: true, session: newSession })
    // Persist session cookie for 7 days and ensure path is root
    response.cookies.set('session', JSON.stringify(newSession), {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 7,
    })

    return response
  } catch (err) {
    console.error('Refresh endpoint error', err)
    return NextResponse.json({ ok: false, message: 'server_error' }, { status: 500 })
  }
}
