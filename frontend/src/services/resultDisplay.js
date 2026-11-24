/** Backend numbers only: null/missing evidence must never become zero. */
export const finiteNumberOrNull = (value) =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

export const percentOrNull = (value, scale = 1) => {
  const number = finiteNumberOrNull(value);
  return number === null ? null : Math.round(number * scale);
};
