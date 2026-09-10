import { AlertTriangle, DatabaseZap, RotateCw } from "lucide-react";

export function LoadingState() {
  return (
    <section className="state-panel state-panel--loading" aria-busy="true" aria-label="Loading research data">
      <div className="state-panel__icon skeleton-pulse" aria-hidden="true" />
      <div>
        <p className="eyebrow">Connecting locally</p>
        <h2>Checking the research service</h2>
        <p>This normally takes less than two seconds.</p>
      </div>
    </section>
  );
}

export function EmptyState({ onRetry }: { onRetry: () => void }) {
  return (
    <section className="state-panel" aria-labelledby="empty-state-title">
      <DatabaseZap aria-hidden="true" />
      <div>
        <p className="eyebrow">Insufficient data</p>
        <h2 id="empty-state-title">No synchronized scanner evidence yet</h2>
        <p>Start the local research service, then retry this view. TRAIDR will stay non-directional until data passes freshness checks.</p>
        <button className="button button--secondary" type="button" onClick={onRetry}>
          <RotateCw size={16} aria-hidden="true" /> Retry connection
        </button>
      </div>
    </section>
  );
}

export function ConnectionNotice({ message }: { message: string }) {
  return (
    <div className="connection-notice" role="status">
      <AlertTriangle size={17} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
