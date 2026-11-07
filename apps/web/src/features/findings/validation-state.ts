export type ValidationState = "verified" | "not_found" | "unavailable" | "invalid" | "mixed" | "skipped";

const STATUSES = ["verified", "not_found", "unavailable", "invalid"] as const;

export function validationStateFromEvent(data: Record<string, unknown>): ValidationState {
  const validationCount = typeof data.validation_count === "number" ? data.validation_count : 0;
  if (validationCount === 0) return "skipped";

  const rawCounts = data.validation_status_counts;
  if (!rawCounts || typeof rawCounts !== "object") return "mixed";
  const counts = STATUSES.map((status) => {
    const value = (rawCounts as Record<string, unknown>)[status];
    return [status, typeof value === "number" && value >= 0 ? value : 0] as const;
  });
  const present = counts.filter(([, count]) => count > 0);
  if (present.length !== 1 || present[0][1] !== validationCount) return "mixed";
  return present[0][0];
}
