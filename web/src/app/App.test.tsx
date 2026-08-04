import axe from "axe-core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { previewSnapshot } from "../lib/mockData";
import type { ResearchViewState } from "../lib/contracts";
import { AppView } from "./App";

const previewState: ResearchViewState = {
  phase: "ready",
  source: "preview",
  snapshot: previewSnapshot,
  connectionMessage: "Local API unavailable. Preview state is active.",
  loadedAt: new Date().toISOString(),
};

function renderApp(path = "/") {
  window.location.hash = path === "/scanner" ? "#/scanner" : "#/";
  const onRetry = vi.fn();
  const result = render(<AppView state={previewState} onRetry={onRetry} />);
  return { ...result, onRetry };
}

it("renders an ADHD-friendly, visibly non-live command center", () => {
  renderApp();

  expect(screen.getByRole("heading", { name: "See risk first. Decide calmly." })).toBeInTheDocument();
  expect(screen.getByText(/PREVIEW DATA · NOT LIVE/i)).toBeInTheDocument();
  expect(screen.getByText("Your next safe action")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /buy|sell|withdraw|leverage|order/i })).not.toBeInTheDocument();
});

it("supports keyboard-friendly navigation to scanner evidence", async () => {
  const user = userEvent.setup();
  renderApp();

  await user.click(screen.getByRole("link", { name: "Live Scanner" }));

  expect(screen.getByRole("heading", { name: "Evidence before direction." })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Search instruments" })).toBeInTheDocument();
});

it("keeps scanner filtering explicit and predictable", async () => {
  const user = userEvent.setup();
  renderApp("/scanner");

  await user.click(screen.getByRole("button", { name: "INSUFFICIENT DATA" }));
  expect(screen.getByRole("heading", { name: "BTCUSDT" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "HYPEUSDT" })).toBeInTheDocument();

  await user.type(screen.getByRole("textbox", { name: "Search instruments" }), "HYPE");
  expect(screen.queryByRole("heading", { name: "BTCUSDT" })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "HYPEUSDT" })).toBeInTheDocument();
});

it("passes the accessibility smoke test", async () => {
  const { container } = renderApp();
  const results = await axe.run(container);
  expect(results.violations).toEqual([]);
});
