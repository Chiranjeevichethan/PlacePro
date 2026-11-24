import { ACTIVITY_FIELDS, RECORD_FIELDS, REVIEW_DETAILS, SKILL_FIELDS,
  parseActivityList, parseClaimList } from '../services/profileReview';

const label = (value) => value.replaceAll('_', ' ').replace(/^./, (char) => char.toUpperCase());

/** Actual schema fields and records; counts always derive from these lists. */
export default function ResumeEvidenceEditor({ profile, onChange, disabled = false, includeDetails = false }) {
  const input = (path, value, handle, multiline = false) => (
    <div className="form-group" key={path}>
      <label htmlFor={`evidence-${path}`}>{label(path.replaceAll('.', ' '))}</label>
      {multiline ? <textarea id={`evidence-${path}`} value={value ?? ''} disabled={disabled}
        rows={3} onChange={(event) => handle(event.target.value)} />
        : <input id={`evidence-${path}`} value={value ?? ''} disabled={disabled}
          onChange={(event) => handle(event.target.value)} />}
    </div>
  );
  return <div>
    {includeDetails && <><h3 className="resume-section-heading">Profile details</h3>
      <div className="modal-fields">{Object.entries(REVIEW_DETAILS).flatMap(([section, keys]) =>
        keys.map((key) => input(`${section}.${key}`, profile[section]?.[key],
          (value) => onChange(`${section}.${key}`, value))))}</div></>}
    <h3 className="resume-section-heading">Skill claims</h3>
    <p className="resume-note">Separate skills with commas. These are claims; assessment scores are kept separately.</p>
    <div className="modal-fields">{SKILL_FIELDS.map((key) => input(`skills.${key}`,
      (profile.skills?.[key] ?? []).join(', '), (value) => onChange(`skills.${key}`, parseClaimList(value))))}</div>
    {Object.entries(RECORD_FIELDS).map(([section, fields]) => <div key={section}>
      <h3 className="resume-section-heading">{label(section)} ({profile[section]?.length ?? 0})</h3>
      {(profile[section] ?? []).map((entry, index) => <fieldset key={`${section}-${index}`} disabled={disabled}>
        <legend>{label(section)} {index + 1}</legend>
        <div className="modal-fields">{fields.map((key) => input(`${section}.${index}.${key}`,
          key === 'technologies' ? (entry[key] ?? []).join(', ') : entry[key], (value) => {
            const entries = structuredClone(profile[section]);
            entries[index][key] = key === 'technologies' ? parseClaimList(value)
              : value === '' ? null : value;
            onChange(section, entries);
          }, key === 'description'))}</div>
        {!disabled && <button type="button" className="dash-btn secondary"
          onClick={() => onChange(section, profile[section].filter((_, i) => i !== index))}>
          Remove {label(section)} {index + 1}</button>}
      </fieldset>)}
      {!disabled && <button type="button" className="dash-btn secondary" onClick={() => onChange(section,
        [...(profile[section] ?? []), Object.fromEntries(fields.map((key) => [key, key === 'technologies' ? [] : null]))])}>
        Add {label(section)}</button>}
    </div>)}
    <h3 className="resume-section-heading">Activities</h3>
    <p className="resume-note">One actual activity per line. Enter records rather than a total count.</p>
    {ACTIVITY_FIELDS.map((key) => input(`achievements.${key}`, (profile.achievements?.[key] ?? []).join('\n'),
      (value) => onChange(`achievements.${key}`, parseActivityList(value)), true))}
  </div>;
}
