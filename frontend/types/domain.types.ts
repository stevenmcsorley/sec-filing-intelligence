export interface FilingList {
  filings: FilingSummary[]
  totalCount: number
  limit: number
  offset: number
}

export interface FilingSummary {
  id: number
  cik: string
  ticker: string | null
  companyName: string | null
  formType: string
  filedAt: Date
  accessionNumber: string
  status: string
  sectionCount: number
  blobCount: number
  analysis?: {
    brief: string | null
    model: string | null
    createdAt: string | null
  } | null
}

export interface FilingDetail extends FilingSummary {
  sourceUrls: string[]
  downloadedAt: Date | null
  blobs: FilingBlob[]
  sections: FilingSection[]
}

export interface FilingBlob {
  id: number
  kind: string
  location: string
  checksum: string | null
  contentType: string | null
}

export interface FilingSection {
  id: number
  title: string
  ordinal: number
  content: string
  textHash: string | null
}

export type ImpactLevel = "High" | "Medium" | "Low"

export interface Alert {
  id: string
  filingId: number
  ticker: string
  impact: ImpactLevel
  confidence: number
  createdAt: Date
}