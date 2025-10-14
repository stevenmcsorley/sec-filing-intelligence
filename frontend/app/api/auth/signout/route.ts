import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const referer = request.headers.get('referer')
    const ua = request.headers.get('user-agent')
    const cookieHeader = request.headers.get('cookie') || ''
    const confirm = request.headers.get('x-confirm-signout')
    console.log('[auth/signout] signout called', { referer, ua, cookiePresent: !!cookieHeader, confirm })

    // Require an explicit confirmation header to avoid accidental signouts
    if (confirm !== '1') {
      console.warn('[auth/signout] missing confirmation header; ignoring signout')
      return NextResponse.json({ ok: false, message: 'missing_confirm' }, { status: 400 })
    }
  } catch (e) {
    console.log('[auth/signout] signout called (failed to read headers)')
  }

  const response = NextResponse.json({ ok: true })
  response.cookies.set('session', '', { httpOnly: true, maxAge: 0, path: '/' })
  return response
}
