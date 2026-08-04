import { AppShell } from "../components/layout/AppShell";
import { LoadingState } from "../components/states/AsyncState";
import { useResearchData } from "../hooks/useResearchData";
import type { ResearchViewState } from "../lib/contracts";
import { useHashRoute } from "../lib/navigation";
import { CommandCenter } from "../routes/CommandCenter";
import { Scanner } from "../routes/Scanner";

interface AppViewProps {
  state: ResearchViewState;
  onRetry: () => void;
}

export function AppView({ state, onRetry }: AppViewProps) {
  const route = useHashRoute();
  return (
    <AppShell state={state} onRetry={onRetry} route={route}>
      {state.phase === "loading" ? (
        <LoadingState />
      ) : route === "/scanner" ? (
        <Scanner state={state} onRetry={onRetry} />
      ) : (
        <CommandCenter state={state} onRetry={onRetry} />
      )}
    </AppShell>
  );
}

export function App() {
  const { reload, ...state } = useResearchData();
  return <AppView state={state} onRetry={reload} />;
}
