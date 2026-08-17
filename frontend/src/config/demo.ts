// ============================================================
// PLACEPRO - PHASE 18 - DEMO CONFIGURATION (ISOLATED)
// ============================================================
// The backend has no authentication yet, so the dashboard uses a
// development/demo profile id. This configuration is intentionally
// isolated in one file: swap to real profile selection when auth
// lands (a later phase). The id is created by:
//   python backend/scripts/seed_demo_profile.py
// ============================================================

const DEMO_PROFILE_ID: string =
  (import.meta.env.VITE_DEMO_PROFILE_ID as string | undefined) ?? "demo-student";

export function getDemoProfileId(): string {
  return DEMO_PROFILE_ID;
}

export const IS_DEMO_MODE = true;

// Skills supported by the Phase 17 assessment engine. The backend
// does not expose a public list endpoint, so the (public, documented)
// list lives here as config - not as duplicated business logic.
export const ASSESSMENT_SKILLS: string[] = [
  "Python",
  "Java",
  "C",
  "C++",
  "JavaScript",
  "SQL",
  "Data Structures",
  "Algorithms",
  "React",
  "Machine Learning",
  "HTML/CSS",
  "Git",
];

// Hard limits enforced by the backend (Phase 17 config) - shown in UI
// copy only; the backend remains the source of truth.
export const ASSESSMENT_MAX_ATTEMPTS = 3;
export const ASSESSMENT_COOLDOWN_HOURS = 24;
