/** Display guidance only. Server ownership, completion and revisions remain authoritative. */
const FIELD_LABELS = {
  cgpa: 'CGPA', branch: 'Branch', college_tier: 'College tier', backlogs: 'Backlogs',
  coding_skills: 'Coding skill', dsa_score: 'DSA score', aptitude_score: 'Aptitude score',
  communication_skills: 'Communication skill', ml_knowledge: 'ML knowledge', system_design: 'System design',
  open_source_contributions: 'Open source contributions', extracurriculars: 'Extracurricular activities',
};

export function studentJourney(profile, completion) {
  if (!profile) return { stage: 'empty', title: 'Start with your student profile',
    detail: 'Upload a PDF or DOCX resume, review what was extracted, then add your academic and technical information.',
    action: 'Create profile', missing: [] };
  const missing = [...new Set((Array.isArray(completion?.missing_fields) ? completion.missing_fields : [])
    .map((name) => FIELD_LABELS[name] || 'Required profile information'))];
  if (completion?.profile_complete !== true) return { stage: 'incomplete', title: 'Complete your prediction inputs',
    detail: 'Resume extraction does not invent skill scores. Add the missing information in Edit Profile, save, then confirm your reviewed profile.',
    action: 'Complete profile', missing };
  if (profile.verified !== true) return { stage: 'confirm', title: 'Confirm your reviewed profile',
    detail: 'Your changes are saved. Review and confirm them on Student Profile before saving a placement prediction.',
    action: 'Review profile', missing: [] };
  return { stage: 'ready', title: 'Profile ready', detail: 'Explore predictions, readiness and practice assessments.', missing: [] };
}

export function isSyntheticDemo(mode = import.meta.env?.VITE_DEMO_MODE) {
  return mode === 'synthetic';
}
