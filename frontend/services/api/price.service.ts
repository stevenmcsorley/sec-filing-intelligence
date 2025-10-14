/** Price data service for fetching stock prices from the backend API. */

export interface CurrentPrice {
  ticker: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  previous_close: number;
  market_cap?: number;
  timestamp: string;
}

export interface HistoricalPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CompanyOverview {
  ticker: string;
  name?: string;
  sector?: string;
  industry?: string;
  market_cap?: number;
  exchange?: string;
  currency?: string;
  timezone?: string;
}

export interface PriceCorrelation {
  ticker: string;
  analysis_period_days: number;
  correlation_insights: Array<{
    filing_date: string;
    filing_type: string;
    price_change_percent: number;
    volume_spike: boolean;
    correlation_strength: string;
  }>;
  summary: string;
}

class PriceDataService {
  private baseUrl: string;

  constructor(baseUrl: string = '/api/v1/price') {
    this.baseUrl = baseUrl;
  }

  async getCurrentPrice(ticker: string, token: string): Promise<CurrentPrice> {
    const response = await fetch(`${this.baseUrl}/current/${ticker}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch current price for ${ticker}`);
    }

    return response.json();
  }

  async getHistoricalPrices(
    ticker: string, 
    days: number = 30, 
    token: string
  ): Promise<{ ticker: string; days: number; data: HistoricalPrice[] }> {
    const response = await fetch(`${this.baseUrl}/historical/${ticker}?days=${days}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch historical prices for ${ticker}`);
    }

    return response.json();
  }

  async getCompanyOverview(ticker: string, token: string): Promise<CompanyOverview> {
    const response = await fetch(`${this.baseUrl}/overview/${ticker}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch company overview for ${ticker}`);
    }

    return response.json();
  }

  async getFilingPriceCorrelation(
    ticker: string, 
    days: number = 30, 
    token: string
  ): Promise<PriceCorrelation> {
    const response = await fetch(`${this.baseUrl}/correlation/${ticker}?days=${days}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch price correlation for ${ticker}`);
    }

    return response.json();
  }
}

export const priceDataService = new PriceDataService();
