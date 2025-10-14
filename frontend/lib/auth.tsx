"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"

interface User {
  id: string
  name?: string
  email?: string
}

interface Session {
  accessToken: string
  refreshToken?: string
  user: User
  roles?: string[]
}

interface AuthContextType {
  user: User | null
  accessToken: string | null
  roles: string[]
  isLoading: boolean
  isAuthenticated: boolean
  signIn: () => void
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [initialLoadComplete, setInitialLoadComplete] = useState(false)

  useEffect(() => {
    // Fetch session from server endpoint (reads httpOnly cookie server-side)
    const checkSession = async () => {
      try {
        const res = await fetch('/api/auth/session', { 
          credentials: 'same-origin',
          cache: 'no-store' // Ensure fresh session data
        })
        const data = await res.json()
        if (data.authenticated) {
          setSession(data.session)
        } else {
          setSession(null)
        }
      } catch (error) {
        console.error('Error fetching session:', error)
        setSession(null)
      } finally {
        setIsLoading(false)
        setInitialLoadComplete(true)
      }
    }

    checkSession()
    
    // Listen for session updates triggered by refresh flow
    const onSessionUpdated = () => {
      refreshSession().catch(() => {})
    }

    window.addEventListener('session:updated', onSessionUpdated)

    return () => {
      window.removeEventListener('session:updated', onSessionUpdated)
    }
  }, [])

  const signIn = () => {
    // Redirect to sign-in page
    window.location.href = '/auth/signin'
  }

  const signOut = async () => {
    // Call server-side signout endpoint which clears cookie
    try {
      await fetch('/api/auth/signout', { 
        method: 'POST', 
        credentials: 'same-origin', 
        headers: { 'x-confirm-signout': '1' } 
      })
    } catch (e) {
      console.error('signOut failed:', e)
    } finally {
      setSession(null)
      window.location.href = '/auth/signin'
    }
  }

  const refreshSession = async () => {
    try {
      setIsLoading(true)
      const res = await fetch('/api/auth/session', { 
        credentials: 'same-origin',
        cache: 'no-store'
      })
      const data = await res.json()
      if (data.authenticated) {
        setSession(data.session)
      } else {
        setSession(null)
      }
    } catch (e) {
      console.error('Failed to refresh session', e)
      setSession(null)
    } finally {
      setIsLoading(false)
    }
  }

  const value: AuthContextType = {
    user: session?.user || null,
    accessToken: session?.accessToken || null,
    roles: session?.roles || [],
    isLoading: isLoading || !initialLoadComplete,
    isAuthenticated: !!session,
    signIn,
    signOut,
    refreshSession,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export function useCapabilityFlags() {
  const { roles } = useAuth()

  // Map roles to capability flags based on PRD requirements
  const capabilities = {
    canViewFilings: roles.includes('basic_free') || roles.includes('analyst_pro') || roles.includes('org_admin') || roles.includes('super_admin'),
    canViewDiffs: roles.includes('analyst_pro') || roles.includes('org_admin') || roles.includes('super_admin'),
    canManageWatchlists: roles.includes('analyst_pro') || roles.includes('org_admin') || roles.includes('super_admin'),
    canViewAlerts: roles.includes('analyst_pro') || roles.includes('org_admin') || roles.includes('super_admin'),
    canAccessAdmin: roles.includes('super_admin'),
    canManageOrg: roles.includes('org_admin') || roles.includes('super_admin'),
  }

  return capabilities
}