import { useEffect, useRef, useState } from "react";
import {
  createProfileFromResume,
  verifyStudentProfile,
} from "../services/api";

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

const SKILL_KEYS = [
  "programming_languages",
  "frameworks",
  "databases",
  "cloud",
  "ai_ml",
  "web_technologies",
  "tools",
  "other_skills",
];

function ResumeUploadModal({
  resumeDraft,
  onDraftCreated,
  onVerified,
  onClose = () => {},
}) {
  /* Initial state derived directly from props — a pending draft (restored
     from storage) opens straight into review. No effect-based sync. */
  const [{ step, draft, message }, setModalState] = useState(() =>
    initialStateFromDraft(resumeDraft)
  );
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [verifyError, setVerifyError] = useState(null);
  const [edits, setEdits] = useState({});
  const inputRef = useRef(null);

  const goUploadStep = () => {
    setModalState({ step: "upload", draft: null, message: null });
    setEdits({});
  };

  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === "Escape" && !uploading && !verifying) onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, uploading, verifying]);

  const editKey = (section, key) => `${section}.${key}`;

  const setEdit = (section, key, value) => {
    const composite = editKey(section, key);
    setEdits((prev) => ({ ...prev, [composite]: value }));
  };

  /**
   * Draft value after any explicit student edit. Returns a string for the
   * review inputs only — the underlying draft object is never mutated with
   * invented values.
   */
  const reviewedValue = (section, key) => {
    const composite = editKey(section, key);
    if (composite in edits) return edits[composite];
    const value = draft?.[section]?.[key];
    return isBlank(value) ? "" : String(value);
  };

  const pickFile = (event) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setUploadError(null);
  };

  const handleUpload = async (event) => {
    event.preventDefault();

    if (!file) {
      setUploadError("Please choose a resume file (.pdf or .docx) first.");
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const result = await createProfileFromResume(file);
      setModalState({ step: "review", draft: result.draftProfile, message: result.message });
      setEdits({});
      onDraftCreated?.(result);
    } catch (err) {
      setUploadError(
        err?.message ?? "Resume upload failed. Please try again."
      );
    } finally {
      setUploading(false);
    }
  };

  /**
   * Build the FULL StudentProfile body for POST /api/profile/verify:
   * the verbatim draft (incl. exact null ML prediction inputs) plus only
   * the fields the student explicitly edited here. Nothing is inferred.
   */
  const buildVerifyBody = () => {
    const body = JSON.parse(JSON.stringify(draft ?? {}));

    for (const [composite, raw] of Object.entries(edits)) {
      const [section, key] = composite.split(".");
      const value = String(raw).trim();

      if (value === "") continue; // blank = leave the draft value as-is

      const numericKeys = new Set(["cgpa", "graduation_year"]);
      if (section === "education" && numericKeys.has(key)) {
        const parsed = Number(value);
        body[section][key] = Number.isFinite(parsed) ? parsed : null;
      } else {
        body[section][key] = value;
      }
    }

    body.verified = false; // the backend flips this to true on verify
    return body;
  };

  const handleVerify = async () => {
    const missing = REVIEW_FIELDS.filter((field) => field.required).filter(
      (field) => isBlank(reviewedValue(field.section, field.key))
    );

    if (missing.length > 0) {
      setVerifyError(
        `Please provide the required field(s): ${missing
          .map((f) => f.label)
          .join(", ")} before verifying.`
      );
      return;
    }

    setVerifying(true);
    setVerifyError(null);

    try {
      const data = await verifyStudentProfile(buildVerifyBody());
      onVerified?.(data);
    } catch (err) {
      setVerifyError(
        err?.message ?? "Profile verification failed. Please try again."
      );
    } finally {
      setVerifying(false);
    }
  };

  const skillEntries = draft?.skills
    ? SKILL_KEYS.flatMap((key) =>
        Array.isArray(draft.skills[key]) ? draft.skills[key] : []
      )
    : [];

  const structuralCounts = [
    { label: "Experience", count: draft?.experience?.length ?? 0 },
    { label: "Internships", count: draft?.internships?.length ?? 0 },
    { label: "Projects", count: draft?.projects?.length ?? 0 },
    { label: "Certifications", count: draft?.certifications?.length ?? 0 },
    {
      label: "Hackathons",
      count: Array.isArray(draft?.achievements?.hackathons)
        ? draft.achievements.hackathons.length
        : 0,
    },
  ];

  const mlMissing = ML_INPUT_FIELDS.filter((field) =>
    isBlank(draft?.ml_inputs?.[field.key])
  );

  return (
    <div
      className="modal-overlay"
      onClick={uploading || verifying ? undefined : onClose}
      role="presentation"
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="resume-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="resume-modal-title">
            {step === "upload" ? "Create Profile from Resume" : "Review Draft Profile"}
          </h2>

          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
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

            <p className="resume-note">
              The backend creates a <strong>draft</strong> profile from your
              resume. You will review it before confirming. The 10 ML
              prediction inputs stay empty until you provide them yourself.
            </p>

            <div className="modal-actions">
              <button
                type="button"
                className="dash-btn secondary"
                onClick={onClose}
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

            <h3 className="resume-section-heading">Extracted Information</h3>
            <div className="modal-fields">
              {REVIEW_FIELDS.map((field) => {
                const value = reviewedValue(field.section, field.key);
                const wasExtracted = !isBlank(draft?.[field.section]?.[field.key]);

                return (
                  <div key={field.key} className="form-group">
                    <label htmlFor={`review-${field.key}`}>
                      {field.label}
                      {field.required ? " *" : ""}
                      {wasExtracted && " (from resume)"}
                    </label>
                    <input
                      id={`review-${field.key}`}
                      type="text"
                      value={value}
                      placeholder={wasExtracted ? "" : "Not provided"}
                      onChange={(event) =>
                        setEdit(field.section, field.key, event.target.value)
                      }
                    />
                  </div>
                );
              })}
            </div>

            <h3 className="resume-section-heading">Skills</h3>
            {skillEntries.length > 0 ? (
              <div className="profile-skills-row">
                {skillEntries.map((skill, index) => (
                  <span key={`${skill}-${index}`} className="skill-chip matched">
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="resume-note">No skills detected in the resume.</p>
            )}

            <h3 className="resume-section-heading">Activities</h3>
            <div className="profile-grid">
              {structuralCounts.map((item) => (
                <div key={item.label} className="profile-item">
                  <span>{item.label}</span>
                  <strong>{item.count}</strong>
                  <small>Extracted entries</small>
                </div>
              ))}
            </div>

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
                  <strong>{isBlank(draft?.ml_inputs?.[field.key]) ? "Not set" : String(draft.ml_inputs[field.key])}</strong>
                  <small>{isBlank(draft?.ml_inputs?.[field.key]) ? "To be provided by you" : "Provided value"}</small>
                </div>
              ))}
            </div>

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
                disabled={uploading || verifying}
              >
                {verifying ? "VERIFYING..." : "Confirm Profile"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResumeUploadModal;
