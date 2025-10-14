"use client"

import Link from "next/link"
import { useEffect, useState, useCallback, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, Shield, Zap, BarChart3, ArrowRight, Star, Loader2 } from "lucide-react"
import { useAuth } from "@/lib/auth"
import { FilingsService } from "@/services/api/filings.service"
import useApiFetch from "@/services/api/useApiFetch"
import { FilingAdapter } from "@/services/adapters/filing.adapter"

export default function HomePage() {
  const { isAuthenticated, accessToken, isLoading: authLoading, user, signOut } = useAuth()
  const [recentFilings, setRecentFilings] = useState<any[]>([])
  const [loadingFilings, setLoadingFilings] = useState(false)

  // Mock data for when not authenticated
  const mockFilings = useMemo(() => [
    {
      cik: "0000320193",
      companyName: "Apple Inc.",
      formType: "10-K",
      filedAt: new Date("2024-10-10T16:30:00Z"),
      summary: "Annual report showing record revenue growth and new product launches including Vision Pro"
    },
    {
      cik: "0001652044",
      companyName: "Alphabet Inc.",
      formType: "10-Q",
      filedAt: new Date("2024-10-08T16:15:00Z"),
      summary: "Q3 earnings beat expectations with strong cloud and AI performance, YouTube growth continues"
    },
    {
      cik: "0001018724",
      companyName: "Amazon.com Inc.",
      formType: "8-K",
      filedAt: new Date("2024-10-05T16:45:00Z"),
      summary: "Major acquisition announcement of Anthropic AI and strategic partnership with Microsoft Azure"
    }
  ], [])

  const { fetchWithAuth } = useApiFetch()

  const loadRecentFilings = useCallback(async () => {
    try {
      setLoadingFilings(true)
      let apiResponse;

      // Wait until auth finishes initial check
      if (authLoading) return

      if (isAuthenticated) {
        // Use authenticated API for logged-in users (shows more data)
        const res = await fetchWithAuth(`/filings/?limit=5`)
        if (!res.ok) throw new Error('Failed to load recent filings')
        apiResponse = await res.json()
      } else {
        // Use public API for homepage visitors
        apiResponse = await FilingsService.getPublicRecent(3)
      }

      const domainData = FilingAdapter.listFromAPI(apiResponse)
      setRecentFilings(domainData.filings.slice(0, 3))
    } catch (error) {
      console.error('Failed to load recent filings:', error)
      // Fall back to mock data if API fails
      setRecentFilings(mockFilings)
    } finally {
      setLoadingFilings(false)
    }
  }, [isAuthenticated, authLoading, fetchWithAuth, mockFilings])

  useEffect(() => {
    loadRecentFilings()
  }, [loadRecentFilings]) // Re-run when authentication status changes

  const displayFilings = recentFilings.length > 0 ? recentFilings : mockFilings

  const features = [
    {
      icon: <TrendingUp className="h-8 w-8 text-green-500" />,
      title: "Real-time Insights",
      description: "Get instant analysis of SEC filings with AI-powered signal detection"
    },
    {
      icon: <Shield className="h-8 w-8 text-blue-500" />,
      title: "Secure & Compliant",
      description: "Enterprise-grade security with role-based access control"
    },
    {
      icon: <Zap className="h-8 w-8 text-yellow-500" />,
      title: "Lightning Fast",
      description: "Process thousands of filings daily with sub-second analysis"
    },
    {
      icon: <BarChart3 className="h-8 w-8 text-purple-500" />,
      title: "Advanced Analytics",
      description: "Deep dive into market trends and company performance metrics"
    }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-background">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-purple-600/10" />
        <div className="relative container mx-auto px-4 py-20 lg:py-32">
          <div className="text-center max-w-4xl mx-auto">
            <Badge variant="secondary" className="mb-4">
              <Star className="h-3 w-3 mr-1" />
              Powered by AI & Real-time Data
            </Badge>
            <h1 className="text-5xl lg:text-7xl font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent mb-6">
              Market Intelligence from SEC Filings
            </h1>
            <p className="text-xl text-muted-foreground mb-8 leading-relaxed">
              Stay ahead of market movements with AI-powered analysis of SEC filings.
              Get real-time insights, signal detection, and comprehensive market intelligence
              from the most important financial documents.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              {!authLoading && isAuthenticated ? (
                <>
                  <Button size="lg" className="text-lg px-8 py-6" onClick={() => signOut()}>
                    Sign Out
                  </Button>
                  <Button size="lg" variant="outline" asChild className="text-lg px-8 py-6">
                    <Link href="/filings">View Filings</Link>
                  </Button>
                </>
              ) : (
                <>
                  <Button size="lg" asChild className="text-lg px-8 py-6">
                    <Link href="/auth/signin">
                      Sign In
                      <ArrowRight className="ml-2 h-5 w-5" />
                    </Link>
                  </Button>
                  <Button size="lg" variant="outline" asChild className="text-lg px-8 py-6">
                    <Link href="/auth/signin">
                      Start Free Trial
                    </Link>
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-card/50">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
              Why Choose SEC Filing Intelligence?
            </h2>
            <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
              Built for financial professionals who need accurate, timely insights from SEC data
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <Card key={index} className="bg-card/50 border-border hover:bg-card/70 transition-colors">
                <CardHeader className="text-center">
                  <div className="mx-auto mb-4 p-3 bg-muted/50 rounded-full w-fit">
                    {feature.icon}
                  </div>
                  <CardTitle className="text-foreground">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-muted-foreground text-center">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Recent Filings Teaser */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
              Recent Market Insights
            </h2>
            <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
              See the latest filings and analysis from major companies
            </p>
          </div>
          {loadingFilings ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid md:grid-cols-1 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
              {displayFilings.map((filing, index) => (
                <Card key={index} className="bg-card/50 border-border hover:bg-card/70 transition-colors">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-foreground text-lg">
                          {filing.companyName || `CIK: ${filing.cik}`}
                          {filing.ticker && (
                            <span className="ml-2 text-sm font-normal text-muted-foreground">
                              ({filing.ticker})
                            </span>
                          )}
                        </CardTitle>
                        <CardDescription className="text-muted-foreground">
                          CIK: {filing.cik}
                        </CardDescription>
                      </div>
                      <Badge variant="outline" className="border-blue-500 text-blue-400">
                        {filing.formType}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-foreground text-sm mb-4">
                      {filing.summary || filing.analysis?.brief || "Recent SEC filing with important disclosures and financial updates"}
                    </p>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Filed {filing.filedAt.toLocaleDateString()}</span>
                      <Button size="sm" variant="ghost" asChild className="text-blue-400 hover:text-blue-300">
                        <Link href={!authLoading && isAuthenticated ? "/filings" : "/auth/signin"}>
                          View Details
                          <ArrowRight className="ml-1 h-3 w-3" />
                        </Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          <div className="text-center mt-12">
            {!authLoading && isAuthenticated ? (
              <Button size="lg" asChild className="text-lg px-8 py-6">
                <Link href="/filings">
                  View All Filings
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Link>
              </Button>
            ) : (
              <Button size="lg" asChild className="text-lg px-8 py-6">
                <Link href="/auth/signin">
                  View All Filings
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Link>
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-r from-primary/10 to-purple-600/10">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
            Ready to Access Market Intelligence?
          </h2>
          <p className="text-muted-foreground text-lg mb-8 max-w-2xl mx-auto">
            Join thousands of financial professionals who rely on our platform for critical market insights
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" asChild className="text-lg px-8 py-6">
              <Link href="/auth/signin">
                Get Started Free
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="text-lg px-8 py-6">
              <Link href="/docs">
                Learn More
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
