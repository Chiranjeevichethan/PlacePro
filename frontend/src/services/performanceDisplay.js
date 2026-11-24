/** Parse display values without converting missing data to zero. */
export function displayNumberOrNull(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value !== "string" || value.trim() === "") return null;
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? parsed : null;
}

export function displayIntegerOrNull(value) {
  const parsed = displayNumberOrNull(value);
  return parsed !== null && Number.isInteger(parsed) ? parsed : null;
}

export function displayCountOrNull(value) {
  const parsed = displayIntegerOrNull(value);
  return parsed !== null && parsed >= 0 ? parsed : null;
}

export function displayPercentOrNull(value, scale = 1) {
  const parsed = displayNumberOrNull(value);
  return parsed === null ? null : Math.round(parsed * scale);
}
