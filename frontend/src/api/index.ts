// ============================================================
// PLACEPRO - PHASE 18 - API SERVICE LAYER
// ============================================================
// Every existing backend endpoint is wrapped here in a dedicated
// module. Components import from this layer only - no fetch calls
// in components, no duplicated business logic.
// ============================================================

import { apiGet, apiPost, apiPut, apiUpload } from "./client";
import type {
  AllCompanyEligibilityResponse,
  AssessmentHistoryResponse,
  CompanyEligibilityResponse,
  CompanySummary,
  PlacementSummaryResponse,
  PredictionResponse,
  ProfileFromResumeResponse,
  ProfileResponse,
  ReadinessResponse,
  RecommendationsResponse,
  SkillViewEntry,
  SkillsViewResponse,
  StartAssessmentResponse,
  StudentProfile,
  SubmitAssessmentResponse,
} from "../types";

// ---------- Profile (Phase 10) ----------

export const profilesApi = {
  get: (id: string) => apiGet<ProfileResponse>(`/api/profile/${id}`),
  update: (id: string, profile: StudentProfile) =>
    apiPut<ProfileResponse>(`/api/profile/${id}`, profile),
  verify: (profile: StudentProfile) =>
    apiPost<ProfileResponse>("/api/profile/verify", profile),
  predict: (id: string) =>
    apiPost<PredictionResponse>(`/api/profile/${id}/predict`),
};

// ---------- Resume (Phase 9 / 16) ----------

export const resumeApi = {
  fromResume: (file: File) =>
    apiUpload<ProfileFromResumeResponse>("/api/profile/from-resume", file),
};

// ---------- Readiness (Phase 12) ----------

export const readinessApi = {
  get: (id: string) => apiGet<ReadinessResponse>(`/api/profile/${id}/readiness`),
  placementSummary: (id: string) =>
    apiGet<PlacementSummaryResponse>(`/api/profile/${id}/placement-summary`),
};

// ---------- Companies / Eligibility (Phase 13) ----------

export const companiesApi = {
  list: () => apiGet<CompanySummary[]>("/api/companies"),
  eligibilityAll: (profileId: string) =>
    apiGet<AllCompanyEligibilityResponse>(
      `/api/profile/${profileId}/eligibility`,
    ),
  eligibilityFor: (profileId: string, companyId: string) =>
    apiGet<CompanyEligibilityResponse>(
      `/api/profile/${profileId}/eligibility/${companyId}`,
    ),
};

// ---------- Recommendations (Phase 14) ----------

export const recommendationsApi = {
  get: (profileId: string, limit?: number) =>
    apiGet<RecommendationsResponse>(
      `/api/profile/${profileId}/recommendations${
        limit ? `?limit=${limit}` : ""
      }`,
    ),
};

// ---------- Skill Assessment (Phase 17) ----------

export const assessmentApi = {
  start: (profileId: string, skill: string, numQuestions?: number) =>
    apiPost<StartAssessmentResponse>("/api/assessment/start", {
      profile_id: profileId,
      skill,
      num_questions: numQuestions,
    }),
  submit: (
    assessmentId: string,
    profileId: string,
    answers: Record<string, string>,
  ) =>
    apiPost<SubmitAssessmentResponse>(
      `/api/assessment/${assessmentId}/submit`,
      { profile_id: profileId, answers },
    ),
  history: (profileId: string) =>
    apiGet<AssessmentHistoryResponse>(`/api/profile/${profileId}/assessments`),
  skills: (profileId: string) =>
    apiGet<SkillsViewResponse>(`/api/profile/${profileId}/skills`),
};

export type { SkillViewEntry };
