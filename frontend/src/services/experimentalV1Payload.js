// V1's own 16-field request builder. Never call the production branch adapter.
const FIELDS = {
  branch: ['branch'], college_tier: ['collegeTier'],
  cgpa: ['cgpa', 4, 10], backlogs: ['backlogs', 0, Infinity, true],
  coding_skills: ['codingSkill', 1, 10], dsa_score: ['dsaScore', 1, 10],
  ml_knowledge: ['mlKnowledge', 0, 10], system_design: ['systemDesign', 0, 10],
  projects_count: ['projects', 0, Infinity, true], certifications: ['certifications', 0, Infinity, true],
  aptitude_score: ['aptitudeScore', 20, 100], communication_skills: ['communicationSkill', 1, 10],
  internships: ['internships', 0, Infinity, true], hackathons: ['hackathons', 0, Infinity, true],
  open_source_contributions: ['openSourceContributions', 0, Infinity, true],
  extracurriculars: ['extracurricular', 0, Infinity, true],
};
const BRANCHES = ['CSE', 'ISE', 'IT', 'ECE', 'EE', 'ME', 'CE', 'Chemical'];
const TIERS = ['Tier-1', 'Tier-2', 'Tier-3'];
export function buildExperimentalV1Payload(draft) {
  const payload = {};
  const invalid = () => { throw new Error('Some experimental V1 inputs are missing or invalid. Please check the form.'); };
  for (const [field, [source, min, max, integer]] of Object.entries(FIELDS)) {
    const raw = draft?.[source];
    if (min === undefined) {
      if (!(field === 'branch' ? BRANCHES : TIERS).includes(raw)) invalid();
      payload[field] = raw;
    } else {
      if ((typeof raw !== 'string' && typeof raw !== 'number') || (typeof raw === 'string' && !raw.trim())) invalid();
      const value = Number(raw);
      if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) invalid();
      payload[field] = value;
    }
  }
  return payload;
}
