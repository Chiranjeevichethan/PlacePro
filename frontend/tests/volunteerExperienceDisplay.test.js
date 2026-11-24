import test from 'node:test';
import assert from 'node:assert/strict';
import { buildEditState, buildPredictionDraftFromProfile, buildSalaryDraftFromProfile,
  flattenBackendProfile, getVolunteerExperienceDisplay } from '../src/services/profileConfig.js';
import { buildProfileCorrection } from '../src/services/profileReview.js';

const volunteer = { company: 'Synthetic Community Workshop', role: 'Volunteer Developer',
  duration: 'Jan 2026 - Mar 2026', technologies: ['HTML', 'CSS'] };
const profile = () => ({ profile_id: 'synthetic-owned', revision: 5, verified: true,
  personal: { name: 'Synthetic Learner', email: 'learner@example.test' },
  education: { branch: 'CSE', cgpa: 8.2 }, skills: { programming_languages: ['Python'] },
  experience: [structuredClone(volunteer)], internships: [{ role: 'Software Intern' }],
  projects: [{ project_name: 'Synthetic Portal' }], certifications: [{ name: 'Synthetic Certificate' }],
  achievements: { hackathons: ['Synthetic Challenge'], open_source_contributions: ['Fictional docs fix'] },
  additional_info: { volunteer_experience: null, github_repositories: 0, linkedin_connections: null },
  ml_inputs: { college_tier: 'Tier-3', backlogs: 0, coding_skills: 7, dsa_score: 6,
    communication_skills: 7, ml_knowledge: 5, system_design: 4, aptitude_score: 75,
    open_source_contributions: 0, extracurriculars: 1 },
});

test('confirmed synthetic volunteer role appears with company, dates and technologies despite missing manual declaration', () => {
  const display = getVolunteerExperienceDisplay(profile());
  assert.equal(display.value, 'Volunteer Developer at Synthetic Community Workshop · Jan 2026 - Mar 2026 · HTML, CSS');
  assert.match(display.detail, /Recorded volunteer roles/);
});

for (const missing of [undefined, null, {}, { experience: [] }, { experience: null }]) {
  test(`missing volunteer sources stay Not set: ${JSON.stringify(missing)}`, () => {
    assert.equal(getVolunteerExperienceDisplay(missing).value, 'Not set');
  });
}

for (const declaration of ['Yes', 'No', 'Synthetic festival helper']) {
  test(`manual-only volunteering remains unchanged: ${declaration}`, () => {
    const source = { experience: [], additional_info: { volunteer_experience: declaration } };
    assert.equal(getVolunteerExperienceDisplay(source).value, declaration);
    assert.match(getVolunteerExperienceDisplay(source).detail, /Self-reported/);
  });
}

test('recorded volunteering and a conflicting manual No remain visibly separate without rewriting either', () => {
  const source = profile(); source.additional_info.volunteer_experience = 'No';
  const before = structuredClone(source);
  const display = getVolunteerExperienceDisplay(source);
  assert.match(display.value, /Volunteer Developer/);
  assert.match(display.detail, /Self-reported volunteering: No/);
  assert.deepEqual(source, before);
  assert.equal(flattenBackendProfile(source).volunteerExperience, 'No');
});

test('a volunteer company name, unrelated role and internship never imply a volunteering experience', () => {
  const source = profile();
  source.experience = [{ role: 'Developer', company: 'Synthetic Volunteer Services' },
    { role: 'Non-volunteer Developer', company: 'Synthetic Lab' }];
  source.internships = [{ role: 'Volunteer Intern', company: 'Synthetic Lab' }];
  assert.equal(getVolunteerExperienceDisplay(source).value, 'Not set');
});

test('partial and multiple explicit volunteer roles preserve missing fields without invented details', () => {
  const source = { experience: [{ role: 'VOLUNTEER TUTOR', company: null, duration: null, technologies: [] },
    { role: 'Volunteering Mentor', company: 'Synthetic Learning Group', technologies: ['Python'] }] };
  assert.equal(getVolunteerExperienceDisplay(source).value,
    'VOLUNTEER TUTOR; Volunteering Mentor at Synthetic Learning Group · Python');
});

test('presentation does not populate manual edit fields or change save payloads, revisions or model form inputs', () => {
  const source = profile(), before = structuredClone(source);
  const display = flattenBackendProfile(source);
  const editBefore = buildEditState(display);
  const payloadBefore = buildProfileCorrection(source, {});
  const placementBefore = buildPredictionDraftFromProfile(display);
  const salaryBefore = buildSalaryDraftFromProfile(display);
  getVolunteerExperienceDisplay(source);
  assert.equal(display.volunteerExperience, '');
  assert.equal(editBefore.volunteerExperience, '');
  assert.equal(payloadBefore.additional_info.volunteer_experience, null);
  assert.deepEqual(buildProfileCorrection(source, {}), payloadBefore);
  assert.deepEqual(buildEditState(flattenBackendProfile(source)), editBefore);
  assert.deepEqual(buildPredictionDraftFromProfile(flattenBackendProfile(source)), placementBefore);
  assert.deepEqual(buildSalaryDraftFromProfile(flattenBackendProfile(source)), salaryBefore);
  assert.deepEqual(source, before);
});

test('switching profiles recomputes the display without retaining another profile volunteer record', () => {
  assert.match(getVolunteerExperienceDisplay(profile()).value, /Synthetic Community Workshop/);
  assert.equal(getVolunteerExperienceDisplay({ profile_id: 'other-owned', experience: [], additional_info: {} }).value, 'Not set');
  assert.equal(getVolunteerExperienceDisplay(profile()).value, getVolunteerExperienceDisplay(profile()).value);
});

test('other structural counts keep their existing sources; manual open-source and social counts are not inferred', () => {
  const source = profile(), display = flattenBackendProfile(source);
  getVolunteerExperienceDisplay(source);
  assert.equal(display.projectsCount, 1);
  assert.equal(display.internshipsCount, 1);
  assert.equal(display.certificationsCount, 1);
  assert.equal(display.hackathonsCount, 1);
  assert.equal(display.openSourceContributions, '0');
  assert.equal(display.githubRepositories, '0');
  assert.equal(display.linkedinConnections, '');
});
