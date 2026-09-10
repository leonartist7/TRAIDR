import { act, renderHook, waitFor } from "@testing-library/react";

import { previewSnapshot } from "../lib/mockData";
import { loadResearchSnapshot } from "../lib/api";
import { RESEARCH_POLL_INTERVAL_MS, useResearchData } from "./useResearchData";

vi.mock("../lib/api", () => ({ loadResearchSnapshot: vi.fn() }));

beforeEach(() => {
  vi.resetAllMocks();
});

it("polls the read-only local snapshot on a bounded interval", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(loadResearchSnapshot).mockResolvedValue(previewSnapshot);
  const { result, unmount } = renderHook(() => useResearchData());

  await waitFor(() => expect(result.current.phase).toBe("ready"));
  expect(loadResearchSnapshot).toHaveBeenCalledTimes(1);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(RESEARCH_POLL_INTERVAL_MS);
  });
  await waitFor(() => expect(loadResearchSnapshot).toHaveBeenCalledTimes(2));

  unmount();
  vi.useRealTimers();
});


it("retains the last live snapshot when a later poll fails", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(loadResearchSnapshot)
    .mockResolvedValueOnce(previewSnapshot)
    .mockRejectedValueOnce(new Error("offline"));
  const { result, unmount } = renderHook(() => useResearchData());

  await waitFor(() => expect(result.current.source).toBe("local-api"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(RESEARCH_POLL_INTERVAL_MS);
  });
  await waitFor(() => expect(result.current.connectionMessage).toContain("offline"));

  expect(result.current.source).toBe("local-api");
  expect(result.current.snapshot).toBe(previewSnapshot);

  unmount();
  vi.useRealTimers();
});
