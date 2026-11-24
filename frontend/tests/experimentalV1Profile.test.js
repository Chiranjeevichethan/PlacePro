import './authFixtures.js';
import assert from 'node:assert/strict';
import test from 'node:test';
import { buildExperimentalV1DraftFromProfile } from '../src/services/experimentalV1Profile.js';
import { mergeResumeSelection, applyReviewEdits } from '../src/services/profileReview.js';
import { createOwnedProfilesController } from '../src/services/ownedProfiles.js';
import { fetchStudentProfile, verifyStudentProfile, buildPredictionPayload } from '../src/services/api.js';

const id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const profile = () => ({ profile_id: id, revision: 4, verified: true,
  personal: { name: 'Saved Student', email: 'student@example.test', github: 'https://github.com/student' },
  education: { branch: 'ME', cgpa: 8.4 },
  internships: [{ role: 'Developer', company: 'Sample Company' }],
  projects: [{ project_name: 'Saved Project' }, { project_name: 'Second Project' }],
  certifications: [{ name: 'Reviewed certificate' }], achievements: { hackathons: ['Code event'] },
  ml_inputs: { college_tier: 'Tier-2', backlogs: 0, aptitude_score: 80, coding_skills: 8,
    communication_skills: 7, dsa_score: 9, ml_knowledge: 0, system_design: 5, open_source_contributions: 1, extracurriculars: 2 },
  additional_info: { age: 24, gender: 'Female', attendance: 90, logical_reasoning: 70,
    mock_interview: 65, leadership: 55, github_repositories: 6, linkedin_connections: 100,
    volunteer_experience: 'Yes', sleep_hours: 7.5, study_hours: 4 },
});

test('V1 uses the saved profile values on the exact production scales', () => {
  const original = profile(), before = structuredClone(original);
  assert.deepEqual(buildExperimentalV1DraftFromProfile(original), {
    branch: 'ME', collegeTier: 'Tier-2', cgpa: '8.4', backlogs: '0', codingSkill: '8',
    dsaScore: '9', mlKnowledge: '0', systemDesign: '5', projects: '2', certifications: '1',
    aptitudeScore: '80', communicationSkill: '7', internships: '1', hackathons: '1',
    openSourceContributions: '1', extracurricular: '2',
  });
  assert.deepEqual(original, before);
});

test('missing resume data stays absent and explicitly empty lists supply zero counts only', () => {
  for (const value of [null, {}, { education: { branch: null, cgpa: null }, additional_info: { age: 22 } }]) {
    assert.deepEqual(buildExperimentalV1DraftFromProfile(value), {});
  }
  assert.deepEqual(buildExperimentalV1DraftFromProfile({ projects: [], internships: [], certifications: [],
    achievements: { hackathons: [] } }), { projects: '0', certifications: '0', internships: '0', hackathons: '0' });
});

test('resume skills, context scores, activity lists, URLs, assessments and salary never manufacture scores/counts', () => {
  const value = profile();
  value.ml_inputs = {};
  value.skills = { programming_languages: ['Python'], tools: ['Git'] };
  value.achievements.extracurriculars = ['Chess club'];
  value.achievements.open_source_contributions = ['Repository URL'];
  value.assessment_evidence = [{ skill: 'Python', score: 100, verified: true }];
  value.salary_package_lpa = 15;
  const draft = buildExperimentalV1DraftFromProfile(value);
  for (const key of ['codingSkill', 'communicationSkill', 'dsaScore', 'mlKnowledge', 'systemDesign',
    'aptitudeScore', 'openSourceContributions', 'extracurricular', 'salary_package_lpa', 'placement_status',
    'age', 'github_repos', 'logical_reasoning_score']) assert.equal(key in draft, false);
});

for (const [source, expected] of [
  ['CSE', 'CSE'], ['IT', 'IT'], ['ECE', 'ECE'], ['EE', 'EE'], ['CE', 'CE'], ['ME', 'ME'],
  ['Mechanical Engineering', 'ME'], ['Civil', 'CE'], ['Electrical and Electronics Engineering', 'EE'],
  ['Chemical', 'Chemical'], ['ISE', 'ISE'], ['constructor', undefined],
]) {
  test(`V1 prefill respects production dropdown vocabulary: ${source}`, () => {
    assert.equal(buildExperimentalV1DraftFromProfile({ education: { branch: source } }).branch, expected);
  });
}

test('invalid values and incompatible score scales remain missing', () => {
  assert.deepEqual(buildExperimentalV1DraftFromProfile({
    education: { branch: 'Unknown', cgpa: 3.9 }, ml_inputs: { college_tier: 'Elite', backlogs: 1.5,
      coding_skills: 80, communication_skills: 0, dsa_score: 0, aptitude_score: 19,
      ml_knowledge: 11, system_design: true, open_source_contributions: -1, extracurriculars: 1.5 },
    projects: [{}], internships: [null], certifications: [{ issuer: 'Only issuer' }], achievements: { hackathons: [''] },
  }), {});
});

test('genuine zeros are preserved only where the production form allows them', () => {
  assert.deepEqual(buildExperimentalV1DraftFromProfile({ education: { cgpa: 0 }, ml_inputs: {
    backlogs: 0, coding_skills: 0, dsa_score: 0, communication_skills: 0, aptitude_score: 0,
    ml_knowledge: 0, system_design: 0, open_source_contributions: 0, extracurriculars: 0,
  } }), { backlogs: '0', mlKnowledge: '0', systemDesign: '0', openSourceContributions: '0', extracurricular: '0' });
});

test('selected corrected resume values persist through the secure API and a fresh canonical profile load', async (t) => {
  let saved = profile();
  const extraction = { ...profile(), education: { branch: 'CE', cgpa: 8.8 }, projects: [{ project_name: 'Resume Project' }] };
  const payload = applyReviewEdits(mergeResumeSelection(saved, extraction, ['education.branch', 'education.cgpa', 'projects']),
    { 'education.cgpa': '9.1' });
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.credentials, 'include');
    if (url.endsWith('/api/profile/verify')) {
      assert.equal(options.headers['x-csrf-token'], 'a'.repeat(64));
      saved = { ...JSON.parse(options.body), revision: 5, verified: true };
    } else assert.ok(url.endsWith('/api/profile/' + id));
    return new Response(JSON.stringify({ profile: saved, completion: {}, message: 'Saved' }), { status: 200 });
  });
  await verifyStudentProfile(payload, 'resume-v1-confirmation');
  const controller = createOwnedProfilesController({ listProfiles: async () => [id], fetchProfile: fetchStudentProfile });
  await controller.reload();
  const restored = controller.getSnapshot().data.profile;
  assert.equal(restored.revision, 5);
  assert.equal(restored.personal.name, 'Saved Student');
  assert.equal(buildExperimentalV1DraftFromProfile(restored).cgpa, '9.1');
  assert.equal(buildExperimentalV1DraftFromProfile(restored).projects, '1');
  assert.equal(buildExperimentalV1DraftFromProfile(restored).branch, 'CE');
  assert.equal(restored.ml_inputs.coding_skills, 8);
});

test('V1 mapping cannot mutate production inputs or change the production payload vocabulary', () => {
  const production = { branch: 'CSE', collegeTier: 'Tier-2', cgpa: '8', backlogs: '0', codingSkill: '8',
    dsaScore: '7', aptitudeScore: '80', communicationSkill: '7', mlKnowledge: '6', systemDesign: '5',
    internships: '1', projects: '2', certifications: '1', hackathons: '1', openSourceContributions: '0', extracurricular: '2' };
  const expected = buildPredictionPayload(production);
  buildExperimentalV1DraftFromProfile(profile());
  assert.deepEqual(buildPredictionPayload(production), expected);
  assert.equal(expected.college_tier, 'Tier-2');
  assert.equal(expected.coding_skills, 8);
  assert.equal('coding_skill_score' in expected, false);
});
