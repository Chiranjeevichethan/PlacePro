import assert from 'node:assert/strict';
import test from 'node:test';
import { access, readFile } from 'node:fs/promises';
import { transformWithOxc } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { buildExperimentalV1DraftFromProfile } from '../src/services/experimentalV1Profile.js';

// Compile both real forms and their real icon dependency in memory; no UI probes.
const modules = new Map();
async function jsxModule(url) {
  if (modules.has(url.href)) return modules.get(url.href);
  let source = await readFile(url, 'utf8');
  for (const match of [...source.matchAll(/from\s+(['"])([^'"]+)\1/g)]) {
    const specifier = match[2];
    let target;
    if (specifier.startsWith('.')) {
      const dependency = new URL(specifier, url);
      const jsx = !dependency.pathname.endsWith('.js') &&
        await access(new URL(specifier + '.jsx', url)).then(() => true, () => false);
      if (jsx) {
        dependency.pathname += '.jsx';
        target = await jsxModule(dependency);
      } else {
        if (!dependency.pathname.endsWith('.js')) dependency.pathname += '.js';
        target = dependency.href;
      }
    } else target = import.meta.resolve(specifier);
    source = source.replace(match[0], 'from ' + JSON.stringify(target));
  }
  const { code } = await transformWithOxc(source, url.pathname, { jsx: { runtime: 'automatic' }, sourcemap: false });
  const target = 'data:text/javascript;base64,' + Buffer.from(code
    .replaceAll('"react/jsx-runtime"', JSON.stringify(import.meta.resolve('react/jsx-runtime')))).toString('base64');
  modules.set(url.href, target);
  return target;
}
const { default: Reference } = await import(await jsxModule(new URL('../src/components/StudentForm.jsx', import.meta.url)));
const { default: V1 } = await import(await jsxModule(new URL('../src/components/ExperimentalV1Form.jsx', import.meta.url)));
const render = (Form, props = {}) => renderToStaticMarkup(createElement(Form, { onPredict() {}, ...props }));
const input = (markup, name) => markup.match(new RegExp(`<input\\b[^>]*name="${name}"[^>]*>`))?.[0];

test('V1 renders byte-identical production controls, sections, labels, options, ranges and layout', () => {
  const production = render(Reference);
  assert.equal(render(V1), '<div class="experimental-v1-form">' + production + '</div>');
  assert.equal((production.match(/name="/g) ?? []).length, 16);
  assert.deepEqual([...production.matchAll(/<(?:input|select)\b[^>]*name="([^"<>]+)"/g)].map(match => match[1]), [
    'branch', 'collegeTier', 'cgpa', 'backlogs', 'codingSkill', 'dsaScore', 'mlKnowledge', 'systemDesign',
    'projects', 'certifications', 'aptitudeScore', 'communicationSkill', 'internships', 'hackathons',
    'openSourceContributions', 'extracurricular',
  ]);
});

test('prefill uses the same profile values as the production controls without converting saved scores', () => {
  const profile = { education: { cgpa: 8.8, branch: 'CE' }, projects: [{ project_name: 'Reviewed project' }],
    ml_inputs: { college_tier: 'Tier-3', coding_skills: 8, communication_skills: 7, extracurriculars: 3 } };
  const markup = render(V1, { profile });
  assert.equal(markup, '<div class="experimental-v1-form">' + render(Reference, { draft: {
    branch: 'CE', collegeTier: 'Tier-3', cgpa: '8.8', backlogs: '', codingSkill: '8', dsaScore: '',
    mlKnowledge: '', systemDesign: '', projects: '1', certifications: '', aptitudeScore: '',
    communicationSkill: '7', internships: '', hackathons: '', openSourceContributions: '', extracurricular: '3',
  } }) + '</div>');
  assert.equal(buildExperimentalV1DraftFromProfile(profile).codingSkill, '8');
});

test('missing values remain empty, including scores and counts with no source', () => {
  const markup = render(V1);
  for (const name of ['cgpa', 'backlogs', 'codingSkill', 'dsaScore', 'mlKnowledge', 'systemDesign',
    'projects', 'certifications', 'aptitudeScore', 'communicationSkill', 'internships', 'hackathons',
    'openSourceContributions', 'extracurricular']) assert.match(input(markup, name), /value=""/);
  assert.doesNotMatch(markup, /salary_package_lpa|name="age"|name="gender"/);
});
