/**
 * Student profile mapping layer (Phase 4B).
 *
 * Single source of truth for:
 *  - the demo profile id expected by the backend seeder
 *  - backend (FastAPI StudentProfile schema) <-> frontend display mapping
 *  - the edit-state shape used by EditProfileModal
 *  - the PUT /api/profile/{id} payload builder
 *
 * The backend PUT replaces the stored profile (the server itself restores
 * provenance / verified / prediction_history), so buildProfilePayload always
 * sends the FULL editable profile derived from the last loaded backend data —
 * never just the modal state, and never server-controlled fields.
 */

/** Demo profile id — canonical value from backend/scripts/seed_demo_profile.py
 * ("frontend uses VITE_DEMO_PROFILE_ID=demo-student"). Not an invented id. */
export const DEMO_PROFILE_ID =
  import.meta.env.VITE_DEMO_PROFILE_ID || "demo-student";

/* ------------------------------------------------------------------ */
/* Display labels (display-only; canonical backend values are kept     */
/* intact in the data and in every request)                            */
/* ------------------------------------------------------------------ */

const BRANCH_DISPLAY = {
  CSE: "Computer Science & Engineering",
  IT: "Information Technology",
  ECE: "Electronics & Communication",
  EE: "Electrical Engineering",
  ME: "Mechanical Engineering",
  CE: "Civil Engineering",
  Chemical: "Chemical Engineering",
};

const TIER_DISPLAY = {
  "Tier-1": "Tier 1",
  "Tier-2": "Tier 2",
  "Tier-3": "Tier 3",
};

const TIER_CANONICAL = {
  "Tier 1": "Tier-1",
  "Tier 2": "Tier-2",
  "Tier 3": "Tier-3",
};

/** Backend college_tier values for the edit modal. */
export const TIER_OPTIONS = [
  { value: "Tier-1", label: "Tier 1" },
  { value: "Tier-2", label: "Tier 2" },
  { value: "Tier-3", label: "Tier 3" },
];

/** Canonical backend branch vocabulary for the edit modal. */
export const BRANCH_OPTIONS = Object.entries(BRANCH_DISPLAY).map(
  ([value, label]) => ({ value, label })
);

const SKILL_ARRAYS = [
  "programming_languages",
  "frameworks",
  "databases",
  "cloud",
  "ai_ml",
  "web_technologies",
  "tools",
  "other_skills",
];

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const asText = (value) =>
  value === null || value === undefined ? "" : String(value);

const parseNumberOrNull = (value) => {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const parseIntegerOrNull = (value) => {
  const parsed = parseNumberOrNull(value);
  return parsed === null ? null : Math.round(parsed);
};

/* ------------------------------------------------------------------ */
/* Validation ranges (backend-enforced bounds, mirrored for the form)  */
/* ------------------------------------------------------------------ */

export const EDIT_RANGES = {
  cgpa: { min: 0, max: 10, label: "CGPA", integer: false },
  attendance: { min: 0, max: 100, label: "Attendance", integer: false },
  backlogs: { min: 0, max: 3, label: "Backlogs", integer: true },
  openSourceContributions: {
    min: 0,
    max: 2,
    label: "Open Source Contributions",
    integer: true,
  },
  extracurriculars: {
    min: 0,
    max: 3,
    label: "Extracurricular Activities",
    integer: true,
  },
};

/* ------------------------------------------------------------------ */
/* Flatten: backend profile -> flat display object used by the UI      */
/* ------------------------------------------------------------------ */

export function flattenBackendProfile(backendProfile) {
  const p = backendProfile ?? {};
  const personal = p.personal ?? {};
  const education = p.education ?? {};
  const ml = p.ml_inputs ?? {};
  const additional = p.additional_info ?? {};
  const achievements = p.achievements ?? {};

  const branch = asText(education.branch);
  const tier = asText(ml.college_tier);

  return {
    /* identity */
    name: asText(personal.name),
    email: asText(personal.email),
    phone: asText(personal.phone),
    location: asText(personal.location),
    linkedin: asText(personal.linkedin),
    github: asText(personal.github),

    /* education */
    degree: asText(education.degree),
    college: asText(education.college),
    graduationYear: asText(education.graduation_year),
    branch, // canonical value (e.g. "CSE")
    branchDisplay:
      BRANCH_DISPLAY[branch] ?? (branch || "Not set"), // friendly label
    cgpa: asText(education.cgpa),

    /* ML inputs (editable) */
    collegeTier: tier, // canonical value ("Tier-2")
    collegeTierDisplay: TIER_DISPLAY[tier] ?? (tier || "Not set"),
    backlogs: asText(ml.backlogs),
    codingSkills: asText(ml.coding_skills),
    dsaScore: asText(ml.dsa_score),
    aptitudeScore: asText(ml.aptitude_score),
    communicationSkills: asText(ml.communication_skills),
    mlKnowledge: asText(ml.ml_knowledge),
    systemDesign: asText(ml.system_design),
    openSourceContributions: asText(ml.open_source_contributions),
    extracurriculars: asText(ml.extracurriculars),

    /* additional info (partially editable) */
    attendance: asText(additional.attendance),
    githubRepositories: asText(additional.github_repositories),
    linkedinConnections: asText(additional.linkedin_connections),
    volunteerExperience: asText(additional.volunteer_experience),

    /* structural sections (read-only display this phase) */
    skills: SKILL_ARRAYS.flatMap((key) => p.skills?.[key] ?? []),
    internshipsCount: Array.isArray(p.internships) ? p.internships.length : 0,
    projectsCount: Array.isArray(p.projects) ? p.projects.length : 0,
    certificationsCount: Array.isArray(p.certifications)
      ? p.certifications.length
      : 0,
    hackathonsCount: Array.isArray(achievements.hackathons)
      ? achievements.hackathons.length
      : 0,

    verified: Boolean(p.verified),
  };
}

/* ------------------------------------------------------------------ */
/* Edit state: flat display object -> flat modal form state (strings)  */
/* ------------------------------------------------------------------ */

export function buildEditState(displayProfile) {
  const d = displayProfile ?? {};
  return {
    name: d.name ?? "",
    branch: d.branch ?? "",
    collegeTier: d.collegeTier ?? "",
    cgpa: d.cgpa ?? "",
    attendance: d.attendance ?? "",
    backlogs: d.backlogs ?? "",
    codingSkills: d.codingSkills ?? "",
    dsaScore: d.dsaScore ?? "",
    aptitudeScore: d.aptitudeScore ?? "",
    communicationSkills: d.communicationSkills ?? "",
    mlKnowledge: d.mlKnowledge ?? "",
    systemDesign: d.systemDesign ?? "",
    openSourceContributions: d.openSourceContributions ?? "",
    extracurriculars: d.extracurriculars ?? "",
    githubRepositories: d.githubRepositories ?? "",
    linkedinConnections: d.linkedinConnections ?? "",
    volunteerExperience: d.volunteerExperience ?? "",
  };
}

/* ------------------------------------------------------------------ */
/* PUT payload: last loaded backend profile + edit state -> full       */
/* StudentProfile body for PUT /api/profile/{id}                       */
/* ------------------------------------------------------------------ */

export function buildProfilePayload(backendProfile, editState) {
  const p = backendProfile ?? {};
  const e = editState ?? {};
  const ml = p.ml_inputs ?? {};
  const additional = p.additional_info ?? {};
  const education = p.education ?? {};
  const personal = p.personal ?? {};

  return {
    profile_id: p.profile_id ?? null,

    personal: {
      ...personal,
      name: e.name?.trim() || personal.name || null,
    },

    education: {
      ...education,
      branch: e.branch || education.branch || null,
      cgpa: parseNumberOrNull(e.cgpa) ?? education.cgpa ?? null,
    },

    /* Read-only structural sections this phase: preserved as stored. */
    skills: p.skills ?? {},
    experience: p.experience ?? [],
    internships: p.internships ?? [],
    projects: p.projects ?? [],
    certifications: p.certifications ?? [],
    achievements: p.achievements ?? {},

    ml_inputs: {
      ...ml,
      college_tier:
        TIER_CANONICAL[e.collegeTier] ?? e.collegeTier ?? ml.college_tier ?? null,
      backlogs: parseIntegerOrNull(e.backlogs) ?? ml.backlogs ?? null,
      coding_skills: parseNumberOrNull(e.codingSkills) ?? ml.coding_skills ?? null,
      dsa_score: parseNumberOrNull(e.dsaScore) ?? ml.dsa_score ?? null,
      aptitude_score:
        parseNumberOrNull(e.aptitudeScore) ?? ml.aptitude_score ?? null,
      communication_skills:
        parseNumberOrNull(e.communicationSkills) ?? ml.communication_skills ?? null,
      ml_knowledge: parseNumberOrNull(e.mlKnowledge) ?? ml.ml_knowledge ?? null,
      system_design: parseNumberOrNull(e.systemDesign) ?? ml.system_design ?? null,
      open_source_contributions:
        parseIntegerOrNull(e.openSourceContributions) ??
        ml.open_source_contributions ??
        null,
      extracurriculars:
        parseIntegerOrNull(e.extracurriculars) ?? ml.extracurriculars ?? null,
    },

    additional_info: {
      ...additional,
      attendance: parseNumberOrNull(e.attendance) ?? additional.attendance ?? null,
      github_repositories:
        parseIntegerOrNull(e.githubRepositories) ??
        additional.github_repositories ??
        null,
      linkedin_connections:
        parseIntegerOrNull(e.linkedinConnections) ??
        additional.linkedin_connections ??
        null,
      volunteer_experience:
        e.volunteerExperience || additional.volunteer_experience || null,
      /* age, gender, logical_reasoning, mock_interview, leadership,
         sleep_hours, study_hours: not exposed this phase — preserved. */
    },

    /* Server-controlled fields below are intentionally NOT sent from the
       modal; the backend restores them on PUT:
       provenance, verified, prediction_history, assessment_evidence,
       original_resume_values. */
  };
}
