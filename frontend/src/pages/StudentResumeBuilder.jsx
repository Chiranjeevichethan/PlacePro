import { useEffect, useMemo, useState } from 'react';
import { useStudentProfileContext } from '../hooks/useStudentProfileContext.js';
import {
  exportResumePdf, fetchResumeDraft, importResumeProfile, saveResumeDraft,
} from '../services/resumeBuilderApi.js';
import {
  blankResumeEntry, DEFAULT_RESUME_DOCUMENT, mergeProfileImport, moveEntry, moveSection,
  RESUME_SECTIONS, resumeCompleteness, sectionHasContent,
} from '../services/resumeBuilder.js';

const PERSONAL_FIELDS = [
  ['name', 'Full name'], ['email', 'Email'], ['phone', 'Phone'], ['location', 'Location'],
  ['linkedin', 'LinkedIn'], ['github', 'GitHub'], ['portfolio', 'Portfolio or website'],
];
const ENTRY_FIELDS = {
  education: [
    ['degree', 'Degree or qualification'], ['field', 'Field of study'], ['institution', 'Institution'],
    ['location', 'Location'], ['start_date', 'Start date'], ['end_date', 'End date or graduation year'],
    ['details', 'Additional details', 'textarea'],
  ],
  skills: [['name', 'Skill'], ['group', 'Category']],
  projects: [['title', 'Project name'], ['description', 'Description', 'textarea'],
    ['technologies', 'Technologies'], ['link', 'Project link']],
  experience: [['role', 'Role'], ['organization', 'Organization'], ['location', 'Location'],
    ['start_date', 'Start date'], ['end_date', 'End date'], ['description', 'Responsibilities or outcomes', 'textarea']],
  internships: [['role', 'Role'], ['organization', 'Organization'], ['location', 'Location'],
    ['start_date', 'Start date'], ['end_date', 'End date'], ['description', 'Responsibilities or outcomes', 'textarea']],
  certifications: [['name', 'Certification'], ['issuer', 'Issuer'], ['date', 'Date or year']],
  achievements: [['title', 'Achievement'], ['description', 'Details', 'textarea']],
};
const SECTION_LABEL = Object.fromEntries(RESUME_SECTIONS);

function originLabel(source, value = 'present') {
  if (!value?.trim()) return 'Missing';
  return source === 'profile' ? 'Imported from profile' : 'Entered by you';
}

function EditorField({ id, label, value, multiline = false, disabled, onChange }) {
  return <label className="resume-builder-field" htmlFor={id}>
    <span>{label}</span>
    {multiline
      ? <textarea id={id} rows={3} value={value || ''} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
      : <input id={id} value={value || ''} disabled={disabled} onChange={(event) => onChange(event.target.value)} />}
  </label>;
}

function PreviewEntry({ section, entry }) {
  if (section === 'skills') return <span className="resume-preview-skill">{entry.name}</span>;
  if (section === 'education') return <article className="resume-preview-entry">
    <div className="resume-preview-entry-heading"><strong>{[entry.degree, entry.field].filter(Boolean).join(' · ')}</strong>
      <span>{[entry.start_date, entry.end_date].filter(Boolean).join(' – ')}</span></div>
    <p>{[entry.institution, entry.location].filter(Boolean).join(' · ')}</p>
    {entry.details && <p>{entry.details}</p>}
  </article>;
  if (section === 'projects') return <article className="resume-preview-entry">
    <strong>{entry.title}</strong>{entry.description && <p>{entry.description}</p>}
    {entry.technologies && <p><b>Technologies:</b> {entry.technologies}</p>}
    {entry.link && <p>{entry.link}</p>}
  </article>;
  if (section === 'experience' || section === 'internships') return <article className="resume-preview-entry">
    <div className="resume-preview-entry-heading"><strong>{[entry.role, entry.organization].filter(Boolean).join(' · ')}</strong>
      <span>{[entry.start_date, entry.end_date].filter(Boolean).join(' – ')}</span></div>
    {entry.location && <p>{entry.location}</p>}{entry.description && <p>{entry.description}</p>}
  </article>;
  if (section === 'certifications') return <p className="resume-preview-entry">
    <strong>{entry.name}</strong>{[entry.issuer, entry.date].filter(Boolean).length > 0
      ? ` · ${[entry.issuer, entry.date].filter(Boolean).join(' · ')}` : ''}
  </p>;
  if (section === 'achievements') return <article className="resume-preview-entry">
    <strong>{entry.title}</strong>{entry.description && <p>{entry.description}</p>}
  </article>;
  return null;
}

function ResumePreview({ document }) {
  const personal = document.personal;
  const visible = document.section_order.filter((section) => document.visible_sections.includes(section)
    && sectionHasContent(document, section));
  const contactValues = ['email', 'phone', 'location', 'linkedin', 'github', 'portfolio']
    .map((field) => personal[field]).filter(Boolean);

  return <article className={`resume-paper resume-template-${document.template}`} aria-label={`${document.template} resume preview`}>
    <header className="resume-paper-header">
      <h2>{personal.name || <span className="resume-preview-placeholder">Add your name</span>}</h2>
      {contactValues.length > 0
        ? <p>{contactValues.join('  |  ')}</p>
        : <p className="resume-preview-placeholder">Add contact information</p>}
    </header>
    {visible.map((section) => <section className="resume-paper-section" key={section}>
      <h3>{SECTION_LABEL[section]}</h3>
      {section === 'summary' ? <p>{document.summary}</p>
        : section === 'skills' ? <div className="resume-preview-skills">{document.skills.filter((entry) => entry.name)
          .map((entry) => <PreviewEntry key={entry.entry_id} section={section} entry={entry} />)}</div>
          : <div className="resume-preview-list">{document[section].map((entry) => <PreviewEntry key={entry.entry_id} section={section} entry={entry} />)}</div>}
    </section>)}
    {visible.length === 0 && <p className="resume-preview-placeholder">Add information in the editor to see resume sections here.</p>}
  </article>;
}

export default function StudentResumeBuilder() {
  const { profileId } = useStudentProfileContext();
  const [document, setDocument] = useState(() => structuredClone(DEFAULT_RESUME_DOCUMENT));
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState('');
  const [savedSnapshot, setSavedSnapshot] = useState(null);

  useEffect(() => {
    let active = true;
    fetchResumeDraft(profileId).then((result) => {
      if (active) {
        setDocument(result.draft);
        setSavedSnapshot(JSON.stringify(result.draft));
      }
    }).catch((requestError) => {
      if (active) setError({ message: requestError.message, status: requestError.status, operation: 'load' });
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [profileId]);

  const hasUnsavedChanges = savedSnapshot !== null && JSON.stringify(document) !== savedSnapshot;
  useEffect(() => {
    if (!hasUnsavedChanges) return undefined;
    const warnBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [hasUnsavedChanges]);

  const completeness = useMemo(() => resumeCompleteness(document), [document]);
  const update = (callback) => {
    setNotice('');
    setDocument((current) => callback(structuredClone(current)));
  };
  const changePersonal = (field, value) => update((current) => {
    current.personal[field] = value;
    current.personal_sources[field] = 'student';
    return current;
  });
  const changeSummary = (value) => update((current) => ({ ...current, summary: value, summary_source: 'student' }));

  const importProfile = async () => {
    if (busy) return;
    setBusy(true); setError(null); setNotice('');
    try {
      const result = await importResumeProfile(profileId);
      setDocument((current) => mergeProfileImport(current, result.content));
      setNotice('Available profile information was added where the resume was empty. Review it and save your resume.');
    } catch (requestError) { setError({ message: requestError.message, status: requestError.status, operation: 'import' }); }
    finally { setBusy(false); }
  };

  const save = async () => {
    if (busy) return null;
    setBusy(true); setError(null); setNotice('');
    try {
      const result = await saveResumeDraft(profileId, document);
      setDocument(result.draft);
      setSavedSnapshot(JSON.stringify(result.draft));
      setNotice('Resume draft saved to your account.');
      return result.draft;
    } catch (requestError) { setError({ message: requestError.message, status: requestError.status, operation: 'save' }); return null; }
    finally { setBusy(false); }
  };

  const exportPdf = async () => {
    if (busy) return;
    setBusy(true); setError(null); setNotice('');
    try {
      const saved = await saveResumeDraft(profileId, document);
      setDocument(saved.draft);
      setSavedSnapshot(JSON.stringify(saved.draft));
      const blob = await exportResumePdf(profileId);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement('a');
      anchor.href = url;
      anchor.download = 'placepro-resume.pdf';
      window.document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice('PDF downloaded. Check the file before sharing it.');
    } catch (requestError) { setError({ message: requestError.message, status: requestError.status, operation: 'export' }); }
    finally { setBusy(false); }
  };

  const retry = async () => {
    if (busy || error?.status === 401) return;
    // Retry the failed operation with the current document, including new edits.
    // Reloading a saved draft is only appropriate after the initial load failed.
    if (error?.operation === 'save') return save();
    if (error?.operation === 'import') return importProfile();
    if (error?.operation === 'export') return exportPdf();
    setLoading(true); setError(null);
    try {
      const result = await fetchResumeDraft(profileId);
      setDocument(result.draft);
      setSavedSnapshot(JSON.stringify(result.draft));
    } catch (requestError) { setError({ message: requestError.message, status: requestError.status, operation: 'load' }); }
    finally { setLoading(false); }
  };

  const updateEntry = (section, entryId, field, value) => update((current) => {
    current[section] = current[section].map((entry) => entry.entry_id === entryId
      ? { ...entry, [field]: value, source: 'student' } : entry);
    return current;
  });

  if (loading) return <div className="resume-builder-page"><p role="status">Loading your saved resume…</p></div>;

  return <div className="resume-builder-page">
    <header className="page-header resume-builder-page-header">
      <div><h1>Student Resume Builder</h1>
        <p>Build a resume from information you provide or explicitly import from your saved profile. Nothing here changes your profile.</p></div>
      <div className="resume-builder-toolbar">
        <button type="button" className="dash-btn secondary" disabled={busy} onClick={importProfile}>Import profile information</button>
        <button type="button" className="dash-btn secondary" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save draft'}</button>
        <button type="button" className="dash-btn primary" disabled={busy} onClick={exportPdf}>Export PDF</button>
      </div>
    </header>
    {error && <div className="resume-builder-error" role="alert"><p>{error.message}</p>
      <button type="button" className="dash-btn secondary" disabled={busy || error.status === 401} onClick={retry}>Retry</button></div>}
    {notice && <p className="resume-builder-notice" role="status">{notice}</p>}
    {hasUnsavedChanges && <p className="resume-builder-notice">Unsaved changes. Save your draft before closing this page.</p>}
    <div className="resume-builder-layout">
      <section className="resume-editor-panel" aria-labelledby="resume-editor-title">
        <div className="resume-editor-panel-heading"><div><span className="career-eyebrow">YOUR CONTENT</span><h2 id="resume-editor-title">Resume editor</h2></div>
          <label className="resume-template-select">Template
            <select value={document.template} disabled={busy} onChange={(event) => update((current) => ({ ...current, template: event.target.value }))}>
              <option value="classic">Classic serif</option><option value="modern">Modern sans serif</option>
            </select>
          </label>
        </div>

        <section className="resume-editor-card" aria-labelledby="resume-contact-title">
          <div className="resume-editor-card-heading"><h3 id="resume-contact-title">Personal information</h3><span className="resume-origin-label">Imported values are labelled</span></div>
          <div className="resume-builder-field-grid">
            {PERSONAL_FIELDS.map(([field, label]) => <div className="resume-origin-field" key={field}>
              <EditorField id={`resume-personal-${field}`} label={label} value={document.personal[field]} disabled={busy}
                onChange={(value) => changePersonal(field, value)} />
              <span>{originLabel(document.personal_sources[field], document.personal[field])}</span>
            </div>)}
          </div>
        </section>

        <div className="resume-section-editor-list">
          {document.section_order.map((section, sectionIndex) => (
            <section className={`resume-editor-card ${document.visible_sections.includes(section) ? '' : 'resume-section-hidden'}`} key={section}>
              <div className="resume-editor-card-heading resume-section-editor-heading">
                <div><h3>{SECTION_LABEL[section]}</h3><span className="resume-origin-label">
                  {section === 'summary' ? originLabel(document.summary_source) : `${document[section].length} item${document[section].length === 1 ? '' : 's'}`}
                </span></div>
                <div className="resume-section-controls">
                  <label><input type="checkbox" checked={document.visible_sections.includes(section)} disabled={busy}
                    onChange={(event) => update((current) => ({ ...current, visible_sections: event.target.checked
                      ? [...current.visible_sections, section] : current.visible_sections.filter((item) => item !== section) }))} /> Show</label>
                  <button type="button" className="resume-icon-action" aria-label={`Move ${SECTION_LABEL[section]} up`}
                    disabled={busy || sectionIndex === 0} onClick={() => update((current) => ({ ...current,
                      section_order: moveSection(current.section_order, section, -1) }))}>↑</button>
                  <button type="button" className="resume-icon-action" aria-label={`Move ${SECTION_LABEL[section]} down`}
                    disabled={busy || sectionIndex === document.section_order.length - 1} onClick={() => update((current) => ({ ...current,
                      section_order: moveSection(current.section_order, section, 1) }))}>↓</button>
                </div>
              </div>
              {section === 'summary' ? <div className="resume-builder-field-grid">
                <EditorField id="resume-summary" label="Career objective or professional summary" value={document.summary}
                  multiline disabled={busy} onChange={changeSummary} />
              </div> : <>
                {document[section].map((entry, entryIndex) => <article className="resume-entry-editor" key={entry.entry_id}>
                  <div className="resume-entry-editor-heading"><strong>{entry[ENTRY_FIELDS[section][0][0]] || `${SECTION_LABEL[section]} item ${entryIndex + 1}`}</strong>
                    <span className="resume-origin-label">{originLabel(entry.source)}</span></div>
                  <div className="resume-builder-field-grid">
                    {ENTRY_FIELDS[section].map(([field, label, type]) => <EditorField key={field}
                      id={`resume-${section}-${entry.entry_id}-${field}`} label={label} value={entry[field]}
                      multiline={type === 'textarea'} disabled={busy}
                      onChange={(value) => updateEntry(section, entry.entry_id, field, value)} />)}
                  </div>
                  <div className="resume-entry-actions">
                    <button type="button" className="dashboard-action-link" disabled={busy || entryIndex === 0}
                      onClick={() => update((current) => ({ ...current,
                        [section]: moveEntry(current[section], entry.entry_id, -1) }))}>Move up</button>
                    <button type="button" className="dashboard-action-link" disabled={busy || entryIndex === document[section].length - 1}
                      onClick={() => update((current) => ({ ...current,
                        [section]: moveEntry(current[section], entry.entry_id, 1) }))}>Move down</button>
                    <button type="button" className="dashboard-action-link resume-remove-entry" disabled={busy}
                      onClick={() => update((current) => ({ ...current,
                        [section]: current[section].filter((item) => item.entry_id !== entry.entry_id) }))}>Remove</button>
                  </div>
                </article>)}
                <button type="button" className="dash-btn secondary resume-add-entry" disabled={busy}
                  onClick={() => update((current) => ({ ...current,
                    [section]: [...current[section], blankResumeEntry(section)] }))}>Add {section === 'skills' ? 'skill' : 'item'}</button>
              </>}
            </section>
          ))}
        </div>
      </section>

      <aside className="resume-builder-sidebar">
        <section className="resume-completeness-card" aria-labelledby="resume-checklist-title">
          <span className="career-eyebrow">CONTENT CHECKLIST</span><h2 id="resume-checklist-title">Useful sections to review</h2>
          <ul>{completeness.map((item) => <li key={item.id} className={item.complete ? 'is-complete' : item.optional ? 'is-optional' : 'is-missing'}>
            <span aria-hidden="true">{item.complete ? '✓' : item.optional ? '○' : '!'}</span>
            <span>{item.label}<small>{item.complete ? 'Added' : item.optional ? 'Optional' : 'Not added yet'}</small></span>
          </li>)}</ul>
          <p>This checklist is guidance, not a resume score or ATS compatibility claim.</p>
        </section>
        <div className="resume-preview-heading"><div><span className="career-eyebrow">LIVE PREVIEW</span><h2>Preview</h2></div>
          <span>{document.template === 'classic' ? 'Classic serif' : 'Modern sans serif'}</span></div>
        <ResumePreview document={document} />
      </aside>
    </div>
  </div>;
}
