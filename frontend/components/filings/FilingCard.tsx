// components/filings/FilingCard.tsx
import { FilingCardProps } from "@/types/ui.types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export const FilingCard = ({ filing, className }: FilingCardProps) => {
  const renderAnalysis = () => {
    if (!filing.analysis?.brief) return null;

    try {
      const analysisData = JSON.parse(filing.analysis.brief);
      
      if (!Array.isArray(analysisData) || analysisData.length === 0) {
        return null;
      }

      return (
        <div className="mt-4 p-3 bg-muted rounded-md">
          <p className="text-xs font-medium text-muted-foreground mb-2">AI Analysis:</p>
          <div className="space-y-2">
            {analysisData.map((item: any, index: number) => (
              <div key={index} className="text-sm">
                {item.change_type && (
                  <div className="flex items-start gap-2">
                    <Badge variant={
                      item.change_type === 'addition' ? 'default' :
                      item.change_type === 'removal' ? 'destructive' :
                      'secondary'
                    } className="text-xs">
                      {item.change_type}
                    </Badge>
                    <div className="flex-1">
                      <p className="font-medium">{item.summary}</p>
                      <p className="text-xs text-muted-foreground">
                        Impact: {item.impact} • Confidence: {item.confidence}
                      </p>
                    </div>
                  </div>
                )}
                {item.type && (
                  <div className="flex items-start gap-2">
                    <Badge variant="outline" className="text-xs">
                      {item.type}
                    </Badge>
                    <div className="flex-1">
                      <p className="font-medium">{item.label}</p>
                      {item.confidence && (
                        <p className="text-xs text-muted-foreground">
                          Confidence: {item.confidence}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          {filing.analysis.model && (
            <p className="text-xs text-muted-foreground mt-2">
              Model: {filing.analysis.model}
            </p>
          )}
        </div>
      );
    } catch (e) {
      // Fallback to raw display if JSON parsing fails
      return (
        <div className="mt-4 p-3 bg-muted rounded-md">
          <p className="text-xs font-medium text-muted-foreground mb-1">AI Analysis:</p>
          <p className="text-sm">{filing.analysis.brief}</p>
          {filing.analysis.model && (
            <p className="text-xs text-muted-foreground mt-1">
              Model: {filing.analysis.model}
            </p>
          )}
        </div>
      );
    }
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{filing.ticker || filing.cik} • {filing.formType}</span>
          <Badge variant={filing.status === 'parsed' ? 'default' : 'secondary'}>
            {filing.status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>{filing.companyName}</p>
          <p>Filed: {filing.filedAt.toLocaleDateString()}</p>
          <p>Accession: {filing.accessionNumber}</p>
          <div className="flex gap-4">
            <span>{filing.sectionCount} sections</span>
            <span>{filing.blobCount} files</span>
          </div>
        </div>
        {renderAnalysis()}
      </CardContent>
    </Card>
  )
}