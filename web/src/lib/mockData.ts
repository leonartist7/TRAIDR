import type {
  ApiEnvelope,
  OverviewData,
  ResearchSnapshot,
  ScannerData,
  ScannerFactor,
  ScannerRow,
  StatusData,
} from "./contracts";

const now = new Date().toISOString();

const unavailableFactors: ScannerFactor[] = [
  ["price_structure", 20],
  ["volume", 10],
  ["order_book_imbalance", 10],
  ["recent_trades", 10],
  ["funding", 10],
  ["oi_change", 10],
  ["liquidation_pressure", 10],
  ["btc_eth_correlation", 5],
  ["news_catalyst", 5],
  ["risk_reward", 10],
].map(([factor, weight]) => ({
  factor: String(factor),
  weight: Number(weight),
  raw_value: null,
  normalized_value: null,
  long_contribution: 0,
  short_contribution: 0,
  explanation: "Waiting for synchronized local evidence.",
  source: null,
  reason_codes: ["PREVIEW_EVIDENCE_UNAVAILABLE"],
}));

const previewRows: ScannerRow[] = ["bitunix:BTCUSDT", "bitunix:HYPEUSDT"].map(
  (instrumentId, index) => ({
    score_id: `preview:${instrumentId}:${index}`,
    instrument_id: instrumentId,
    observed_at: null,
    recorded_at: now,
    status: "INSUFFICIENT_DATA",
    direction: "NO_TRADE",
    score: null,
    long_score: null,
    short_score: null,
    risk_score: null,
    conflicts: [],
    reason_codes: ["LOCAL_API_UNAVAILABLE", "PREVIEW_ONLY"],
    factors: unavailableFactors,
    shadow: null,
    can_execute_trades: false,
  }),
);

function envelope<T>(data: T): ApiEnvelope<T> {
  return {
    status: "INSUFFICIENT_DATA",
    as_of: now,
    data,
    freshness: {
      data: {
        state: "UNKNOWN",
        observed_at: null,
        age_seconds: null,
        maximum_age_seconds: 300,
      },
    },
    reason_codes: ["LOCAL_API_UNAVAILABLE", "PREVIEW_ONLY"],
    can_execute_trades: false,
    request_id: "preview-local",
  };
}

export const previewSnapshot: ResearchSnapshot = {
  status: envelope<StatusData>({
    database_exists: false,
    table_count: 0,
    service_state: "OFFLINE",
    latest_heartbeat: null,
    provider_health: [],
    safety: {
      runtime_mode: "research_only",
      local_only: true,
      live_trading_implemented: false,
      withdrawals_implemented: false,
      default_action: "HOLD",
    },
  }),
  overview: envelope<OverviewData>({
    scanner: previewRows,
    alerts: [],
    paper_positions: [],
    service_heartbeats: [],
    shadow_evidence: [],
    news: [],
  }),
  scanner: envelope<ScannerData>({
    rows: previewRows,
    limit: 24,
    total: previewRows.length,
  }),
};
