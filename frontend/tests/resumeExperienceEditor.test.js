import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { transformWithOxc } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { loadResumeReview, mergeResumeSelection, applyReviewEdits, validateReviewRecords }
  from '../src/services/profileReview.js';

// Compile the actual JSX component in memory with the installed production tool.
// No browser, server, dependency installation or generated project file is needed.
const componentURL = new URL('../src/components/ResumeEvidenceEditor.jsx', import.meta.url);
const reviewURL = new URL('../src/services/profileReview.js', import.meta.url);
const source = (await readFile(componentURL, 'utf8'))
  .replace("'../services/profileReview'", JSON.stringify(reviewURL.href));
const transformed = await transformWithOxc(source, 'ResumeEvidenceEditor.jsx', {
  jsx: { runtime: 'automatic' }, sourcemap: false,
});
const code = transformed.code.replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')));
const { default: Editor } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));

const extractedExperience = { role: 'Volunteer Developer', company: 'Synthetic Community Workshop',
  duration: 'Jan 2026 - Mar 2026', technologies: ['HTML', 'CSS'] };
const storedExperience = { role: 'Synthetic Existing Developer', company: 'Synthetic Existing Lab',
  duration: '2025', technologies: ['Python'] };
const current = () => ({ profile_id: 'synthetic-owned', revision: 5, verified: true,
  personal: { name: 'Synthetic Current Learner', email: 'current@example.test' },
  education: { branch: 'CSE', cgpa: 8.2 }, experience: [structuredClone(storedExperience)],
  internships: [{ role: 'Synthetic Intern', company: 'Synthetic Practice Lab', duration: '2025', technologies: ['SQL'] }],
  projects: [{ project_name: 'Synthetic Existing Portal', description: 'Keep this description', technologies: ['Java'] }],
  certifications: [{ name: 'Synthetic Existing Certificate', issuer: 'Synthetic Academy', year: 2025 }],
  skills: { programming_languages: ['Java'] }, achievements: { hackathons: ['Synthetic Event'] },
  ml_inputs: { coding_skills: 7 }, additional_info: { volunteer_experience: null },
});
const extraction = () => ({ ...current(), experience: [structuredClone(extractedExperience)] });

function inputs(profile, onChange = () => {}) {
  const values = new Map();
  function visit(node) {
    if (Array.isArray(node)) return node.forEach(visit);
    if (!node || typeof node !== 'object') return;
    if (node.type === 'input' || node.type === 'textarea') values.set(node.props.id, node.props);
    visit(node.props?.children);
  }
  visit(Editor({ profile, onChange }));
  return values;
}

function assertExperienceValues(profile, expected) {
  const controls = inputs(profile);
  for (const key of ['role', 'company', 'duration', 'technologies']) {
    assert.equal(controls.get(`evidence-experience.0.${key}`).value,
      key === 'technologies' ? expected[key].join(', ') : expected[key] ?? '');
  }
  const markup = renderToStaticMarkup(createElement(Editor, { profile, onChange() {} }));
  for (const key of ['role', 'company', 'duration', 'technologies']) {
    const value = key === 'technologies' ? expected[key].join(', ') : expected[key] ?? '';
    assert.ok(markup.includes(`id="evidence-experience.0.${key}" value="${value}"`), key);
  }
}

for (const scenario of ['existing record', 'empty list', 'blank record']) {
test(`actual upload response -> select only experience -> four rendered inputs with ${scenario}`, async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.ok(url.endsWith('/api/profile/synthetic-owned/resume-preview'));
    assert.equal(init.body.get('revision'), '5');
    return new Response(JSON.stringify({ profile: extraction(), completion: {}, message: 'Review extraction' }),
      { headers: { 'Content-Type': 'application/json' } });
  });
  const original = current();
  if (scenario === 'empty list') original.experience = [];
  if (scenario === 'blank record') original.experience = [{ role: null, company: null, duration: null, technologies: [] }];
  const before = structuredClone(original);
  const { draftProfile } = await loadResumeReview(new File(['synthetic'], 'resume.docx'), original);
  const reviewBase = mergeResumeSelection(original, draftProfile, ['experience']);
  const editorProfile = applyReviewEdits(reviewBase, {}, false);
  assertExperienceValues(editorProfile, extractedExperience);
  validateReviewRecords(editorProfile);
  for (const section of ['personal', 'education', 'internships', 'projects', 'certifications', 'skills', 'ml_inputs', 'additional_info']) {
    assert.deepEqual(editorProfile[section], before[section], section);
  }
  assert.equal(editorProfile.revision, before.revision);
  assert.deepEqual(original, before);
});
}

test('unchecked experience renders all existing values without importing the resume record', () => {
  const editorProfile = applyReviewEdits(mergeResumeSelection(current(), extraction(), []), {}, false);
  assertExperienceValues(editorProfile, storedExperience);
});

test('deselecting and reselecting experience restores current then extracted input values', () => {
  const original = current(), draft = extraction();
  for (const [selected, expected] of [[['experience'], extractedExperience], [[], storedExperience], [['experience'], extractedExperience]]) {
    assertExperienceValues(applyReviewEdits(mergeResumeSelection(original, draft, selected), {}, false), expected);
  }
});

test('editor callbacks correct each experience field and produce a valid reviewed submission', () => {
  const base = mergeResumeSelection(current(), extraction(), ['experience']);
  let edits = {};
  const corrections = { role: 'Reviewed Volunteer Developer', company: 'Synthetic Reviewed Workshop',
    duration: 'Feb 2026 - Mar 2026', technologies: 'HTML, CSS, JavaScript' };
  for (const [key, value] of Object.entries(corrections)) {
    const controls = inputs(applyReviewEdits(base, edits, false), (path, entries) => { edits = { ...edits, [path]: entries }; });
    controls.get(`evidence-experience.0.${key}`).onChange({ target: { value } });
  }
  const payload = applyReviewEdits(base, edits);
  validateReviewRecords(payload);
  assertExperienceValues(payload, { ...corrections, technologies: ['HTML', 'CSS', 'JavaScript'] });
  assert.deepEqual(base.experience, [extractedExperience]);
  assert.equal(payload.revision, 5);
});

test('partial extraction keeps genuinely missing fields blank without erasing its known role', () => {
  const draft = extraction();
  draft.experience = [{ role: 'Volunteer Developer', company: null, duration: null, technologies: [] }];
  assertExperienceValues(applyReviewEdits(mergeResumeSelection(current(), draft, ['experience']), {}, false), draft.experience[0]);
});

test('other record editor fields remain populated when only experience is imported', () => {
  const controls = inputs(applyReviewEdits(mergeResumeSelection(current(), extraction(), ['experience']), {}, false));
  assert.equal(controls.get('evidence-internships.0.role').value, 'Synthetic Intern');
  assert.equal(controls.get('evidence-projects.0.project_name').value, 'Synthetic Existing Portal');
  assert.equal(controls.get('evidence-projects.0.description').value, 'Keep this description');
  assert.equal(controls.get('evidence-certifications.0.name').value, 'Synthetic Existing Certificate');
});
