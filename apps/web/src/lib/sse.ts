import type { StreamEvent } from "./contracts";

function parseBlock(block: string): StreamEvent | null {
  const fields = new Map<string, string>();
  for (const line of block.trim().split(/\r?\n/)) {
    const separator = line.indexOf(":");
    if (separator < 0 || line.startsWith(":")) continue;
    fields.set(line.slice(0, separator), line.slice(separator + 1).trimStart());
  }
  const id = Number(fields.get("id"));
  const event = fields.get("event");
  const data = fields.get("data");
  if (!Number.isInteger(id) || !event || data === undefined) return null;
  try {
    return { id, event, data: JSON.parse(data) as Record<string, unknown> };
  } catch {
    return null;
  }
}

export class SSEDecoder {
  private buffer = "";

  push(chunk: string): StreamEvent[] {
    this.buffer += chunk;
    const blocks = this.buffer.split(/\r?\n\r?\n/);
    this.buffer = blocks.pop() ?? "";
    return blocks.flatMap((block) => {
      const event = parseBlock(block);
      return event ? [event] : [];
    });
  }

  flush(): StreamEvent[] {
    const block = this.buffer;
    this.buffer = "";
    const event = block.trim() ? parseBlock(block) : null;
    return event ? [event] : [];
  }
}

export function parseSSE(payload: string): StreamEvent[] {
  const decoder = new SSEDecoder();
  return [...decoder.push(payload), ...decoder.flush()];
}
