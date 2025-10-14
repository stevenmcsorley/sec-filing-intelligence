/**
 * Filing Correlation Service
 * 
 * Service for fetching and managing filing correlation data
 */

export interface FilingCorrelation {
  filing_id: string
  ticker: string
  form_type: string
  filing_date: string
  title: string
  price_change_percent: number
  volume_spike_ratio: number
  price_volatility: number
  correlation_strength: 'strong' | 'moderate' | 'weak'
  market_impact_score: number
  confidence_level: number
  days_before_filing: number
  days_after_filing: number
  sector_impact?: string
}

export interface CorrelationSummary {
  ticker: string
  total_filings: number
  strong_correlations: number
  moderate_correlations: number
  weak_correlations: number
  avg_price_impact: number
  avg_volume_spike: number
  high_impact_forms: string[]
  analysis_period_days: number
}

class FilingCorrelationService {
  private baseUrl = '/api/v1/correlation'

  /**
   * Get filing correlations for a specific ticker
   */
  async getFilingCorrelations(
    ticker: string,
    token: string,
    daysLookback: number = 30,
    minPriceChange: number = 1.0
  ): Promise<FilingCorrelation[]> {
    try {
      const params = new URLSearchParams({
        days_lookback: daysLookback.toString(),
        min_price_change: minPriceChange.toString()
      })

      const response = await fetch(
        `${this.baseUrl}/filing/${ticker}?${params}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch filing correlations: ${response.statusText}`)
      }

      return await response.json()
    } catch (error) {
      console.error('Error fetching filing correlations:', error)
      throw error
    }
  }

  /**
   * Get correlation summary for a specific ticker
   */
  async getCorrelationSummary(
    ticker: string,
    token: string,
    daysLookback: number = 30
  ): Promise<CorrelationSummary> {
    try {
      const params = new URLSearchParams({
        days_lookback: daysLookback.toString()
      })

      const response = await fetch(
        `${this.baseUrl}/summary/${ticker}?${params}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch correlation summary: ${response.statusText}`)
      }

      return await response.json()
    } catch (error) {
      console.error('Error fetching correlation summary:', error)
      throw error
    }
  }

  /**
   * Convert correlation data to chart format
   */
  convertToChartData(correlations: FilingCorrelation[]) {
    return correlations.map(correlation => ({
      date: correlation.filing_date,
      formType: correlation.form_type,
      title: correlation.title,
      priceChangePercent: correlation.price_change_percent,
      volumeSpike: correlation.volume_spike_ratio > 1.5,
      correlationStrength: correlation.correlation_strength,
      marketImpactScore: correlation.market_impact_score,
      confidenceLevel: correlation.confidence_level
    }))
  }

  /**
   * Get correlation strength color
   */
  getCorrelationStrengthColor(strength: 'strong' | 'moderate' | 'weak'): string {
    switch (strength) {
      case 'strong':
        return '#ef4444' // red
      case 'moderate':
        return '#f59e0b' // yellow
      case 'weak':
        return '#10b981' // green
      default:
        return '#6b7280' // gray
    }
  }

  /**
   * Get correlation strength label
   */
  getCorrelationStrengthLabel(strength: 'strong' | 'moderate' | 'weak'): string {
    switch (strength) {
      case 'strong':
        return 'Strong Correlation'
      case 'moderate':
        return 'Moderate Correlation'
      case 'weak':
        return 'Weak Correlation'
      default:
        return 'Unknown'
    }
  }
}

export const filingCorrelationService = new FilingCorrelationService()
