/**
 * useProfile - shared hook that reads the EXISTING PlacePro profile data
 * (localStorage key "placepro_profile") and live-updates when the profile is
 * edited. Deliberately does NOT create a second profile system: it reuses the
 * same storage key and "placepro-profile-updated" event already used by
 * StudentProfile.jsx and ProfileDropdown.jsx.
 */
import { useEffect, useState } from "react";

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

function loadProfile() {
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

export default function useProfile() {
  const [profile, setProfile] = useState(loadProfile);

  useEffect(() => {
    const sync = () => setProfile(loadProfile());
    window.addEventListener("storage", sync);
    window.addEventListener("placepro-profile-updated", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("placepro-profile-updated", sync);
    };
  }, []);

  return profile;
}
