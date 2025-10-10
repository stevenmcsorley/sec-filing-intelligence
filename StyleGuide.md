SEC Filing Intelligence — UI Development Style Guide
🎯 Architecture Principles

Core Goals

Maintainable: Clear boundaries: UI ↔ services ↔ adapters ↔ domain types.

Testable: Unit + integration + E2E (Playwright) with Keycloak login flows.

Scalable: Handles very large filings (virtualized readers, chunked UIs), many alerts, and multi-tenant RBAC.

Regression-safe: Strong typing, storybook for critical components, realistic fixtures from real parsed data (never synthetic).

Non-Negotiables

No hardcoded credentials or mock/dummy data in the app or stories — fixtures must be redacted real payloads captured via dev tooling.

All access is policy-driven: UI respects server-enforced OPA decisions and Keycloak roles.

Feature/tier gating in UI is presentational only; enforcement happens server-side.

📁 Project Structure
src/
├── app/                       # Next.js routes (app router)
│   ├── filings/               # /filings, /filings/[id]
│   ├── alerts/                # /alerts stream & filters
│   ├── portfolios/            # watchlists, portfolios
│   ├── admin/                 # super-admin consoles (phase 1)
│   └── settings/              # user/org settings
├── components/                # Reusable UI components
│   ├── filings/               # Filing-specific components (readers, diffs)
│   ├── alerts/                # Alert cards, impact badges
│   ├── charts/                # Viz (price/impact timelines)
│   ├── forms/                 # Forms (watchlist rules)
│   ├── ui/                    # Generic UI library (cards, tables, modals)
│   └── layout/                # Shell, nav, auth guards
├── services/                  # API calls and external services
│   ├── api/                   # REST/GraphQL clients (fetch wrappers)
│   ├── auth/                  # Keycloak OIDC client helpers
│   └── adapters/              # API ↔ domain mappers
├── hooks/                     # Custom hooks (useFiling, useAlertsStream, ...)
├── domain/                    # Business logic helpers (pure)
├── types/                     # Shared TS types
│   ├── api.types.ts
│   ├── ui.types.ts
│   └── domain.types.ts
├── utils/                     # Pure utilities (formatters, token meters)
├── constants/                 # App constants (OPA actions, roles, tiers)
├── config/                    # Runtime config readers (env schema)
└── test/                      # Test utilities, Playwright, MSW (for contract playback)


Note: If you use MSW, back it with recorded real responses (PII-scrubbed) from dev/staging. Do not invent fields.

🧩 React + TypeScript Component Style

1) Component Declaration

Named exports with arrow functions; no React.FC; no default exports.

export const ImpactBadge = ({ impact, className = "" }: ImpactBadgeProps) => (
  <span className={["inline-flex rounded px-2 py-0.5 text-xs", className].filter(Boolean).join(" ")}>
    {impact}
  </span>
)


2) Props Types in *.types.ts

// components/alerts/ImpactBadge.types.ts
export type ImpactLevel = "High" | "Medium" | "Low"

export interface ImpactBadgeProps {
  impact: ImpactLevel
  className?: string
}


3) Defaults & Destructuring — use parameter defaults, not defaultProps.

4) Children & Composition — prefer slots/children over boolean props for “showDiff”, “showEntities”.

5) DOM Types — never any. Use specific React event types.

6) className Merging — always accept className?: string on presentational components.

7) Generics — e.g., virtualized list <T,> for alerts and sections.

8) forwardRef & memo — use for inputs/virtualized scrollers; set displayName.

9) Component Folder Layout

components/filings/FilingReader/
  FilingReader.tsx
  FilingReader.types.ts
  FilingReader.test.tsx
  FilingReader.stories.tsx
  index.ts

🔄 Services Layer Pattern

API Service Structure (Keycloak tokens, OPA decisions happen server-side)

// services/api/filings.service.ts
export class FilingsService {
  private static readonly BASE = "/api/filings"

  static async list(q: URLSearchParams): Promise<APIFilingList> {
    const res = await fetch(`${this.BASE}?${q.toString()}`, { credentials: "include" })
    if (!res.ok) throw new Error("Failed to fetch filings")
    return res.json()
  }

  static async get(id: string): Promise<APIFilingDetail> {
    const res = await fetch(`${this.BASE}/${id}`, { credentials: "include" })
    if (!res.ok) throw new Error("Failed to fetch filing")
    return res.json()
  }

  static async analysis(id: string): Promise<APIFilingAnalysis> {
    const res = await fetch(`${this.BASE}/${id}/analysis`, { credentials: "include" })
    if (!res.ok) throw new Error("Failed to fetch analysis")
    return res.json()
  }
}


Adapter Pattern (snake_case → camelCase, dates/arrays normalized)

// services/adapters/filing.adapter.ts
export class FilingAdapter {
  static listFromAPI(api: APIFilingList): FilingList {
    return {
      count: api.count,
      results: api.results.map(FilingAdapter.itemFromAPI),
    }
  }
  static itemFromAPI(a: APIFilingItem): FilingSummary {
    return {
      id: a.id,
      ticker: a.ticker,
      cik: a.cik,
      formType: a.form_type,
      filedAt: new Date(a.filed_at),
      impactScore: a.impact_score,
      confidence: a.confidence,
    }
  }
}


Auth Helpers

Use a tiny auth helper to read Keycloak tokens from cookies (Next.js Server Actions) — never hardcode secrets.

UI shows/hides buttons via role claims, but server enforces via OPA.

🧪 Testing Strategy

Test-IDs Convention (domain-aware)

Format: {feature}-{component}-{element}-{id?}

<div data-testid="filings-list">
  <article data-testid="filings-item-0001234567-24-000010">
    <button data-testid="filings-open-0001234567-24-000010">Open</button>
  </article>
</div>

<div data-testid="alert-card-TSLA-2025-10-10T12:30:00Z"></div>


Component Tests

Heavy ones: FilingReader, DiffViewer, AlertsStream, WatchlistForm.

Mock network with recorded real responses (MSW).

Accessibility checks (axe) for readers and tables.

E2E (Playwright)

Keycloak login flow (OIDC).

Super-admin visibility of admin console.

Tier gating: free user sees delayed alert banners; pro sees diff tabs.

📝 TypeScript Best Practices

Organize Types by Layer

// types/domain.types.ts
export interface FilingSummary {
  id: string
  ticker: string
  cik: string
  formType: string
  filedAt: Date
  impactScore?: number
  confidence?: number
}

export interface FilingAnalysis {
  sections: Array<{ title: string; summary: string; tokens: number }>
  entities: Array<{ type: string; text: string }>
  diff?: { summary: string; changedSections: string[] }
}

export type ImpactLevel = "High" | "Medium" | "Low"

export interface Alert {
  id: string
  filingId: string
  ticker: string
  impact: ImpactLevel
  confidence: number
  createdAt: Date
}

// types/api.types.ts
export interface APIFilingItem {
  id: string
  ticker: string
  cik: string
  form_type: string
  filed_at: string
  impact_score?: number
  confidence?: number
}

export interface APIFilingDetail extends APIFilingItem {
  source_urls: string[]
}

export interface APIFilingAnalysis {
  sections: Array<{ title: string; summary: string; tokens: number }>
  entities: Array<{ type: string; text: string }>
  diff?: { summary: string; changed_sections: string[] }
}

// types/ui.types.ts
export interface FilingReaderProps {
  filing: FilingSummary
  analysis?: FilingAnalysis
  canViewDiff: boolean
}


Generic APIResponse remains as in the original guide.

🎨 Component Library Standards (Domain Examples)

Naming

FilingCard, FilingReader, FilingDiffViewer

AlertCard, AlertImpactBadge, AlertsStream

WatchlistForm, TickerPicker, RuleBuilder

AdminQueuesPanel, AdminPolicyAuditTable

Composition

export const FilingDetail = ({ filing, analysis, canViewDiff }: FilingReaderProps) => (
  <Card>
    <CardHeader title={`${filing.ticker} • ${filing.formType}`} />
    <CardContent>
      <SectionSummaries sections={analysis?.sections ?? []} />
      {canViewDiff && analysis?.diff ? <DiffViewer diff={analysis.diff} /> : null}
    </CardContent>
  </Card>
)

🔧 Performance Patterns (Critical for Large Filings)

Virtualized lists/readers (e.g., react-virtualized / react-virtuoso) for section lists and alert streams.

Progressive disclosure: show section headers first, lazy-load content.

Code-splitting: dynamic import for DiffViewer, HeavyChart.

Streaming UI: show “Analyzing…” skeletons; render sections as they arrive.

Memoization: useMemo/useCallback for derived maps (sections by title), expensive diffs.

Abortable fetches when switching filings quickly.

🚫 Anti-Patterns to Avoid

Prop drilling auth/role flags — use an AuthContext that reads claims from server-set cookies and hydrates minimal client state.

API calls in components — use services/api/* + hooks/*.

Client-side authorization logic as enforcement — UI hints only, never trust the client.

⚙️ Professional Configuration

ESLint

Same rules as your baseline, plus:

"@next/next/no-img-element": "off" if you must use <img> for streamed previews.

"jsx-a11y/*" recommended.

TSConfig

Same strictness as baseline; add "paths" for @components/*, @services/*, @types/*.

Env/Config

Read all runtime config via a single validated module (config/env.ts) using zod.

No secrets in client bundles; server reads via env/secret mounts.

🔐 Auth, Roles & Tier Gating in UI

Keycloak:

Roles used in UI for visibility hints: super_admin, org_admin, analyst_pro, basic_free.

OPA:

Server decides; UI consumes booleans from API responses like:

can_view_diff: boolean

alert_delay_minutes: number

limits: { maxTickers: number }

Pattern: Prefer capability flags from backend over duplicating policy logic in the frontend.

📊 Domain-Specific UI Patterns

Filing Reader

Outline (section TOC) + sticky heading

Section virtualization + “jump to changes”

Token usage badges (educational; not a control)

Diff Viewer

Collapsible changed sections

Inline add/remove markers with summary at top

Alerts Stream

Live mode (SSE/WebSocket) with pause buffer

Impact & confidence badges; quick filter chips

Watchlist / Rule Builder

Ticker multi-select (search + paste CSV)

Rule chips: FormType, Category, MinConfidence, Impact≥

Preview: “Last 30 days matching alerts”

🧰 Example Hooks
// hooks/useAlertsStream.ts
export const useAlertsStream = (params: { watchlistId?: string }) => {
  // SSE/WebSocket connection, returns alerts[], status, pause/resume
}

// hooks/useFiling.ts
export const useFiling = (id: string) => {
  // fetch filing + analysis; abort/switch intelligently
}

📋 Professional Code Review Checklist (Domain-aware)

Component Structure

Named arrow exports, no React.FC, props with defaults

Presentational components accept className

No API calls directly in components

TypeScript Quality

Domain types used (FilingSummary, FilingAnalysis, Alert)

Adapters translate API <-> domain (no leaky snake_case)

Specific event types; proper generics for lists

Accessibility & UX

Keyboard nav in readers/diffs

Live region for new alerts

Focus management on route changes

Architecture

All data flows via services; adapters present

Auth hints are UI only; server enforces

Virtualization for long lists/sections

Skeletons & streaming for long operations

Security

No secrets in code; no mock data

UI renders capability flags from API; no client-side enforcement

Error states never leak tokens or raw stack traces

✅ Ready-To-Build Defaults

Next.js (app router), Tailwind, shadcn/ui, lucide-react

Radix primitives for accessible dialogs/menus

Playwright for E2E (Keycloak login helpers)

Storybook for critical components using redacted real fixtures

react-virtuoso for lists; dynamic imports for heavy views