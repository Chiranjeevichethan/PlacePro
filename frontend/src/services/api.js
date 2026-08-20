const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8765";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  let data = null;

  try {
    data = await response.json();
  } catch {
    // Response may not contain JSON.
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      `API request failed (${response.status})`;

    throw new Error(
      typeof message === "string" ? message : JSON.stringify(message)
    );
  }

  return data;
}

/**
 * Real PlacePro ML prediction.
 *
 * IMPORTANT:
 * The backend requires all 16 model features.
 * We do NOT invent missing values.
 */
export async function predictPlacement(profile) {
  return request("/api/predict", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      branch: profile.branch,
      college_tier: profile.collegeTier,
      cgpa: Number(profile.cgpa),
      backlogs: Number(profile.backlogs),
      coding_skills: Number(profile.codingSkills),
      dsa_score: Number(profile.dsaScore),
      aptitude_score: Number(profile.aptitudeScore),
      communication_skills: Number(profile.communicationSkills),
      ml_knowledge: Number(profile.mlKnowledge),
      system_design: Number(profile.systemDesign),
      internships: Number(profile.internships),
      projects_count: Number(profile.projects),
      certifications: Number(profile.certifications),
      hackathons: Number(profile.hackathons),
      open_source_contributions: Number(profile.openSourceContributions),
      extracurriculars: Number(profile.extracurriculars),
    }),
  });
}

/**
 * Resume upload.
 */
export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/api/resume/upload", {
    method: "POST",
    body: formData,
  });
}

/**
 * Analyze a resume without creating a profile.
 */
export async function analyzeResume(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/api/resume/analyze", {
    method: "POST",
    body: formData,
  });
}

/**
 * Create a student profile from an uploaded resume.
 */
export async function createProfileFromResume(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/api/profile/from-resume", {
    method: "POST",
    body: formData,
  });
}

/**
 * Get a profile.
 */
export async function getProfile(profileId) {
  return request(`/api/profile/${encodeURIComponent(profileId)}`);
}

/**
 * Update a profile.
 */
export async function updateProfile(profileId, profile) {
  return request(`/api/profile/${encodeURIComponent(profileId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profile),
  });
}

/**
 * Verify a profile.
 */
export async function verifyProfile(profileId) {
  return request("/api/profile/verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      profile_id: profileId,
    }),
  });
}

/**
 * Predict using an already-created verified profile.
 */
export async function predictProfile(profileId) {
  return request(
    `/api/profile/${encodeURIComponent(profileId)}/predict`,
    {
      method: "POST",
    }
  );
}

/**
 * Get readiness.
 */
export async function getReadiness(profileId) {
  return request(
    `/api/profile/${encodeURIComponent(profileId)}/readiness`
  );
}

/**
 * Get placement summary.
 */
export async function getPlacementSummary(profileId) {
  return request(
    `/api/profile/${encodeURIComponent(profileId)}/placement-summary`
  );
}

/**
 * Get active companies.
 */
export async function getCompanies() {
  return request("/api/companies");
}

/**
 * Get company eligibility.
 */
export async function getEligibility(profileId) {
  return request(
    `/api/profile/${encodeURIComponent(profileId)}/eligibility`
  );
}

/**
 * Get company recommendations.
 */
export async function getRecommendations(profileId, limit) {
  const query = limit ? `?limit=${encodeURIComponent(limit)}` : "";

  return request(
    `/api/profile/${encodeURIComponent(profileId)}/recommendations${query}`
  );
}

/**
 * Start a skill assessment.
 */
export async function startAssessment(profileId, skill) {
  return request("/api/assessment/start", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      profile_id: profileId,
      skill,
    }),
  });
}

/**
 * Submit a skill assessment.
 */
export async function submitAssessment(assessmentId, answers) {
  return request(
    `/api/assessment/${encodeURIComponent(assessmentId)}/submit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        answers,
      }),
    }
  );
}

/**
 * Health check.
 */
export async function healthCheck() {
  return request("/health");
}