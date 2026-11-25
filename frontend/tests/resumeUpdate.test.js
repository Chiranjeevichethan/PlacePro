import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { applyReviewEdits, loadResumeReview, mergeResumeSelection, validateResumeFile, resumeComparisonRows, resumeSelectionState } from '../src/services/profileReview.js';
import { verifyStudentProfile } from '../src/services/api.js';
import { profileStamp } from '../src/services/profileState.js';
import { flattenBackendProfile, buildPredictionDraftFromProfile, buildSalaryDraftFromProfile } from '../src/services/profileConfig.js';

const current = () => ({ profile_id: 'owned-profile', revision: 3, verified: true,
  personal: { name: 'Synthetic Current', email: 'current@example.test' },
  education: { branch: 'CSE', cgpa: 8 }, skills: { programming_languages: ['Java'] },
  projects: [{ project_name: 'Keep Project', technologies: ['Java'] }], internships: [], experience: [],
  certifications: [], achievements: { hackathons: ['Keep Activity'] },
  ml_inputs: { coding_skills: 7, college_tier: 'Tier-2', backlogs: 0 }, additional_info: { attendance: 90 },
  prediction_history: [{ placement_probability: .6 }], assessment_evidence: [{ score: 70 }],
  original_resume_values: { name: 'Keep Original' }, provenance: { user: ['personal.name'] },
});
const extraction = () => ({ profile_id: 'owned-profile', revision: 3, verified: false,
  personal: { name: 'Extracted Student', email: 'resume@example.test' },
  education: { branch: null, cgpa: 8.4 }, skills: { programming_languages: ['Python'] },
  projects: [], internships: [], experience: [], certifications: [],
  achievements: { hackathons: [] }, ml_inputs: { coding_skills: null }, additional_info: {},
});
const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

test('Select All is opt-in and includes only nonempty extracted fields, with partial/count states', () => {
  const extracted = extraction();
  extracted.personal = { name: 'Resume Student', email: 'resume@example.test', phone: '123', location: 'City' };
  extracted.education = { branch: 'CSE', cgpa: 0 };
  extracted.skills = { programming_languages: ['Python'] };
  extracted.projects = [{ project_name: 'Resume Project' }];
  const rows = resumeComparisonRows(current(), extracted);
  const none = resumeSelectionState(rows, []);
  assert.equal(none.eligiblePaths.length, 8);
  assert.equal(none.allSelected, false);
  assert.equal(none.indeterminate, false);
  assert.equal(none.selectedCount, 0);
  const all = resumeSelectionState(rows, none.eligiblePaths);
  assert.equal(all.allSelected, true);
  assert.equal(all.selectedCount, 8);
  assert.equal(all.indeterminate, false);
  const partial = resumeSelectionState(rows, none.eligiblePaths.slice(1));
  assert.equal(partial.allSelected, false);
  assert.equal(partial.indeterminate, true);
  assert.equal(partial.selectedCount, 7);
  assert.equal(resumeSelectionState(rows, []).selectedCount, 0);
  assert.deepEqual(mergeResumeSelection(current(), extracted, []).projects, current().projects);
});

test('Select All never imports missing extraction, empty records, whitespace or ML/security fields', () => {
  const extracted = extraction();
  extracted.personal = { name: '   ' };
  extracted.education = {};
  extracted.skills = { programming_languages: [] };
  extracted.projects = [{ project_name: null, technologies: [] }];
  extracted.ml_inputs = { coding_skills: 10 };
  extracted.prediction_history = [{ placement_probability: 1 }];
  const state = resumeSelectionState(resumeComparisonRows(current(), extracted), []);
  assert.deepEqual(state.eligiblePaths, []);
  assert.equal(state.allSelected, false);
});

test('preview preserves every current field until explicit selection and strips server-controlled submission fields', () => {
  const original = current(), before = structuredClone(original);
  const merged = mergeResumeSelection(original, extraction());
  for (const section of ['personal','education','skills','projects','ml_inputs','additional_info']) {
    assert.deepEqual(merged[section], original[section]);
  }
  assert.equal(merged.revision, 3);
  assert.equal(merged.prediction_history, undefined);
  assert.equal(merged.assessment_evidence, undefined);
  assert.equal(merged.provenance, undefined);
  assert.deepEqual(original, before);
});

test('only selected fields change; student correction wins without replacing ML or unrelated records', () => {
  const merged = mergeResumeSelection(current(), extraction(), ['education.cgpa','skills.programming_languages']);
  const corrected = applyReviewEdits(merged, { 'education.cgpa': '8.7' });
  assert.equal(corrected.education.cgpa, 8.7);
  assert.deepEqual(corrected.skills.programming_languages, ['Python']);
  assert.equal(corrected.personal.email, 'current@example.test');
  assert.deepEqual(corrected.projects, current().projects);
  assert.deepEqual(corrected.ml_inputs, current().ml_inputs);
});

test('empty extraction never clears a list or scalar unless explicitly selected', () => {
  assert.deepEqual(mergeResumeSelection(current(), extraction()).projects, current().projects);
  const selected = mergeResumeSelection(current(), extraction(), ['projects','education.branch']);
  assert.deepEqual(selected.projects, []);
  assert.equal(selected.education.branch, null);
});

for (const path of ['account_id','ml_inputs.coding_skills','prediction_history','assessment_evidence','provenance','revision']) {
  test(`resume cannot import protected field ${path}`, () => {
    assert.throws(() => mergeResumeSelection(current(), extraction(), [path]), /Unsupported/);
  });
}

test('profile and revision mismatch cannot merge another preview', () => {
  assert.throws(() => mergeResumeSelection(current(), { ...extraction(), revision: 2 }), /Profile changed/);
  assert.throws(() => mergeResumeSelection(current(), { ...extraction(), profile_id: 'foreign' }), /Profile changed/);
});

for (const [name, size] of [['resume.txt',12],['resume.pdf',0],['resume.docx',5*1024*1024+1]]) {
  test(`invalid selected file ${name} with size ${size} fails before network`, async (t) => {
    t.mock.method(globalThis,'fetch', () => assert.fail('No invalid-file network request'));
    assert.throws(() => validateResumeFile({ name,size }));
    await assert.rejects(loadResumeReview({ name,size },current()));
  });
}

test('owned extraction and explicit corrected confirmation use cookie/CSRF transport and refresh downstream drafts', async (t) => {
  let submitted;
  t.mock.method(globalThis,'fetch',async (url, init) => {
    assert.equal(init.credentials,'include');
    assert.ok(new Headers(init.headers).get('X-CSRF-Token'));
    if (url.endsWith('/resume-preview')) {
      assert.equal(init.body.get('revision'),'3');
      return response({ profile: extraction(), completion: {}, message: 'Review extraction' });
    }
    assert.ok(url.endsWith('/api/profile/verify'));
    submitted=JSON.parse(init.body);
    return response({ profile: { ...submitted, revision: 4, verified: true }, completion: {}, message: 'Confirmed' });
  });
  const original=current();
  const preview=await loadResumeReview(new File(['synthetic'],'resume.docx'), original);
  const payload=applyReviewEdits(mergeResumeSelection(original,preview.draftProfile,['education.cgpa']),{ 'education.cgpa':'8.7' });
  const confirmed=await verifyStudentProfile(payload,'retry-confirmation');
  assert.equal(submitted.revision,3);
  assert.equal(submitted.education.cgpa,8.7);
  assert.notEqual(profileStamp(original.profile_id, original),profileStamp(confirmed.profile.profile_id,confirmed.profile));
  const display=flattenBackendProfile(confirmed.profile);
  assert.equal(Number(buildPredictionDraftFromProfile(display).cgpa),8.7);
  assert.equal(Number(buildSalaryDraftFromProfile(display).cgpa),8.7);
});

for (const failure of ['stale','foreign','invalid']) {
  test(`preview ${failure} response never falls back to creation or merge`, async (t) => {
    let calls=0;
    t.mock.method(globalThis,'fetch',async () => {
      calls++;
      if (failure==='stale') return response({ detail:'stale' },409);
      return response({ profile: { ...extraction(), profile_id: failure==='foreign'?'foreign':'owned-profile', revision: 2 },completion:{},message:'bad' });
    });
    await assert.rejects(loadResumeReview(new File(['synthetic'],'resume.pdf'),current()));
    assert.equal(calls,1);
  });
}
