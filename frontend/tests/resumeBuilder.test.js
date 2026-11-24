import './authFixtures.js';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  DEFAULT_RESUME_DOCUMENT, blankResumeEntry, mergeProfileImport, moveEntry, moveSection,
  resumeCompleteness, sectionHasContent,
} from '../src/services/resumeBuilder.js';
import { exportResumePdf, fetchResumeDraft, importResumeProfile, saveResumeDraft } from '../src/services/resumeBuilderApi.js';

const profileId = 'owned-profile-123';
const response = (body, status = 200, headers = { 'Content-Type': 'application/json' }) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), { status, headers });

test('profile import fills only blank values and does not create duplicate entries', () => {
  const initial = structuredClone(DEFAULT_RESUME_DOCUMENT);
  initial.personal.name = 'Student-edited name';
  initial.personal_sources.name = 'student';
  initial.skills = [{ entry_id: 'existing', source: 'student', name: 'Python', group: '' }];
  const imported = {
    personal: { name: 'Canonical profile name', email: 'student@example.org' },
    skills: [
      { entry_id: 'existing', source: 'profile', name: 'Python', group: '' },
      { entry_id: 'profile-sql', source: 'profile', name: 'SQL', group: 'Database' },
    ],
  };

  const merged = mergeProfileImport(initial, imported);
  assert.equal(merged.personal.name, 'Student-edited name');
  assert.equal(merged.personal.email, 'student@example.org');
  assert.equal(merged.personal_sources.email, 'profile');
  assert.deepEqual(merged.skills.map(({ entry_id }) => entry_id), ['existing', 'profile-sql']);
  assert.deepEqual(initial.skills.map(({ entry_id }) => entry_id), ['existing']);
});

test('section and entry reordering is immutable and respects list boundaries', () => {
  const originalSections = ['summary', 'education', 'skills'];
  assert.deepEqual(moveSection(originalSections, 'skills', -1), ['summary', 'skills', 'education']);
  assert.deepEqual(moveSection(originalSections, 'summary', -1), originalSections);
  assert.deepEqual(originalSections, ['summary', 'education', 'skills']);

  const entries = [blankResumeEntry('projects', 'first'), blankResumeEntry('projects', 'second')];
  assert.deepEqual(moveEntry(entries, 'second', -1).map(({ entry_id }) => entry_id), ['second', 'first']);
  assert.deepEqual(moveEntry(entries, 'first', -1), entries);
  assert.deepEqual(entries.map(({ entry_id }) => entry_id), ['first', 'second']);
});

test('resume completeness distinguishes missing from complete required sections', () => {
  const empty = structuredClone(DEFAULT_RESUME_DOCUMENT);
  assert.deepEqual(resumeCompleteness(empty).filter((item) => !item.optional && !item.complete).map(({ id }) => id),
    ['contact', 'education', 'skills', 'projects']);
  assert.equal(sectionHasContent(empty, 'experience'), false);

  const complete = {
    ...empty,
    personal: { ...empty.personal, name: 'A Student', email: 'student@example.org' },
    education: [{ institution: 'Example University' }],
    skills: [{ name: 'Python' }],
    projects: [{ description: 'A documented project' }],
  };
  assert.ok(resumeCompleteness(complete).filter((item) => !item.optional).every(({ complete: done }) => done));
  assert.equal(sectionHasContent(complete, 'education'), true);
});

test('authenticated API reads, saves, imports, and exports profile-scoped resume data', async (t) => {
  const calls = [];
  const pdf = new Blob(['%PDF-1.4 test'], { type: 'application/pdf' });
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    calls.push({ url: String(url), init });
    if (String(url).endsWith('/export.pdf')) return new Response(pdf, { headers: { 'Content-Type': 'application/pdf' } });
    if (String(url).endsWith('/import')) return response({ content: DEFAULT_RESUME_DOCUMENT });
    if (init?.method === 'PUT') return response({ draft: init.body, has_saved_draft: true });
    return response({ draft: DEFAULT_RESUME_DOCUMENT, has_saved_draft: false });
  });

  await fetchResumeDraft(profileId);
  await saveResumeDraft(profileId, DEFAULT_RESUME_DOCUMENT);
  await importResumeProfile(profileId);
  assert.equal((await exportResumePdf(profileId)).type, 'application/pdf');

  assert.equal(calls.length, 4);
  assert.ok(calls.every(({ url, init }) => url.includes(`/api/profile/${profileId}/resume-builder`)
    && init.credentials === 'include' && init.cache === 'no-store'));
  assert.equal(calls[1].init.method, 'PUT');
  assert.equal(calls[1].init.headers['x-csrf-token'], 'a'.repeat(64));
  assert.equal(calls[2].init.method, 'POST');
  assert.equal(calls[3].init.method, 'POST');
  assert.equal(calls[3].init.headers['x-csrf-token'], 'a'.repeat(64));
  assert.doesNotMatch(calls.map(({ init }) => init.body || '').join(' '), /account_id|student_id/);
});

test('PDF API rejects a non-PDF success response and preserves server errors', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => response({ message: 'unexpected' }));
  await assert.rejects(exportResumePdf(profileId), /did not return a PDF/);

  t.mock.method(globalThis, 'fetch', async () => response({ detail: 'Save your resume first.' }, 409));
  await assert.rejects(exportResumePdf(profileId), /Save your resume first/);
});

test('editor wires two templates, live preview, section controls, save/export, and completeness guidance', async () => {
  const page = await readFile(new URL('../src/pages/StudentResumeBuilder.jsx', import.meta.url), 'utf8');
  const app = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
  const sidebar = await readFile(new URL('../src/components/Sidebar.jsx', import.meta.url), 'utf8');
  assert.match(page, /value="classic"/);
  assert.match(page, /value="modern"/);
  assert.match(page, /aria-label={`Move \$\{SECTION_LABEL\[section\]\} up`}/);
  assert.match(page, /aria-label={`Move \$\{SECTION_LABEL\[section\]\} down`}/);
  assert.match(page, /setDocument\(\(current\) => mergeProfileImport/);
  assert.match(page, /<ResumePreview document=\{document\}/);
  assert.match(page, /resumeCompleteness\(document\)/);
  assert.match(page, /const update = \(callback\) => \{\s*setNotice\(''\);\s*setDocument/,
    'Any edit must clear a previous save-success notice.');
  assert.match(page, /onClick=\{exportPdf\}/);
  assert.match(app, /currentPage === "resume" \|\| resumeBuilderVisited/);
  assert.match(app, /<StudentResumeBuilder key=\{profileId\} \/>/);
  assert.match(page, /window\.addEventListener\('beforeunload', warnBeforeUnload\)/);
  assert.doesNotMatch(page, /localStorage|sessionStorage/);
  assert.match(sidebar, /page: "resume", label: "Resume Builder"/);
});
