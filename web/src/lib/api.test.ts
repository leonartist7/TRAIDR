import { loadResearchSnapshot, ResearchApiError } from "./api";
import { previewSnapshot } from "./mockData";

it("loads the three bounded read-only API contracts", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
    new Response(JSON.stringify(previewSnapshot.status), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await loadResearchSnapshot();

  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(fetchMock.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
});

it("rejects any response that claims execution authority", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
    new Response(JSON.stringify({ ...previewSnapshot.status, can_execute_trades: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await expect(loadResearchSnapshot()).rejects.toThrow(ResearchApiError);
});
