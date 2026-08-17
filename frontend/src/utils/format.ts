// Formatting + label helpers shared across pages.

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function score(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/** Title-case a snake_case / kebab / lower-case label for display. */
export function humanize(label: string): string {
  return label
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function titleFromKey(key: string): string {
  return humanize(key);
}

// ---------- Status labels / tones ----------

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_BY_STATUS: Record<string, Tone> = {
  PLACED: "success",
  ELIGIBLE: "success",
  RECOMMENDED: "success",
  PASS: "success",
  VERIFIED: "success",
  TRUE: "success",

  INCOMPLETE: "warning",
  UNKNOWN: "warning",
  NOT_ELIGIBLE: "danger",
  NOT_RECOMMENDED: "danger",
  FAIL: "danger",
  FALSE: "neutral",

  DEVELOPING: "warning",
  "NEEDS IMPROVEMENT": "danger",
};

export function toneForStatus(status: string): Tone {
  const upper = (status ?? "").toUpperCase();
  if (upper in TONE_BY_STATUS) return TONE_BY_STATUS[upper];
  return "neutral";
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    NOT_ELIGIBLE: "Not Eligible",
    NOT_RECOMMENDED: "Not Recommended",
    PLACED: "Placed",
  };
  if (map[status]) return map[status];
  return humanize(status);
}
