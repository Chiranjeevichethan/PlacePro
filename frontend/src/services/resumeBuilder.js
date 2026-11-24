export const RESUME_SECTIONS = [
  ['summary', 'Professional Summary'], ['education', 'Education'], ['skills', 'Skills'],
  ['projects', 'Projects'], ['experience', 'Work Experience'], ['internships', 'Internships'],
  ['certifications', 'Certifications'], ['achievements', 'Achievements'],
];

export const DEFAULT_RESUME_DOCUMENT = {
  revision: 0,
  template: 'classic',
  section_order: RESUME_SECTIONS.map(([id]) => id),
  visible_sections: RESUME_SECTIONS.map(([id]) => id),
  personal: { name: '', email: '', phone: '', location: '', linkedin: '', github: '', portfolio: '' },
  personal_sources: {},
  summary: '',
  summary_source: 'student',
  education: [], skills: [], projects: [], experience: [], internships: [], certifications: [], achievements: [],
};

const ENTRY_FIELDS = {
  education: ['institution', 'degree', 'field', 'location', 'start_date', 'end_date', 'details'],
  skills: ['name', 'group'],
  projects: ['title', 'description', 'technologies', 'link'],
  experience: ['role', 'organization', 'location', 'start_date', 'end_date', 'description'],
  internships: ['role', 'organization', 'location', 'start_date', 'end_date', 'description'],
  certifications: ['name', 'issuer', 'date'],
  achievements: ['title', 'description'],
};

export function blankResumeEntry(section, entryId = globalThis.crypto?.randomUUID?.() || `entry-${Date.now()}`) {
  return Object.fromEntries([['entry_id', entryId], ['source', 'student'], ...ENTRY_FIELDS[section].map((field) => [field, ''])]);
}

export function mergeProfileImport(document, imported) {
  const next = structuredClone(document);
  for (const [field, value] of Object.entries(imported.personal || {})) {
    if (!next.personal[field]?.trim() && value?.trim()) {
      next.personal[field] = value;
      next.personal_sources[field] = 'profile';
    }
  }
  for (const section of ['education', 'skills', 'projects', 'experience', 'internships', 'certifications', 'achievements']) {
    const existingIds = new Set(next[section].map((entry) => entry.entry_id));
    for (const entry of imported[section] || []) {
      if (!existingIds.has(entry.entry_id)) next[section].push(entry);
    }
  }
  return next;
}

export function moveSection(order, section, direction) {
  const index = order.indexOf(section);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= order.length) return order;
  const next = [...order];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}

export function moveEntry(entries, entryId, direction) {
  const index = entries.findIndex((entry) => entry.entry_id === entryId);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= entries.length) return entries;
  const next = [...entries];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}

const populated = (value) => typeof value === 'string' ? value.trim().length > 0
  : Array.isArray(value) ? value.some(populated) : Boolean(value);

export function resumeCompleteness(document) {
  const hasContact = populated(document.personal.name)
    && (populated(document.personal.email) || populated(document.personal.phone));
  const hasEducation = document.education.some((entry) => populated(entry.institution) || populated(entry.degree));
  const hasSkills = document.skills.some((entry) => populated(entry.name));
  const hasProjectDescription = document.projects.some((entry) => populated(entry.description));
  const hasExperience = [...document.experience, ...document.internships]
    .some((entry) => populated(entry.organization) || populated(entry.role));
  return [
    { id: 'contact', label: 'Name and at least one contact method', complete: hasContact, optional: false },
    { id: 'education', label: 'Education details', complete: hasEducation, optional: false },
    { id: 'skills', label: 'At least one skill', complete: hasSkills, optional: false },
    { id: 'projects', label: 'A project description', complete: hasProjectDescription, optional: false },
    { id: 'experience', label: 'Work or internship details, if applicable', complete: hasExperience, optional: true },
  ];
}

export function sectionHasContent(document, section) {
  if (section === 'summary') return populated(document.summary);
  return (document[section] || []).some((entry) => Object.entries(entry)
    .some(([key, value]) => key !== 'entry_id' && key !== 'source' && populated(value)));
}
