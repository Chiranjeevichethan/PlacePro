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

import { API_BASE_URL, authenticatedFetch } from './apiTransport.js';
import { buildExperimentalV1Payload } from './experimentalV1Payload.js';
export { API_BASE_URL } from './apiTransport.js';

/**
 * Branch vocabulary of the production model:
 * CSE, IT, ECE, EE, ME, CE, Chemical.
 *
 * The Information-Science family is a frontend label; the model's dataset
 * has no ISE category, so those spellings are mapped to "CSE". This is the
 * existing mapping (no new categories are invented).
 */
const BRANCH_SYNONYMS = {
  ISE: "CSE",
  "Information Science": "CSE",
  "Information Science and Engineering": "CSE",
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
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the profile service. Please make sure the FastAPI backend is running."
    , { cause });
  }

  if (!response.ok) {
    if (response.status === 404) {
      const error = new Error("Student profile was not found.");
      error.code = 'PROFILE_NOT_FOUND';
      error.status = 404;
      throw error;
    }

    throw new Error("Unable to load student profile. Please try again.");
  }

  let data;

  try {
    data = await response.json();
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error("Unable to load student profile. Please try again.", { cause });
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
export async function updateStudentProfile(profileId, payload, requestId) {
  let response;

  try {
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        ...(requestId ? { headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId } } : {}),
      }
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the profile service. Please make sure the FastAPI backend is running."
    , { cause });
  }

  if (!response.ok) {
    if (response.status === 409) {
      const error = new Error('Profile changed since it was loaded. Reload it and review your edits before saving.');
      error.status = 409;
      throw error;
    }
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error("Unable to save profile changes. Please try again.", { cause });
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
 *     readiness_score,          // number 0-100, may be fractional (rule-based)
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
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/readiness`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the readiness service. Please make sure the FastAPI backend is running."
    , { cause });
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error("Unable to load readiness data. Please try again.", { cause });
  }

  /* Malformed 200: validate the required top-level structure instead of
     substituting zeros or inventing values. */
  if (
    !data ||
    typeof data !== "object" ||
    typeof data.readiness_score !== "number" ||
    !Number.isFinite(data.readiness_score) ||
    data.readiness_score < 0 || data.readiness_score > 100 ||
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
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/recommendations${
        query ? `?${query}` : ""
      }`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the recommendations service. Please make sure the FastAPI backend is running."
    , { cause });
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error("Unable to load recommendations. Please try again.", { cause });
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
 *     readiness_score, readiness_level, readiness_breakdown,
 *     strengths[], skill_gaps[], improvement_plan[]
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
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(
        profileId
      )}/placement-summary`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the placement summary service. Please make sure the FastAPI backend is running."
    , { cause });
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
      } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "The placement summary service returned an unexpected response. Please try again."
    , { cause });
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
 *                assessment_score, assessment_verified, level,
 *                evidence_status, evidence_sources, profile_confirmed,
 *                assessment_timestamp }]
 *   }
 *
 * The backend is authoritative: counts, scores, and histories are returned
 * as-is — empty histories mean count 0 / nulls, never substituted values.
 * Throws an Error with a user-readable message on any failure.
 */
export async function fetchPerformance(profileId) {
  let response;

  try {
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/performance`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the performance service. Please make sure the FastAPI backend is running."
    , { cause });
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
      } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "The performance service returned an unexpected response. Please try again."
    , { cause });
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

const toInteger = (value) => {
  const number = toNumber(value);
  return Number.isInteger(number) ? number : NaN;
};

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
 *   coding_skills              ← codingSkill        (UI 1–10 = model scale)
 *   dsa_score                  ← dsaScore
 *   aptitude_score             ← aptitudeScore
 *   communication_skills       ← communicationSkill (UI 1–10 = model scale)
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
 * count fields must be integers. Categorical encoding is left to
 * the backend pipeline — raw strings are sent.
 */
export function buildPredictionPayload(formData) {
  return {
    branch: mapBranch(formData.branch),
    college_tier: mapCollegeTier(formData.collegeTier),
    cgpa: toNumber(formData.cgpa),
    backlogs: toInteger(formData.backlogs),
    coding_skills: toNumber(formData.codingSkill),
    dsa_score: toNumber(formData.dsaScore),
    aptitude_score: toNumber(formData.aptitudeScore),
    communication_skills: toNumber(formData.communicationSkill),
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
    response = await authenticatedFetch(`${API_BASE_URL}/api/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the prediction service. Please make sure the FastAPI backend is running."
    , { cause });
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
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
  const probabilityValue = data?.placement_probability;
  const confidenceValue = data?.confidence;

  if (
    typeof probabilityValue !== 'number' || !Number.isFinite(probabilityValue) || probabilityValue < 0 || probabilityValue > 1 ||
    typeof confidenceValue !== 'number' || !Number.isFinite(confidenceValue) || confidenceValue < 0 || confidenceValue > 1 ||
    !['PLACED', 'NOT PLACED'].includes(data?.prediction) ||
    typeof data?.model_version !== 'string' || !data.model_version.trim()
  ) {
    throw new Error(
      "The prediction service returned an invalid response. Please try again."
    );
  }

  return {
    probability: Math.round(probabilityValue * 100),
    status:
      data.prediction === "PLACED" ? "LIKELY PLACED" : "PLACEMENT RISK",
    confidence: Math.round(confidenceValue * 100),
    modelVersion: data.model_version,
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

const mapSalaryBranch = (branch) => SALARY_BRANCH_SYNONYMS[branch] ?? branch;

/**
 * Map the salary form data (prefilled from the student profile) to the
 * model fields expected by POST /api/salary-predict. Nothing else is sent -
 * in particular no student id, placement status, or stored salary value:
 *
 *   branch                     <- branch (canonical or ISE family -> "CSE")
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
 * A known profile collegeTier is supplied to the existing optional API field.
 * Missing tier is omitted and retains the backend's configured fallback.
 *
 * Unlike the placement form, coding_skills / communication_skills arrive on
 * the profile's existing 0-10 scale and are sent unchanged. All values are
 * real numbers (never numeric strings, null, or NaN); count fields are
 * required to be integers. Categorical encoding is left to the backend
 * pipeline - raw strings are sent.
 */
export function buildSalaryPayload(formData) {
  return {
    branch: mapSalaryBranch(formData.branch),
    ...(typeof formData.collegeTier === 'string' && formData.collegeTier.trim()
      ? { college_tier: mapCollegeTier(formData.collegeTier) } : {}),
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
    response = await authenticatedFetch(`${API_BASE_URL}/api/salary-predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the salary prediction service. Please make sure the backend is running."
    , { cause });
  }

  if (!response.ok) {
    if (response.status === 422) {
      let detail = null;

      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "The salary prediction service returned an unexpected response. Please try again."
    , { cause });
  }

  /* Malformed 200: validate the required value instead of displaying
     undefined/NaN or substituting an invented salary. */
  const salaryValue = data?.predicted_salary_lpa;

  if (typeof salaryValue !== 'number' || !Number.isFinite(salaryValue) || salaryValue < 0 ||
      typeof data?.model_version !== 'string' || !data.model_version.trim()) {
    throw new Error(
      "The salary prediction service returned an unexpected response. Please try again."
    );
  }

  return {
    predictedSalaryLpa: salaryValue,
    modelVersion: data.model_version,
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
    diagnostics: data.diagnostics ?? {},
    extraction_summary: data.extraction_summary ?? {},
  };
}

/** Analyze a re-upload without creating, selecting or modifying a profile. */
export async function analyzeResumeForReview(file, profile) {
  if (!profile?.profile_id || !Number.isInteger(profile.revision) || profile.revision < 1) {
    throw new Error('Reload your profile before uploading a resume.');
  }
  const formData = new FormData();
  formData.append('file', file);
  formData.append('revision', String(profile.revision));
  let response;
  try {
    response = await authenticatedFetch(`${API_BASE_URL}/api/profile/${encodeURIComponent(profile.profile_id)}/resume-preview`, { method: 'POST', body: formData });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error('Cannot reach the resume service. Please make sure the backend is running.', { cause });
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error('The resume service returned an unexpected response. Please try again.'); }
  if (!response.ok) throw Object.assign(new Error(response.status === 409
    ? 'Profile changed. Reload it and upload the resume again.'
    : typeof data.detail === 'string' ? data.detail : formatValidationError(data.detail)), { status: response.status });
  if (data.profile?.profile_id !== profile.profile_id || data.profile?.revision !== profile.revision) {
    throw new Error('The resume service returned an unexpected response. Please try again.');
  }
  return validateDraftFromResumeResponse(data);
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
export async function createProfileFromResume(file, requestId) {
  const formData = new FormData();
  formData.append("file", file); // field name matches the backend schema

  let response;

  try {
    response = await authenticatedFetch(`${API_BASE_URL}/api/profile/from-resume`, {
      method: "POST",
      body: formData, // fetch sets multipart boundary; no manual Content-Type
      ...(requestId ? { headers: { 'Idempotency-Key': requestId } } : {}),
    });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the resume service. Please make sure the backend is running."
    , { cause });
  }

  if (!response.ok) {
    let detail = null;

    try {
      const body = await response.json();
      detail = body?.detail ?? null;
    } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "The resume service returned an unexpected response. Please try again."
    , { cause });
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
export async function verifyStudentProfile(profileBody, requestId) {
  if (!profileBody || typeof profileBody !== "object") {
    throw new Error(
      "The reviewed profile is missing. Please upload your resume again before verifying."
    );
  }

  let response;

  try {
    response = await authenticatedFetch(`${API_BASE_URL}/api/profile/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(profileBody),
      ...(requestId ? { headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId } } : {}),
    });
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the profile service. Please make sure the backend is running."
    , { cause });
  }

  if (!response.ok) {
    let detail = null;

    try {
      const body = await response.json();
      detail = body?.detail ?? null;
    } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
      // Body could not be parsed; fall back to generic messages below.
    }

    if (response.status === 422) {
      throw new Error(
        typeof detail === "string" && detail.trim() !== ""
          ? detail
          : "The profile could not be verified. Please check the details and try again."
      );
    }

    if (response.status === 409) {
      const error = new Error('Profile changed since it was loaded. Reload it and review the latest values before confirming.');
      error.status = 409;
      throw error;
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "The profile service returned an unexpected response. Please try again."
    , { cause });
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
   EXPERIMENTAL V1 PLACEMENT PREDICTION
   ================================================================ */

async function requestExperimentalV1(payload) {
  let response;

  try {
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/experimental/v1/predict`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the experimental V1 prediction service. Please make sure the backend is running.",
      { cause }
    );
  }

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw Object.assign(new Error(
        response.status === 401
          ? "Your session has expired. Sign in again."
          : "Security check failed. Refresh the session and try again."
      ), { status: response.status });
    }

    if (response.status === 422) {
      let detail = null;
      try {
        const body = await response.json();
        detail = body?.detail ?? null;
      } catch {
        // Use the fallback validation message.
      }
      throw new Error(formatValidationError(detail));
    }

    throw new Error(
      `Experimental V1 prediction failed (HTTP ${response.status}). Please try again.`
    );
  }

  return response.json();
}

function normalizeExperimentalV1Response(data) {
  const probability = data?.placement_probability;
  const confidence = data?.confidence;

  if (
    typeof probability !== "number" ||
    !Number.isFinite(probability) ||
    probability < 0 ||
    probability > 1 ||
    typeof confidence !== "number" ||
    !Number.isFinite(confidence) ||
    confidence < 0 ||
    confidence > 1 ||
    !["Placed", "Not Placed"].includes(data?.prediction) ||
    typeof data?.model_version !== "string" ||
    !data.model_version.trim() ||
    data?.experimental !== true ||
    typeof data?.synthetic_data_notice !== "string" ||
    !data.synthetic_data_notice.trim()
  ) {
    throw new Error(
      "The experimental V1 service returned an invalid response. Please try again."
    );
  }

  return {
    probability: Math.round(probability * 100),
    status: data.prediction === "Placed" ? "LIKELY PLACED" : "PLACEMENT RISK",
    confidence: Math.round(confidence * 100),
    modelVersion: data.model_version,
    experimental: data.experimental,
    syntheticDataNotice: data.synthetic_data_notice,
  };
}

export async function predictExperimentalV1(formData) {
  const payload = buildExperimentalV1Payload(formData);
  const data = await requestExperimentalV1(payload);
  return normalizeExperimentalV1Response(data);
}
/* ================================================================
   MOCK TEST ASSESSMENT (Phase 6B)
   ================================================================ */

/**
 * Assessment requests retain HTTP status and retry metadata so callers can
 * distinguish expiry, duplicate completion, cooldown and uncertain delivery.
 */
async function assessmentRequest(path, options, fallbackMessage) {
  let response;
  try {
    response = await authenticatedFetch(API_BASE_URL + path, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
      ...options,
    });
  } catch (cause) {
    const error = new Error(
      cause?.name === "TimeoutError"
        ? "The assessment request timed out. Check its status before trying again."
        : "Cannot reach the assessment service. Please check your connection and try again."
    , { cause });
    error.status = null;
    throw error;
  }

  let body = null;
  try {
    body = await response.json();
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    // A failed/malformed response still carries its HTTP status.
  }

  if (!response.ok) {
    const detail = body?.detail;
    const message =
      response.status === 422 && Array.isArray(detail)
        ? formatValidationError(detail)
        : typeof detail === "string" && detail.trim()
          ? detail
          : response.status === 410
            ? "This assessment has expired. Late answers cannot be scored."
            : response.status === 409
              ? "This assessment has already been submitted. Checking the saved result."
              : fallbackMessage;
    const error = new Error(message);
    error.status = response.status;
    const bodySeconds = Number(body?.retry_after_seconds);
    const headerSeconds = Number(response.headers.get("Retry-After"));
    error.retryAfterSeconds =
      Number.isFinite(bodySeconds) && bodySeconds > 0
        ? bodySeconds
        : Number.isFinite(headerSeconds) && headerSeconds > 0
          ? headerSeconds
          : null;
    error.nextAllowedAt =
      typeof body?.next_allowed_at === "string" ? body.next_allowed_at : null;
    throw error;
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    const error = new Error(
      "The assessment service returned an unexpected response. Check the assessment status."
    );
    error.status = response.status;
    throw error;
  }
  return body;
}

/** Start a server-selected session. No score or deadline is invented here. */
export async function startAssessment(profileId, skill, numQuestions, requestId) {
  return assessmentRequest(
    "/api/assessment/start",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profileId,
        skill,
        num_questions: numQuestions,
      }),
      ...(requestId ? { headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId } } : {}),
    },
    "Unable to start the assessment. Please try again."
  );
}

/** Submit answer text; the backend owns scoring and submission policy. */
export async function submitAssessment(assessmentId, profileId, answers, requestId) {
  return assessmentRequest(
    "/api/assessment/" + encodeURIComponent(assessmentId) + "/submit",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, answers }),
      ...(requestId ? { headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId } } : {}),
    },
    "Unable to submit the assessment. Please try again."
  );
}

/** Reload authoritative timing/status and, after completion, the public result. */
export async function fetchAssessment(assessmentId) {
  return assessmentRequest(
    "/api/assessment/" + encodeURIComponent(assessmentId),
    {},
    "Unable to load the assessment. Please try again."
  );
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
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/assessments`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the assessment history service. Please make sure the FastAPI backend is running."
    , { cause });
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error("Unable to load assessment history. Please try again.", { cause });
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
    response = await authenticatedFetch(
      `${API_BASE_URL}/api/profile/${encodeURIComponent(profileId)}/skills`
    );
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error(
      "Cannot reach the skills service. Please make sure the FastAPI backend is running."
    , { cause });
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
  } catch (cause) {
    if (cause?.status === 401 || cause?.status === 403) throw cause;
    throw new Error("Unable to load the skills view. Please try again.", { cause });
  }

  if (!data || typeof data !== "object") {
    throw new Error(
      "The skills service returned an unexpected response. Please try again."
    );
  }

  return data;
}
