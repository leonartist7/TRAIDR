import { Filter, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { ScannerCard } from "../components/scanner/ScannerCard";
import { EmptyState } from "../components/states/AsyncState";
import type { ResearchViewState } from "../lib/contracts";

const filters = ["ALL", "OK", "NO_TRADE", "INSUFFICIENT_DATA", "DEGRADED"] as const;
type FilterValue = (typeof filters)[number];

export function Scanner({ state, onRetry }: { state: ResearchViewState; onRetry: () => void }) {
  const [filter, setFilter] = useState<FilterValue>("ALL");
  const [query, setQuery] = useState("");
  const visibleRows = useMemo(() => {
    const rows = state.snapshot?.scanner.data.rows ?? [];
    return rows.filter((row) => {
      const matchesFilter = filter === "ALL" || row.status === filter;
      const matchesQuery = row.instrument_id.toLowerCase().includes(query.trim().toLowerCase());
      return matchesFilter && matchesQuery;
    });
  }, [filter, query, state.snapshot]);

  return (
    <div className="page-stack">
      <section className="page-hero" aria-labelledby="scanner-title">
        <div>
          <p className="eyebrow">Live scanner · Step 2</p>
          <h1 id="scanner-title">Evidence before direction.</h1>
          <p className="page-hero__lede">Every score exposes its raw inputs, source, weight, contribution, timestamp, and veto reason.</p>
        </div>
        <div className="scanner-count" aria-live="polite"><strong>{visibleRows.length}</strong><span>shown</span></div>
      </section>

      <section className="filter-panel" aria-label="Scanner filters">
        <label className="search-field">
          <Search size={17} aria-hidden="true" />
          <span className="sr-only">Search instruments</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search BTCUSDT…" />
        </label>
        <div className="filter-buttons" role="group" aria-label="Filter by evidence status">
          <Filter size={16} aria-hidden="true" />
          {filters.map((value) => (
            <button
              type="button"
              key={value}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {value.replaceAll("_", " ")}
            </button>
          ))}
        </div>
      </section>

      {visibleRows.length > 0 ? (
        <section className="scanner-list" aria-label="Scanner results">
          {visibleRows.map((row) => <ScannerCard row={row} key={row.score_id} />)}
        </section>
      ) : (
        <EmptyState onRetry={onRetry} />
      )}
    </div>
  );
}
