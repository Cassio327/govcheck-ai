import { afterEach, describe, expect, it, vi } from "vitest";

import { watchAnalysis } from "../../src/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("watchAnalysis", () => {
  it("reconnects with Last-Event-ID and keeps the replay duplicate-free", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("id: 1\nevent: analysis.started\ndata: {}\n\n", { status: 200 }))
      .mockResolvedValueOnce(new Response("id: 1\nevent: analysis.started\ndata: {}\n\nid: 2\nevent: analysis.completed\ndata: {}\n\n", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const events = [];
    for await (const event of watchAnalysis("document-id", { pollIntervalMs: 0, timeoutMs: 2_000 })) {
      events.push(event);
    }

    expect(events.map((event) => event.id)).toEqual([1, 2]);
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("Last-Event-ID")).toBe("1");
  });
});
