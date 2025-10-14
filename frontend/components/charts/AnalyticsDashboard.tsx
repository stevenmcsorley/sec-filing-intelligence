"use client"

import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  BarChart3, 
  TrendingUp, 
  Calendar,
  Activity,
  RefreshCw,
  Download,
  Maximize2,
  Minimize2
} from 'lucide-react'
import { HistoricalPrice } from '@/services/api/price.service'
import { PriceChart } from './PriceChart'
import { FilingCorrelationChart } from './FilingCorrelationChart'

interface FilingMarker {
  date: string
  formType: string
  title: string
  impact: 'high' | 'medium' | 'low'
}

interface FilingCorrelation {
  date: string
  formType: string
  title: string
  priceChangePercent: number
  volumeSpike: boolean
  correlationStrength: 'strong' | 'moderate' | 'weak'
}

interface AnalyticsDashboardProps {
  ticker: string
  historicalPrices: HistoricalPrice[]
  filingMarkers: FilingMarker[]
  filingCorrelations: FilingCorrelation[]
  loading?: boolean
  onRefresh?: () => void
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  ticker,
  historicalPrices,
  filingMarkers,
  filingCorrelations,
  loading = false,
  onRefresh
}) => {
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick')
  const [showVolume, setShowVolume] = useState(true)
  const [isExpanded, setIsExpanded] = useState(false)

  const chartHeight = isExpanded ? 500 : 300

  // Calculate some basic analytics
  const analytics = React.useMemo(() => {
    if (!historicalPrices.length) return null

    const prices = historicalPrices.map(p => p.close)
    const volumes = historicalPrices.map(p => p.volume)
    
    const priceChange = prices[prices.length - 1] - prices[0]
    const priceChangePercent = (priceChange / prices[0]) * 100
    
    const avgVolume = volumes.reduce((a, b) => a + b, 0) / volumes.length
    const maxVolume = Math.max(...volumes)
    const volumeSpikeDays = volumes.filter(v => v > avgVolume * 1.5).length
    
    const highImpactFilings = filingMarkers.filter(f => f.impact === 'high').length
    const strongCorrelations = filingCorrelations.filter(f => f.correlationStrength === 'strong').length

    return {
      priceChange,
      priceChangePercent,
      avgVolume,
      maxVolume,
      volumeSpikeDays,
      highImpactFilings,
      strongCorrelations
    }
  }, [historicalPrices, filingMarkers, filingCorrelations])

  if (loading) {
    return (
      <Card className="w-full">
        <CardContent className="p-6">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-2 text-muted-foreground">Loading analytics...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Analytics Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Price Change</p>
                <p className={`text-2xl font-bold ${analytics?.priceChangePercent && analytics.priceChangePercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {analytics?.priceChangePercent ? `${analytics.priceChangePercent >= 0 ? '+' : ''}${analytics.priceChangePercent.toFixed(2)}%` : 'N/A'}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Volume Spikes</p>
                <p className="text-2xl font-bold text-blue-600">
                  {analytics?.volumeSpikeDays || 0}
                </p>
                <p className="text-xs text-muted-foreground">days</p>
              </div>
              <Activity className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">High Impact</p>
                <p className="text-2xl font-bold text-red-600">
                  {analytics?.highImpactFilings || 0}
                </p>
                <p className="text-xs text-muted-foreground">filings</p>
              </div>
              <Calendar className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Strong Correlations</p>
                <p className="text-2xl font-bold text-orange-600">
                  {analytics?.strongCorrelations || 0}
                </p>
                <p className="text-xs text-muted-foreground">patterns</p>
              </div>
              <BarChart3 className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              {ticker} Price Analysis
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setChartType(chartType === 'candlestick' ? 'line' : 'candlestick')}
              >
                {chartType === 'candlestick' ? 'Line Chart' : 'Candlestick'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowVolume(!showVolume)}
              >
                {showVolume ? 'Hide Volume' : 'Show Volume'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
              {onRefresh && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onRefresh}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <PriceChart
            historicalPrices={historicalPrices}
            filingMarkers={filingMarkers}
            height={chartHeight}
            showVolume={showVolume}
          />
        </CardContent>
      </Card>

      {/* Filing Correlation Chart */}
      {filingCorrelations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Filing Impact Correlation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <FilingCorrelationChart
              historicalPrices={historicalPrices}
              filingCorrelations={filingCorrelations}
              height={300}
            />
          </CardContent>
        </Card>
      )}

      {/* Filing Legend */}
      {filingMarkers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Filing Types Legend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge variant="destructive" className="text-xs">
                <div className="w-2 h-2 bg-red-500 rounded-full mr-1"></div>
                High Impact
              </Badge>
              <Badge variant="secondary" className="text-xs">
                <div className="w-2 h-2 bg-yellow-500 rounded-full mr-1"></div>
                Medium Impact
              </Badge>
              <Badge variant="default" className="text-xs">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                Low Impact
              </Badge>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default AnalyticsDashboard
