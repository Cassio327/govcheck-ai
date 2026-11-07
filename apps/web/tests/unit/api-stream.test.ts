import { afterEach, describe, expect, it, vi } from "vitest";

import { watchAnalysis } from "../../src/lib/api";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

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

  it("waits at least one second between default replay requests", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("id: 1\nevent: analysis.started\ndata: {}\n\n", { status: 200 }))
      .mockResolvedValueOnce(new Response("id: 2\nevent: analysis.completed\ndata: {}\n\n", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const iterator = watchAnalysis("document-id", { timeoutMs: 2_000 });

    expect((await iterator.next()).value?.id).toBe(1);
    const terminal = iterator.next();
    await vi.advanceTimersByTimeAsync(999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect((await terminal).value?.id).toBe(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
