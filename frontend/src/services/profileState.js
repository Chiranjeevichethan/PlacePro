/** Request guards for the canonical server profile. No browser mirror is authoritative. */
export const profileStamp = (profileId, profile) => JSON.stringify([
  profileId, profile?.revision ?? null, Boolean(profile?.verified),
]);

export function requireSource(response, profile) {
  if (response?.profile_id !== profile.profile_id || response?.source_revision !== profile.revision) {
    throw new Error('Profile changed while loading this view. Refresh the profile and try again.');
  }
  return response;
}

export const predictionStamp = (profileKey, inputs) => JSON.stringify([profileKey, inputs]);

/** Another tab may clear the old mirror while selecting a different profile.
 * Read the active ID at delivery time; queued events can describe an older ID. */
export function createProfileRefreshHandlers({ refresh, readProfileId, profileIdKey, profileKey }) {
  return {
    onFocus: () => refresh(readProfileId()),
    onStorage: (event) => {
      if (event.key === profileIdKey || event.key === profileKey) return refresh(readProfileId());
    },
  };
}

export function createPredictionController(predict) {
  let state = { key: null, result: null, error: null, busy: false };
  let generation = 0;
  const listeners = new Set();
  const publish = (next) => { state = { ...state, ...next }; listeners.forEach((listener) => listener()); };
  const select = (key) => {
    if (key === state.key) return;
    generation += 1;
    publish({ key, result: null, error: null, busy: false });
  };
  return {
    subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot: () => state, select,
    cancel: () => { generation += 1; },
    async run(key, inputs) {
      select(key);
      if (state.busy) return;
      const request = ++generation;
      publish({ busy: true, error: null });
      try {
        const result = await predict(structuredClone(inputs));
        if (generation === request) publish({ result });
      } catch (error) {
        if (generation === request) publish({ error: error.message || 'Unable to calculate this prediction.' });
      } finally {
        if (generation === request) publish({ busy: false });
      }
    },
  };
}

/** An older response cannot undo a saved edit or repopulate a switched profile. */
export function createProfileController({ profileId, fetchProfile, mirror = () => {} }) {
  let state = { profileId, data: null, status: 'loading', error: null, profileMissing: false };
  let generation = 0;
  const listeners = new Set();
  const publish = (next) => {
    state = { ...state, ...next };
    listeners.forEach((listener) => listener());
  };
  const check = (data, id) => {
    if (data?.profile?.profile_id !== id || !Number.isInteger(data.profile.revision) || data.profile.revision < 0) {
      throw new Error('The profile service returned an unexpected profile. Please retry.');
    }
  };
  const accept = (data) => {
    publish({ data, status: 'success', error: null, profileMissing: false });
    mirror(state.profileId, data);
  };
  return {
    subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot: () => state,
    cancel: () => { generation += 1; },
    async refresh(nextId = state.profileId) {
      const request = ++generation;
      if (!nextId) {
        mirror(null, null);
        publish({ profileId: null, data: null, status: 'empty', error: null, profileMissing: true });
        return;
      }
      const switching = nextId !== state.profileId;
      if (switching) mirror(nextId, null);
      publish({ profileId: nextId, data: switching ? null : state.data,
        status: 'loading', error: null, profileMissing: false });
      try {
        const data = await fetchProfile(nextId);
        if (request !== generation) return;
        check(data, nextId);
        if (state.data?.profile?.revision > data.profile.revision) {
          throw new Error('A newer profile has already been loaded. Please retry.');
        }
        accept(data);
        return data;
      } catch (error) {
        if (request !== generation) return;
        publish({ status: 'error', data: [401, 403, 404].includes(error.status) ? null : state.data,
          error: error.message || 'Unable to load student profile.',
          profileMissing: !state.data && error.code === 'PROFILE_NOT_FOUND' });
      }
    },
    apply(data) {
      check(data, state.profileId);
      if (state.data?.profile?.revision > data.profile.revision) return false;
      generation += 1;
      accept(data);
      return true;
    },
  };
}
