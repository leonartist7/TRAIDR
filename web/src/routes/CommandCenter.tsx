import { Activity, ArrowRight, CheckCircle2, CircleAlert, Database, Radar, ShieldCheck, WalletCards } from "lucide-react";

import { ScannerCard } from "../components/scanner/ScannerCard";
import { ConnectionNotice, EmptyState } from "../components/states/AsyncState";
import type { ResearchViewState } from "../lib/contracts";

interface Props {
  state: ResearchViewState;
  onRetry: () => void;
}

export function CommandCenter({ state, onRetry }: Props) {
  const snapshot = state.snapshot;
  if (!snapshot) return <EmptyState onRetry={onRetry} />;

  const scannerRows = snapshot.overview.data.scanner.slice(0, 3);
  const status = snapshot.status.status;
  const isReady = status === "OK" && state.source === "local-api";
  const nextAction = isReady
    ? "Review the highest-quality evidence before forming a thesis."
    : "Start the local research service, then retry the connection.";
  const providers = snapshot.status.data.provider_health;
  const news = snapshot.overview.data.news.slice(0, 4);

  return (
    <div className="page-stack">
      {state.connectionMessage && <ConnectionNotice message={state.connectionMessage} />}

      <section className="page-hero" aria-labelledby="command-center-title">
        <div>
          <p className="eyebrow">Command center · Step 1</p>
          <h1 id="command-center-title">See risk first. Decide calmly.</h1>
          <p className="page-hero__lede">One clear research view for market evidence, safety vetoes, and paper-state context.</p>
        </div>
        <div className="session-chip"><span /> Local session</div>
      </section>

      <section className="next-action" aria-labelledby="next-action-title">
        <div className="next-action__number">01</div>
        <div>
          <p className="eyebrow">Your next safe action</p>
          <h2 id="next-action-title">{nextAction}</h2>
          <p>{isReady ? "Directional treatment appears only when evidence is fresh, complete, and conflict-free." : "Preview remains non-directional and cannot be mistaken for live evidence."}</p>
        </div>
        <button className="button button--primary" type="button" onClick={onRetry}>
          Check local data <ArrowRight size={16} aria-hidden="true" />
        </button>
      </section>

      <section aria-labelledby="risk-summary-title">
        <div className="section-heading">
          <div><p className="eyebrow">Risk-first summary</p><h2 id="risk-summary-title">What matters now</h2></div>
          <span className={`status-copy status-copy--${status.toLowerCase()}`}>{status.replaceAll("_", " ")}</span>
        </div>
        <div className="metric-grid">
          <article className="metric-card metric-card--accent">
            <Database aria-hidden="true" />
            <span>Local database</span>
            <strong>{snapshot.status.data.database_exists ? "Connected" : "Not ready"}</strong>
            <small>{snapshot.status.data.table_count} verified tables visible</small>
          </article>
          <article className="metric-card">
            <Radar aria-hidden="true" />
            <span>Scanner coverage</span>
            <strong>{snapshot.scanner.data.total} instruments</strong>
            <small>{scannerRows.filter((row) => row.status === "OK").length} currently pass data gates</small>
          </article>
          <article className="metric-card">
            <WalletCards aria-hidden="true" />
            <span>Paper positions</span>
            <strong>{snapshot.overview.data.paper_positions.length}</strong>
            <small>Simulation only · no exchange actions</small>
          </article>
          <article className="metric-card">
            <ShieldCheck aria-hidden="true" />
            <span>Execution authority</span>
            <strong>Disabled</strong>
            <small>Read-only research boundary enforced</small>
          </article>
        </div>
      </section>

      <section aria-labelledby="research-queue-title">
        <div className="section-heading">
          <div><p className="eyebrow">Research queue</p><h2 id="research-queue-title">Review these next</h2></div>
          <a className="text-link" href="#/scanner">Open scanner <ArrowRight size={15} aria-hidden="true" /></a>
        </div>
        {scannerRows.length > 0 ? (
          <div className="scanner-grid">
            {scannerRows.map((row) => <ScannerCard row={row} compact key={row.score_id} />)}
          </div>
        ) : (
          <EmptyState onRetry={onRetry} />
        )}
      </section>

      <section aria-labelledby="provider-health-title">
        <div className="section-heading">
          <div><p className="eyebrow">Observed facts · connection health</p><h2 id="provider-health-title">Provider readiness</h2></div>
          <span className="status-copy">{providers.length} guarded sources</span>
        </div>
        <div className="provider-grid">
          {providers.length === 0 && (
            <p className="data-unavailable">Provider metadata appears when the local API is connected.</p>
          )}
          {providers.slice(0, 6).map((provider) => (
            <article className="provider-card" key={String(provider.provider)}>
              <div><Activity size={16} aria-hidden="true" /><strong>{String(provider.provider)}</strong></div>
              <span>{String(provider.state ?? "DATA_NOT_AVAILABLE").replaceAll("_", " ")}</span>
              <small>{String(provider.role ?? "Read-only research context")}</small>
              <p>{String(provider.quota_model ?? "Unknown quota")} · {String(provider.cost_tier ?? "unknown cost")}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="intelligence-split" aria-label="Derivatives and catalyst intelligence">
        <article className="intelligence-panel">
          <p className="eyebrow">Derived feature · zero weight</p>
          <h2>Derivatives regime</h2>
          {snapshot.overview.data.shadow_evidence.length > 0 ? (
            snapshot.overview.data.shadow_evidence.slice(0, 3).map((item) => (
              <div className="timeline-row" key={`${item.provider}-${item.observed_at}`}>
                <span>{item.market_regime.replaceAll("_", " ")}</span>
                <strong>{item.setup_class.replaceAll("_", " ")}</strong>
                <small>{item.data_quality_score.toFixed(0)}% quality · {item.freshness}</small>
              </div>
            ))
          ) : <p className="data-unavailable">Data not available. Shadow scoring remains disabled.</p>}
        </article>
        <article className="intelligence-panel">
          <p className="eyebrow">Observed facts · never directional alone</p>
          <h2>News & catalysts</h2>
          {news.length > 0 ? news.map((item) => (
            <div className="timeline-row" key={String(item.evidence_id)}>
              <span>{String(item.source ?? "Unknown source")}</span>
              <strong>{String(item.headline ?? "Headline unavailable")}</strong>
              <small>{String(item.mapping_state ?? "UNMAPPED").replaceAll("_", " ")}</small>
            </div>
          )) : <p className="data-unavailable">Data not available. No catalyst value is inferred.</p>}
        </article>
      </section>

      <section className="guidance-panel" aria-labelledby="guidance-title">
        <div>
          <p className="eyebrow">Three-step workflow</p>
          <h2 id="guidance-title">How to use this screen</h2>
        </div>
        <ol>
          <li><CircleAlert aria-hidden="true" /><span><strong>Check status.</strong> Stale or missing data means stop.</span></li>
          <li><Radar aria-hidden="true" /><span><strong>Review factors.</strong> Open the scanner and inspect all evidence.</span></li>
          <li><CheckCircle2 aria-hidden="true" /><span><strong>Record a thesis.</strong> Any position remains paper-only.</span></li>
        </ol>
      </section>
    </div>
  );
}
