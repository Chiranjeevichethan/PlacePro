import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { formatResumeFieldValue, resumeComparisonRows, mergeResumeSelection, applyReviewEdits }
  from '../src/services/profileReview.js';

const current = { profile_id: 'owned-fixture', revision: 4,
  personal: { name: 'Synthetic Current Profile', email: 'current@example.test' },
  projects: [{ project_name: 'Synthetic Existing Project', description: 'Preserve this description', technologies: ['Java'] }],
  skills: { programming_languages: ['Java'] }, internships: [], experience: [], ml_inputs: {},
};
const extracted = { profile_id: 'owned-fixture', revision: 4,
  personal: { name: 'Synthetic Demo Learner', email: 'synthetic-resume@example.test' },
  skills: { programming_languages: ['Python', 'JavaScript', 'SQL'], frameworks: ['React', 'Node.js', 'Spring Boot'],
    databases: ['PostgreSQL', 'SQLite'], cloud: ['Docker', 'AWS'], ai_ml: ['Machine Learning', 'pandas', 'NumPy'],
    web_technologies: ['HTML', 'CSS', 'REST API'], tools: ['Git', 'VS Code'], other_skills: ['Teamwork', 'Problem Solving'] },
  projects: [{ project_name: 'Synthetic Library Planner', description: 'Fictional tracker\nAdded input validation',
    technologies: ['Python', 'FastAPI', 'SQLite'] }],
  internships: [{ role: 'Software Intern', company: 'Synthetic Practice Lab', duration: 'Jun 2025 - Aug 2025', technologies: ['Python'] }],
  experience: [{ role: 'Volunteer Developer', company: 'Synthetic Community Workshop', duration: 'Jan 2026 - Mar 2026', technologies: ['HTML'] }],
};

test('extraction comparison never labels preserved current identity as extracted identity', () => {
  const rows = resumeComparisonRows(current, extracted);
  const email = rows.find(({ path }) => path === 'personal.email');
  assert.equal(email.currentValue, 'current@example.test');
  assert.equal(email.extractedValue, 'synthetic-resume@example.test');
  const retained = mergeResumeSelection(current, extracted);
  assert.equal(retained.personal.email, 'current@example.test');
  assert.equal(rows.find(({ path }) => path === 'personal.name').extractedValue, 'Synthetic Demo Learner');
});

test('missing extraction stays missing even when the current profile has a value', () => {
  const rows = resumeComparisonRows(current, { ...extracted, personal: {} });
  const email = rows.find(({ path }) => path === 'personal.email');
  assert.equal(formatResumeFieldValue(email.extractedValue), 'Not provided');
  assert.equal(email.currentValue, 'current@example.test');
});

test('display exposes project descriptions, technologies, role, company and complete duration', () => {
  const project = formatResumeFieldValue(extracted.projects);
  for (const content of ['Synthetic Library Planner', 'Fictional tracker', 'Added input validation', 'FastAPI', 'SQLite']) {
    assert.ok(project.includes(content));
  }
  for (const section of ['internships', 'experience']) {
    const text = formatResumeFieldValue(extracted[section]);
    for (const content of Object.values(extracted[section][0]).flat()) assert.ok(text.includes(content));
  }
  assert.equal(formatResumeFieldValue([]), 'None found');
});

test('all eight skill categories map independently and selected records accept student corrections', () => {
  const paths = Object.keys(extracted.skills).map((key) => `skills.${key}`);
  const merged = mergeResumeSelection(current, extracted, [...paths, 'projects', 'internships', 'experience']);
  assert.deepEqual(merged.skills, extracted.skills);
  assert.deepEqual(merged.internships, extracted.internships);
  assert.deepEqual(merged.experience, extracted.experience);
  const corrected = applyReviewEdits(merged, { projects: [{ ...merged.projects[0], description: 'Reviewed fictional project' }] });
  assert.equal(corrected.projects[0].description, 'Reviewed fictional project');
  assert.equal(corrected.personal.email, current.personal.email);
  assert.equal(corrected.revision, 4);
  assert.equal(extracted.projects[0].description, 'Fictional tracker\nAdded input validation');
});
