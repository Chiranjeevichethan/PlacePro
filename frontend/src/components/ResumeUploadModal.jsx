import { useEffect, useRef, useState } from "react";
import AccessibleModal from "./AccessibleModal";
import { verifyStudentProfile } from "../services/api";
import ResumeEvidenceEditor from './ResumeEvidenceEditor';
import { createRetryIntent } from '../services/retryIntent';
import { resumeDiagnosticInstance, traceResume } from '../services/resumeDiagnostics.js';
import { applyReviewEdits, loadResumeReview, validateReviewRecords, mergeResumeSelection,
  formatResumeFieldValue, resumeComparisonRows, resumeSelectionState } from '../services/profileReview';

/**
 * Initial modal state derived from a pending/restored draft (if any).
 * Extracted here so no setState-in-effect sync is needed.
 */
function initialStateFromDraft(resumeDraft) {
  if (!resumeDraft) {
    return { step: "upload", draft: null, message: null };
  }
  return {
    step: "review",
    draft: resumeDraft,
    message: "Draft profile loaded from your last resume upload.",
  };
}

/**
 * Schema-defined review fields for the draft profile.
 * Only backend-declared fields are listed here — nothing is invented.
 * `draftPath` points into the verbatim draft object.
 * `emptyLabel` is shown when the value is exactly null/empty: the field is
 * rendered as NOT SET, because the 10 ML prediction inputs MUST remain
 * missing until the student explicitly provides them.
 */
const REVIEW_FIELDS = [
  { key: "name", label: "Name", section: "personal", required: true },
  { key: "email", label: "Email", section: "personal", required: true },
  { key: "phone", label: "Phone", section: "personal" },
  { key: "location", label: "Location", section: "personal" },
  { key: "linkedin", label: "LinkedIn", section: "personal" },
  { key: "github", label: "GitHub", section: "personal" },
  { key: "portfolio", label: "Portfolio", section: "personal" },
  { key: "degree", label: "Degree", section: "education" },
  { key: "branch", label: "Branch", section: "education" },
  { key: "college", label: "College", section: "education" },
  { key: "cgpa", label: "CGPA", section: "education" },
  { key: "graduation_year", label: "Graduation Year", section: "education" },
];

/**
 * The 10 ML prediction inputs (from the canonical StudentProfile schema).
 * They are reported from the draft as missing/Not set — NEVER inferred
 * from resume content. The student provides them explicitly (now via the
 * Edit Profile modal, later via a dedicated ML-input form).
 */
const ML_INPUT_FIELDS = [
  { key: "college_tier", label: "College Tier" },
  { key: "backlogs", label: "Backlogs" },
  { key: "coding_skills", label: "Coding Skill" },
  { key: "dsa_score", label: "DSA Score" },
  { key: "aptitude_score", label: "Aptitude Score" },
  { key: "communication_skills", label: "Communication Skill" },
  { key: "ml_knowledge", label: "ML Knowledge" },
  { key: "system_design", label: "System Design" },
  { key: "open_source_contributions", label: "Open Source Contributions" },
  { key: "extracurriculars", label: "Extracurricular Activities" },
];

const isBlank = (value) =>
  value === null || value === undefined || String(value).trim() === "";

function ResumeUploadModal({
  resumeDraft,
  preservedProfile = null,
  onDraftCreated,
  onVerified,
  onClose = () => {},
}) {
  /* Initial state derived directly from props — a pending draft (restored
     from storage) opens straight into review. No effect-based sync. */
  const [{ step, draft, message }, setModalState] = useState(() =>
    initialStateFromDraft(preservedProfile?.profile_id ? null : resumeDraft)
  );
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [verifyError, setVerifyError] = useState(null);
  const [edits, setEdits] = useState({});
  const [baseProfile] = useState(() => preservedProfile ? structuredClone(preservedProfile) : null);
  const updatingExisting = Boolean(baseProfile?.profile_id);
  const [selectedFields, setSelectedFields] = useState([]);
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [extractionInfo, setExtractionInfo] = useState(null);
  const reviewBase = updatingExisting && draft ? mergeResumeSelection(baseProfile, draft, selectedFields) : draft;
  const comparisonRows = updatingExisting && draft ? resumeComparisonRows(baseProfile, draft) : [];
  const selection = resumeSelectionState(comparisonRows, selectedFields);
  const selectAllRef = useRef(null);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = selection.indeterminate;
  }, [step, selection.indeterminate]);
  const inputRef = useRef(null);
  const requestInFlight = useRef(false);
  const [uploadIntent] = useState(createRetryIntent);
  const [verifyIntent] = useState(createRetryIntent);
  const uploadKey = useRef(null);
  const mounted = useRef(false);
  const [diagnosticId] = useState(resumeDiagnosticInstance);
  useEffect(() => {
    mounted.current = true;
    traceResume('modal.mount', { instance: diagnosticId, source: 'ResumeUploadModal' });
    return () => {
      traceResume('modal.unmount', { instance: diagnosticId, source: 'ResumeUploadModal' });
      mounted.current = false;
    };
  }, [diagnosticId]);
  useEffect(() => {
    traceResume('modal.state', { instance: diagnosticId, source: 'ResumeUploadModal.commit',
      phase: step, uploading, verifying, selectedExperience: selectedFields.includes('experience') });
  }, [diagnosticId, step, uploading, verifying, selectedFields]);

  const requestClose = (reason, event) => {
    traceResume('close.request', { instance: diagnosticId, source: 'ResumeUploadModal.requestClose',
      reason, eventType: event?.type || '', eventTrusted: Boolean(event?.isTrusted),
      targetTag: event?.target?.tagName || '' });
    return onClose(event);
  };

  const goUploadStep = () => {
    traceResume('review.reset', { instance: diagnosticId, source: 'ResumeUploadModal.goUploadStep' });
    setModalState({ step: "upload", draft: null, message: null });
    setEdits({});
    setSelectedFields([]);
    setReviewConfirmed(false);
    setExtractionInfo(null);
  };

  const editKey = (section, key) => `${section}.${key}`;

  const setEdit = (section, key, value) => {
    const composite = editKey(section, key);
    setEdits((prev) => ({ ...prev, [composite]: value }));
    setReviewConfirmed(false);
  };

  const changeSelection = (nextSelection) => {
    const changed = new Set([...selectedFields, ...nextSelection]
      .filter(path => selectedFields.includes(path) !== nextSelection.includes(path)));
    setSelectedFields(nextSelection);
    setEdits((previous) => Object.fromEntries(Object.entries(previous).filter(([path]) => !changed.has(path))));
    setReviewConfirmed(false);
  };

  /**
   * Draft value after any explicit student edit. Returns a string for the
   * review inputs only — the underlying draft object is never mutated with
   * invented values.
   */
  const reviewedValue = (section, key) => {
    const composite = editKey(section, key);
    if (composite in edits) return edits[composite];
    const value = reviewBase?.[section]?.[key];
    return isBlank(value) ? "" : String(value);
  };

  const pickFile = (event) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    uploadKey.current = selected ? crypto.randomUUID() : null;
    setUploadError(null);
  };

  const handleUpload = async (event) => {
    event.preventDefault();
    if (requestInFlight.current) return;

    if (!file) {
      setUploadError("Please choose a resume file (.pdf or .docx) first.");
      return;
    }

    setUploading(true);
    traceResume('extraction.start', { instance: diagnosticId, source: 'ResumeUploadModal.handleUpload' });
    requestInFlight.current = true;
    setUploadError(null);

    try {
      const result = await loadResumeReview(file, baseProfile, uploadKey.current || uploadIntent([file.name,file.size,file.lastModified]));
      if (!mounted.current) {
        traceResume('extraction.ignored', { instance: diagnosticId, source: 'ResumeUploadModal.handleUpload', reason: 'unmounted' });
        return;
      }
      traceResume('extraction.complete', { instance: diagnosticId, source: 'ResumeUploadModal.handleUpload' });
      const draftProfile = result.draftProfile;
      setExtractionInfo(result);
      setModalState({ step: "review", draft: draftProfile, message: result.message });
      setEdits({});
      setSelectedFields([]);
      setReviewConfirmed(false);
      if (!result.updatesExisting) onDraftCreated?.({ ...result, draftProfile });
    } catch (err) {
      traceResume('extraction.error', { instance: diagnosticId, source: 'ResumeUploadModal.handleUpload', status: err?.status || 0 });
      if (mounted.current) setUploadError(
        err?.message ?? "Resume upload failed. Please try again."
      );
    } finally {
      requestInFlight.current = false;
      if (mounted.current) setUploading(false);
    }
  };

  /**
   * Build the FULL StudentProfile body for POST /api/profile/verify:
   * the verbatim draft (incl. exact null ML prediction inputs) plus only
   * the fields the student explicitly edited here. Nothing is inferred.
   */
  const buildVerifyBody = () => {
    const body = applyReviewEdits(reviewBase, edits);
    validateReviewRecords(body);
    return body;
  };

  const handleVerify = async () => {
    if (requestInFlight.current) return;
    if (updatingExisting && !reviewConfirmed) {
      setVerifyError('Review the changes and check the confirmation box before saving.');
      return;
    }
    const missing = REVIEW_FIELDS.filter((field) => field.required).filter(
      (field) => isBlank(reviewedValue(field.section, field.key))
    );

    if (missing.length > 0) {
      if (mounted.current) setVerifyError(
        `Please provide the required field(s): ${missing
          .map((f) => f.label)
          .join(", ")} before verifying.`
      );
      return;
    }

    setVerifying(true);
    traceResume('confirmation.start', { instance: diagnosticId, source: 'ResumeUploadModal.handleVerify' });
    requestInFlight.current = true;
    setVerifyError(null);

    try {
      const payload = buildVerifyBody();
      const data = await verifyStudentProfile(payload, verifyIntent(payload));
      if (mounted.current) {
        traceResume('confirmation.callback', { instance: diagnosticId, source: 'ResumeUploadModal.handleVerify' });
        onVerified?.(data);
      } else traceResume('confirmation.ignored', { instance: diagnosticId, source: 'ResumeUploadModal.handleVerify', reason: 'unmounted' });
    } catch (err) {
      traceResume('confirmation.error', { instance: diagnosticId, source: 'ResumeUploadModal.handleVerify', status: err?.status || 0 });
      setVerifyError(
        err?.message ?? "Profile verification failed. Please try again."
      );
    } finally {
      requestInFlight.current = false;
      if (mounted.current) setVerifying(false);
    }
  };

  const mlMissing = ML_INPUT_FIELDS.filter((field) =>
    isBlank(reviewBase?.ml_inputs?.[field.key])
  );

  return (
    <AccessibleModal
      labelledBy="resume-modal-title"
      describedBy={step === "upload" ? "resume-modal-description-upload" : "resume-modal-description-review"}
      closeBlocked={uploading || verifying}
      onEscape={(event) => requestClose("escape", event)}
      onBackdropClose={(event) => requestClose("backdrop", event)}
    >
        <div className="modal-header">
          <h2 id="resume-modal-title">
            {step === "upload" ? (updatingExisting ? "Update Profile from Resume" : "Create Profile from Resume")
              : (updatingExisting ? "Review Resume Changes" : "Review Draft Profile")}
          </h2>

          <button
            type="button"
            className="modal-close"
            onClick={(event) => requestClose('close-button', event)}
            aria-label="Close resume workflow"
            disabled={uploading || verifying}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {message && (
          <div className="form-error-summary resume-info-banner" role="status">
            {message}
          </div>
        )}

        {step === "upload" && (
          <form onSubmit={handleUpload} noValidate>
            {uploadError && (
              <div className="form-error-summary" role="alert">
                {uploadError}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="resume-file-input">Resume (.pdf or .docx)</label>
              <input
                ref={inputRef}
                id="resume-file-input"
                type="file"
                accept=".pdf,.docx"
                onChange={pickFile}
              />
              {file && (
                <span className="field-error resume-file-selected">
                  Selected: {file.name}
                </span>
              )}
            </div>

            <p id="resume-modal-description-upload" className="resume-note">
              PDF or DOCX, up to 5 MB. Readable text is required; scanned PDFs need OCR, which is unavailable.
              {updatingExisting ? ' Extraction saves nothing. Your existing information stays unchanged until you choose changes and confirm.' : <>The backend creates a <strong>draft</strong> profile from your
              resume. You will review it before confirming. The 10 ML
              prediction inputs stay empty until you provide them yourself.</>}
            </p>

            <div className="modal-actions">
              <button
                type="button"
                className="dash-btn secondary"
                onClick={(event) => requestClose('cancel', event)}
                disabled={uploading}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="dash-btn primary"
                disabled={uploading || !file}
              >
                {uploading ? "UPLOADING..." : "Upload & Extract"}
              </button>
            </div>
          </form>
        )}

        {step === "review" && draft && (
          <div>
            {verifyError && (
              <div className="form-error-summary" role="alert">
                {verifyError}
              </div>
            )}

            <h3 className="resume-section-heading">Resume extraction preview</h3>
            <p className="resume-note">Uploaded file: {file?.name || 'Previously uploaded resume'}.
              Uploading does not change your current profile.</p>
            <p id="resume-modal-description-review" className="resume-note">Extraction can miss or misread information. Review every selected value.
              Detected sections: {extractionInfo?.diagnostics?.detected_sections?.join(', ') || 'No labelled sections found'}.
              Missing fields remain empty; skill scores are never invented.</p>
            {updatingExisting && <details open className="resume-import-options">
              <summary>Choose fields to use from this resume <span aria-live="polite">({selection.selectedCount} selected)</span></summary>
              <label className="resume-select-all">
                <input ref={selectAllRef} type="checkbox" checked={selection.allSelected}
                  aria-checked={selection.indeterminate ? 'mixed' : selection.allSelected}
                  disabled={verifying || selection.eligiblePaths.length === 0}
                  onChange={(event) => changeSelection(event.target.checked ? selection.eligiblePaths : [])} />
                Select all
              </label>
              <p>“Extracted from uploaded file” shows only the extraction. “Current profile” shows stored information.
                Unchecked fields keep your current values, including your name and email.
                Selecting a list replaces that list; review its entries below.
                Changing a selection resets any correction for that field.</p>
              {comparisonRows.map(({ path, currentValue, extractedValue }) => <div className="resume-import-option" key={path}>
                <label><input type="checkbox" checked={selectedFields.includes(path)} disabled={verifying}
                  onChange={(event) => {
                    changeSelection(event.target.checked ? [...selectedFields, path] : selectedFields.filter((item) => item !== path));
                  }} /> Use resume: {path.replaceAll('.', ' ').replaceAll('_', ' ')}</label>
                <div style={{ whiteSpace: 'pre-wrap' }}>Current profile: {formatResumeFieldValue(currentValue)}</div>
                <div style={{ whiteSpace: 'pre-wrap' }}>Extracted from uploaded file: {formatResumeFieldValue(extractedValue)}</div>
              </div>)}
            </details>}
            <h3 className="resume-section-heading">Profile values to save after your review</h3>
            <p className="resume-note">The editable fields below contain your current values plus the resume fields
              you selected and your corrections. They are not a separate extraction result.
              Nothing is saved until you confirm.</p>
            <div className="modal-fields">
              {REVIEW_FIELDS.map((field) => {
                const value = reviewedValue(field.section, field.key);
                const fromResume = !updatingExisting || selectedFields.includes(editKey(field.section, field.key));
                const wasExtracted = fromResume && !isBlank(draft?.[field.section]?.[field.key]);

                return (
                  <div key={field.key} className="form-group">
                    <label htmlFor={`review-${field.key}`}>
                      {field.label}
                      {field.required ? " *" : ""}
                      {editKey(field.section, field.key) in edits ? ' (your correction)' : wasExtracted ? ' (from resume)' : updatingExisting ? ' (current value)' : ''}
                    </label>
                    <input
                      id={`review-${field.key}`}
                      type="text"
                      value={value}
                      placeholder={wasExtracted ? "" : "Not provided"}
                      onChange={(event) =>
                        setEdit(field.section, field.key, event.target.value)
                      }
                      disabled={verifying}
                    />
                  </div>
                );
              })}
            </div>

            <ResumeEvidenceEditor profile={applyReviewEdits(reviewBase, edits, false)}
              disabled={verifying}
              onChange={(path, value) => {
                if (path === 'experience') traceResume('experience.edit', { instance: diagnosticId, source: 'ResumeEvidenceEditor.onChange' });
                setEdits((previous) => ({ ...previous, [path]: value }));
                setReviewConfirmed(false);
              }} />

            <h3 className="resume-section-heading">
              ML Prediction Inputs (not in the resume)
            </h3>
            <p className="resume-note">
              {mlMissing.length === ML_INPUT_FIELDS.length
                ? "These are currently empty and were NOT taken from your resume. Provide them after verifying, via Edit Profile."
                : `Still missing: ${mlMissing.map((f) => f.label).join(", ")}.`}
            </p>
            <div className="profile-grid">
              {ML_INPUT_FIELDS.map((field) => (
                <div key={field.key} className="profile-item">
                  <span>{field.label}</span>
                  <strong>{isBlank(reviewBase?.ml_inputs?.[field.key]) ? "Not set" : String(reviewBase.ml_inputs[field.key])}</strong>
                  <small>{isBlank(reviewBase?.ml_inputs?.[field.key]) ? "To be provided by you" : "Preserved provided value"}</small>
                </div>
              ))}
            </div>

            {updatingExisting && <label className={`resume-confirmation${reviewConfirmed ? ' is-confirmed' : ''}`}>
              <input id="resume-confirm-update" type="checkbox" checked={reviewConfirmed} disabled={verifying}
                onChange={(event) => setReviewConfirmed(event.target.checked)} />
              <span>I reviewed the selected values and corrections and confirm updating my profile.</span>
            </label>}
            <div className="modal-actions">
              <button
                type="button"
                className="dash-btn secondary"
                onClick={goUploadStep}
                disabled={uploading || verifying}
              >
                Upload a Different Resume
              </button>

              <button
                type="button"
                className="dash-btn primary"
                onClick={handleVerify}
                disabled={uploading || verifying || (updatingExisting && !reviewConfirmed)}
              >
                {verifying ? "SAVING..." : updatingExisting ? "Confirm & Update My Profile" : "Confirm Profile"}
              </button>
            </div>
          </div>
        )}
    </AccessibleModal>
  );
}

export default ResumeUploadModal;
