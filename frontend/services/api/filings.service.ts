// services/api/filings.service.ts
import { APIFilingDetail, APIFilingList } from "@/types/api.types"

export class FilingsService {
  private static readonly BASE = "http://localhost:8000/filings/"

  static async list(params?: {
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

    const res = await fetch(`${this.BASE}?${searchParams.toString()}`)
    if (!res.ok) throw new Error("Failed to fetch filings")
    return res.json()
  }

  static async get(id: number): Promise<APIFilingDetail> {
    const res = await fetch(`${this.BASE}/${id}`)
    if (!res.ok) throw new Error("Failed to fetch filing")
    return res.json()
  }

  static async getSections(id: number): Promise<any[]> {
    const res = await fetch(`${this.BASE}/${id}/sections`)
    if (!res.ok) throw new Error("Failed to fetch filing sections")
    return res.json()
  }

  static async getContent(id: number, kind: "raw" | "text" | "sections" = "text"): Promise<any> {
    const res = await fetch(`${this.BASE}/${id}/content?kind=${kind}`)
    if (!res.ok) throw new Error("Failed to fetch filing content")
    return res.json()
  }
}