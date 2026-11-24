// Canonical saved profile -> the unchanged production form's values and scales.
const BRANCHES = {
  cse: 'CSE', 'computer science': 'CSE', 'computer science and engineering': 'CSE',
  'computer science & engineering': 'CSE',
  ise: 'ISE', 'information science': 'ISE', 'information science and engineering': 'ISE',
  it: 'IT', 'information technology': 'IT',
  ece: 'ECE', 'electronics and communication engineering': 'ECE',
  ee: 'EE', eee: 'EE', 'electrical engineering': 'EE', 'electrical and electronics engineering': 'EE',
  ce: 'CE', civil: 'CE', 'civil engineering': 'CE',
  me: 'ME', mechanical: 'ME', 'mechanical engineering': 'ME',
  chemical: 'Chemical', 'chemical engineering': 'Chemical',
};
const text = (value) => typeof value === 'string' ? value.trim() : '';
function numberText(value, min, max = Infinity, integer = false) {
  if ((typeof value !== 'number' && typeof value !== 'string') ||
      (typeof value === 'string' && !value.trim())) return '';
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max &&
    (!integer || Number.isInteger(parsed)) ? String(parsed) : '';
}
function recordCount(records, titles) {
  if (!Array.isArray(records) || records.some(record =>
    !record || !titles.some(title => text(record[title])))) return '';
  return String(records.length);
}

export function buildExperimentalV1DraftFromProfile(profile) {
  const education = profile?.education ?? {};
  const ml = profile?.ml_inputs ?? {};
  const tier = text(ml.college_tier).match(/^Tier[ -]([123])$/i);
  const branch = text(education.branch).toLowerCase();
  const hackathons = profile?.achievements?.hackathons;
  const values = {
    branch: Object.hasOwn(BRANCHES, branch) ? BRANCHES[branch] : '',
    collegeTier: tier ? `Tier-${tier[1]}` : '',
    cgpa: numberText(education.cgpa, 4, 10),
    backlogs: numberText(ml.backlogs, 0, Infinity, true),
    codingSkill: numberText(ml.coding_skills, 1, 10),
    dsaScore: numberText(ml.dsa_score, 1, 10),
    mlKnowledge: numberText(ml.ml_knowledge, 0, 10),
    systemDesign: numberText(ml.system_design, 0, 10),
    projects: recordCount(profile?.projects, ['project_name']),
    certifications: recordCount(profile?.certifications, ['name']),
    aptitudeScore: numberText(ml.aptitude_score, 20, 100),
    communicationSkill: numberText(ml.communication_skills, 1, 10),
    internships: recordCount(profile?.internships, ['role', 'company']),
    hackathons: Array.isArray(hackathons) && hackathons.every(entry => text(entry)) ? String(hackathons.length) : '',
    openSourceContributions: numberText(ml.open_source_contributions, 0, Infinity, true),
    extracurricular: numberText(ml.extracurriculars, 0, Infinity, true),
  };
  // No scores/counts are inferred from skill lists, URLs, assessments, context or salary.
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ''));
}
