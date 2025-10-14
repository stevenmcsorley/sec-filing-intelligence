import { NextResponse } from 'next/server'

export async function GET() {
  console.log('Test API route called')
  return NextResponse.json({ message: 'Test API works', timestamp: new Date().toISOString() })
}