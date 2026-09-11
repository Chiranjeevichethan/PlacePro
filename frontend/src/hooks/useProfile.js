/**
 * Profile hooks (Phase 4B).
 *
 * The BACKEND (GET /api/profile/{id}) is the source of truth for profile
 * data. There is exactly one profile source and one mirror:
 *
 *  - useStudentProfile(): loads the real backend profile for the Student
 *    Profile page. On success it mirrors the flattened profile to
 *    localStorage ("placepro_profile") and dispatches the existing
 *    "placepro-profile-updated" event. Returns { profile, loading, error,
 *    refetch } — `profile` is null while loading/failed (never fake data).
 *
 *  - useProfile(): existing hook used by demo pages (Salary Prediction,
 *    Skill Gap, Company Recommendations — later phases). Unchanged return
 *    contract: the flat profile object, now fed by the backend mirror
 *    instead of stale edit-session values.
 */
import { useCallback, useEffect, useState } from "react";
import { fetchStudentProfile } from "../services/api";
import { DEMO_PROFILE_ID, flattenBackendProfile } from "../services/profileConfig";

const PROFILE_KEY = "placepro_profile";

const DEFAULT_PROFILE = {
  name: "Bhargav",
  branch: "Information Science and Engineering",
  collegeTier: "Tier 2",
  cgpa: "8.2",
  attendance: "88",
  internships: "2",
  projects: "3",
  certifications: "4",
  githubRepositories: "5",
  linkedinConnections: "120",
  skills: "",
  preferredRole: "",
};

function loadMirror() {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) {
      return { ...DEFAULT_PROFILE, ...JSON.parse(raw) };
    }
  } catch {
    // Ignore malformed storage and fall back to defaults.
  }
  return DEFAULT_PROFILE;
}

/**
 * Loads the student profile from the real backend.
 * The backend is authoritative: no demo values are ever substituted here.
 */
export function useStudentProfile() {
  const [status, setStatus] = useState("loading");
  const [profile, setProfile] = useState(null);
  const [rawProfile, setRawProfile] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;

    fetchStudentProfile(DEMO_PROFILE_ID)
      .then((data) => {
        if (!active) return;

        const display = flattenBackendProfile(data.profile);
        setProfile(display);
        setRawProfile(data.profile);
        setStatus("success");

        // Mirror for useProfile() consumers (demo pages) and the navbar.
        try {
          localStorage.setItem(PROFILE_KEY, JSON.stringify(display));
          window.dispatchEvent(new Event("placepro-profile-updated"));
        } catch {
          // Storage may be unavailable; the page still shows backend data.
        }
      })
      .catch((err) => {
        if (!active) return;

        setProfile(null);
        setRawProfile(null);
        setStatus("error");
        setError(
          err?.message ??
            "Unable to load student profile. Please try again."
        );
      });

    return () => {
      active = false;
    };
  }, [attempt]);

  const refetch = useCallback(() => {
    // Event-handler state updates (not effect-body): restart the load.
    setAttempt((n) => n + 1);
    setStatus("loading");
    setError(null);
  }, []);

  /**
   * Applies a successful PUT response (the updated backend profile) without
   * a refetch: { profile, completion, message } -> { profile: {...} }.
   */
  const applyUpdatedProfile = useCallback((data) => {
    if (!data?.profile) return;

    const display = flattenBackendProfile(data.profile);
    setProfile(display);
    setRawProfile(data.profile);

    try {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(display));
      window.dispatchEvent(new Event("placepro-profile-updated"));
    } catch {
      // Storage may be unavailable; the page still shows backend data.
    }
  }, []);

  return {
    profile,
    rawProfile,
    loading: status === "loading",
    error,
    refetch,
    applyUpdatedProfile,
  };
}

/**
 * Legacy/demo hook (unchanged contract): reads the profile mirror that
 * useStudentProfile() keeps in sync with the backend.
 */
export default function useProfile() {
  const [profile, setProfile] = useState(loadMirror);

  useEffect(() => {
    const sync = () => setProfile(loadMirror());
    window.addEventListener("storage", sync);
    window.addEventListener("placepro-profile-updated", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("placepro-profile-updated", sync);
    };
  }, []);

  return profile;
}
