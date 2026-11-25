import { useCallback, useEffect, useState } from 'react';
import { useStudentProfileContext } from './useStudentProfileContext';
import { requireSource } from '../services/profileState.js';

/** Retain the last valid response on retry failure, but never render another source. */
export function useProfileResource(load) {
  const { profileId, rawProfile, profileKey, loading, error: profileError, refetch: refreshProfile } = useStudentProfileContext();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState(null);
  const refetch = useCallback(() => { refreshProfile(); setAttempt((value) => value + 1); },[refreshProfile]);
  useEffect(() => {
    let active = true;
    if (!rawProfile || profileError) return () => { active = false; };
    load(profileId).then((data) => {
      requireSource(data, rawProfile);
      if (active) setState({ key: profileKey, attempt, data, error: null });
    }).catch((error) => {
      if (active) setState((previous) => ({ key: profileKey, attempt,
        data: previous?.key === profileKey ? previous.data : null, error: error.message }));
    });
    return () => { active = false; };
  }, [load, profileId, profileKey, rawProfile, profileError, attempt]);
  const current = state?.key === profileKey ? state : null;
  return { data: rawProfile && !profileError ? current?.data ?? null : null,
    error: profileError || (!loading && !rawProfile ? 'Create or select an available profile to view this analysis.' : current?.error),
    loading: loading || (Boolean(rawProfile) && !profileError && (!current || current.attempt !== attempt)),
    refetch };
}
