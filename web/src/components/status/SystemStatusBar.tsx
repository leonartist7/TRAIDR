import { Database, RefreshCw, ShieldCheck, WifiOff } from "lucide-react";

import type { ResearchViewState } from "../../lib/contracts";
import { formatAge, formatUtc } from "../../lib/format";

interface Props {
  state: ResearchViewState;
  onRetry: () => void;
}

export function SystemStatusBar({ state, onRetry }: Props) {
  const statusEnvelope = state.snapshot?.status;
  const status = statusEnvelope?.status ?? "INSUFFICIENT_DATA";
  const databaseExists = statusEnvelope?.data.database_exists ?? false;
  const heartbeat = statusEnvelope?.data.latest_heartbeat ?? null;
  const isPreview = state.source === "preview";

  return (
    <header className="status-bar" aria-label="System status">
      <div className="status-bar__primary" aria-live="polite">
        <span className={`status-pill status-pill--${status.toLowerCase()}`}>
          {isPreview ? <WifiOff size={14} aria-hidden="true" /> : <ShieldCheck size={14} aria-hidden="true" />}
          {isPreview ? "PREVIEW / OFFLINE" : status.replaceAll("_", " ")}
        </span>
        <span className="research-lock"><ShieldCheck size={14} aria-hidden="true" /> Research only</span>
      </div>

      <dl className="status-bar__facts">
        <div>
          <dt><Database size={14} aria-hidden="true" /> Database</dt>
          <dd>{databaseExists ? "Connected" : "Unavailable"}</dd>
        </div>
        <div>
          <dt>Heartbeat</dt>
          <dd title={formatUtc(heartbeat)}>{formatAge(heartbeat)}</dd>
        </div>
        <div>
          <dt>As of</dt>
          <dd>{formatUtc(statusEnvelope?.as_of ?? null)}</dd>
        </div>
      </dl>

      <button className="icon-button" type="button" onClick={onRetry} aria-label="Retry local data connection">
        <RefreshCw size={17} aria-hidden="true" />
      </button>
    </header>
  );
}
