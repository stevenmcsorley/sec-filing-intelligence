// app/filings/page.tsx
"use client"

import { useEffect, useState } from "react"
import { FilingsService } from "@/services/api/filings.service"
import { FilingAdapter } from "@/services/adapters/filing.adapter"
import { FilingCard } from "@/components/filings/FilingCard"
import { CompanyCard } from "@/components/filings/CompanyCard"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { FilingList } from "@/types/domain.types"

interface Filters {
  search?: string
  formType?: string
  status?: string
  filedAfter?: Date
  filedBefore?: Date
}

export default function FilingsPage() {
  console.log('FilingsPage component mounted')
  
  const [filings, setFilings] = useState<FilingList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>({})

  useEffect(() => {
    loadFilings()
  }, [])

  const loadFilings = async (searchFilters?: Filters) => {
    try {
      setLoading(true)
      const apiFilters = searchFilters || {}
      
      // Determine search parameters - don't pass both cik and ticker
      let searchParams: any = {
        limit: 100, // Get more filings to group by company
        form_type: apiFilters.formType,
        status: apiFilters.status,
        filed_after: apiFilters.filedAfter,
        filed_before: apiFilters.filedBefore,
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
      
      const apiResponse = await FilingsService.list(searchParams)
      console.log('API Response:', apiResponse)
      const domainData = FilingAdapter.listFromAPI(apiResponse)
      console.log('Domain Data:', domainData)
      setFilings(domainData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load filings')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    loadFilings(filters)
  }

  const handleFilterChange = (key: keyof Filters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const clearFilters = () => {
    setFilters({})
    loadFilings({})
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
            <p>Loading filings... (Component mounted)</p>
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
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">SEC Filing Intelligence</h1>
        <p className="text-muted-foreground mt-2">
          Monitor company activity through their SEC filings with AI-powered analysis
        </p>
      </div>

      {/* Search and Filter Controls */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Search & Filter</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <Input
                id="search"
                placeholder="CIK, ticker, or company name"
                value={filters.search || ''}
                onChange={(e) => handleFilterChange('search', e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="formType">Form Type</Label>
              <Select value={filters.formType || 'all'} onValueChange={(value) => handleFilterChange('formType', value === 'all' ? undefined : value)}>
                <SelectTrigger>
                  <SelectValue placeholder="All forms" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All forms</SelectItem>
                  <SelectItem value="4">Form 4</SelectItem>
                  <SelectItem value="8-K">Form 8-K</SelectItem>
                  <SelectItem value="10-K">Form 10-K</SelectItem>
                  <SelectItem value="10-Q">Form 10-Q</SelectItem>
                  <SelectItem value="13D">Schedule 13D</SelectItem>
                  <SelectItem value="144">Form 144</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
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
              <Label>Date Range</Label>
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
          <div className="flex gap-2 mt-4">
            <Button onClick={handleSearch}>
              Search
            </Button>
            <Button variant="outline" onClick={clearFilters}>
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {filings && (
        <>
          <div className="mb-4 text-sm text-muted-foreground">
            Showing {companyGroups.length} companies with {filings.filings.length} total filings
          </div>

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

          {companyGroups.length === 0 && (
            <Card>
              <CardContent className="py-8">
                <p className="text-center text-muted-foreground">
                  No companies found. Try adjusting your search filters.
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}