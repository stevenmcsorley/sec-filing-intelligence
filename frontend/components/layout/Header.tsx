"use client"

import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"

export default function Header() {
  const { isAuthenticated, isLoading, user, signOut } = useAuth()

  return (
    <header className="w-full border-b border-slate-800 bg-slate-950/50">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <Link href="/" className="font-bold text-lg">
          SEC Filing Intelligence
        </Link>
        <div>
          {!isLoading && isAuthenticated ? (
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-300">{user?.name || user?.email}</span>
              <Button size="sm" variant="ghost" onClick={() => signOut()}>
                Sign Out
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link href="/auth/signin">
                <Button size="sm">Sign In</Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
