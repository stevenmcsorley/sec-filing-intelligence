// components/filings/FilingCard.tsx
import { FilingCardProps } from "@/types/ui.types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export const FilingCard = ({ filing, className }: FilingCardProps) => {
  // For Form 4 filings, try to extract issuer information from analysis
  const getDisplayInfo = () => {
    if (filing.formType === '4') {
      // For Form 4 (insider filings), the company name is the filer, not the issuer
      // Try to extract issuer info from analysis or show as insider filing
      let issuerName = null;
      let issuerTicker = filing.ticker;
      
      if (filing.analysis?.brief) {
        try {
          const analysisData = JSON.parse(filing.analysis.brief);
          // Look for issuer information in the analysis
          // This is a temporary fix - ideally this should come from backend
          const issuerEntity = analysisData.find((item: any) => 
            item.type === 'issuer' || item.label?.includes('Company') || item.label?.includes('Corp')
          );
          if (issuerEntity) {
            issuerName = issuerEntity.label;
          }
        } catch (e) {
          // Ignore parsing errors
        }
      }
      
      return {
        title: `${issuerTicker || filing.cik} • Insider Filing (Form 4)`,
        companyDisplay: issuerName || `${filing.companyName} (Insider)`,
        isInsiderFiling: true
      };
    }
    
    return {
      title: `${filing.ticker || filing.cik} • ${filing.formType}`,
      companyDisplay: filing.companyName,
      isInsiderFiling: false
    };
  };

  const displayInfo = getDisplayInfo();
  const renderAnalysis = () => {
    if (!filing.analysis?.brief) return null;

    try {
      const analysisData = JSON.parse(filing.analysis.brief);
      
      if (!Array.isArray(analysisData) || analysisData.length === 0) {
        return null;
      }

      // For Form 4 filings, add a header to clarify these are insider transactions
      const isForm4 = filing.formType === '4';
      
      return (
        <div className="mt-4 p-3 bg-muted rounded-md">
          <p className="text-xs font-medium text-muted-foreground mb-2">
            {isForm4 ? 'Insider Transaction Analysis:' : 'AI Analysis:'}
          </p>
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
                      {item.type === 'executive_change' && isForm4 ? 'Insider' : item.type}
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
          <p className="text-xs font-medium text-muted-foreground mb-1">
            {filing.formType === '4' ? 'Insider Transaction Analysis:' : 'AI Analysis:'}
          </p>
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
          <span>{displayInfo.title}</span>
          <Badge variant={filing.status === 'parsed' ? 'default' : 'secondary'}>
            {filing.status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>{displayInfo.companyDisplay}</p>
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