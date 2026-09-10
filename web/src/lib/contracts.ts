export type ApiStatus = "OK" | "DEGRADED" | "NO_TRADE" | "INSUFFICIENT_DATA" | "ERROR";
export type FreshnessState = "FRESH" | "STALE" | "UNKNOWN";
export type DataSource = "local-api" | "preview";

export interface FreshnessInfo {
  state: FreshnessState;
  observed_at: string | null;
  age_seconds: number | null;
  maximum_age_seconds: number | null;
}

export interface ApiEnvelope<T> {
  status: ApiStatus;
  as_of: string;
  data: T;
  freshness: Record<string, FreshnessInfo>;
  reason_codes: string[];
  can_execute_trades: false;
  request_id: string;
}

export interface StatusData {
  database_exists: boolean;
  table_count: number;
  service_state: string;
  latest_heartbeat: string | null;
  provider_health: Array<Record<string, unknown>>;
  safety: Record<string, unknown>;
}

export interface ShadowEvidence {
  provider: string;
  observed_at: string | null;
  freshness: FreshnessState;
  setup_class: string;
  market_regime: string;
  crowding_score: number | null;
  squeeze_risk: number | null;
  catalyst_risk: number | null;
  data_quality_score: number;
  probability_state: string;
  scoring_weight: 0;
  fields: Record<string, number>;
  conflicts: string[];
  reason_codes: string[];
  can_execute_trades: false;
}

export interface ScannerFactor {
  factor: string;
  weight: number;
  raw_value: number | null;
  normalized_value: number | null;
  long_contribution: number;
  short_contribution: number;
  explanation: string;
  source: string | null;
  reason_codes: string[];
}

export interface ScannerRow {
  score_id: string;
  instrument_id: string;
  observed_at: string | null;
  recorded_at: string | null;
  status: string;
  direction: string;
  score: number | null;
  long_score: number | null;
  short_score: number | null;
  risk_score: number | null;
  conflicts: string[];
  reason_codes: string[];
  factors: ScannerFactor[];
  shadow: ShadowEvidence | null;
  can_execute_trades: false;
}

export interface ScannerData {
  rows: ScannerRow[];
  limit: number;
  total: number;
}

export interface OverviewData {
  scanner: ScannerRow[];
  alerts: Array<Record<string, unknown>>;
  paper_positions: Array<Record<string, unknown>>;
  service_heartbeats: Array<Record<string, unknown>>;
  shadow_evidence: ShadowEvidence[];
  news: Array<Record<string, unknown>>;
}

export interface ResearchSnapshot {
  status: ApiEnvelope<StatusData>;
  overview: ApiEnvelope<OverviewData>;
  scanner: ApiEnvelope<ScannerData>;
}

export interface ResearchViewState {
  phase: "loading" | "ready";
  source: DataSource;
  snapshot: ResearchSnapshot | null;
  connectionMessage: string | null;
  loadedAt: string | null;
}
