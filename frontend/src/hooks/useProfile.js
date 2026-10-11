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
const PROFILE_ID_KEY = "placepro_profile_id";
const RESUME_DRAFT_KEY = "placepro_resume_draft";

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

/**
 * Persist / restore the pending resume draft between verify steps.
 * The draft is a verbatim backend DraftStudentProfile — it may contain
 * exact null fields (the 10 ML prediction inputs MUST stay missing until
 * the student explicitly provides them).
 */
function loadResumeDraft() {
  try {
    const raw = localStorage.getItem(RESUME_DRAFT_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") return parsed;
    }
  } catch {
    // Ignore malformed storage and treat as "no pending draft".
  }
  return null;
}

function saveResumeDraft(draft) {
  try {
    localStorage.setItem(RESUME_DRAFT_KEY, JSON.stringify(draft));
    return true;
  } catch {
    // Storage may be unavailable; the app still works within one session.
    return false;
  }
}

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

const normalizeProfileId = (value) =>
  typeof value === "string" && value.trim() !== ""
    ? value.trim()
    : DEMO_PROFILE_ID;

function loadProfileId() {
  try {
    return normalizeProfileId(localStorage.getItem(PROFILE_ID_KEY));
  } catch {
    return DEMO_PROFILE_ID;
  }
}

function saveProfileId(profileId) {
  try {
    localStorage.setItem(PROFILE_ID_KEY, normalizeProfileId(profileId));
  } catch {
    // Storage may be unavailable; in-memory state still selects the profile.
  }
}

/**
 * Loads the student profile from the real backend.
 * The backend is authoritative: no demo values are ever substituted here.
 */
export function useStudentProfile() {
  const [profileId, setProfileId] = useState(loadProfileId);
  const [status, setStatus] = useState("loading");
  const [profile, setProfile] = useState(null);
  const [rawProfile, setRawProfile] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [resumeDraft, setResumeDraft] = useState(loadResumeDraft);

  useEffect(() => {
    let active = true;

    fetchStudentProfile(profileId)
      .then((data) => {
        if (!active) return;

        const display = flattenBackendProfile(data.profile);
        setProfile(display);
        setRawProfile(data.profile);
        setStatus("success");

        // Mirror for useProfile() consumers (demo pages) and the navbar.
        try {
          localStorage.setItem(PROFILE_KEY, JSON.stringify(display));
          saveProfileId(data.profile?.profile_id ?? profileId);
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
  }, [attempt, profileId]);

  const refetch = useCallback((nextProfileId) => {
    const requestedProfileId = normalizeProfileId(nextProfileId ?? profileId);

    if (requestedProfileId !== profileId) {
      saveProfileId(requestedProfileId);
      setProfileId(requestedProfileId);
    } else {
      setAttempt((n) => n + 1);
    }

    // Event-handler state updates (not effect-body): restart the load.
    setStatus("loading");
    setError(null);
  }, [profileId]);

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
      saveProfileId(data.profile?.profile_id ?? profileId);
      window.dispatchEvent(new Event("placepro-profile-updated"));
    } catch {
      // Storage may be unavailable; the page still shows backend data.
    }
  }, [profileId]);

  /**
   * Stores the verbatim draft profile created from a resume
   * (POST /api/profile/from-resume response payload). No field is
   * inferred or filled in here — nulls stay null.
   */
  const setPendingResumeDraft = useCallback((draftProfile) => {
    if (!draftProfile || typeof draftProfile !== "object") return;
    setResumeDraft(draftProfile);
    saveResumeDraft(draftProfile);
  }, []);

  /**
   * Clears the pending draft after a successful verify (or explicit
   * discard by the student).
   */
  const clearPendingResumeDraft = useCallback(() => {
    setResumeDraft(null);
    try {
      localStorage.removeItem(RESUME_DRAFT_KEY);
    } catch {
      // Storage may be unavailable; in-memory state is already cleared.
    }
  }, []);

  return {
    profileId,
    profile,
    rawProfile,
    loading: status === "loading",
    error,
    refetch,
    applyUpdatedProfile,
    resumeDraft,
    setPendingResumeDraft,
    clearPendingResumeDraft,
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
