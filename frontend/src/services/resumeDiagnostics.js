import { authSession } from './auth.js';

// Investigation instrumentation requires an explicit opt-in in development.
// Production builds stay silent, including synthetic demo builds.
const enabled = import.meta.env?.DEV === true &&
  import.meta.env?.VITE_RESUME_DIAGNOSTICS === '1';
let context = {};
let sequence = 0;
let instance = 0;
const activities = new Map();
const keys = ['source', 'reason', 'page', 'nextPage', 'profileId', 'previousProfileId',
  'previous', 'next', 'open', 'instance', 'phase', 'uploading', 'verifying',
  'selectedExperience', 'loading', 'refreshing', 'profileError', 'profileMissing',
  'status', 'eventType', 'eventTrusted', 'targetTag'];

export function safeResumeDiagnostic(fields) {
  return Object.fromEntries(keys.filter((key) => key in fields &&
    ['string', 'number', 'boolean'].includes(typeof fields[key])).map((key) => [key, fields[key]]));
}

export function resumeDiagnosticInstance() { return enabled ? ++instance : null; }

export function traceResume(event, fields = {}) {
  if (!enabled) return;
  // Never accept a resume, file, request body, credential or token into the log.
  const safe = safeResumeDiagnostic(fields);
  if (event === 'app.state') context = safe;
  if (event === 'modal.state') activities.set(safe.instance, safe);
  const session = authSession.getSnapshot();
  const record = { sequence: ++sequence, timeMs: Math.round(performance.now()), event,
    ...context, ...activities.get(safe.instance), ...safe,
    authStatus: session.status, authEpoch: session.epoch };
  const log = window.__placeproResumeDiagnostics ||= [];
  log.push(record);
  if (log.length > 1000) log.shift();
  console.debug('[PlacePro resume]', JSON.stringify(record));
  if (event === 'modal.unmount') activities.delete(safe.instance);
}
