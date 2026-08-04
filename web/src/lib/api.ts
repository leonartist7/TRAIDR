import type {
  ApiEnvelope,
  OverviewData,
  ResearchSnapshot,
  ScannerData,
  StatusData,
} from "./contracts";

const API_ROOT = "/api/v1";

export class ResearchApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ResearchApiError";
  }
}

async function readEnvelope<T>(path: string, signal?: AbortSignal): Promise<ApiEnvelope<T>> {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "X-Request-ID": `web-${crypto.randomUUID()}`,
    },
    signal,
  });

  if (!response.ok) {
    throw new ResearchApiError(`Local API returned ${response.status}.`);
  }

  const payload = (await response.json()) as ApiEnvelope<T>;
  if (payload.can_execute_trades !== false) {
    throw new ResearchApiError("Unsafe API contract rejected.");
  }
  return payload;
}

export async function loadResearchSnapshot(signal?: AbortSignal): Promise<ResearchSnapshot> {
  const [status, overview, scanner] = await Promise.all([
    readEnvelope<StatusData>("/status", signal),
    readEnvelope<OverviewData>("/overview?limit=12", signal),
    readEnvelope<ScannerData>("/scanner?limit=24", signal),
  ]);
  return { status, overview, scanner };
}
