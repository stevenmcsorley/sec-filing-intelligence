"use client"

import { useAuth } from "@/lib/auth"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

interface ProtectedRouteProps {
  children: React.ReactNode
  requireAuth?: boolean
}

export function ProtectedRoute({ children, requireAuth = true }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [hasTimedOut, setHasTimedOut] = useState(false)

  useEffect(() => {
    // If we've been loading for more than 3 seconds, assume no session exists
    const timer = setTimeout(() => {
      setHasTimedOut(true)
    }, 3000)

    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    // Redirect if not authenticated and auth is required
    if ((hasTimedOut || !isLoading) && requireAuth && !isAuthenticated) {
      router.push("/auth/signin")
    }
  }, [isAuthenticated, isLoading, hasTimedOut, requireAuth, router])

  // If loading and not timed out, show loading spinner
  if (isLoading && !hasTimedOut) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  // If not authenticated and auth required, show redirect message
  if (requireAuth && !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div>Redirecting to sign in...</div>
      </div>
    )
  }

  return children
}