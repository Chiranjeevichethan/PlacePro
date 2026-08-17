// ============================================================
// PLACEPRO - PHASE 18 - CENTRALIZED API TYPES
// ============================================================
// Single source of truth for the shapes returned by the existing
// FastAPI endpoints (Phases 8-17). These mirror the backend pydantic
// schemas - the frontend never duplicates backend business logic, it
// only types the responses.
// ============================================================

// ---------- Profile (Phase 10) ----------

export interface PersonalInfo {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  linkedin?: string | null;
  github?: string | null;
  portfolio?: string | null;
}

export interface EducationInfo {
  degree?: string | null;
  branch?: string | null;
  college?: string | null;
  cgpa?: number | null;
  graduation_year?: number | null;
}

export interface MlInputs {
  college_tier?: string | null;
  backlogs?: number | null;
  coding_skills?: number | null;
  dsa_score?: number | null;
  aptitude_score?: number | null;
  communication_skills?: number | null;
  ml_knowledge?: number | null;
  system_design?: number | null;
  open_source_contributions?: number | null;
  extracurriculars?: number | null;
}

export interface SkillSet {
  programming_languages: string[];
  frameworks: string[];
  databases: string[];
  cloud: string[];
  ai_ml: string[];
  web_technologies: string[];
  tools: string[];
  other_skills: string[];
}

export interface ExperienceEntry {
  company?: string | null;
  role?: string | null;
  duration?: string | null;
  technologies: string[];
}

export interface InternshipEntry {
  company?: string | null;
  role?: string | null;
  duration?: string | null;
  technologies: string[];
}

export interface ProjectEntry {
  project_name?: string | null;
  description?: string | null;
  technologies: string[];
}

export interface CertificationEntry {
  name?: string | null;
  issuer?: string | null;
  year?: number | null;
}

export interface Achievements {
  hackathons: string[];
  awards: string[];
  coding_achievements: string[];
}

export interface Provenance {
  resume: string[];
  user: string[];
  ml: string[];
}

export interface PredictionHistoryEntry {
  timestamp: string;
  model_version: string;
  placement_probability: number;
  prediction: string;
}

export interface AssessmentEvidenceEntry {
  skill: string;
  score: number;
  level: string;
  source: string;
  verified: boolean;
  assessment_id: string;
  attempt: number;
  timestamp: string;
}

export interface StudentProfile {
  profile_id?: string | null;
  personal: PersonalInfo;
  education: EducationInfo;
  skills: SkillSet;
  experience: ExperienceEntry[];
  internships: InternshipEntry[];
  projects: ProjectEntry[];
  certifications: CertificationEntry[];
  achievements: Achievements;
  ml_inputs: MlInputs;
  provenance: Provenance;
  original_resume_values: Record<string, unknown>;
  assessment_evidence: AssessmentEvidenceEntry[];
  verified: boolean;
  prediction_history: PredictionHistoryEntry[];
}

export interface ProfileCompletion {
  profile_complete: boolean;
  missing_fields: string[];
  ml_feature_mapping: Record<string, unknown>;
}

export interface ProfileResponse {
  profile: StudentProfile;
  completion: ProfileCompletion;
  message: string;
}

// ---------- Resume (Phase 9 + 16) ----------

export interface ExtractionInfo {
  raw_text_preview?: string | null;
  page_count?: number | null;
  extraction_success: boolean;
  ocr_required?: boolean;
}

export interface FieldEvidence {
  field: string;
  value?: number | string | null;
  source: string;
  evidence?: string | null;
}

export interface ResumeDiagnostics {
  page_count?: number | null;
  word_count: number;
  detected_sections: string[];
  extraction_completeness: number;
  ocr_required: boolean;
  scanned_document_warning: boolean;
}

export interface ExtractionSummary {
  fields_extracted: number;
  counts: Record<string, number>;
  has_education: boolean;
  has_cgpa: boolean;
  has_github: boolean;
  has_linkedin: boolean;
}

export interface FeatureAvailabilityEntry {
  field: string;
  status: string;
  reason: string;
}

export interface ProfileFromResumeResponse extends ProfileResponse {
  provenance: FieldEvidence[];
  confidence: Record<string, string>;
  diagnostics: ResumeDiagnostics;
  extraction_summary: ExtractionSummary;
  feature_availability: FeatureAvailabilityEntry[];
}

// ---------- Prediction (Phase 8 / 11) ----------

export interface PredictionResponse {
  ready_for_prediction: boolean;
  prediction?: string | null;
  placement_probability?: number | null;
  confidence?: number | null;
  model_version?: string | null;
  missing_fields: string[];
  reason?: string | null;
  prediction_history: PredictionHistoryEntry[];
}

// ---------- Readiness (Phase 12) ----------

export interface StrengthEntry {
  skill: string;
  category?: string | null;
  evidence: string[];
}

export interface SkillGapEntry {
  skill: string;
  category: string;
  priority: string; // HIGH / MEDIUM / LOW
  reason: string;
  action?: string;
}

export interface ImprovementItem {
  priority: number;
  skill: string;
  reason: string;
  action: string;
}

export interface ReadinessBreakdown {
  technical_skills: number;
  projects: number;
  internships: number;
  certifications: number;
  communication: number;
  profile_completeness: number;
}

export interface ProfileCompletenessView {
  percentage: number;
  missing_fields: string[];
}

export interface ReadinessResponse {
  profile_id: string;
  readiness_score: number;
  readiness_level: string;
  readiness_breakdown: ReadinessBreakdown;
  strengths: StrengthEntry[];
  skill_gaps: SkillGapEntry[];
  improvement_plan: ImprovementItem[];
  profile_completeness: ProfileCompletenessView;
}

export interface PlacementSummaryResponse {
  ready_for_prediction: boolean;
  prediction?: string | null;
  placement_probability?: number | null;
  confidence?: number | null;
  model_version?: string | null;
  missing_fields: string[];
  reason?: string | null;
  readiness_score: number;
  readiness_level: string;
  readiness_breakdown: ReadinessBreakdown;
  strengths: StrengthEntry[];
  skill_gaps: SkillGapEntry[];
  improvement_plan: ImprovementItem[];
}

// ---------- Companies / Eligibility (Phase 13) ----------

export interface CompanySummary {
  company_id: string;
  company_name: string;
  industry?: string | null;
  roles: string[];
}

export interface RequirementResult {
  requirement: string;
  student_value?: number | string | null;
  required_value?: number | string | number[] | string[] | null;
  status: string; // PASS / FAIL / UNKNOWN
  mandatory: boolean;
  explanation: string;
  action?: string | null;
}

export interface RequirementGroups {
  passed: RequirementResult[];
  failed: RequirementResult[];
  unknown: RequirementResult[];
}

export interface CompanyEligibilityResponse {
  company_id: string;
  company_name: string;
  status: string; // ELIGIBLE / NOT_ELIGIBLE / INCOMPLETE
  requirements: RequirementGroups;
  missing_information: string[];
  explanation: string[];
}

export interface CompanyEligibilitySummary {
  company: CompanySummary;
  status: string;
  passed_count: number;
  failed_count: number;
  unknown_count: number;
  major_reasons: string[];
}

export interface AllCompanyEligibilityResponse {
  eligible: CompanyEligibilitySummary[];
  not_eligible: CompanyEligibilitySummary[];
  incomplete: CompanyEligibilitySummary[];
}

// ---------- Recommendations (Phase 14) ----------

export interface SkillMatch {
  score: number;
  required_matched: string[];
  required_missing: string[];
  preferred_matched: string[];
  preferred_missing: string[];
}

export interface RecommendationItem {
  company_id: string;
  company_name: string;
  status: string; // RECOMMENDED / ELIGIBLE / INCOMPLETE / NOT_RECOMMENDED
  recommendation_score: number;
  eligibility_status: string;
  skill_match: SkillMatch;
  readiness_score: number;
  readiness_level: string;
  placement_probability?: number | null;
  reasons: string[];
  improvement_actions: string[];
  missing_information: string[];
}

export interface RecommendationGroups {
  recommended: RecommendationItem[];
  eligible: RecommendationItem[];
  incomplete: RecommendationItem[];
  not_recommended: RecommendationItem[];
}

export interface RecommendationsResponse {
  profile_id: string;
  recommendations: RecommendationGroups;
}

// ---------- Skill Assessment (Phase 17) ----------

export interface AssessmentQuestion {
  question_id: string;
  skill: string;
  topic: string;
  difficulty: string; // EASY / MEDIUM / HARD
  question_type: string;
  question: string;
  options: string[];
}

export interface StartAssessmentResponse {
  assessment_id: string;
  skill: string;
  attempt: number;
  total_questions: number;
  questions: AssessmentQuestion[];
  time_limit_minutes?: number | null;
}

export interface SubmitAssessmentResponse {
  assessment_id: string;
  skill: string;
  attempt: number;
  skill_score: number;
  level: string;
  correct: number;
  total: number;
  difficulty_breakdown: Record<string, number>;
  topic_breakdown: Record<string, number>;
  message: string;
}

export interface AssessmentHistoryEntry {
  skill: string;
  score: number;
  level: string;
  source: string;
  verified: boolean;
  assessment_id: string;
  attempt: number;
  timestamp: string;
}

export interface AssessmentHistoryResponse {
  profile_id: string;
  assessments: AssessmentHistoryEntry[];
}

export interface SkillViewEntry {
  skill: string;
  resume_detected: boolean;
  user_entered: boolean;
  assessment_score?: number | null;
  assessment_verified: boolean;
  level?: string | null;
}

export interface SkillsViewResponse {
  profile_id: string;
  skills: SkillViewEntry[];
}

// ---------- API error shape (FastAPI validation / HTTP errors) ----------

export interface ApiErrorDetail {
  detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
}

export class ApiError extends Error {
  status: number;
  detail?: string;
  validation?: Array<{ loc: string[]; msg: string; type: string }>;

  constructor(status: number, detail?: string, validation?: ApiErrorDetail["detail"]) {
    super(detail ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    if (Array.isArray(validation)) this.validation = validation;
  }
}
