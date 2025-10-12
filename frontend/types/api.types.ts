// types/api.types.ts
export interface APIFilingItem {
  id: number
  cik: string
  ticker: string | null
  company_name: string | null
  form_type: string
  filed_at: string
  accession_number: string
  status: string
  downloaded_at: string | null
  section_count: number
  blob_count: number
  analysis?: {
    brief: string | null
    model: string | null
    created_at: string | null
  } | null
}

export interface APIFilingList {
  filings: APIFilingItem[]
  total_count: number
  limit: number
  offset: number
}

export interface APIFilingDetail extends APIFilingItem {
  source_urls: string[]
  blobs: APIFilingBlob[]
  sections: APIFilingSection[]
}

export interface APIFilingBlob {
  id: number
  kind: string
  location: string
  checksum: string | null
  content_type: string | null
}

export interface APIFilingSection {
  id: number
  title: string
  ordinal: number
  content: string
  text_hash: string | null
}

export interface APIFilingAnalysis {
  sections: Array<{ title: string; summary: string; tokens: number }>
  entities: Array<{ type: string; text: string }>
  diff?: { summary: string; changed_sections: string[] }
}