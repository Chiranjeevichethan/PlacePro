import { API_BASE_URL, authenticatedFetch } from './apiTransport.js';

function builderPath(profileId, suffix = '') {
  return `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/resume-builder${suffix}`;
}

async function safeError(response) {
  let data;
  try { data = await response.json(); } catch { data = null; }
  const detail = typeof data?.detail === 'string' ? data.detail : null;
  return Object.assign(new Error(detail || (response.status === 409
    ? 'The resume changed. Reload and review it before continuing.'
    : response.status === 401 ? 'Your session has expired. Sign in again.'
      : response.status === 403 ? 'The security check failed. Refresh and retry.'
        : 'The resume builder is unavailable. Please retry.')), { status: response.status });
}

async function jsonRequest(profileId, suffix = '', method = 'GET', payload) {
  let response;
  try {
    response = await authenticatedFetch(builderPath(profileId, suffix), {
      method,
      ...(payload === undefined ? {} : {
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      }),
    });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error('Cannot reach the resume builder. Check your connection and retry.', { cause });
  }
  if (!response.ok) throw await safeError(response);
  try { return await response.json(); }
  catch (cause) { throw new Error('The resume service returned an unexpected response.', { cause }); }
}

export const fetchResumeDraft = (profileId) => jsonRequest(profileId);
export const saveResumeDraft = (profileId, document) => jsonRequest(profileId, '', 'PUT', document);
export const importResumeProfile = (profileId) => jsonRequest(profileId, '/import', 'POST', {});

export async function exportResumePdf(profileId) {
  let response;
  try {
    response = await authenticatedFetch(builderPath(profileId, '/export.pdf'), { method: 'POST' });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error('Cannot reach the PDF export service. Check your connection and retry.', { cause });
  }
  if (!response.ok) throw await safeError(response);
  if (!response.headers.get('content-type')?.toLowerCase().startsWith('application/pdf')) {
    throw new Error('The export service did not return a PDF file.');
  }
  return response.blob();
}
