import { analyzeResumeForReview, createProfileFromResume } from './api.js';
import { buildProfilePayload } from './profileConfig.js';

export const SKILL_FIELDS = [
  'programming_languages', 'frameworks', 'databases', 'cloud', 'ai_ml',
  'web_technologies', 'tools', 'other_skills',
];
export const RECORD_FIELDS = {
  projects: ['project_name', 'description', 'technologies'],
  internships: ['role', 'company', 'duration', 'technologies'],
  experience: ['role', 'company', 'duration', 'technologies'],
  certifications: ['name', 'issuer', 'year'],
};
export const ACTIVITY_FIELDS = [
  'hackathons', 'awards', 'coding_achievements', 'open_source_contributions', 'extracurriculars',
];
export const REVIEW_DETAILS = {
  personal: ['email', 'phone', 'location', 'linkedin', 'github', 'portfolio'],
  education: ['degree', 'college', 'graduation_year'],
};

const FORM_PATHS = {
  name: ['personal.name'], branch: ['education.branch'], cgpa: ['education.cgpa', 'number'],
  collegeTier: ['ml_inputs.college_tier'], backlogs: ['ml_inputs.backlogs', 'integer'],
  codingSkills: ['ml_inputs.coding_skills', 'number'], dsaScore: ['ml_inputs.dsa_score', 'number'],
  aptitudeScore: ['ml_inputs.aptitude_score', 'number'], communicationSkills: ['ml_inputs.communication_skills', 'number'],
  mlKnowledge: ['ml_inputs.ml_knowledge', 'number'], systemDesign: ['ml_inputs.system_design', 'number'],
  openSourceContributions: ['ml_inputs.open_source_contributions', 'integer'],
  extracurriculars: ['ml_inputs.extracurriculars', 'integer'], attendance: ['additional_info.attendance', 'number'],
  githubRepositories: ['additional_info.github_repositories', 'integer'],
  linkedinConnections: ['additional_info.linkedin_connections', 'integer'],
  volunteerExperience: ['additional_info.volunteer_experience'],
};

/** Preserve untouched confirmed values exactly; blanks in explicitly edited
 * fields clear them. Structural correction requires no unrelated ML inputs. */
export function buildProfileCorrection(profile, formEdits, evidenceEdits = {}) {
  const result = buildProfilePayload(profile, formEdits);
  for (const [field, raw] of Object.entries(formEdits)) {
    const mapping = FORM_PATHS[field];
    if (!mapping) throw new Error('Unsupported profile correction.');
    const [path, type] = mapping;
    const [section, key] = path.split('.');
    const text = String(raw ?? '').trim();
    if (!text) result[section][key] = null;
    else if (type) {
      const value = Number(text);
      if (!Number.isFinite(value) || (type === 'integer' && !Number.isInteger(value))) {
        throw new Error(`${field} must be a valid ${type === 'integer' ? 'whole number' : 'number'}.`);
      }
      result[section][key] = value;
    }
  }
  return applyReviewEdits(result, evidenceEdits);
}

export const parseClaimList = (text) => [...new Set(String(text).split(',')
  .map((item) => item.trim()).filter(Boolean))];
export const parseActivityList = (text) => [...new Set(String(text).split('\n')
  .map((item) => item.trim()).filter(Boolean))];

/** The owned preview never creates/selects a profile; confirmation is separate. */
export async function loadResumeReview(file, currentProfile, requestId) {
  validateResumeFile(file);
  if (currentProfile?.profile_id) {
    return { ...await analyzeResumeForReview(file, currentProfile), previewOnly: false, updatesExisting: true };
  }
  return { ...await createProfileFromResume(file, requestId), previewOnly: false, updatesExisting: false };
}

export function validateResumeFile(file) {
  if (!file || !/\.(pdf|docx)$/i.test(file.name)) throw new Error('Choose a PDF or DOCX resume.');
  if (!file.size) throw new Error('The resume file is empty.');
  if (file.size > 5 * 1024 * 1024) throw new Error('Resume file is too large. Maximum size is 5 MB.');
}

export const RESUME_IMPORT_PATHS = [
  ...['name', ...REVIEW_DETAILS.personal].map((key) => `personal.${key}`),
  ...['branch', 'cgpa', ...REVIEW_DETAILS.education].map((key) => `education.${key}`),
  ...SKILL_FIELDS.map((key) => `skills.${key}`),
  ...Object.keys(RECORD_FIELDS),
  ...ACTIVITY_FIELDS.map((key) => `achievements.${key}`),
];

export function resumeFieldValue(profile, path) {
  return path.split('.').reduce((value, key) => value?.[key], profile);
}

/** Display extraction separately from the preserved values proposed for saving. */
export function resumeComparisonRows(current, extraction) {
  return RESUME_IMPORT_PATHS.map((path) => ({ path,
    currentValue: structuredClone(resumeFieldValue(current, path)),
    extractedValue: structuredClone(resumeFieldValue(extraction, path)),
  }));
}

const hasExtractedValue = (value) => {
  if (Array.isArray(value)) return value.some(hasExtractedValue);
  if (value && typeof value === 'object') return Object.values(value).some(hasExtractedValue);
  if (typeof value === 'number') return Number.isFinite(value);
  return typeof value === 'string' && Boolean(value.trim());
};

export function resumeSelectionState(rows, selected) {
  const eligiblePaths = rows.filter(row => hasExtractedValue(row.extractedValue)).map(row => row.path);
  const selectedCount = new Set(selected.filter(path => rows.some(row => row.path === path))).size;
  const allSelected = eligiblePaths.length > 0 && eligiblePaths.every(path => selected.includes(path));
  return { eligiblePaths, selectedCount, allSelected, indeterminate: selectedCount > 0 && !allSelected };
}

export function formatResumeFieldValue(value) {
  if (value === null || value === undefined || value === '') return 'Not provided';
  if (Array.isArray(value)) {
    return value.length ? value.map(formatResumeFieldValue).join('\n') : 'None found';
  }
  if (typeof value === 'object') {
    return Object.entries(value).map(([key, entry]) =>
      `${key.replaceAll('_', ' ')}: ${formatResumeFieldValue(entry)}`).join('; ');
  }
  return String(value);
}

/** Keep every stored field unless the student explicitly chooses its extraction.
 * Existing ML inputs, evidence, identity and histories cannot be imported. */
export function mergeResumeSelection(current, extraction, selected = []) {
  if (current.profile_id !== extraction.profile_id || current.revision !== extraction.revision) {
    throw new Error('Profile changed. Reload it and review the resume again.');
  }
  const edits = {};
  for (const path of selected) {
    if (!RESUME_IMPORT_PATHS.includes(path)) throw new Error('Unsupported resume field.');
    const emptyValue = path.startsWith('personal.') || path.startsWith('education.') ? null : [];
    edits[path] = structuredClone(resumeFieldValue(extraction, path) ?? emptyValue);
  }
  const payload = buildProfilePayload(current, {});
  payload.ml_inputs = structuredClone(current.ml_inputs ?? {});
  payload.additional_info = structuredClone(current.additional_info ?? {});
  return applyReviewEdits(payload, edits);
}

/** Apply explicit corrections only. Empty values clear extraction; missing
 * edits preserve it. Never manufacture count records, scores or provenance. */
export function applyReviewEdits(profile, edits, validateNumbers = true) {
  const result = structuredClone(profile);
  for (const [path, raw] of Object.entries(edits)) {
    const [section, key] = path.split('.');
    if (!['personal', 'education', 'skills', 'achievements', ...Object.keys(RECORD_FIELDS)].includes(section)) {
      throw new Error('Unsupported profile correction.');
    }
    let value = raw;
    if (validateNumbers && (section === 'personal' || section === 'education')) {
      value = String(raw ?? '').trim() || null;
      if (section === 'education' && ['cgpa', 'graduation_year'].includes(key) && value !== null) {
        value = Number(value);
        if (!Number.isFinite(value) || (key === 'graduation_year' && !Number.isInteger(value))) {
          throw new Error(`${key.replaceAll('_', ' ')} must be a valid number.`);
        }
      }
    }
    if (key) result[section] = { ...result[section], [key]: value };
    else result[section] = structuredClone(value);
  }
  result.verified = false;
  return result;
}

export function validateReviewRecords(profile) {
  for (const section of Object.keys(RECORD_FIELDS)) {
    for (const entry of profile[section] ?? []) {
      const title = section === 'projects' ? entry.project_name
        : section === 'certifications' ? entry.name : entry.role || entry.company;
      if (!String(title ?? '').trim()) throw new Error(`Provide a title for each ${section} entry or remove it.`);
      if (section === 'certifications' && entry.year !== null && entry.year !== undefined &&
          (!Number.isInteger(Number(entry.year)) || String(entry.year).trim() === '')) {
        throw new Error('Certification year must be a whole number or left empty.');
      }
    }
  }
}
