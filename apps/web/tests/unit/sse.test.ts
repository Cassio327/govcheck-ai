import { describe, expect, it } from "vitest";

import { SSEDecoder, parseSSE } from "../../src/lib/sse";

describe("parseSSE", () => {
  it("parses versioned replay events without inventing fields", () => {
    const events = parseSSE(
      'id: 3\nevent: analysis.evidence_critic.completed\ndata: {"supported_count":2}\n\n' +
        'id: 4\nevent: analysis.completed\ndata: {}\n\n',
    );

    expect(events).toEqual([
      { id: 3, event: "analysis.evidence_critic.completed", data: { supported_count: 2 } },
      { id: 4, event: "analysis.completed", data: {} },
    ]);
  });

  it("decodes events incrementally across network chunk boundaries", () => {
    const decoder = new SSEDecoder();

    expect(decoder.push("id: 7\nevent: analysis.extraction.completed\nda")).toEqual([]);
    expect(decoder.push('ta: {"finding_count":2}\n\nid: 8\nevent: analysis.completed\ndata: {}\n')).toEqual([
      { id: 7, event: "analysis.extraction.completed", data: { finding_count: 2 } },
    ]);
    expect(decoder.push("\n")).toEqual([
      { id: 8, event: "analysis.completed", data: {} },
    ]);
  });
});
