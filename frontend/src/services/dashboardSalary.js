import { buildSalaryPayload } from './api.js';
import { BRANCH_OPTIONS, TIER_OPTIONS } from './profileConfig.js';

// Mirror the salary page's input rules. Mapping and calculations stay in
// the existing salary service; this only explains whether a preview can run.
const NUMERIC_INPUTS = [
  ['cgpa', 'CGPA', 10],
  ['backlogs', 'Backlogs', undefined, true],
  ['codingSkills', 'Coding skill', 10],
  ['dsaScore', 'DSA score', 10],
  ['aptitudeScore', 'Aptitude score', 100],
  ['communicationSkills', 'Communication skill', 10],
  ['mlKnowledge', 'ML knowledge', 10],
  ['systemDesign', 'System design', 10],
  ['internships', 'Internships', undefined, true],
  ['projects', 'Projects', undefined, true],
  ['certifications', 'Certifications', undefined, true],
  ['hackathons', 'Hackathons', undefined, true],
  ['openSourceContributions', 'Open source contributions', 2, true],
  ['extracurriculars', 'Extracurricular activities', 3, true],
];

export function validateDashboardSalaryDraft(draft) {
  const issues = [];
  const missing = (value) => value == null || String(value).trim() === '';
  const payload = buildSalaryPayload(draft);

  if (missing(draft.branch)) {
    issues.push({ field: 'branch', message: 'Branch is missing.' });
  } else if (!BRANCH_OPTIONS.some(({ value }) => value === payload.branch)) {
    issues.push({ field: 'branch', message: 'Branch needs a supported value.' });
  }

  if (!missing(draft.collegeTier) &&
      !TIER_OPTIONS.some(({ value }) => value === payload.college_tier)) {
    issues.push({ field: 'collegeTier', message: 'College tier needs a supported value.' });
  }

  for (const [field, label, max, integer] of NUMERIC_INPUTS) {
    const raw = draft[field];
    const value = Number(raw);
    if (missing(raw)) {
      issues.push({ field, message: `${label} is missing.` });
    } else if (!['string', 'number'].includes(typeof raw) || !Number.isFinite(value)) {
      issues.push({ field, message: `${label} needs a valid number.` });
    } else if (value < 0 || (max !== undefined && value > max)) {
      issues.push({ field, message: max === undefined
        ? `${label} must be 0 or greater.` : `${label} must be between 0 and ${max}.` });
    } else if (integer && !Number.isInteger(value)) {
      issues.push({ field, message: `${label} must be a whole number.` });
    }
  }
  return issues;
}
