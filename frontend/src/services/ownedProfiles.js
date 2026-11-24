import { API_BASE_URL, authenticatedFetch } from './apiTransport.js';
import { createProfileController } from './profileState.js';
import { requireSource } from './profileState.js';

export async function saveProfilePrediction(profileId, revision, requestId) {
  const response = await authenticatedFetch(`${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/predict`, {
    method: 'POST', headers: { 'Idempotency-Key': requestId },
  });
  if (!response.ok) {
    const message = response.status === 409 ? 'Profile changed. Refresh and review it before predicting.'
      : response.status === 403 ? 'Security check failed. Refresh your session and try again.'
        : 'Unable to save this profile prediction. Please retry.';
    throw Object.assign(new Error(message), { status: response.status });
  }
  const data = requireSource(await response.json(), { profile_id: profileId, revision });
  if (!data.ready_for_prediction || !Array.isArray(data.prediction_history)) throw new Error('Verify and complete your profile before saving a prediction.');
  return data;
}

export async function fetchOwnedProfiles() {
  const response = await authenticatedFetch(API_BASE_URL + '/api/account/profiles');
  if (!response.ok) throw Object.assign(new Error('Unable to load your profiles. Refresh your session and try again.'), { status: response.status });
  const data = await response.json();
  if (!Array.isArray(data?.profiles) || data.profiles.some((p) => !/^[a-f0-9-]{36}$/.test(p?.profile_id)) ||
      new Set(data.profiles.map((p) => p.profile_id)).size !== data.profiles.length) throw new Error('The profile list returned an unexpected response.');
  return data.profiles.map((p) => p.profile_id);
}

export function selectedProfileKey(accountId) { return `placepro_selected_profile:${encodeURIComponent(API_BASE_URL)}:${accountId}`; }

export function createOwnedProfilesController({ fetchProfile, listProfiles = fetchOwnedProfiles, initialProfile = null, onSelected = () => {} }) {
  const core = createProfileController({ profileId: null, fetchProfile });
  let state = { ...core.getSnapshot(), ids: [], listLoading: true, listError: null };
  let generation = 0;
  const listeners = new Set();
  const publish = (next) => { state = { ...state, ...next }; listeners.forEach((listener) => listener()); };
  core.subscribe(() => { publish(core.getSnapshot()); onSelected(core.getSnapshot().profileId); });
  return {
    subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot: () => state,
    cancel() { generation++; core.cancel(); },
    async reload(nextId = core.getSnapshot().profileId || initialProfile) {
      const request = ++generation;
      publish({ listLoading: true, listError: null });
      try {
        const ids = await listProfiles();
        if (request !== generation) return;
        publish({ ids, listLoading: false });
        const chosen = nextId === null ? null : ids.includes(nextId) ? nextId : ids[0] ?? null;
        await core.refresh(chosen ?? ids[0] ?? null);
      } catch (error) {
        if (request !== generation) return;
        const denied = [401, 403].includes(error.status);
        // Only an authorization denial invalidates the selected workspace.
        // A temporary list failure must leave its profile and drafts mounted.
        if (denied) core.refresh(null);
        publish({ ...(denied ? { ids: [] } : {}), listLoading: false,
          listError: denied ? 'Unable to load your profiles. Refresh your session and try again.'
            : 'Unable to load your profiles. Please retry.' });
      }
    },
    select(id) {
      generation++;
      if (id !== null && !state.ids.includes(id)) throw new Error('Choose one of your available profiles.');
      return core.refresh(id);
    },
    apply: (data) => core.apply(data),
  };
}
