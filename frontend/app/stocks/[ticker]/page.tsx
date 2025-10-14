// app/stocks/[ticker]/page.tsx
"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { 
  TrendingUp, 
  TrendingDown, 
  Building2, 
  Calendar,
  DollarSign,
  Users,
  AlertTriangle,
  BarChart3,
  FileText,
  Clock,
  Activity,
  Target,
  Zap,
  Star,
  Download,
  Share2,
  Bell,
  Eye,
  RefreshCw,
  ExternalLink
} from "lucide-react"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useAuth } from "@/lib/auth"
import useApiFetch from "@/services/api/useApiFetch"
import { FilingAdapter } from "@/services/adapters/filing.adapter"
import { FilingCard } from "@/components/filings/FilingCard"
import { priceDataService, CurrentPrice, HistoricalPrice, CompanyOverview } from "@/services/api/price.service"

interface StockProfile {
  ticker: string
  companyName: string
  cik: string
  sector?: string
  industry?: string
  marketCap?: number
  currentPrice?: number
  priceChange?: number
  priceChangePercent?: number
  volume?: number
  avgVolume?: number
  filingCount: number
  lastFilingDate?: Date
  highImpactFilings: number
  insiderTransactions: number
  peRatio?: number
  eps?: number
  dividendYield?: number
  beta?: number
  website?: string
  description?: string
}

interface PriceCorrelation {
  date: string
  price: number
  filingImpact?: 'high' | 'medium' | 'low'
  filingType?: string
  filingTitle?: string
}

interface FilingInsight {
  type: 'insider_activity' | 'earnings' | 'material_event' | 'ownership_change'
  title: string
  description: string
  impact: 'high' | 'medium' | 'low'
  confidence: number
  date: Date
  filingId: string
}

interface FilingHistory {
  filings: any[]
  totalCount: number
  highImpactCount: number
  insiderCount: number
  quarterlyCount: number
  annualCount: number
}

export default function StockProfilePage() {
  const params = useParams()
  const ticker = params.ticker as string
  
  const { isAuthenticated, isLoading: authLoading } = useAuth()
  const { fetchWithAuth } = useApiFetch()
  
  const [profile, setProfile] = useState<StockProfile | null>(null)
  const [filingHistory, setFilingHistory] = useState<FilingHistory | null>(null)
  const [priceCorrelation, setPriceCorrelation] = useState<PriceCorrelation[]>([])
  const [filingInsights, setFilingInsights] = useState<FilingInsight[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'analytics' | 'insights' | 'filings'>('overview')
  
  // Price data state
  const [currentPrice, setCurrentPrice] = useState<CurrentPrice | null>(null)
  const [historicalPrices, setHistoricalPrices] = useState<HistoricalPrice[]>([])
  const [companyOverview, setCompanyOverview] = useState<CompanyOverview | null>(null)
  const [priceLoading, setPriceLoading] = useState(false)

  const loadPriceData = useCallback(async () => {
    if (!isAuthenticated) return
    
    try {
      setPriceLoading(true)
      const token = localStorage.getItem('access_token')
      if (!token) return
      
      // Load current price, historical data, and company overview in parallel
      const [currentPriceData, historicalData, overviewData] = await Promise.allSettled([
        priceDataService.getCurrentPrice(ticker, token),
        priceDataService.getHistoricalPrices(ticker, 30, token),
        priceDataService.getCompanyOverview(ticker, token)
      ])
      
      if (currentPriceData.status === 'fulfilled') {
        setCurrentPrice(currentPriceData.value)
      }
      
      if (historicalData.status === 'fulfilled') {
        setHistoricalPrices(historicalData.value.data)
      }
      
      if (overviewData.status === 'fulfilled') {
        setCompanyOverview(overviewData.value)
      }
      
    } catch (error) {
      console.error('Error loading price data:', error)
    } finally {
      setPriceLoading(false)
    }
  }, [ticker, isAuthenticated])

  const loadStockProfile = useCallback(async () => {
    try {
      setLoading(true)
      
      // Load filing history first (this will work)
      const filingsResponse = await fetchWithAuth(`/filings/?ticker=${ticker}&limit=50`)
      if (!filingsResponse.ok) throw new Error('Failed to load filing history')
      const filingsData = await filingsResponse.json()
      
      // Create mock profile data from filings
      const mockProfile: StockProfile = {
        ticker: ticker.toUpperCase(),
        companyName: filingsData.filings[0]?.company_name || `${ticker} Corp`,
        cik: filingsData.filings[0]?.cik || '0000000000',
        sector: 'Technology', // Mock data
        industry: 'Software',
        marketCap: 5000000000, // Mock $5B
        currentPrice: 125.50, // Mock price
        priceChange: 2.30,
        priceChangePercent: 1.87,
        volume: 1500000,
        avgVolume: 2000000,
        filingCount: filingsData.total_count || 0,
        lastFilingDate: filingsData.filings[0] ? new Date(filingsData.filings[0].filed_at) : undefined,
        highImpactFilings: filingsData.filings.filter((f: any) => f.form_type === '4' || f.form_type === '8-K').length,
        insiderTransactions: filingsData.filings.filter((f: any) => f.form_type === '4').length,
        peRatio: 25.4,
        eps: 4.95,
        dividendYield: 0.8,
        beta: 1.2,
        website: `https://www.${ticker.toLowerCase()}.com`,
        description: `Professional analysis and monitoring for ${ticker} through SEC filings and market data.`
      }
      
      // Generate mock price correlation data
      const mockPriceCorrelation: PriceCorrelation[] = [
        { date: '2024-01-01', price: 120.00 },
        { date: '2024-01-15', price: 122.50, filingImpact: 'medium', filingType: '10-Q', filingTitle: 'Q4 Earnings' },
        { date: '2024-02-01', price: 118.75 },
        { date: '2024-02-15', price: 125.00, filingImpact: 'high', filingType: '8-K', filingTitle: 'Major Contract' },
        { date: '2024-03-01', price: 127.25 },
        { date: '2024-03-15', price: 124.50, filingImpact: 'low', filingType: '4', filingTitle: 'Insider Sale' },
        { date: '2024-04-01', price: 128.75 },
        { date: '2024-04-15', price: 125.50, filingImpact: 'medium', filingType: '10-K', filingTitle: 'Annual Report' }
      ]
      
      // Generate mock filing insights
      const mockInsights: FilingInsight[] = [
        {
          type: 'insider_activity',
          title: 'Executive Stock Purchase',
          description: 'CEO purchased 10,000 shares at $125.50, indicating confidence in company direction.',
          impact: 'high',
          confidence: 0.92,
          date: new Date('2024-04-10'),
          filingId: '1'
        },
        {
          type: 'earnings',
          title: 'Strong Q1 Performance',
          description: 'Revenue exceeded expectations by 8%, driven by strong demand in core markets.',
          impact: 'high',
          confidence: 0.88,
          date: new Date('2024-04-05'),
          filingId: '2'
        },
        {
          type: 'material_event',
          title: 'Strategic Partnership',
          description: 'Announced partnership with major cloud provider, expected to boost market share.',
          impact: 'medium',
          confidence: 0.75,
          date: new Date('2024-03-20'),
          filingId: '3'
        }
      ]
      
      setProfile(mockProfile)
      setFilingHistory({
        filings: filingsData.filings,
        totalCount: filingsData.total_count,
        highImpactCount: filingsData.filings.filter((f: any) => f.form_type === '4' || f.form_type === '8-K').length,
        insiderCount: filingsData.filings.filter((f: any) => f.form_type === '4').length,
        quarterlyCount: filingsData.filings.filter((f: any) => f.form_type === '10-Q').length,
        annualCount: filingsData.filings.filter((f: any) => f.form_type === '10-K').length
      })
      setPriceCorrelation(mockPriceCorrelation)
      setFilingInsights(mockInsights)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stock profile')
    } finally {
      setLoading(false)
    }
  }, [ticker, fetchWithAuth])

  useEffect(() => {
    if (!authLoading && ticker) {
      loadStockProfile()
      loadPriceData()
    }
  }, [authLoading, ticker, loadStockProfile, loadPriceData])

  if (loading) {
    return (
      <ProtectedRoute>
        <div className="container mx-auto py-8">
          <Card>
            <CardContent className="py-8">
              <p>Loading stock profile...</p>
            </CardContent>
          </Card>
        </div>
      </ProtectedRoute>
    )
  }

  if (error) {
    return (
      <ProtectedRoute>
        <div className="container mx-auto py-8">
          <Card>
            <CardContent className="py-8">
              <p className="text-destructive">Error: {error}</p>
              <Button onClick={loadStockProfile} className="mt-4">
                Try Again
              </Button>
            </CardContent>
          </Card>
        </div>
      </ProtectedRoute>
    )
  }

  if (!profile) {
    return (
      <ProtectedRoute>
        <div className="container mx-auto py-8">
          <Card>
            <CardContent className="py-8">
              <p>Stock profile not found</p>
            </CardContent>
          </Card>
        </div>
      </ProtectedRoute>
    )
  }

  return (
    <ProtectedRoute>
      <div className="container mx-auto py-8">
        {/* Professional Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 text-white">
                <Building2 className="h-8 w-8" />
              </div>
              <div>
                <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  {profile.ticker}
                </h1>
                <p className="text-xl text-muted-foreground font-medium">
                  {companyOverview?.name || profile.companyName}
                </p>
                <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
                  <span className="flex items-center gap-1">
                    <Target className="h-4 w-4" />
                    CIK: {profile.cik}
                  </span>
                  {(companyOverview?.sector || profile.sector) && (
                    <span className="flex items-center gap-1">
                      <BarChart3 className="h-4 w-4" />
                      {companyOverview?.sector || profile.sector}
                    </span>
                  )}
                  {profile.website && (
                    <a 
                      href={profile.website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Website
                    </a>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm">
                <Bell className="h-4 w-4 mr-2" />
                Watch
              </Button>
              <Button variant="outline" size="sm">
                <Share2 className="h-4 w-4 mr-2" />
                Share
              </Button>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
              <Button variant="outline" size="sm" onClick={loadStockProfile} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>
          
          {/* Price and Key Metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Price Card */}
            <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-green-800">Current Price</p>
                    <div className="text-3xl font-bold text-green-900">
                      {priceLoading ? (
                        <div className="animate-pulse bg-green-200 h-8 w-24 rounded"></div>
                      ) : (
                        `$${currentPrice?.price?.toFixed(2) || profile.currentPrice?.toFixed(2) || 'N/A'}`
                      )}
                    </div>
                    {(currentPrice?.change || profile.priceChange) && (
                      <div className={`text-sm font-medium ${
                        (currentPrice?.change || profile.priceChange || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {(currentPrice?.change || profile.priceChange || 0) >= 0 ? '+' : ''}
                        ${(currentPrice?.change || profile.priceChange || 0).toFixed(2)} 
                        ({(currentPrice?.change_percent || profile.priceChangePercent || 0).toFixed(2)}%)
                      </div>
                    )}
                  </div>
                  <div className="p-3 rounded-full bg-green-100">
                    {profile.priceChange && profile.priceChange >= 0 ? (
                      <TrendingUp className="h-6 w-6 text-green-600" />
                    ) : (
                      <TrendingDown className="h-6 w-6 text-red-600" />
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Market Cap Card */}
            <Card className="bg-gradient-to-r from-blue-50 to-cyan-50 border-blue-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-blue-800">Market Cap</p>
                    <div className="text-2xl font-bold text-blue-900">
                      {companyOverview?.market_cap ? 
                        `$${(companyOverview.market_cap / 1000000000).toFixed(1)}B` : 
                        profile.marketCap ? 
                          `$${(profile.marketCap / 1000000000).toFixed(1)}B` : 
                          'N/A'
                      }
                    </div>
                    <div className="text-sm text-blue-600">
                      Volume: {currentPrice?.volume?.toLocaleString() || profile.volume?.toLocaleString() || 'N/A'}
                    </div>
                  </div>
                  <div className="p-3 rounded-full bg-blue-100">
                    <DollarSign className="h-6 w-6 text-blue-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Key Ratios Card */}
            <Card className="bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-purple-800">Key Ratios</p>
                    <div className="space-y-1">
                      <div className="text-sm font-bold text-purple-900">
                        P/E: {profile.peRatio || 'N/A'}
                      </div>
                      <div className="text-sm font-bold text-purple-900">
                        Beta: {profile.beta || 'N/A'}
                      </div>
                      <div className="text-sm font-bold text-purple-900">
                        Yield: {profile.dividendYield ? (profile.dividendYield * 100).toFixed(1) + '%' : 'N/A'}
                      </div>
                    </div>
                  </div>
                  <div className="p-3 rounded-full bg-purple-100">
                    <BarChart3 className="h-6 w-6 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Professional Tab Navigation */}
        <div className="mb-8">
          <div className="flex rounded-lg border bg-muted p-1">
            {[
              { id: 'overview', label: 'Overview', icon: Eye },
              { id: 'analytics', label: 'Analytics', icon: BarChart3 },
              { id: 'insights', label: 'AI Insights', icon: Zap },
              { id: 'filings', label: 'Filings', icon: FileText }
            ].map((tab) => (
              <Button
                key={tab.id}
                variant={activeTab === tab.id ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setActiveTab(tab.id as any)}
                className="flex-1 flex items-center gap-2"
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Filing Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="bg-gradient-to-r from-blue-50 to-blue-100 border-blue-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-blue-600" />
                    <span className="text-sm font-medium text-blue-800">Total Filings</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-900 mt-1">{filingHistory?.totalCount || 0}</div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-r from-red-50 to-red-100 border-red-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-600" />
                    <span className="text-sm font-medium text-red-800">High Impact</span>
                  </div>
                  <div className="text-2xl font-bold text-red-900 mt-1">{filingHistory?.highImpactCount || 0}</div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-r from-green-50 to-green-100 border-green-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-green-600" />
                    <span className="text-sm font-medium text-green-800">Insider Trades</span>
                  </div>
                  <div className="text-2xl font-bold text-green-900 mt-1">{filingHistory?.insiderCount || 0}</div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-r from-purple-50 to-purple-100 border-purple-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-purple-600" />
                    <span className="text-sm font-medium text-purple-800">Last Filing</span>
                  </div>
                  <div className="text-sm font-bold text-purple-900 mt-1">
                    {profile.lastFilingDate ? profile.lastFilingDate.toLocaleDateString() : 'N/A'}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Company Description */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  Company Overview
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">
                  {profile.description || `Professional analysis and monitoring for ${profile.ticker} through comprehensive SEC filing intelligence. Track insider activity, material events, and financial performance with AI-powered insights.`}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="space-y-6">
            {/* Price Correlation Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Price Correlation with Filings
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg flex items-center justify-center border-2 border-dashed border-blue-200">
                  <div className="text-center">
                    <BarChart3 className="h-12 w-12 text-blue-400 mx-auto mb-4" />
                    <p className="text-blue-600 font-medium">Price Correlation Chart</p>
                    <p className="text-sm text-blue-500">Interactive chart showing stock price movements correlated with filing events</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Filing Impact Analysis */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Filing Impact Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">High Impact Filings</span>
                      <Badge variant="destructive">{filingHistory?.highImpactCount || 0}</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Medium Impact Filings</span>
                      <Badge variant="default">{filingHistory?.filings.filter((f: any) => f.form_type === '10-K' || f.form_type === '10-Q').length || 0}</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Low Impact Filings</span>
                      <Badge variant="secondary">{filingHistory?.filings.filter((f: any) => f.form_type === '144' || f.form_type === '3').length || 0}</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    Filing Frequency
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Quarterly Reports</span>
                      <Badge variant="outline">{filingHistory?.quarterlyCount || 0}</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Annual Reports</span>
                      <Badge variant="outline">{filingHistory?.annualCount || 0}</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Material Events</span>
                      <Badge variant="outline">{filingHistory?.filings.filter((f: any) => f.form_type === '8-K').length || 0}</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {activeTab === 'insights' && (
          <div className="space-y-6">
            {/* AI Insights */}
            <div className="grid gap-4">
              {filingInsights.map((insight, index) => (
                <Card key={index} className={`border-l-4 ${
                  insight.impact === 'high' ? 'border-l-red-500 bg-red-50/30' :
                  insight.impact === 'medium' ? 'border-l-yellow-500 bg-yellow-50/30' :
                  'border-l-blue-500 bg-blue-50/30'
                }`}>
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant={
                            insight.impact === 'high' ? 'destructive' :
                            insight.impact === 'medium' ? 'default' :
                            'secondary'
                          }>
                            {insight.type.replace('_', ' ').toUpperCase()}
                          </Badge>
                          <Badge variant="outline">
                            {Math.round(insight.confidence * 100)}% Confidence
                          </Badge>
                        </div>
                        <h3 className="text-lg font-semibold mb-2">{insight.title}</h3>
                        <p className="text-muted-foreground mb-3">{insight.description}</p>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-4 w-4" />
                            {insight.date.toLocaleDateString()}
                          </span>
                          <span className="flex items-center gap-1">
                            <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                            AI Analysis
                          </span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'filings' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Recent Filings</h2>
              <Button variant="outline" size="sm">
                View All Filings
              </Button>
            </div>
            
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filingHistory?.filings.slice(0, 6).map((filing: any) => (
                <FilingCard key={filing.id} filing={FilingAdapter.summaryFromAPI(filing)} />
              ))}
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  )
}
