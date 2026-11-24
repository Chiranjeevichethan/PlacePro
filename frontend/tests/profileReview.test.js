import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadResumeReview, applyReviewEdits, buildProfileCorrection, validateReviewRecords,
  parseClaimList, parseActivityList } from '../src/services/profileReview.js';
import { fetchStudentProfile } from '../src/services/api.js';

const profile = () => ({
  profile_id: 'existing-student', revision: 4, personal: { name: 'Ananya Rao', email: 'ananya@example.com', phone: '12345' },
  education: { degree: 'B.Tech', branch: 'Information Science and Engineering', college: 'Example College',
    cgpa: 9.1, graduation_year: 2025 }, skills: { programming_languages: ['Java'], tools: ['Git'] },
  projects: [{ project_name: 'Weather App', description: 'Forecast dashboard', technologies: ['Java'] }],
  internships: [], experience: [], certifications: [{ name: 'AWS Certified Cloud Practitioner.', issuer: null, year: 2024 }],
  achievements: { hackathons: ['CodeFest'], open_source_contributions: ['Docs fix'], extracurriculars: [] },
  ml_inputs: { college_tier: 'Tier-2', coding_skills: 7.5, backlogs: 0 },
  additional_info: { attendance: 85, sleep_hours: 7.5 }, verified: true,
  provenance: { resume: ['certifications'], user: ['education.cgpa'] },
  original_resume_values: { 'skills.programming_languages': ['Python'] },
  assessment_evidence: [{ skill: 'Python', score: 100, source: 'assessment', verified: true }],
  prediction_history: [{ placement_probability: .75 }],
});
const response = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});
const analysis = (email = 'ananya@example.com') => ({
  profile: { profile_id: 'existing-student', revision: 4,
    personal: { name: 'Extracted Name', email }, education: { cgpa: 8.4 },
    skills: { programming_languages: ['Python'] }, certifications: [], ml_inputs: { coding_skills: null } },
  completion: {}, message: 'Review selected changes',
  provenance: [{ field: 'email', source: 'resume', evidence: email }],
});
const file = () => new File(['test resume'], 'resume.pdf', { type: 'application/pdf' });

for (const verified of [true, false]) {
  for (const email of ['ananya@example.com', 'other@example.com']) {
    test(`loaded profile ${verified} and email ${email} uses analysis without creating or selecting a profile`, async (t) => {
      const original = profile(); original.verified = verified;
      const before = structuredClone(original);
      const calls = [];
      t.mock.method(globalThis, 'fetch', async (url, init) => { calls.push([url, init]); return response(analysis(email)); });
      for (let i = 0; i < 3; i++) {
        const result = await loadResumeReview(file(), original);
        assert.equal(result.previewOnly, false);
        assert.equal(result.updatesExisting, true);
        assert.equal(result.draftProfile.profile_id, original.profile_id);
        assert.equal(result.draftProfile.revision, original.revision);
        assert.equal(result.draftProfile.personal.email, email);
        assert.equal(result.draftProfile.verified, false);
        assert.equal(result.draftProfile.ml_inputs.coding_skills, null);
      }
      assert.deepEqual(original, before);
      assert.equal(calls.length, 3);
      assert.ok(calls.every(([url, init]) => url.endsWith('/api/profile/existing-student/resume-preview')
        && init.method === 'POST' && init.body.get('revision') === '4'));
    });
  }
}

test('no loaded profile creates an independent unconfirmed draft', async (t) => {
  const draft = profile(); draft.profile_id = 'new-draft'; draft.verified = false;
  t.mock.method(globalThis, 'fetch', async (url) => {
    assert.ok(url.endsWith('/api/profile/from-resume'));
    return response({ profile: draft, completion: {}, message: 'Review draft' });
  });
  const result = await loadResumeReview(file(), null);
  assert.equal(result.previewOnly, false);
  assert.equal(result.draftProfile.profile_id, 'new-draft');
  assert.equal(result.draftProfile.verified, false);
});

for (const failure of ['network', 'ocr', 'invalid', 'json']) {
  test(`resume review ${failure} failure never falls back to profile creation`, async (t) => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url) => {
      calls.push(url);
      if (failure === 'network') throw new Error('offline');
      if (failure === 'ocr') return response({ detail: 'OCR_REQUIRED: no text' }, 422);
      if (failure === 'json') return new Response('invalid JSON');
      return response({ success: false });
    });
    await assert.rejects(loadResumeReview(file(), profile()));
    assert.equal(calls.length, 1);
    assert.ok(calls[0].endsWith('/api/profile/existing-student/resume-preview'));
  });
}

test('explicit structural corrections preserve originals, identity, histories and untouched manual values', () => {
  const original = profile(); const before = structuredClone(original);
  const corrected = applyReviewEdits(original, { 'skills.programming_languages': ['C++'], certifications: [],
    'education.cgpa': '9.3', 'achievements.extracurriculars': ['Volunteer at college festival'] });
  assert.equal(corrected.profile_id, original.profile_id);
  assert.equal(corrected.verified, false);
  assert.equal(corrected.education.cgpa, 9.3);
  assert.deepEqual(corrected.certifications, []);
  assert.deepEqual(corrected.assessment_evidence, original.assessment_evidence);
  assert.deepEqual(corrected.original_resume_values, original.original_resume_values);
  assert.deepEqual(corrected.ml_inputs, original.ml_inputs);
  assert.deepEqual(original, before);
});

test('correction form preserves untouched branch, CGPA, zero and manual fields exactly', () => {
  const original = profile();
  const result = buildProfileCorrection(original, {}, { certifications: [] });
  assert.deepEqual(result.education, original.education);
  assert.equal(result.ml_inputs.backlogs, 0);
  assert.equal(result.ml_inputs.coding_skills, 7.5);
  assert.equal(result.additional_info.sleep_hours, 7.5);
  assert.deepEqual(result.skills, original.skills);
  assert.equal(result.provenance, undefined);
  assert.equal(result.assessment_evidence, undefined); // restored by server, never sent as claimed evidence
  assert.equal(result.verified, false);
});

test('structural correction works with missing branch and tier', () => {
  const original = profile(); original.education.branch = null; original.ml_inputs.college_tier = null;
  const result = buildProfileCorrection(original, {}, { projects: [] });
  assert.equal(result.education.branch, null);
  assert.equal(result.ml_inputs.college_tier, null);
  assert.deepEqual(result.projects, []);
});

test('explicit form blanks clear incorrect values without erasing untouched values', () => {
  const result = buildProfileCorrection(profile(), { cgpa: '', branch: '', backlogs: '', collegeTier: '', attendance: '' });
  assert.equal(result.education.cgpa, null);
  assert.equal(result.education.branch, null);
  assert.equal(result.ml_inputs.backlogs, null);
  assert.equal(result.ml_inputs.college_tier, null);
  assert.equal(result.additional_info.attendance, null);
  assert.equal(result.ml_inputs.coding_skills, 7.5);
});

for (const [field, value] of [['backlogs', '1.5'], ['githubRepositories', '2.4'],
  ['codingSkills', 'Infinity'], ['dsaScore', 'oops'], ['not_a_field', '1']]) {
  test(`invalid explicit ${field} does not round or silently preserve old values`, () => {
    assert.throws(() => buildProfileCorrection(profile(), { [field]: value }));
  });
}

for (const path of ['verified', 'provenance', 'assessment_evidence', 'prediction_history', 'original_resume_values', 'profile_id']) {
  test(`review corrections cannot write server field ${path}`, () => {
    assert.throws(() => applyReviewEdits(profile(), { [path]: [] }), /Unsupported/);
  });
}

test('empty lists clear claims; comma and line lists deduplicate literal records', () => {
  assert.deepEqual(parseClaimList('Python, SQL, Python, ,'), ['Python', 'SQL']);
  assert.deepEqual(parseActivityList('CodeFest\nDocs fix\nCodeFest\n'), ['CodeFest', 'Docs fix']);
  assert.deepEqual(parseClaimList(''), []);
  const result = applyReviewEdits(profile(), { 'personal.phone': '', 'education.graduation_year': '',
    'skills.programming_languages': [] });
  assert.equal(result.personal.phone, null);
  assert.equal(result.education.graduation_year, null);
  assert.deepEqual(result.skills.programming_languages, []);
});

test('record review rejects blank titles and fractional certification years without creating placeholder records', () => {
  const original = profile(); validateReviewRecords(original);
  assert.throws(() => validateReviewRecords({ projects: [{ project_name: null }] }), /title/);
  assert.throws(() => validateReviewRecords({ certifications: [{ name: 'Course Certificate', year: 2024.5 }] }), /whole number/);
  assert.throws(() => applyReviewEdits(original, { 'education.graduation_year': '2024.5' }), /valid number/);
});

test('profile 404 is explicitly distinguishable for new-profile creation', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({ detail: 'not found' }, 404));
  await assert.rejects(fetchStudentProfile('missing'), { code: 'PROFILE_NOT_FOUND', status: 404 });
});

for (const failure of ['network', 'server']) {
  test(`profile ${failure} failure is not mistaken for a missing profile`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => {
      if (failure === 'network') throw new Error('offline');
      return response({ detail: 'unavailable' }, 503);
    });
    await assert.rejects(fetchStudentProfile('existing'), (error) => error.code !== 'PROFILE_NOT_FOUND');
  });
}
