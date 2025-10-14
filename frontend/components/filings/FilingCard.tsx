// components/filings/FilingCard.tsx
import { FilingCardProps } from "@/types/ui.types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  CheckCircle, 
  Clock,
  DollarSign,
  Users,
  Building2,
  FileText,
  Calendar,
  Download,
  Eye,
  Star,
  Zap,
  Target,
  BarChart3,
  Activity
} from "lucide-react"

export const FilingCard = ({ filing, className }: FilingCardProps) => {
  // Enhanced display logic with professional categorization
  const getDisplayInfo = () => {
    const isForm4 = filing.formType === '4'
    const isForm8K = filing.formType === '8-K'
    const isForm10K = filing.formType === '10-K'
    const isForm10Q = filing.formType === '10-Q'
    const isForm144 = filing.formType === '144'
    const isSchedule13D = filing.formType === 'SCHEDULE 13D/A'
    const isForm3 = filing.formType === '3'
    
    // Clean company name (remove common prefixes/suffixes)
    const cleanCompanyName = (name: string | null) => {
      if (!name) return 'Unknown Company'
      return name
        .replace(/^(Company \d+|D - |HR - |FWP - )/, '')
        .replace(/\s+(INC|CORP|LLC|LTD|CO)$/i, '')
        .trim()
    }
    
    // Get display ticker - prefer ticker, fallback to CIK with better formatting
    const getDisplayTicker = () => {
      if (filing.ticker) {
        return filing.ticker
      }
      // Format CIK better - remove leading zeros and add prefix
      const cleanCik = filing.cik.replace(/^0+/, '') || filing.cik
      return `CIK:${cleanCik}`
    }
    
    let title = `${getDisplayTicker()}`
    let subtitle = cleanCompanyName(filing.companyName)
    let icon = <Building2 className="h-5 w-5" />
    let priority = "low"
    let category = "regulatory"
    let impact = "low"
    
    if (isForm4) {
      title = `${getDisplayTicker()} • Insider Trading`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <Users className="h-5 w-5" />
      priority = "high"
      category = "insider"
      impact = "high"
    } else if (isForm8K) {
      title = `${getDisplayTicker()} • Material Event`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <AlertTriangle className="h-5 w-5" />
      priority = "high"
      category = "material"
      impact = "high"
    } else if (isForm10K) {
      title = `${getDisplayTicker()} • Annual Report`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <BarChart3 className="h-5 w-5" />
      priority = "medium"
      category = "financial"
      impact = "medium"
    } else if (isForm10Q) {
      title = `${getDisplayTicker()} • Quarterly Report`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <Activity className="h-5 w-5" />
      priority = "medium"
      category = "financial"
      impact = "medium"
    } else if (isForm144) {
      title = `${getDisplayTicker()} • Rule 144`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <FileText className="h-5 w-5" />
      priority = "medium"
      category = "securities"
      impact = "medium"
    } else if (isSchedule13D) {
      title = `${getDisplayTicker()} • Beneficial Ownership`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <Target className="h-5 w-5" />
      priority = "high"
      category = "ownership"
      impact = "high"
    } else if (isForm3) {
      title = `${getDisplayTicker()} • Initial Ownership`
      subtitle = cleanCompanyName(filing.companyName)
      icon = <Star className="h-5 w-5" />
      priority = "medium"
      category = "insider"
      impact = "medium"
    }
    
    return { title, subtitle, icon, priority, category, impact }
  }

  const displayInfo = getDisplayInfo()
  
  // Professional analysis rendering with enhanced insights
  const renderAnalysis = () => {
    if (!filing.analysis?.brief) {
        return (
          <div className="mt-4 p-4 bg-muted border border-border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              <span className="text-sm font-semibold text-card-foreground">Analysis Pending</span>
            </div>
            <p className="text-sm text-muted-foreground">This filing is being processed by our AI analysis engine.</p>
          </div>
        )
    }

    try {
      const analysisData = JSON.parse(filing.analysis.brief)
      
      if (!Array.isArray(analysisData) || analysisData.length === 0) {
        return (
          <div className="mt-4 p-4 bg-muted border border-border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold text-card-foreground">Standard Filing</span>
            </div>
            <p className="text-sm text-muted-foreground">This appears to be a routine regulatory filing.</p>
          </div>
        )
      }

      // Enhanced grouping with more sophisticated categorization
      const groupedAnalysis: {
        transactions: any[]
        changes: any[]
        alerts: any[]
        insights: any[]
        other: any[]
      } = {
        transactions: [],
        changes: [],
        alerts: [],
        insights: [],
        other: []
      }

      analysisData.forEach((item: any) => {
        if (item.type === 'transaction' || item.change_type) {
          groupedAnalysis.transactions.push(item)
        } else if (item.type?.includes('change') || item.type?.includes('departure')) {
          groupedAnalysis.changes.push(item)
        } else if (item.impact === 'high' || item.confidence > 0.8) {
          groupedAnalysis.alerts.push(item)
        } else if (item.type?.includes('insight') || item.type?.includes('analysis')) {
          groupedAnalysis.insights.push(item)
        } else {
          groupedAnalysis.other.push(item)
        }
      })

      return (
        <div className="mt-4 space-y-3">
          {/* High Priority Alerts */}
          {groupedAnalysis.alerts.length > 0 && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
                <span className="text-sm font-semibold text-red-900 dark:text-red-100">High Impact Alert</span>
                <Badge variant="destructive" className="text-xs">Critical</Badge>
              </div>
              <div className="space-y-2">
                {groupedAnalysis.alerts.slice(0, 2).map((item: any, index: number) => (
                  <div key={index} className="text-sm text-red-800 dark:text-red-200 bg-red-100 dark:bg-red-900/30 p-2 rounded border-l-2 border-red-400">
                    <div className="font-medium">{item.summary || item.label}</div>
                    {item.confidence && (
                      <div className="text-xs text-red-600 dark:text-red-300 mt-1">
                        Confidence: {Math.round(item.confidence * 100)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Transactions (for Form 4) */}
          {groupedAnalysis.transactions.length > 0 && (
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <DollarSign className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                <span className="text-sm font-semibold text-blue-900 dark:text-blue-100">Transaction Details</span>
                <Badge variant="default" className="text-xs">{groupedAnalysis.transactions.length}</Badge>
              </div>
              <div className="space-y-2">
                {groupedAnalysis.transactions.slice(0, 2).map((item: any, index: number) => (
                  <div key={index} className="text-sm text-blue-800 dark:text-blue-200 bg-blue-100 dark:bg-blue-900/30 p-2 rounded">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={
                        item.change_type === 'addition' ? 'default' :
                        item.change_type === 'removal' ? 'destructive' :
                        'secondary'
                      } className="text-xs">
                        {item.change_type || item.type}
                      </Badge>
                      <span className="font-medium">{item.summary || item.label}</span>
                    </div>
                    {item.amount && (
                      <div className="text-xs text-blue-600 dark:text-blue-300 font-mono">
                        Amount: {item.amount}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Key Insights */}
          {groupedAnalysis.insights.length > 0 && (
            <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
                <span className="text-sm font-semibold text-green-900 dark:text-green-100">Key Insights</span>
              </div>
              <div className="space-y-2">
                {groupedAnalysis.insights.slice(0, 2).map((item: any, index: number) => (
                  <div key={index} className="text-sm text-green-800 dark:text-green-200 bg-green-100 dark:bg-green-900/30 p-2 rounded">
                    {item.summary || item.label}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Changes */}
          {groupedAnalysis.changes.length > 0 && (
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                <span className="text-sm font-semibold text-yellow-900 dark:text-yellow-100">Recent Changes</span>
              </div>
              <div className="space-y-2">
                {groupedAnalysis.changes.slice(0, 2).map((item: any, index: number) => (
                  <div key={index} className="text-sm text-yellow-800 dark:text-yellow-200 bg-yellow-100 dark:bg-yellow-900/30 p-2 rounded">
                    {item.summary || item.label}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Model attribution */}
          {filing.analysis.model && (
            <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border">
              <span>Powered by {filing.analysis.model}</span>
              <span className="flex items-center gap-1">
                <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                AI Analysis
              </span>
            </div>
          )}
        </div>
      )
    } catch (e) {
        // Fallback to simple display
        return (
          <div className="mt-4 p-4 bg-muted border border-border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold text-card-foreground">Analysis Summary</span>
            </div>
            <p className="text-sm text-muted-foreground">{filing.analysis.brief}</p>
            {filing.analysis.model && (
              <div className="flex items-center justify-between text-xs text-muted-foreground mt-2 pt-2 border-t border-border">
                <span>Powered by {filing.analysis.model}</span>
                <span className="flex items-center gap-1">
                  <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                  AI Analysis
                </span>
              </div>
            )}
          </div>
        )
    }
  }

  // Get status styling
  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'parsed': return 'default'
      case 'failed': return 'destructive'
      case 'pending': return 'secondary'
      default: return 'outline'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'parsed': return <CheckCircle className="h-3 w-3" />
      case 'failed': return <AlertTriangle className="h-3 w-3" />
      case 'pending': return <Clock className="h-3 w-3" />
      default: return <Clock className="h-3 w-3" />
    }
  }

  const getStatusDisplayText = (status: string) => {
    switch (status) {
      case 'parsed': return 'Processed'
      case 'failed': return 'Analysis Failed'
      case 'pending': return 'Processing'
      case 'downloaded': return 'Downloaded'
      default: return status.charAt(0).toUpperCase() + status.slice(1)
    }
  }

  // Get priority styling
  const getPriorityStyling = (priority: string) => {
    switch (priority) {
      case 'high': return 'border-l-4 border-l-destructive bg-destructive/5'
      case 'medium': return 'border-l-4 border-l-warning bg-warning/5'
      case 'low': return 'border-l-4 border-l-info bg-info/5'
      default: return 'border-l-4 border-l-muted-foreground bg-muted/20'
    }
  }

  // Get category badge styling
  const getCategoryBadge = (category: string) => {
    const variants = {
      insider: { variant: 'destructive' as const, label: 'Insider' },
      material: { variant: 'destructive' as const, label: 'Material' },
      financial: { variant: 'default' as const, label: 'Financial' },
      securities: { variant: 'secondary' as const, label: 'Securities' },
      ownership: { variant: 'destructive' as const, label: 'Ownership' },
      regulatory: { variant: 'outline' as const, label: 'Regulatory' }
    }
    return variants[category as keyof typeof variants] || variants.regulatory
  }

  return (
    <Card className={`${className} ${getPriorityStyling(displayInfo.priority)} hover:shadow-lg transition-all duration-200 group`}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-lg font-semibold">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-card shadow-sm group-hover:shadow-md transition-shadow">
              {displayInfo.icon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg">{displayInfo.title}</span>
                <Badge variant={getCategoryBadge(displayInfo.category).variant} className="text-xs">
                  {getCategoryBadge(displayInfo.category).label}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground font-medium">{displayInfo.subtitle}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant={getStatusVariant(filing.status)} className="text-xs">
              <div className="flex items-center gap-1">
                {getStatusIcon(filing.status)}
                {getStatusDisplayText(filing.status)}
              </div>
            </Badge>
            {displayInfo.impact === 'high' && (
              <Badge variant="destructive" className="text-xs animate-pulse">
                <Zap className="h-3 w-3 mr-1" />
                High Impact
              </Badge>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      
      <CardContent className="pt-0">
        {/* Filing metadata */}
        <div className="grid grid-cols-2 gap-4 mb-4 p-3 bg-card/50 rounded-lg">
          <div className="flex items-center gap-2 text-sm">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{filing.filedAt.toLocaleDateString()}</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span>{filing.sectionCount} sections</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Download className="h-4 w-4 text-muted-foreground" />
            <span>{filing.blobCount} files</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-xs font-mono text-muted-foreground">{filing.accessionNumber}</span>
          </div>
        </div>
        
        {renderAnalysis()}
        
        {/* Action buttons */}
        <div className="mt-4 pt-3 border-t flex gap-2">
          <Button variant="outline" size="sm" className="flex-1 text-xs">
            <Eye className="h-3 w-3 mr-1" />
            View Details
          </Button>
          <Button variant="ghost" size="sm" className="text-xs">
            <Download className="h-3 w-3" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}