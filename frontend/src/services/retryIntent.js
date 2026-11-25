/** Keep a retry identity only for the same reviewed intent in this mounted UI. */
export function createRetryIntent() {
  let signature = null;
  let key = null;
  return (payload) => {
    const next = JSON.stringify(payload);
    if (next !== signature) { signature = next; key = crypto.randomUUID(); }
    return key;
  };
}
