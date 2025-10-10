const HomePage = () => (
  <section className="space-y-6">
    <header>
      <p className="uppercase tracking-widest text-xs text-slate-400">SEC Filing Intelligence</p>
      <h1 className="text-4xl font-semibold mt-2">Market-moving insights from real SEC filings</h1>
    </header>
    <p className="text-slate-300 leading-relaxed">
      This Next.js app provides the presentation layer for ingestion, analysis, and alerting services. The MVP
      prioritizes real data pipelines, Groq-powered summaries, and strict RBAC enforced via Keycloak + OPA.
    </p>
    <ul className="space-y-3 text-slate-300">
      <li>• Live filing ingestion from EDGAR with change detection.</li>
      <li>• AI signal scoring with impact, confidence, and governance categories.</li>
      <li>• Tiered alert delivery respecting subscription limits and delay windows.</li>
      <li>• Observability-first dashboards for ingestion lag, token usage, and queue depth.</li>
    </ul>
    <footer className="text-sm text-slate-500">
      Review the repo&apos;s <code>docs/</code> directory for contributor onboarding and the Trello ↔ GitHub workflow.
    </footer>
  </section>
);

export default HomePage;
