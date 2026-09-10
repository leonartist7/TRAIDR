import { useCallback, useEffect, useState } from "react";

import { loadResearchSnapshot } from "../lib/api";
import type { ResearchViewState } from "../lib/contracts";
import { previewSnapshot } from "../lib/mockData";

const initialState: ResearchViewState = {
  phase: "loading",
  source: "local-api",
  snapshot: null,
  connectionMessage: null,
  loadedAt: null,
};

export const RESEARCH_POLL_INTERVAL_MS = 15_000;

export function useResearchData(): ResearchViewState & { reload: () => void } {
  const [state, setState] = useState<ResearchViewState>(initialState);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => {
    setReloadKey((value) => value + 1);
    setState((current) => ({ ...current, phase: "loading" }));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const previewOnly = import.meta.env.VITE_TRAIDR_DATA_MODE === "preview";
    let pollTimer: number | null = null;
    let hasLiveSnapshot = false;

    async function load(): Promise<void> {
      if (previewOnly) {
        setState({
          phase: "ready",
          source: "preview",
          snapshot: previewSnapshot,
          connectionMessage: "Preview mode is enabled. No local research data is being shown.",
          loadedAt: new Date().toISOString(),
        });
        return;
      }

      try {
        const snapshot = await loadResearchSnapshot(controller.signal);
        hasLiveSnapshot = true;
        setState({
          phase: "ready",
          source: "local-api",
          snapshot,
          connectionMessage: null,
          loadedAt: new Date().toISOString(),
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        const message = error instanceof Error
          ? `Local API unavailable: ${error.message}`
          : "Local API unavailable. Preview state is active.";
        setState((current) => hasLiveSnapshot && current.snapshot
          ? { ...current, phase: "ready", connectionMessage: message }
          : {
              phase: "ready",
              source: "preview",
              snapshot: previewSnapshot,
              connectionMessage: message,
              loadedAt: new Date().toISOString(),
            });
      }
    }

    void load();
    if (!previewOnly) {
      pollTimer = window.setInterval(() => {
        if (!document.hidden) void load();
      }, RESEARCH_POLL_INTERVAL_MS);
    }
    return () => {
      controller.abort();
      if (pollTimer !== null) window.clearInterval(pollTimer);
    };
  }, [reloadKey]);

  return { ...state, reload };
}
