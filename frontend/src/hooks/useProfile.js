/** Account-scoped in-memory profiles; browser caches never establish access. */
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { fetchStudentProfile } from '../services/api.js';
import { flattenBackendProfile } from '../services/profileConfig.js';
import { createOwnedProfilesController, selectedProfileKey } from '../services/ownedProfiles.js';
import { profileStamp } from '../services/profileState.js';
import { useStudentProfileContext } from './useStudentProfileContext.js';

export function useStudentProfile(accountId) {
  const [controller] = useState(() => {
    const key = selectedProfileKey(accountId);
    let initialProfile = null;
    try { initialProfile = sessionStorage.getItem(key); } catch { /* Selection can stay in memory. */ }
    return createOwnedProfilesController({ fetchProfile: fetchStudentProfile, initialProfile,
      onSelected(id) { try { if (id) sessionStorage.setItem(key, id); else sessionStorage.removeItem(key); } catch { /* No private profile data is cached. */ } },
    });
  });
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  const [resumeDraft, setResumeDraft] = useState(null);
  useEffect(() => {
    controller.reload();
    return () => controller.cancel();
  }, [controller]);
  const refetch = useCallback((nextId) => controller.reload(nextId), [controller]);
  const selectProfile = useCallback((id) => {
    setResumeDraft(null);
    return controller.select(id);
  }, [controller]);
  const applyUpdatedProfile = useCallback((data) => controller.apply(data), [controller]);
  const rawProfile = state.data?.profile ?? null;
  return {
    profileId: state.profileId, rawProfile,
    profile: rawProfile ? flattenBackendProfile(rawProfile) : null,
    completion: state.data?.completion ?? null,
    profileKey: profileStamp(state.profileId, rawProfile),
    ownedProfileIds: state.ids, listLoading: state.listLoading,
    loading: !rawProfile && (state.listLoading || state.status === 'loading'),
    refreshing: Boolean(rawProfile) && (state.listLoading || state.status === 'loading'),
    error: state.listError || state.error, profileMissing: state.profileMissing,
    refetch, selectProfile, applyUpdatedProfile, resumeDraft,
    setPendingResumeDraft: setResumeDraft,
    clearPendingResumeDraft: useCallback(() => setResumeDraft(null), []),
  };
}

/** Retained display contract, now reading the authoritative shared context. */
export default function useProfile() { return useStudentProfileContext().profile || {}; }
