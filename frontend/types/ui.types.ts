// types/ui.types.ts
import { FilingDetail, FilingSummary } from "./domain.types"

export interface FilingCardProps {
  filing: FilingSummary
  className?: string
}

export interface FilingReaderProps {
  filing: FilingDetail
  canViewDiff: boolean
  className?: string
}