import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { profilesApi } from "../api";
import { getDemoProfileId } from "../config/demo";
import type { ProfileCompletion, StudentProfile } from "../types";

const PROFILE_ID_KEY = "placepro_active_profile_id";

function loadProfileId(): string {
  try {
    const stored = localStorage.getItem(PROFILE_ID_KEY);
    if (stored) return stored;
  } catch {
    // localStorage unavailable (SSR, private browsing edge case)
  }
  return getDemoProfileId();
}

function saveProfileId(id: string) {
  try {
    localStorage.setItem(PROFILE_ID_KEY, id);
  } catch {
    // ignore
  }
}

interface ProfileContextValue {
  profile: StudentProfile | null;
  completion: ProfileCompletion | null;
  profileId: string;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** Switch the active profile (e.g. after resume import creates a new one). */
  switchProfile: (newId: string) => void;
  /** True when the profile exists on the backend. */
  exists: boolean;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState<string>(loadProfileId);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [completion, setCompletion] = useState<ProfileCompletion | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Re-fetch whenever profileId changes
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await profilesApi.get(profileId);
        if (!cancelled) {
          setProfile(res.profile);
          setCompletion(res.completion);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load profile.");
          setProfile(null);
          setCompletion(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [profileId]);

  const refresh = useCallback(async () => {
    // Silent refresh when a profile is already loaded: flipping the global
    // loading flag here would make ProfileGate swap to <PageLoader />, which
    // unmounts gated pages mid-flight (e.g. PredictionPage awaits refresh()
    // inside run()) and discards their in-flight results. Initial loads
    // still show the loader; refreshes of an existing profile update in place.
    const hadProfile = profile !== null;
    if (!hadProfile) setLoading(true);
    setError(null);
    try {
      const res = await profilesApi.get(profileId);
      setProfile(res.profile);
      setCompletion(res.completion);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile.");
      setProfile(null);
      setCompletion(null);
    } finally {
      setLoading(false);
    }
  }, [profileId, profile]);

  const switchProfile = useCallback((newId: string) => {
    saveProfileId(newId);
    setProfileId(newId);
  }, []);

  const value: ProfileContextValue = {
    profile,
    completion,
    profileId,
    loading,
    error,
    refresh,
    switchProfile,
    exists: profile !== null,
  };

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile(): ProfileContextValue {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}
