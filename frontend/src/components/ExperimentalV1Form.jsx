import { useState } from 'react';
import StudentForm from './StudentForm';
import { initialFormData } from '../data/formDefaults.js';
import { buildExperimentalV1DraftFromProfile } from '../services/experimentalV1Profile.js';

// Reuse the reference form without changing its production implementation.
function ExperimentalV1Form({ onPredict, isSubmitting = false, profile = null, onValuesChange }) {
  const [manualEdits, setManualEdits] = useState({});
  const draft = { ...initialFormData, ...buildExperimentalV1DraftFromProfile(profile), ...manualEdits };
  const handleDraftChange = (next) => {
    const changes = Object.fromEntries(Object.entries(next).filter(([field, value]) => value !== draft[field]));
    if (!Object.keys(changes).length) return;
    setManualEdits((previous) => ({ ...previous, ...changes }));
    onValuesChange?.();
  };

  return <div className="experimental-v1-form">
    <StudentForm draft={draft} onDraftChange={handleDraftChange}
      onPredict={(values) => { if (!isSubmitting) onPredict(values); }} isSubmitting={isSubmitting} />
  </div>;
}

export default ExperimentalV1Form;
