// services/adapters/filing.adapter.ts
import { APIFilingDetail, APIFilingItem, APIFilingList } from "@/types/api.types"
import { FilingDetail, FilingSummary, FilingList } from "@/types/domain.types"

export class FilingAdapter {
  static listFromAPI(api: APIFilingList): FilingList {
    return {
      filings: api.filings.map(FilingAdapter.summaryFromAPI),
      totalCount: api.total_count,
      limit: api.limit,
      offset: api.offset,
    }
  }

  static summaryFromAPI(api: APIFilingItem): FilingSummary {
    return {
      id: api.id,
      cik: api.cik,
      ticker: api.ticker,
      companyName: api.company_name,
      formType: api.form_type,
      filedAt: new Date(api.filed_at),
      accessionNumber: api.accession_number,
      status: api.status,
      sectionCount: api.section_count,
      blobCount: api.blob_count,
      analysis: api.analysis ? {
        brief: api.analysis.brief,
        model: api.analysis.model,
        createdAt: api.analysis.created_at,
      } : null,
    }
  }

  static detailFromAPI(api: APIFilingDetail): FilingDetail {
    return {
      ...FilingAdapter.summaryFromAPI(api),
      sourceUrls: api.source_urls,
      downloadedAt: api.downloaded_at ? new Date(api.downloaded_at) : null,
      blobs: api.blobs.map(blob => ({
        id: blob.id,
        kind: blob.kind,
        location: blob.location,
        checksum: blob.checksum,
        contentType: blob.content_type,
      })),
      sections: api.sections.map(section => ({
        id: section.id,
        title: section.title,
        ordinal: section.ordinal,
        content: section.content,
        textHash: section.text_hash,
      })),
    }
  }
}