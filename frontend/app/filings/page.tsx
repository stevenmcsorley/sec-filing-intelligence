// app/filings/page.tsx
"use client"

import { useEffect, useState, useCallback } from "react"
import { FilingsService } from "@/services/api/filings.service"
import useApiFetch from "@/services/api/useApiFetch"
import { FilingAdapter } from "@/services/adapters/filing.adapter"
import { FilingCard } from "@/components/filings/FilingCard"
import { CompanyCard } from "@/components/filings/CompanyCard"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { 
  Search, 
  Filter, 
  Calendar, 
  TrendingUp, 
  AlertTriangle, 
  Users, 
  FileText,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Download,
  Eye
} from "lucide-react"
import { FilingList } from "@/types/domain.types"

interface Filters {
  search?: string
  formType?: string
  status?: string
  filedAfter?: Date
  filedBefore?: Date
  priority?: string
}

interface PaginationState {
  page: number
  limit: number
  total: number
  hasNext: boolean
  hasPrev: boolean
}

export default function FilingsPage() {
  console.log('FilingsPage component mounted')
  
  const { isAuthenticated, isLoading: authLoading, accessToken } = useAuth()
  const [filings, setFilings] = useState<FilingList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>({})
  const [pagination, setPagination] = useState<PaginationState>({
    page: 1,
    limit: 20,
    total: 0,
    hasNext: false,
    hasPrev: false
  })
  const [viewMode, setViewMode] = useState<'cards' | 'companies'>('cards')
  const [sortBy, setSortBy] = useState<'date' | 'priority' | 'company'>('date')

  const { fetchWithAuth } = useApiFetch()

  const loadFilings = useCallback(async (searchFilters?: Filters, pageNum?: number) => {
    try {
      setLoading(true)
      const apiFilters = searchFilters || filters
      const currentPage = pageNum || pagination.page
      
      // Determine search parameters
      let searchParams: any = {
        limit: pagination.limit,
        offset: (currentPage - 1) * pagination.limit,
      }
      
      // Only add parameters that have actual values
      if (apiFilters.formType && apiFilters.formType !== 'undefined' && apiFilters.formType.trim() !== '') {
        searchParams.form_type = apiFilters.formType
      }
      if (apiFilters.status && apiFilters.status !== 'undefined' && apiFilters.status.trim() !== '') {
        searchParams.status = apiFilters.status
      }
      if (apiFilters.priority && apiFilters.priority !== 'undefined' && apiFilters.priority.trim() !== '') {
        searchParams.priority = apiFilters.priority
      }
      if (apiFilters.filedAfter && apiFilters.filedAfter instanceof Date) {
        searchParams.filed_after = apiFilters.filedAfter.toISOString().split('T')[0]
      }
      if (apiFilters.filedBefore && apiFilters.filedBefore instanceof Date) {
        searchParams.filed_before = apiFilters.filedBefore.toISOString().split('T')[0]
      }
      
      if (apiFilters.search) {
        // If search looks like a number, treat it as CIK, otherwise as ticker/company name
        const isNumeric = /^\d+$/.test(apiFilters.search.trim())
        if (isNumeric) {
          searchParams.cik = apiFilters.search.trim()
        } else {
          searchParams.ticker = apiFilters.search.trim()
        }
      }
      
      let apiResponse
      if (isAuthenticated) {
        const url = `/filings/?${new URLSearchParams(searchParams).toString()}`
        const res = await fetchWithAuth(url)
        if (!res.ok) throw new Error('Failed to fetch filings')
        apiResponse = await res.json()
      } else {
        apiResponse = await FilingsService.list(undefined, searchParams)
      }
      
      console.log('API Response:', apiResponse)
      const domainData = FilingAdapter.listFromAPI(apiResponse)
      console.log('Domain Data:', domainData)
      
      setFilings(domainData)
      
      // Update pagination state
      setPagination(prev => ({
        ...prev,
        page: currentPage,
        total: apiResponse.total || domainData.filings.length,
        hasNext: domainData.filings.length === pagination.limit,
        hasPrev: currentPage > 1
      }))
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load filings')
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, filters, pagination.page, pagination.limit, fetchWithAuth])

  useEffect(() => {
    // Only load after the auth provider has finished its initial check
    if (!authLoading) {
      loadFilings()
    }
  }, [isAuthenticated, authLoading, loadFilings])

  const handleSearch = () => {
    setPagination(prev => ({ ...prev, page: 1 }))
    loadFilings(filters, 1)
  }

  const handleFilterChange = (key: keyof Filters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const clearFilters = () => {
    setFilters({})
    setPagination(prev => ({ ...prev, page: 1 }))
    loadFilings({}, 1)
  }

  const handlePageChange = (newPage: number) => {
    loadFilings(filters, newPage)
  }

  const handleRefresh = () => {
    loadFilings(filters, pagination.page)
  }

  // Group filings by company
  const groupFilingsByCompany = (filings: FilingList['filings']) => {
    const companyGroups: Record<string, { 
      companyName: string
      cik: string
      ticker?: string
      filings: FilingList['filings']
    }> = {}

    filings.forEach(filing => {
      const key = filing.cik // Use CIK as the unique identifier
      if (!companyGroups[key]) {
        companyGroups[key] = {
          companyName: filing.companyName || `CIK: ${filing.cik}`,
          cik: filing.cik,
          ticker: filing.ticker || undefined,
          filings: []
        }
      }
      companyGroups[key].filings.push(filing)
    })

    // Convert to array and sort by most recent filing
    return Object.values(companyGroups).sort((a, b) => {
      const aLatest = Math.max(...a.filings.map(f => f.filedAt.getTime()))
      const bLatest = Math.max(...b.filings.map(f => f.filedAt.getTime()))
      return bLatest - aLatest // Most recent first
    })
  }

  const companyGroups = filings ? groupFilingsByCompany(filings.filings) : []

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>SEC Filings</CardTitle>
          </CardHeader>
          <CardContent>
            <p>Loading filings...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>SEC Filings</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-destructive">Error: {error}</p>
            <Button onClick={() => loadFilings()} className="mt-4">
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <ProtectedRoute>
      <div className="container mx-auto py-8">
        {/* Professional Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                SEC Filing Intelligence
              </h1>
              <p className="text-muted-foreground mt-2 text-lg">
                Monitor company activity through their SEC filings with AI-powered analysis
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
            </div>
          </div>
          
          {/* Stats Cards */}
          {filings && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
              <Card className="bg-gradient-to-r from-blue-50 to-blue-100 border-blue-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-blue-600" />
                    <div>
                      <p className="text-sm font-medium text-blue-800">Total Filings</p>
                      <p className="text-2xl font-bold text-blue-900">{filings.filings.length}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-r from-green-50 to-green-100 border-green-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-green-600" />
                    <div>
                      <p className="text-sm font-medium text-green-800">With Analysis</p>
                      <p className="text-2xl font-bold text-green-900">
                        {filings.filings.filter(f => f.analysis?.brief).length}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-r from-red-50 to-red-100 border-red-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-600" />
                    <div>
                      <p className="text-sm font-medium text-red-800">High Impact</p>
                      <p className="text-2xl font-bold text-red-900">
                        {filings.filings.filter(f => f.formType === '4' || f.formType === '8-K').length}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-gradient-to-r from-purple-50 to-purple-100 border-purple-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-purple-600" />
                    <div>
                      <p className="text-sm font-medium text-purple-800">Companies</p>
                      <p className="text-2xl font-bold text-purple-900">{companyGroups.length}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {/* Enhanced Search and Filter Controls */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <Search className="h-5 w-5" />
                Search & Filter
              </CardTitle>
              <div className="flex items-center gap-2">
                <div className="flex rounded-md border">
                  <Button
                    variant={viewMode === 'cards' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('cards')}
                    className="rounded-r-none"
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    Cards
                  </Button>
                  <Button
                    variant={viewMode === 'companies' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('companies')}
                    className="rounded-l-none"
                  >
                    <Users className="h-4 w-4 mr-1" />
                    Companies
                  </Button>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div className="space-y-2">
                <Label htmlFor="search" className="flex items-center gap-1">
                  <Search className="h-4 w-4" />
                  Search
                </Label>
                <Input
                  id="search"
                  placeholder="CIK, ticker, or company name"
                  value={filters.search || ''}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="formType" className="flex items-center gap-1">
                  <FileText className="h-4 w-4" />
                  Form Type
                </Label>
                <Select value={filters.formType || 'all'} onValueChange={(value) => handleFilterChange('formType', value === 'all' ? undefined : value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="All forms" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All forms</SelectItem>
                    <SelectItem value="4">Form 4 - Insider Trading</SelectItem>
                    <SelectItem value="8-K">Form 8-K - Material Events</SelectItem>
                    <SelectItem value="10-K">Form 10-K - Annual Report</SelectItem>
                    <SelectItem value="10-Q">Form 10-Q - Quarterly Report</SelectItem>
                    <SelectItem value="SCHEDULE 13D/A">Schedule 13D/A - Ownership</SelectItem>
                    <SelectItem value="144">Form 144 - Rule 144</SelectItem>
                    <SelectItem value="3">Form 3 - Initial Ownership</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="priority" className="flex items-center gap-1">
                  <AlertTriangle className="h-4 w-4" />
                  Priority
                </Label>
                <Select value={filters.priority || 'all'} onValueChange={(value) => handleFilterChange('priority', value === 'all' ? undefined : value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="All priorities" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All priorities</SelectItem>
                    <SelectItem value="high">High Impact</SelectItem>
                    <SelectItem value="medium">Medium Impact</SelectItem>
                    <SelectItem value="low">Low Impact</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="status" className="flex items-center gap-1">
                  <Filter className="h-4 w-4" />
                  Status
                </Label>
                <Select value={filters.status || 'all'} onValueChange={(value) => handleFilterChange('status', value === 'all' ? undefined : value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    <SelectItem value="parsed">Parsed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Date Range
                </Label>
                <div className="flex gap-2">
                  <Input
                    type="date"
                    placeholder="From"
                    value={filters.filedAfter?.toISOString().split('T')[0] || ''}
                    onChange={(e) => handleFilterChange('filedAfter', e.target.value ? new Date(e.target.value) : undefined)}
                  />
                  <Input
                    type="date"
                    placeholder="To"
                    value={filters.filedBefore?.toISOString().split('T')[0] || ''}
                    onChange={(e) => handleFilterChange('filedBefore', e.target.value ? new Date(e.target.value) : undefined)}
                  />
                </div>
              </div>
            </div>
            
            <div className="flex items-center justify-between mt-6">
              <div className="flex gap-2">
                <Button onClick={handleSearch} className="flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Search
                </Button>
                <Button variant="outline" onClick={clearFilters}>
                  Clear Filters
                </Button>
              </div>
              
              <div className="flex items-center gap-2">
                <Label htmlFor="sortBy">Sort by:</Label>
                <Select value={sortBy} onValueChange={(value) => setSortBy(value as 'date' | 'priority' | 'company')}>
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="date">Date</SelectItem>
                    <SelectItem value="priority">Priority</SelectItem>
                    <SelectItem value="company">Company</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results Section */}
        {filings && (
          <>
            {/* Results Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <h2 className="text-xl font-semibold">
                  {viewMode === 'cards' ? 'Filing Cards' : 'Company Groups'}
                </h2>
                <Badge variant="outline" className="text-sm">
                  {viewMode === 'cards' ? filings.filings.length : companyGroups.length} results
                </Badge>
                <Badge variant="secondary" className="text-sm">
                  Page {pagination.page} of {Math.ceil(pagination.total / pagination.limit)}
                </Badge>
              </div>
              
              {/* Pagination Controls */}
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => handlePageChange(pagination.page - 1)}
                  disabled={!pagination.hasPrev || loading}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, Math.ceil(pagination.total / pagination.limit)) }, (_, i) => {
                    const pageNum = i + 1
                    const isCurrentPage = pageNum === pagination.page
                    return (
                      <Button
                        key={pageNum}
                        variant={isCurrentPage ? "default" : "outline"}
                        size="sm"
                        onClick={() => handlePageChange(pageNum)}
                        disabled={loading}
                        className="w-8 h-8 p-0"
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                </div>
                
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => handlePageChange(pagination.page + 1)}
                  disabled={!pagination.hasNext || loading}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Results Display */}
            {viewMode === 'cards' ? (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {filings.filings.map((filing) => (
                  <FilingCard key={filing.id} filing={filing} />
                ))}
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {companyGroups.map((company) => (
                  <CompanyCard
                    key={company.cik}
                    companyName={company.companyName}
                    cik={company.cik}
                    ticker={company.ticker}
                    filings={company.filings}
                  />
                ))}
              </div>
            )}

            {/* Empty State */}
            {(viewMode === 'cards' ? filings.filings.length === 0 : companyGroups.length === 0) && (
              <Card>
                <CardContent className="py-12 text-center">
                  <div className="flex flex-col items-center gap-4">
                    <div className="p-4 rounded-full bg-muted">
                      <Search className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold">No results found</h3>
                      <p className="text-muted-foreground">
                        Try adjusting your search filters or clear all filters to see all filings.
                      </p>
                    </div>
                    <Button variant="outline" onClick={clearFilters}>
                      Clear All Filters
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
    </div>
    </ProtectedRoute>
  )
}