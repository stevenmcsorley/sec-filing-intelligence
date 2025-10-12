// components/filings/CompanyCard.tsx
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChevronDown, ChevronUp, TrendingUp, Activity } from "lucide-react"
import { FilingCard } from "./FilingCard"
import { FilingSummary } from "@/types/domain.types"

interface CompanyCardProps {
  companyName: string
  cik: string
  ticker?: string
  filings: FilingSummary[]
  className?: string
}

export const CompanyCard = ({ companyName, cik, ticker, filings, className }: CompanyCardProps) => {
  const [expanded, setExpanded] = useState(false)

  // Sort filings by date (newest first)
  const sortedFilings = [...filings].sort((a, b) => b.filedAt.getTime() - a.filedAt.getTime())
  const latestFiling = sortedFilings[0]

  // Calculate activity metrics
  const recentFilings = sortedFilings.filter(f => {
    const daysAgo = (Date.now() - f.filedAt.getTime()) / (1000 * 60 * 60 * 24)
    return daysAgo <= 30 // Last 30 days
  })

  const getActivityLevel = () => {
    if (recentFilings.length >= 10) return { level: 'high', color: 'text-red-500', icon: TrendingUp }
    if (recentFilings.length >= 5) return { level: 'medium', color: 'text-yellow-500', icon: Activity }
    return { level: 'low', color: 'text-green-500', icon: Activity }
  }

  const activity = getActivityLevel()
  const ActivityIcon = activity.icon

  const renderLatestFilingAnalysis = () => {
    if (!latestFiling?.analysis?.brief) return null

    try {
      const analysisData = JSON.parse(latestFiling.analysis.brief)

      if (!Array.isArray(analysisData) || analysisData.length === 0) {
        return (
          <div className="mt-3 p-2 bg-muted/50 rounded text-xs">
            {latestFiling.analysis.brief}
          </div>
        )
      }

      // Show first 2-3 analysis items as preview
      const previewItems = analysisData.slice(0, 2)

      return (
        <div className="mt-3 space-y-1">
          {previewItems.map((item: any, index: number) => (
            <div key={index} className="flex items-start gap-2 text-xs">
              <Badge variant="outline" className="text-xs px-1 py-0">
                {item.change_type || item.type || 'update'}
              </Badge>
              <span className="flex-1 truncate">
                {item.summary || item.label || JSON.stringify(item)}
              </span>
            </div>
          ))}
          {analysisData.length > 2 && (
            <p className="text-xs text-muted-foreground">+{analysisData.length - 2} more insights</p>
          )}
        </div>
      )
    } catch (e) {
      return (
        <div className="mt-3 p-2 bg-muted/50 rounded text-xs">
          {latestFiling.analysis.brief.substring(0, 100)}...
        </div>
      )
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold">{companyName}</span>
            {ticker && (
              <Badge variant="secondary" className="text-xs">
                {ticker}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-1 ${activity.color}`}>
              <ActivityIcon className="h-4 w-4" />
              <span className="text-xs capitalize">{activity.level}</span>
            </div>
            <Badge variant="outline" className="text-xs">
              {filings.length} filing{filings.length !== 1 ? 's' : ''}
            </Badge>
          </div>
        </CardTitle>
        <div className="text-sm text-muted-foreground">
          CIK: {cik} • {recentFilings.length} in last 30 days
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Latest Filing Preview */}
        {latestFiling && (
          <div className="border-l-2 border-primary/20 pl-3 py-2 bg-muted/30 rounded-r">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium">
                Latest: {latestFiling.formType}
              </span>
              <Badge variant={latestFiling.status === 'parsed' ? 'default' : 'secondary'} className="text-xs">
                {latestFiling.status}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mb-2">
              Filed {latestFiling.filedAt.toLocaleDateString()} • {latestFiling.accessionNumber}
            </p>
            {renderLatestFilingAnalysis()}
          </div>
        )}

        {/* Expand/Collapse Button */}
        <div className="mt-4 flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="text-xs"
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3 w-3 mr-1" />
                Hide filings
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3 mr-1" />
                Show all filings ({filings.length})
              </>
            )}
          </Button>
        </div>

        {/* Expanded Filing List */}
        {expanded && (
          <div className="mt-4 space-y-3">
            {sortedFilings.map((filing) => (
              <FilingCard key={filing.id} filing={filing} className="border-l-4 border-l-primary/10" />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}