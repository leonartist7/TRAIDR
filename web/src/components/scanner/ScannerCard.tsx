import { AlertTriangle, ChevronRight, Clock3, Gauge, ShieldAlert } from "lucide-react";

import type { ScannerRow } from "../../lib/contracts";
import { compactScore, formatAge, humanizeReason, instrumentLabel } from "../../lib/format";

export function ScannerCard({ row, compact = false }: { row: ScannerRow; compact?: boolean }) {
  const directional = row.status === "OK" && (row.direction === "LONG" || row.direction === "SHORT");
  const displayDirection = directional ? row.direction : "NO TRADE";
  const topFactors = [...row.factors]
    .sort((a, b) => Math.abs(b.long_contribution) - Math.abs(a.long_contribution))
    .slice(0, compact ? 2 : 3);

  return (
    <article className={`scanner-card scanner-card--${directional ? row.direction.toLowerCase() : "blocked"}`}>
      <div className="scanner-card__header">
        <div>
          <p className="eyebrow">{row.status.replaceAll("_", " ")}</p>
          <h3>{instrumentLabel(row.instrument_id)}</h3>
        </div>
        <span className="direction-badge"><ShieldAlert size={14} aria-hidden="true" /> {displayDirection}</span>
      </div>

      <div className="score-strip">
        <div><span>Research score</span><strong>{compactScore(row.score)}</strong></div>
        <div><span>Risk score</span><strong>{compactScore(row.risk_score)}</strong></div>
        <div><span>Evidence</span><strong>{row.factors.filter((factor) => factor.raw_value !== null).length}/10</strong></div>
      </div>

      {row.shadow && (
        <section className="shadow-intelligence" aria-label="Zero-weight shadow intelligence">
          <div className="shadow-intelligence__heading">
            <span>Derived · shadow</span>
            <strong>0% score weight · {row.shadow.probability_state}</strong>
          </div>
          <div className="shadow-intelligence__grid">
            <div><span>Regime</span><strong>{humanizeReason(row.shadow.market_regime)}</strong></div>
            <div><span>Setup</span><strong>{humanizeReason(row.shadow.setup_class)}</strong></div>
            <div><span>Crowding</span><strong>{compactScore(row.shadow.crowding_score)}</strong></div>
            <div><span>Data quality</span><strong>{compactScore(row.shadow.data_quality_score)}</strong></div>
          </div>
          {row.shadow.conflicts.length > 0 && (
            <p className="conflict-note"><AlertTriangle size={15} aria-hidden="true" /> Shadow source conflict · no trade</p>
          )}
        </section>
      )}

      <div className="factor-list" aria-label="Strongest contributing factors">
        {topFactors.map((factor) => (
          <div className="factor-row" key={factor.factor}>
            <span>{humanizeReason(factor.factor)}</span>
            <strong>{factor.raw_value === null ? "Waiting" : factor.raw_value.toFixed(2)}</strong>
          </div>
        ))}
      </div>

      {row.conflicts.length > 0 && (
        <p className="conflict-note"><AlertTriangle size={15} aria-hidden="true" /> {row.conflicts.length} source conflict{row.conflicts.length === 1 ? "" : "s"}</p>
      )}

      <footer className="scanner-card__footer">
        <span><Clock3 size={14} aria-hidden="true" /> {formatAge(row.observed_at)}</span>
        <a href="#/scanner" aria-label={`Review ${instrumentLabel(row.instrument_id)} scanner evidence`}>
          Review evidence <ChevronRight size={15} aria-hidden="true" />
        </a>
      </footer>

      {!compact && (
        <details className="factor-details">
          <summary><Gauge size={16} aria-hidden="true" /> Exact factor breakdown</summary>
          <div className="factor-table" role="table" aria-label={`${instrumentLabel(row.instrument_id)} factors`}>
            {row.factors.map((factor) => (
              <div className="factor-table__row" role="row" key={factor.factor}>
                <span role="cell">{humanizeReason(factor.factor)}</span>
                <span role="cell">Raw: {factor.raw_value ?? "missing"}</span>
                <span role="cell">Weight: {factor.weight}</span>
                <span role="cell">Impact: {factor.long_contribution.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </article>
  );
}
