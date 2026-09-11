/**
 * PlacePro API service.
 *
 * Talks to the FastAPI prediction backend (production model
 * "placepro-final-v1") at POST /api/predict and normalizes the response
 * for the UI. The backend result is authoritative: no probability,
 * confidence, or model-version values are computed in the frontend.
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
