/**
 * PlacePro API service.
 *
 * Talks to the FastAPI prediction backend (production model
 * "placepro-final-v1") at POST /api/predict and normalizes the response
 * for the UI. The backend result is authoritative: no probability,
 * confidence, or model-version values are computed in the frontend.
 *
 * Phase 6B adds the Mock Test assessment endpoints (start/submit/fetch
 * assessment, assessment history, and the profile skills view). The
 * backend is again authoritative: questions, scoring, and statuses are
 * returned as-is — nothing is mocked or recomputed here.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8765";

/**
 * Branch vocabulary of the production model:
 * CSE, IT, ECE, EE, ME, CE, Chemical.
 *
 * "Information Science" is the frontend's existing synonym for the
 * Information-Science family; the backend maps that family to "CSE".
 * This is the only synonym kept here — no other branch mappings exist.
 */
const BRANCH_SYNONYMS = {
  "Information Science": "CSE",
};

/** Frontend tier values ("1" | "2" | "3") → canonical backend values. */
const COLLEGE_TIERS = {
  1: "Tier-1",
  2: "Tier-2",
  3: "Tier-3",
};

/**
 * Fetch the stored student profile from the backend.
 *
 * GET /api/profile/{id} -> { profile, completion, message }
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchStudentProfile(profileId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}`
    );
  } catch {
    throw new Error(
      "Cannot reach the profile service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Student profile was not found.");
    }

    throw new Error("Unable to load student profile. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to load student profile. Please try again.");
  }

  if (!data?.profile) {
    throw new Error("Unable to load student profile. Please try again.");
  }

  return data;
}

/**
 * Save edits to the stored student profile.
 *
 * PUT /api/profile/{id} with the full editable profile body ->
 * { profile, completion, message } (the updated profile).
 * Throws an Error with a user-readable message on any failure.
 */
export async function updateStudentProfile(profileId, payload) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      }
    );
  } catch {
    throw new Error(
      "Cannot reach the profile service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(formatValidationError(detail));
    }

    if (response.status === 404) {
      throw new Error("Student profile was not found.");
    }

    throw new Error("Unable to save profile changes. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to save profile changes. Please try again.");
  }

  if (!data?.profile) {
    throw new Error("Unable to save profile changes. Please try again.");
  }

  return data;
}

/**
 * Fetch the placement readiness + skill-gap analysis from the backend.
 *
 * GET /api/profile/{id}/readiness -> ReadinessResponse:
 *   {
 *     profile_id,
 *     readiness_score,          // integer 0-100 (rule-based, NOT the ML probability)
 *     readiness_level,          // e.g. "Placement Ready"
 *     readiness_breakdown,      // documented 0-100 score components
 *     strengths: [{ skill, category?, evidence? }],
 *     skill_gaps: [{ skill, category, priority, reason }],
 *     improvement_plan: [{ priority, skill, reason, action }],
 *     profile_completeness: { percentage, missing_fields }
 *   }
 *
 * The backend is authoritative: nothing here is computed or substituted.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchStudentReadiness(profileId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/readiness`
    );
  } catch {
    throw new Error(
      "Cannot reach the readiness service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Student readiness data was not found.");
    }

    throw new Error("Unable to load readiness data. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to load readiness data. Please try again.");
  }

  /* Malformed 200: validate the required top-level structure instead of
     substituting zeros or inventing values. */
  if (
    !data ||
    typeof data !== "object" ||
    !Number.isFinite(Number(data.readiness_score)) ||
    typeof data.readiness_level !== "string" ||
    !data.readiness_breakdown ||
    typeof data.readiness_breakdown !== "object"
  ) {
    throw new Error(
      "The readiness service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Fetch ranked company recommendations for a profile.
 *
 * GET /api/profile/{id}/recommendations?limit=... -> RecommendationsResponse:
 *   {
 *     profile_id,
 *     recommendations: {
 *       recommended:      [RecommendationItem],  // backend-ranked
 *       eligible:         [RecommendationItem],
 *       incomplete:       [RecommendationItem],
 *       not_recommended:  [RecommendationItem]
 *     }
 *   }
 *
 * RecommendationItem (all fields consumed defensively; only the first five
 * are required by the backend schema):
 *   company_id, company_name, status, recommendation_score (0-100),
 *   eligibility_status, skill_match { score, required_matched,
 *   required_missing, preferred_matched, preferred_missing },
 *   readiness_score, readiness_level, placement_probability (0-1 | null),
 *   reasons[], improvement_actions[], missing_information[]
 *
 * The backend is authoritative: companies, ordering, and every score come
 * from the response — nothing is computed or substituted here.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchCompanyRecommendations(profileId, limit) {
  const params = new URLSearchParams();
  if (Number.isFinite(Number(limit)) && limit !== null && limit !== undefined) {
    params.set("limit", String(Math.round(Number(limit))));
  }
  const query = params.toString();

  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/recommendations${
        query ? `?${query}` : ""
      }`
    );
  } catch {
    throw new Error(
      "Cannot reach the recommendations service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Company recommendations were not found.");
    }

    throw new Error("Unable to load recommendations. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to load recommendations. Please try again.");
  }

  /* Malformed 200: validate the required structure instead of substituting
     demo companies or empty groups. */
  const groups = data?.recommendations;
  const hasValidGroup = (value) =>
    value === undefined || value === null || Array.isArray(value);

  if (
    !data ||
    typeof data !== "object" ||
    typeof data.profile_id !== "string" ||
    !groups ||
    typeof groups !== "object" ||
    !hasValidGroup(groups.recommended) ||
    !hasValidGroup(groups.eligible) ||
    !hasValidGroup(groups.incomplete) ||
    !hasValidGroup(groups.not_recommended)
  ) {
    throw new Error(
      "The recommendations service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Fetch the combined placement prediction + readiness summary for a profile.
 *
 * GET /api/profile/{profileId}/placement-summary ->
 *   {
 *     ready_for_prediction: boolean,
 *     placement_probability: number (0-1) | null,   // null before first run
 *     prediction: "PLACED" | "NOT PLACED" | null,
 *     confidence: number (0-1) | null,
 *     model_version: string | null,
 *     missing_fields: string[],
 *     reason: string | null,
 *     readiness: { ...full Phase 12 readiness response }
 *   }
 *
 * The backend is authoritative: probability/confidence/prediction are
 * returned as-is and may legitimately be null before the first prediction
 * — callers must render an honest empty state, never 0%.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchPlacementSummary(profileId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(
        profileId
      )}/placement-summary`
    );
  } catch {
    throw new Error(
      "Cannot reach the placement summary service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Placement summary was not found.");
    }

    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(
        typeof detail === "string" && detail.trim() !== ""
          ? detail
          : "Profile must be verified before a placement summary can be generated."
      );
    }

    throw new Error("Unable to load the placement summary. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The placement summary service returned an unexpected response. Please try again."
    );
  }

  /* Malformed 200: require an object; the nullable fields are validated
     defensively by the caller (null is a valid "no prediction yet" state). */
  if (!data || typeof data !== "object") {
    throw new Error(
      "The placement summary service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Fetch consolidated performance analytics for a profile.
 *
 * GET /api/profile/{profileId}/performance ->
 *   {
 *     profile_id,
 *     verified: boolean,
 *     summary: {
 *       predictions_count, latest_prediction, latest_probability,
 *       latest_timestamp, highest_probability, lowest_probability,
 *       assessments_count, skills_assessed, average_score,
 *       latest_skill, latest_score, latest_level, latest_timestamp
 *     },
 *     prediction_history: [{ prediction, placement_probability, timestamp, ... }],
 *     assessment_history: [{ skill, score, level, attempt, verified,
 *                            assessment_id, timestamp }],
 *     readiness: { ...full readiness response },
 *     skills: [{ skill, resume_detected, user_entered,
 *                assessment_score, assessment_verified, level }]
 *   }
 *
 * The backend is authoritative: counts, scores, and histories are returned
 * as-is — empty histories mean count 0 / nulls, never substituted values.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchPerformance(profileId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/performance`
    );
  } catch {
    throw new Error(
      "Cannot reach the performance service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Student performance data was not found.");
    }

    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(
        typeof detail === "string" && detail.trim() !== ""
          ? detail
          : "Profile must be verified before performance analytics can be generated."
      );
    }

    throw new Error("Unable to load performance data. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The performance service returned an unexpected response. Please try again."
    );
  }

  /* Malformed 200: validate the top-level structure instead of
     substituting empty summaries. */
  if (
    !data ||
    typeof data !== "object" ||
    !data.summary ||
    typeof data.summary !== "object"
  ) {
    throw new Error(
      "The performance service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/** Readable labels for backend validation fields (HTTP 422 messages). */
const FIELD_LABELS = {
  branch: "Branch",
  college_tier: "College Tier",
  cgpa: "CGPA",
  backlogs: "Backlogs",
  coding_skills: "Coding Skills",
  dsa_score: "DSA Score",
  aptitude_score: "Aptitude Score",
  communication_skills: "Communication Skills",
  ml_knowledge: "ML Knowledge",
  system_design: "System Design",
  internships: "Internships",
  projects_count: "Projects",
  certifications: "Certifications",
  hackathons: "Hackathons",
  open_source_contributions: "Open Source Contributions",
  extracurriculars: "Extracurricular Activities",
};

const toNumber = (value) => {
  if (value === "" || value === null || value === undefined) {
    return NaN;
  }

  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : NaN;
};

const toInteger = (value) => Math.round(toNumber(value));

const mapBranch = (branch) => BRANCH_SYNONYMS[branch] ?? branch;

const mapCollegeTier = (tier) => COLLEGE_TIERS[tier] ?? tier;

/**
 * Map the prediction form data to the EXACT 16 model fields expected by
 * POST /api/predict. Nothing else is sent:
 *
 *   branch                     ← branch (ISE display value → "CSE")
 *   college_tier               ← collegeTier ("1" → "Tier-1", etc.)
 *   cgpa                       ← cgpa
 *   backlogs                   ← backlogs
 *   coding_skills              ← codingSkill / 10   (0–100 UI → 0–10)
 *   dsa_score                  ← dsaScore
 *   aptitude_score             ← aptitudeScore
 *   communication_skills       ← communicationSkill / 10
 *   ml_knowledge               ← mlKnowledge
 *   system_design              ← systemDesign
 *   internships                ← internships
 *   projects_count             ← projects
 *   certifications             ← certifications
 *   hackathons                 ← hackathons
 *   open_source_contributions  ← openSourceContributions
 *   extracurriculars           ← extracurricular
 *
 * All values are real numbers (never numeric strings, null, or NaN);
 * count fields are rounded to integers. Categorical encoding is left to
 * the backend pipeline — raw strings are sent.
 */
export function buildPredictionPayload(formData) {
  return {
    branch: mapBranch(formData.branch),
    college_tier: mapCollegeTier(formData.collegeTier),
    cgpa: toNumber(formData.cgpa),
    backlogs: toInteger(formData.backlogs),
    coding_skills: toNumber(formData.codingSkill) / 10,
    dsa_score: toNumber(formData.dsaScore),
    aptitude_score: toNumber(formData.aptitudeScore),
    communication_skills: toNumber(formData.communicationSkill) / 10,
    ml_knowledge: toNumber(formData.mlKnowledge),
    system_design: toNumber(formData.systemDesign),
    internships: toInteger(formData.internships),
    projects_count: toInteger(formData.projects),
    certifications: toInteger(formData.certifications),
    hackathons: toInteger(formData.hackathons),
    open_source_contributions: toInteger(formData.openSourceContributions),
    extracurriculars: toInteger(formData.extracurricular),
  };
}

const formatValidationError = (detail) => {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        const field = Array.isArray(item?.loc)
          ? item.loc[item.loc.length - 1]
          : null;
        const message = item?.msg ?? "Invalid value";
        const label = field ? (FIELD_LABELS[field] ?? field) : null;
        return label ? `${label}: ${message}` : message;
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  return "The prediction service rejected the submitted values. Please check the form and try again.";
};

async function requestPrediction(payload) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "Cannot reach the prediction service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(formatValidationError(detail));
    }

    throw new Error(
      `Prediction request failed (HTTP ${response.status}). Please try again.`
    );
  }

  return response.json();
}

/**
 * Normalize the backend response for the existing UI objects:
 *
 *   placement_probability (0–1) → probability (percentage)
 *   prediction ("PLACED" | "NOT PLACED") → status ("LIKELY PLACED" | "PLACEMENT RISK")
 *   confidence (0–1) → confidence (percentage)
 *   model_version → modelVersion (displayed as-is)
 */
function normalizePredictionResponse(data) {
  const probabilityValue = toNumber(data?.placement_probability);
  const confidenceValue = toNumber(data?.confidence);

  if (!Number.isFinite(probabilityValue) || !Number.isFinite(confidenceValue)) {
    throw new Error(
      "The prediction service returned an invalid response. Please try again."
    );
  }

  return {
    probability: Math.round(probabilityValue * 100),
    status:
      data.prediction === "PLACED" ? "LIKELY PLACED" : "PLACEMENT RISK",
    confidence: Math.round(confidenceValue * 100),
    modelVersion: data.model_version ?? null,
  };
}

/* ================================================================
   SALARY PREDICTION (Phase 5C)
   ================================================================ */

/**
 * Branch synonyms for the salary model request. Reuses the placement
 * mapping (BRANCH_SYNONYMS, "Information Science" -> "CSE") and adds the
 * Information-Science family spellings that can appear in profile data.
 * Canonical backend branch values are: CSE, IT, ECE, EE, ME, CE, Chemical.
 */
const SALARY_BRANCH_SYNONYMS = {
  ...BRANCH_SYNONYMS,
  ISE: "CSE",
  "Information Science and Engineering": "CSE",
};

/**
 * College-tier spellings that can appear in profile data -> canonical
 * backend values (Tier-1 / Tier-2 / Tier-3). Reuses the placement form's
 * "1" | "2" | "3" mapping and adds the display spellings.
 */
const SALARY_COLLEGE_TIERS = {
  ...COLLEGE_TIERS,
  "Tier 1": "Tier-1",
  "Tier 2": "Tier-2",
  "Tier 3": "Tier-3",
};

const mapSalaryBranch = (branch) => SALARY_BRANCH_SYNONYMS[branch] ?? branch;

const mapSalaryCollegeTier = (tier) => SALARY_COLLEGE_TIERS[tier] ?? tier;

/**
 * Map the salary form data (prefilled from the student profile) to the
 * EXACT 16 model fields expected by POST /api/salary-predict. Nothing else
 * is sent - in particular no student id, placement status, or stored
 * salary value:
 *
 *   branch                     <- branch (canonical or ISE family -> "CSE")
 *   college_tier               <- collegeTier (canonical or "Tier 2" -> "Tier-2")
 *   cgpa                       <- cgpa
 *   backlogs                   <- backlogs
 *   coding_skills              <- codingSkills      (profile 0-10 scale)
 *   dsa_score                  <- dsaScore
 *   aptitude_score             <- aptitudeScore
 *   communication_skills       <- communicationSkills (profile 0-10 scale)
 *   ml_knowledge               <- mlKnowledge
 *   system_design              <- systemDesign
 *   internships                <- internships
 *   projects_count             <- projects
 *   certifications             <- certifications
 *   hackathons                 <- hackathons
 *   open_source_contributions  <- openSourceContributions
 *   extracurriculars           <- extracurriculars
 *
 * Unlike the placement form, coding_skills / communication_skills arrive on
 * the profile's existing 0-10 scale and are sent unchanged. All values are
 * real numbers (never numeric strings, null, or NaN); count fields are
 * rounded to integers. Categorical encoding is left to the backend
 * pipeline - raw strings are sent.
 */
export function buildSalaryPayload(formData) {
  return {
    branch: mapSalaryBranch(formData.branch),
    college_tier: mapSalaryCollegeTier(formData.collegeTier),
    cgpa: toNumber(formData.cgpa),
    backlogs: toInteger(formData.backlogs),
    coding_skills: toNumber(formData.codingSkills),
    dsa_score: toNumber(formData.dsaScore),
    aptitude_score: toNumber(formData.aptitudeScore),
    communication_skills: toNumber(formData.communicationSkills),
    ml_knowledge: toNumber(formData.mlKnowledge),
    system_design: toNumber(formData.systemDesign),
    internships: toInteger(formData.internships),
    projects_count: toInteger(formData.projects),
    certifications: toInteger(formData.certifications),
    hackathons: toInteger(formData.hackathons),
    open_source_contributions: toInteger(formData.openSourceContributions),
    extracurriculars: toInteger(formData.extracurriculars),
  };
}

/**
 * POST /api/salary-predict with the validated 16-field payload.
 *
 * The backend salary model (placepro-salary-v1) is a Ridge regression
 * trained on PLACED students only, so its estimate is conditional on
 * placement. The response is authoritative:
 *   { predicted_salary_lpa: number, model_version: string }
 *
 * Returns { predictedSalaryLpa: number, modelVersion: string | null }.
 * Throws an Error with a user-readable message on any failure (network,
 * 422 validation, 503 unavailable, 500, or malformed response body).
 */
export async function requestSalaryPrediction(payload) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/salary-predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "Cannot reach the salary prediction service. Please make sure the backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(formatValidationError(detail));
    }

    if (response.status === 503) {
      throw new Error(
        "Salary prediction service is currently unavailable. Please try again later."
      );
    }

    if (response.status === 500) {
      throw new Error(
        "Unable to calculate the salary estimate. Please try again."
      );
    }

    throw new Error(
      `Salary prediction request failed (HTTP ${response.status}). Please try again.`
    );
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The salary prediction service returned an unexpected response. Please try again."
    );
  }

  /* Malformed 200: validate the required value instead of displaying
     undefined/NaN or substituting an invented salary. */
  const salaryValue = toNumber(data?.predicted_salary_lpa);

  if (!Number.isFinite(salaryValue)) {
    throw new Error(
      "The salary prediction service returned an unexpected response. Please try again."
    );
  }

  return {
    predictedSalaryLpa: salaryValue,
    modelVersion:
      typeof data.model_version === "string" ? data.model_version : null,
  };
}

/* ================================================================
   RESUME → DRAFT PROFILE → VERIFY (Phase 16/18)
   ================================================================ */

const DRAFT_NULLABLE_TEXT_FIELDS = [
  ["personal", "name"],
  ["personal", "email"],
  ["personal", "phone"],
  ["personal", "location"],
  ["personal", "linkedin"],
  ["personal", "github"],
  ["personal", "portfolio"],
  ["education", "degree"],
  ["education", "branch"],
  ["education", "college"],
];

/**
 * Validate the DRAFT StudentProfile returned by POST /api/profile/from-resume.
 *
 * Rejects a response whose shape is not the documented Phase 16 contract
 * (ProfileFromResumeResponse). Every declared field is normalized to exactly
 * null when absent or non-conforming — nothing is invented or defaulted:
 * the "ML prediction inputs" stay null so the honest "Not set" state can be
 * shown until the student provides real values.
 */
function validateDraftFromResumeResponse(data) {
  if (!data || typeof data !== "object" || !data.profile || typeof data.profile !== "object") {
    throw new Error(
      "The resume service returned an unexpected response. Please try again."
    );
  }

  if (typeof data.completion !== "object" || data.completion === null) {
    throw new Error(
      "The resume service returned an unexpected response. Please try again."
    );
  }

  if (typeof data.message !== "string") {
    throw new Error(
      "The resume service returned an unexpected response. Please try again."
    );
  }

  const draft = data.profile;
  /* Start from a verbatim copy of the backend draft so server-controlled
     fields (profile_id, provenance, original_resume_values, ...) are
     preserved exactly as returned — the verify body must be the FULL
     profile as the backend created it. */
  const normalized = JSON.parse(JSON.stringify(draft));
  normalized.verified = false;

  /* Textual declared fields: normalized to exact null when absent or
     non-conforming — nothing is invented or defaulted. */
  const text = (sections, field) => {
    const value = draft?.[sections]?.[field];
    if (typeof value === "string") {
      normalized[sections][field] = value;
    } else if (value !== null && value !== undefined && value !== "") {
      // Wrong type (e.g. number where a string is expected): keep the value
      // visible in the review but normalized, never silently dropped.
      normalized[sections][field] = String(value);
    } else {
      // Exact null (or empty string) — kept as null: displayed as "Not set"
      // and blocking verification until the student enters it.
      normalized[sections][field] = null;
    }
  };

  if (draft.personal && typeof draft.personal === "object") {
    DRAFT_NULLABLE_TEXT_FIELDS.filter(([s]) => s === "personal").forEach(
      ([section, field]) => text(section, field)
    );
  }

  if (draft.education && typeof draft.education === "object") {
    DRAFT_NULLABLE_TEXT_FIELDS.filter(([s]) => s === "education").forEach(
      ([section, field]) => text(section, field)
    );
    const cgpa = draft.education.cgpa;
    normalized.education.cgpa = typeof cgpa === "number" ? cgpa : null;
    const graduationYear = draft.education.graduation_year;
    if (graduationYear === null || graduationYear === undefined) {
      normalized.education.graduation_year = null;
    } else if (Number.isInteger(graduationYear)) {
      normalized.education.graduation_year = graduationYear;
    } else {
      const parsed = Number(graduationYear);
      normalized.education.graduation_year = Number.isInteger(parsed) ? parsed : null;
    }
  }

  /* Structural arrays: kept as-is when they are proper arrays of objects
     (backend-extracted evidence). Anything else is normalized to an empty
     array so the review UI shows an honest "None found" instead of crashing. */
  const isEntryArray = (v) =>
    Array.isArray(v) && v.every((e) => e === null || typeof e === "object");
  normalized.experience = isEntryArray(draft.experience) ? draft.experience : [];
  normalized.internships = isEntryArray(draft.internships) ? draft.internships : [];
  normalized.projects = isEntryArray(draft.projects) ? draft.projects : [];
  normalized.certifications = isEntryArray(draft.certifications)
    ? draft.certifications
    : [];

  if (draft.skills && typeof draft.skills === "object") {
    normalized.skills = {};
    for (const [key, value] of Object.entries(draft.skills)) {
      normalized.skills[key] = Array.isArray(value) ? value : [];
    }
  }

  if (draft.achievements && typeof draft.achievements === "object") {
    normalized.achievements = {};
    for (const [key, value] of Object.entries(draft.achievements)) {
      normalized.achievements[key] = Array.isArray(value) ? value : [];
    }
  }

  /* IMPORTANT: the 10 ML prediction inputs MUST remain missing until the
     student explicitly provides them. They are never inferred from resume
     content; any non-conforming backend value here becomes exact null. */
  if (draft.ml_inputs && typeof draft.ml_inputs === "object") {
    normalized.ml_inputs = {};
    for (const field of [
      "college_tier",
      "backlogs",
      "coding_skills",
      "dsa_score",
      "aptitude_score",
      "communication_skills",
      "ml_knowledge",
      "system_design",
      "open_source_contributions",
      "extracurriculars",
    ]) {
      const value = draft.ml_inputs[field];
      normalized.ml_inputs[field] = value === null || value === undefined ? null : value;
    }
  }

  if (draft.additional_info && typeof draft.additional_info === "object") {
    normalized.additional_info = {};
    for (const [key, value] of Object.entries(draft.additional_info)) {
      normalized.additional_info[key] = value === undefined ? null : value;
    }
  }

  return {
    draftProfile: normalized,
    completion: data.completion,
    message: data.message,
    provenance: Array.isArray(data.provenance) ? data.provenance : [],
    confidence:
      data.confidence && typeof data.confidence === "object" ? data.confidence : {},
    feature_availability: Array.isArray(data.feature_availability)
      ? data.feature_availability
      : [],
  };
}

/**
 * Upload a resume and have the backend create a DRAFT profile for review.
 *
 * POST /api/profile/from-resume (multipart/form-data, field "file") ->
 * ProfileFromResumeResponse, i.e.
 *   {
 *     profile: StudentProfile,       // draft (verified: false)
 *     completion: { profile_complete, missing_fields, ... },
 *     message: string,
 *     provenance: [...],             // optional additive fields
 *     confidence: {...},
 *     diagnostics: {...},
 *     extraction_summary: {...},
 *     feature_availability: [...]
 *   }
 *
 * The response is validated against the documented contract and returned
 * as-is (after normalization of declared fields to exact null). Nothing is
 * invented here — especially the 10 ML prediction inputs, which stay
 * missing until the student explicitly provides them.
 * Throws an Error with a user-readable message on any failure.
 */
export async function createProfileFromResume(file) {
  const formData = new FormData();
  formData.append("file", file); // field name matches the backend schema

  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/profile/from-resume`, {
      method: "POST",
      body: formData, // fetch sets multipart boundary; no manual Content-Type
    });
  } catch {
    throw new Error(
      "Cannot reach the resume service. Please make sure the backend is running."
    );
  }

  if (!response.ok) {
    let detail = null;

    try {
      const body = await response.json();
      detail = body?.detail ?? null;
    } catch {
      // Body could not be parsed; fall back to generic messages below.
    }

    if (response.status === 422) {
      throw new Error(
        typeof detail === "string" && detail.trim() !== ""
          ? detail
          : "The uploaded resume was rejected. Please check the file and try again."
      );
    }

    if (response.status === 413) {
      throw new Error(
        "The resume file is too large. Please upload a smaller file."
      );
    }

    throw new Error(
      `Resume upload failed (HTTP ${response.status}). Please try again.`
    );
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The resume service returned an unexpected response. Please try again."
    );
  }

  return validateDraftFromResumeResponse(data);
}

/**
 * Explicitly confirm the reviewed profile.
 *
 * POST /api/profile/verify with the FULL edited StudentProfile as the JSON
 * body. On success the backend stores the profile with verified: true and
 * returns { profile, completion, message } (ProfileResponse).
 *
 * The full profile body (including any null ml_inputs fields) is REQUIRED
 * by the contract, so the caller must pass the exact draft/profile object
 * that was reviewed. No new values are invented here.
 * Throws an Error with a user-readable message on any failure.
 */
export async function verifyStudentProfile(profileBody) {
  if (!profileBody || typeof profileBody !== "object") {
    throw new Error(
      "The reviewed profile is missing. Please upload your resume again before verifying."
    );
  }

  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/profile/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(profileBody),
    });
  } catch {
    throw new Error(
      "Cannot reach the profile service. Please make sure the backend is running."
    );
  }

  if (!response.ok) {
    let detail = null;

    try {
      const body = await response.json();
      detail = body?.detail ?? null;
    } catch {
      // Body could not be parsed; fall back to generic messages below.
    }

    if (response.status === 422) {
      throw new Error(
        typeof detail === "string" && detail.trim() !== ""
          ? detail
          : "The profile could not be verified. Please check the details and try again."
      );
    }

    if (response.status === 404) {
      throw new Error(
        typeof detail === "string" && detail.trim() !== ""
          ? detail
          : "Student profile was not found."
      );
    }

    throw new Error(
      `Profile verification failed (HTTP ${response.status}). Please try again.`
    );
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The profile service returned an unexpected response. Please try again."
    );
  }

  if (!data?.profile || typeof data.completion !== "object") {
    throw new Error(
      "The profile service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Request a placement prediction from the production backend.
 * Throws an Error with a user-readable message on any failure.
 */
export async function predictPlacement(formData) {
  const payload = buildPredictionPayload(formData);

  // Safety net: the form validates before this point, but never send
  // missing/invalid numeric values to the backend. (branch/college_tier
  // are the only string fields and are always non-empty in the payload.)
  const hasInvalidNumber = Object.entries(payload).some(
    ([field, value]) =>
      field !== "branch" &&
      field !== "college_tier" &&
      !Number.isFinite(value)
  );

  if (hasInvalidNumber) {
    throw new Error(
      "Some prediction inputs are missing or invalid. Please check the form and try again."
    );
  }

  const data = await requestPrediction(payload);

  return normalizePredictionResponse(data);
}

/* ================================================================
   MOCK TEST ASSESSMENT (Phase 6B)
   ================================================================ */

/**
 * Start a new mock-test assessment.
 *
 * POST /api/assessment/start with { profile_id, skill, num_questions }.
 * The backend selects the questions and returns the created assessment;
 * that response is authoritative and is returned as-is — no questions,
 * answers, or scores are invented here.
 * Throws an Error with a user-readable message on any failure.
 */
export async function startAssessment(profileId, skill, numQuestions) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/assessment/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        profile_id: profileId,
        skill: skill,
        num_questions: numQuestions,
      }),
    });
  } catch {
    throw new Error(
      "Cannot reach the assessment service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(formatValidationError(detail));
    }

    if (response.status === 404) {
      throw new Error(
        "Could not start the assessment: the profile or skill was not found."
      );
    }

    if (response.status === 429) {
      // Cooldown/attempt-limit: surface the backend's own detail message
      // (e.g. "Please wait before retrying Python. Next attempt allowed
      // after ...") instead of a generic retry error. No local cooldown
      // calculation — the backend is authoritative.
      let rateDetail = null;

      try {
        const body = await response.json();
        rateDetail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(
        typeof rateDetail === "string" && rateDetail.trim() !== ""
          ? rateDetail
          : "Unable to start the assessment. Please try again."
      );
    }

    throw new Error("Unable to start the assessment. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to start the assessment. Please try again.");
  }

  /* Malformed 200: require a JSON object instead of substituting an
     invented assessment; deeper shape checks belong to the consumer. */
  if (!data || typeof data !== "object") {
    throw new Error(
      "The assessment service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Submit a student's answers for an assessment.
 *
 * POST /api/assessment/{assessmentId}/submit with { profile_id, answers }.
 * The backend grades the submission and returns the result; that response
 * is authoritative and is returned as-is — nothing is scored here.
 * Throws an Error with a user-readable message on any failure.
 */
export async function submitAssessment(assessmentId, profileId, answers) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/assessment/${encodeURIComponent(
        assessmentId
      )}/submit`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          profile_id: profileId,
          answers: answers,
        }),
      }
    );
  } catch {
    throw new Error(
      "Cannot reach the assessment service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Body could not be parsed; fall back to the generic message below.
      }

      throw new Error(formatValidationError(detail));
    }

    if (response.status === 404) {
      throw new Error("Assessment was not found.");
    }

    throw new Error("Unable to submit the assessment. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to submit the assessment. Please try again.");
  }

  if (!data || typeof data !== "object") {
    throw new Error(
      "The assessment service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Fetch a previously started assessment (questions + current state).
 *
 * GET /api/assessment/{assessmentId}
 * The response is authoritative and is returned as-is.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchAssessment(assessmentId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/assessment/${encodeURIComponent(assessmentId)}`
    );
  } catch {
    throw new Error(
      "Cannot reach the assessment service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Assessment was not found.");
    }

    throw new Error("Unable to load the assessment. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to load the assessment. Please try again.");
  }

  if (!data || typeof data !== "object") {
    throw new Error(
      "The assessment service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Fetch a profile's past assessment attempts.
 *
 * GET /api/profile/{profileId}/assessments
 * The history returned by the backend is authoritative and is returned
 * as-is — nothing is filtered or recomputed here.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchAssessmentHistory(profileId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/assessments`
    );
  } catch {
    throw new Error(
      "Cannot reach the assessment history service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Assessment history was not found.");
    }

    throw new Error("Unable to load assessment history. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to load assessment history. Please try again.");
  }

  if (!data || typeof data !== "object") {
    throw new Error(
      "The assessment history service returned an unexpected response. Please try again."
    );
  }

  return data;
}

/**
 * Fetch a profile's skill view (per-skill proficiency as tracked by the
 * backend and updated by assessments).
 *
 * GET /api/profile/{profileId}/skills
 * The response is authoritative and is returned as-is.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchSkillsView(profileId) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/skills`
    );
  } catch {
    throw new Error(
      "Cannot reach the skills service. Please make sure the FastAPI backend is running."
    );
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Skill view data was not found.");
    }

    throw new Error("Unable to load the skills view. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Unable to load the skills view. Please try again.");
  }

  if (!data || typeof data !== "object") {
    throw new Error(
      "The skills service returned an unexpected response. Please try again."
    );
  }

  return data;
}
