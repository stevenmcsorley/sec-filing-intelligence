# SEC Filings Explained - Analysis Rules & Patterns

This document defines the key SEC filing types and their analysis patterns to enable rule-based pre-processing before sending to Groq for AI analysis. This reduces API costs and improves accuracy.

## Core Filing Types & Analysis Rules

### Form 4 - Statement of Changes in Beneficial Ownership
**Purpose**: Reports insider trading (purchases/sales of company stock by officers, directors, and beneficial owners)

**Key Analysis Patterns**:
- **Transaction Type**: Purchase, Sale, Gift, Exercise of Options, etc.
- **Volume**: Number of shares and dollar amounts
- **Price**: Transaction price vs current market price
- **Insider Role**: CEO, CFO, Director, etc.
- **Timing**: Proximity to earnings announcements or other material events

**Rule-Based Flags**:
- Large transactions (>$1M or >10% of holdings)
- Multiple insiders trading same direction
- Transactions near earnings dates
- Unusual transaction types (gifts, trusts)

**Impact Scoring**:
- High: CEO/CFO large sales, multiple insiders selling
- Medium: Director transactions, option exercises
- Low: Small transactions, routine gifts

### Form 8-K - Current Report
**Purpose**: Reports material events that shareholders should know about

**Key Analysis Patterns**:
- **Item Categories**: 
  - Item 1.01: Entry into material agreements
  - Item 2.02: Results of operations (earnings)
  - Item 3.01: Notice of delisting
  - Item 4.01: Changes in registrant's certifying accountant
  - Item 5.01: Changes in control of registrant
  - Item 5.02: Departure/arrival of directors/officers
  - Item 5.03: Amendments to articles of incorporation
  - Item 5.07: Submission of matters to vote
  - Item 8.01: Other events

**Rule-Based Flags**:
- Executive changes (CEO/CFO departures)
- Earnings announcements
- M&A announcements
- Regulatory issues
- Accounting changes

**Impact Scoring**:
- High: CEO departure, M&A, earnings misses
- Medium: Director changes, contract announcements
- Low: Routine filings, minor amendments

### Form 10-K - Annual Report
**Purpose**: Comprehensive annual report including financial statements, business overview, risk factors

**Key Analysis Patterns**:
- **Financial Health**: Revenue trends, profitability, debt levels
- **Risk Factors**: New or changed risk disclosures
- **Business Model**: Changes in strategy or operations
- **Management Discussion**: Forward-looking statements
- **Auditor Changes**: New accounting firm

**Rule-Based Flags**:
- Revenue/earnings growth/decline trends
- New risk factors added
- Auditor changes
- Going concern warnings
- Material weaknesses in controls

**Impact Scoring**:
- High: Going concern warnings, auditor changes, major strategy shifts
- Medium: Revenue declines, new risk factors
- Low: Routine annual updates

### Form 10-Q - Quarterly Report
**Purpose**: Quarterly financial results and business updates

**Key Analysis Patterns**:
- **Quarterly Performance**: Revenue, earnings vs expectations
- **Guidance**: Forward-looking statements
- **Cash Flow**: Operating cash flow trends
- **Segment Performance**: Business unit results

**Rule-Based Flags**:
- Earnings beats/misses
- Guidance changes
- Cash flow deterioration
- Segment performance issues

**Impact Scoring**:
- High: Major earnings misses, guidance cuts
- Medium: Modest beats/misses, segment issues
- Low: In-line results

### Schedule 13D - Beneficial Ownership Report
**Purpose**: Reports acquisition of >5% beneficial ownership, often activist investors

**Key Analysis Patterns**:
- **Investor Type**: Activist, institutional, individual
- **Ownership Level**: Percentage owned
- **Intent**: Passive investment vs activist intent
- **Previous Holdings**: Changes in position

**Rule-Based Flags**:
- New activist positions
- Large ownership increases
- Intent to influence management
- Previous activist history

**Impact Scoring**:
- High: Known activist investors, hostile intent
- Medium: Large institutional positions
- Low: Passive investment statements

### Form 144 - Notice of Proposed Sale
**Purpose**: Notice of intent to sell restricted securities

**Key Analysis Patterns**:
- **Volume**: Number of shares to be sold
- **Timing**: When sale will occur
- **Seller**: Who is selling (insider vs affiliate)

**Rule-Based Flags**:
- Large volume sales
- Insider selling
- Timing near earnings

**Impact Scoring**:
- High: Large insider sales
- Medium: Moderate volume sales
- Low: Small affiliate sales

## Company Name & Ticker Resolution Rules

### Common Company Name Patterns
- **Corporation Suffixes**: Corp, Inc, LLC, Ltd, Co, Company
- **Abbreviations**: Intl, Sys, Tech, Mfg, Grp
- **Variations**: Common misspellings and alternative names

### Ticker Lookup Priority
1. **Primary Ticker**: Most commonly used ticker symbol
2. **Alternative Tickers**: Multiple classes of stock
3. **Historical Tickers**: Recently changed symbols
4. **CIK Fallback**: Use CIK when ticker unavailable

### Company Matching Rules
- **Exact Match**: Perfect company name match
- **Fuzzy Match**: Similar names with high confidence
- **Partial Match**: Contains key company identifiers
- **Manual Review**: Flag for human verification

## Pre-Analysis Rules to Reduce Groq Usage

### 1. Filing Classification
- **High Priority**: Form 4, 8-K, 13D (immediate analysis)
- **Medium Priority**: 10-Q, 144 (batch analysis)
- **Low Priority**: 10-K, routine filings (delayed analysis)

### 2. Content Filtering
- **Skip Analysis**: Very short filings, routine amendments
- **Quick Analysis**: Simple transactions, standard disclosures
- **Full Analysis**: Complex filings, material events

### 3. Pattern Recognition
- **Template Matching**: Common filing patterns
- **Keyword Detection**: Material event keywords
- **Numerical Analysis**: Transaction amounts, percentages

### 4. Confidence Scoring
- **High Confidence**: Clear patterns, standard language
- **Medium Confidence**: Some ambiguity, requires AI
- **Low Confidence**: Complex language, unusual patterns

## Implementation Strategy

### Phase 1: Rule-Based Pre-Processing
1. Implement filing type classification
2. Add company name normalization
3. Create pattern matching rules
4. Build confidence scoring

### Phase 2: Smart Groq Usage
1. Only send high-impact filings to Groq
2. Use smaller, focused prompts
3. Implement result caching
4. Add fallback analysis

### Phase 3: Continuous Improvement
1. Track analysis accuracy
2. Refine rules based on results
3. Add new patterns as discovered
4. Optimize for cost vs quality

## Metrics & Monitoring

### Cost Reduction Targets
- **Groq Usage**: Reduce by 60-70%
- **Analysis Speed**: Improve by 40-50%
- **Accuracy**: Maintain or improve current levels

### Quality Metrics
- **False Positives**: Minimize irrelevant alerts
- **False Negatives**: Catch all material events
- **Response Time**: Sub-minute for high-priority filings

### Business Impact
- **User Engagement**: More relevant, timely alerts
- **Subscription Value**: Clear differentiation by tier
- **Operational Efficiency**: Reduced manual review needs
