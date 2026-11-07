import { describe, expect, it } from "vitest";

import { validationStateFromEvent } from "../../src/features/findings/validation-state";

describe("validationStateFromEvent", () => {
  it("preserves unavailable and mixed outcomes instead of trusting the attempt count", () => {
    expect(validationStateFromEvent({
      validation_count: 1,
      validation_status_counts: { verified: 0, not_found: 0, unavailable: 1, invalid: 0 },
    })).toBe("unavailable");
    expect(validationStateFromEvent({
      validation_count: 2,
      validation_status_counts: { verified: 1, not_found: 0, unavailable: 1, invalid: 0 },
    })).toBe("mixed");
  });

  it("fails closed when an older event has no status breakdown", () => {
    expect(validationStateFromEvent({ validation_count: 1 })).toBe("mixed");
    expect(validationStateFromEvent({ validation_count: 0 })).toBe("skipped");
  });
});
