// services/api/filings.service.ts
import { APIFilingDetail, APIFilingList } from "@/types/api.types"
import { apiFetch, buildUrl } from "./fetcher"

export class FilingsService {
  private static readonly PATH = '/filings'

  static async list(accessToken?: string, params?: {
    limit?: number
    offset?: number
    cik?: string
    ticker?: string
    form_type?: string
    status?: string
    filed_after?: Date
    filed_before?: Date
  }): Promise<APIFilingList> {
    const searchParams = new URLSearchParams()

    if (params?.limit) searchParams.set("limit", params.limit.toString())
    if (params?.offset) searchParams.set("offset", params.offset.toString())
    if (params?.cik) searchParams.set("cik", params.cik)
    if (params?.ticker) searchParams.set("ticker", params.ticker)
    if (params?.form_type) searchParams.set("form_type", params.form_type)
    if (params?.status) searchParams.set("status", params.status)
    if (params?.filed_after) searchParams.set("filed_after", params.filed_after.toISOString())
    if (params?.filed_before) searchParams.set("filed_before", params.filed_before.toISOString())

    const url = buildUrl(`${this.PATH}/?${searchParams.toString()}`)
    const res = await apiFetch(url, {}, accessToken)
    if (!res.ok) throw new Error("Failed to fetch filings")
    return res.json()
  }

  static async get(id: number, accessToken?: string): Promise<APIFilingDetail> {
    const url = buildUrl(`${this.PATH}/${id}`)
    const res = await apiFetch(url, {}, accessToken)
    if (!res.ok) throw new Error("Failed to fetch filing")
    return res.json()
  }

  static async getSections(id: number, accessToken?: string): Promise<any[]> {
    const url = buildUrl(`${this.PATH}/${id}/sections`)
    const res = await apiFetch(url, {}, accessToken)
    if (!res.ok) throw new Error("Failed to fetch filing sections")
    return res.json()
  }

  static async getPublicRecent(limit: number = 3): Promise<APIFilingList> {
    try {
      const url = buildUrl(`/public/filings/recent?limit=${limit}`)
      const response = await apiFetch(url)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('Failed to fetch public recent filings:', error)
      // Return empty list as fallback
      return {
        filings: [],
        total_count: 0,
        limit,
        offset: 0,
      }
    }
  }
}