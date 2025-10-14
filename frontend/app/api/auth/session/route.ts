import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    console.log('[auth/session] request received')
    const cookieHeader = request.headers.get('cookie') || ''
    const cookies = Object.fromEntries(cookieHeader.split(';').map(c => {
      const [k, ...v] = c.trim().split('=')
      return [k, decodeURIComponent(v.join('='))]
    }).filter(Boolean))

    if (!cookies.session) {
      console.log('[auth/session] no session cookie')
      return NextResponse.json({ authenticated: false }, { status: 200 })
    }

    try {
  const session = JSON.parse(cookies.session)
  console.log('[auth/session] found session for user', session?.user?.email || session?.user?.id)
  return NextResponse.json({ authenticated: true, session })
    } catch (e) {
      return NextResponse.json({ authenticated: false }, { status: 200 })
    }
  } catch (err) {
    console.error('Error reading session:', err)
    return NextResponse.json({ authenticated: false }, { status: 500 })
  }
}
