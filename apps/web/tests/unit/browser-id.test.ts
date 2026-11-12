import { describe, expect, it, vi } from "vitest";

import { createBrowserId } from "../../src/lib/browser-id";

describe("createBrowserId", () => {
  it("falls back when randomUUID is unavailable", () => {
    const original = window.crypto.randomUUID;
    Object.defineProperty(window.crypto, "randomUUID", { configurable: true, value: undefined });
    vi.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);

    expect(createBrowserId()).toMatch(/^local-/);

    Object.defineProperty(window.crypto, "randomUUID", { configurable: true, value: original });
    vi.restoreAllMocks();
  });
});
