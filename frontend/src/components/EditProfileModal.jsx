import { useRef, useState } from "react";
import { updateStudentProfile } from "../services/api";
import AccessibleModal from "./AccessibleModal";
import { createRetryIntent } from '../services/retryIntent';
import ResumeEvidenceEditor from './ResumeEvidenceEditor';
import { applyReviewEdits, buildProfileCorrection, validateReviewRecords } from '../services/profileReview';
import {
  BRANCH_OPTIONS,
  EDIT_RANGES,
  TIER_OPTIONS,
  buildEditState,
} from "../services/profileConfig";

/**
 * Editable fields are exactly the fields supported by the backend PUT
 * schema (PersonalInfo.name, EducationInfo.branch/cgpa, MlInputs,
 * and the AdditionalInfo subset below). Server-controlled fields
 * (provenance, verified, prediction history, assessment evidence) remain
 * server controlled. Structural resume sections can be corrected below.
 */
const FIELDS = [
  { name: "name", label: "Name", type: "text", placeholder: "Full name" },
  {
    name: "branch",
    label: "Branch",
    type: "select",
    options: BRANCH_OPTIONS,
    placeholder: "Select Branch",
  },
  {
    name: "collegeTier",
    label: "College Tier",
    type: "select",
    options: TIER_OPTIONS,
    placeholder: "Select Tier",
  },
  { name: "cgpa", label: "CGPA (0 - 10)", type: "number", step: "0.01" },
  {
    name: "attendance",
    label: "Attendance % (0 - 100)",
    type: "number",
    step: "0.1",
  },
  { name: "backlogs", label: "Backlogs (0 - 3)", type: "number", step: "1" },
  {
    name: "codingSkills",
    label: "Coding Skill (1 - 10)",
    type: "number",
    step: "0.1",
  },
  { name: "dsaScore", label: "DSA Score (1 - 10)", type: "number", step: "0.1" },
  {
    name: "aptitudeScore",
    label: "Aptitude Score (20 - 100)",
    type: "number",
    step: "1",
  },
  {
    name: "communicationSkills",
    label: "Communication Skill (1 - 10)",
    type: "number",
    step: "0.1",
  },
  {
    name: "mlKnowledge",
    label: "ML Knowledge (0 - 10)",
    type: "number",
    step: "0.1",
  },
  {
    name: "systemDesign",
    label: "System Design (0 - 10)",
    type: "number",
    step: "0.1",
  },
  {
    name: "openSourceContributions",
    label: "Open Source Contributions (0 - 2)",
    type: "number",
    step: "1",
  },
  {
    name: "extracurriculars",
    label: "Extracurricular Activities (0 - 3)",
    type: "number",
    step: "1",
  },
  {
    name: "githubRepositories",
    label: "GitHub Repositories",
    type: "number",
    step: "1",
  },
  {
    name: "linkedinConnections",
    label: "LinkedIn Connections",
    type: "number",
    step: "1",
  },
  {
    name: "volunteerExperience",
    label: "Volunteer Experience",
    type: "select",
    options: ["Yes", "No"],
    placeholder: "Select",
  },
];

function EditProfileModal({
  profileId,
  profile,
  backendProfile,
  onSaved,
  onReload,
  onClose = () => {},
}) {
  const [form, setForm] = useState(() => buildEditState(profile));
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [evidenceEdits, setEvidenceEdits] = useState({});
  const [formEdits, setFormEdits] = useState({});
  const [baseline] = useState(() => backendProfile);
  const inFlight = useRef(false);
  const [retryIntent] = useState(createRetryIntent);
  const [conflict, setConflict] = useState(false);

  const setField = (name, value) => {
    setForm((prev) => ({ ...prev, [name]: value }));
    setFormEdits((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const validate = () => {
    const next = {};
    const numeric = (value) => value !== "" && Number.isFinite(Number(value));

    Object.entries(EDIT_RANGES).forEach(([field, { min, max, label }]) => {
      const value = formEdits[field];

      if (String(value ?? "").trim() === "") return; // explicit blank clears the field

      if (!numeric(value)) {
        next[field] = `${label} must be a number.`;
      } else if (Number(value) < min || Number(value) > max) {
        next[field] = `${label} must be between ${min} and ${max}.`;
      }
    });

    ["githubRepositories", "linkedinConnections"].forEach((field) => {
      const value = formEdits[field];
      if (String(value ?? "").trim() !== "" && !numeric(value)) {
        next[field] = "Please enter a valid non-negative number.";
      } else if (numeric(value) && Number(value) < 0) {
        next[field] = "Please enter a valid non-negative number.";
      }
    });

    return next;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (inFlight.current) return;

    const next = validate();
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }

    setErrors({});
    setSubmitError(null);
    setConflict(false);
    inFlight.current = true;
    setSaving(true);

    try {
      const payload = buildProfileCorrection(baseline, formEdits, evidenceEdits);
      validateReviewRecords(payload);
      const targetProfileId = profileId || backendProfile?.profile_id;
      const data = await updateStudentProfile(targetProfileId, payload, retryIntent([targetProfileId,payload]));
      onSaved?.(data);
      onClose();
    } catch (err) {
      setConflict(err?.status === 409);
      // Keep the modal open and the existing profile data untouched.
      setSubmitError(
        err?.message ?? "Unable to save profile changes. Please try again."
      );
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  };

  return (
    <AccessibleModal
      labelledBy="edit-profile-title"
      describedBy="edit-profile-description"
      closeBlocked={saving}
      onEscape={onClose}
      onBackdropClose={onClose}
    >
        <div className="modal-header">
          <h2 id="edit-profile-title">Edit Profile</h2>

          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
            disabled={saving}
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

        {conflict && <button type="button" className="dash-btn secondary" onClick={onReload}>Reload profile</button>}
        <form onSubmit={handleSubmit} noValidate>
          {submitError && (
            <div className="form-error-summary" role="alert">
              {submitError}
            </div>
          )}

          <div className="modal-fields">
            {FIELDS.map((field) => {
              const hasError = Boolean(errors[field.name]);
              const value = form[field.name] ?? "";

              /* Keep a resume-extracted branch (e.g. "Information Science and
                 Engineering") visible and selectable even though it is not a
                 canonical model category; the API layer applies the existing
                 ISE -> CSE mapping where needed. */
              const options =
                field.name === "branch" &&
                value &&
                !BRANCH_OPTIONS.some((option) => option.value === value)
                  ? [{ value, label: value }, ...BRANCH_OPTIONS]
                  : field.options;

              return (
                <div key={field.name} className="form-group">
                  <label htmlFor={`edit-${field.name}`}>{field.label}</label>

                  {field.type === "select" ? (
                    <select
                      id={`edit-${field.name}`}
                      name={field.name}
                      disabled={saving}
                      value={value}
                      onChange={(event) =>
                        setField(field.name, event.target.value)
                      }
                      className={hasError ? "invalid" : ""}
                      aria-invalid={hasError || undefined}
                      aria-describedby={hasError ? `edit-${field.name}-error` : undefined}
                    >
                      <option value="">{field.placeholder}</option>
                      {options.map((option) => {
                        const optionValue =
                          typeof option === "string" ? option : option.value;
                        const optionLabel =
                          typeof option === "string" ? option : option.label;

                        return (
                          <option key={optionValue} value={optionValue}>
                            {optionLabel}
                          </option>
                        );
                      })}
                    </select>
                  ) : (
                    <input
                      id={`edit-${field.name}`}
                      type={field.type}
                      name={field.name}
                      disabled={saving}
                      value={value}
                      onChange={(event) =>
                        setField(field.name, event.target.value)
                      }
                      placeholder={field.placeholder}
                      step={field.step}
                      min={EDIT_RANGES[field.name]?.min}
                      max={EDIT_RANGES[field.name]?.max}
                      className={hasError ? "invalid" : ""}
                      aria-invalid={hasError || undefined}
                      aria-describedby={hasError ? `edit-${field.name}-error` : undefined}
                    />
                  )}

                  {hasError && (
                    <span className="field-error" id={`edit-${field.name}-error`}>{errors[field.name]}</span>
                  )}
                </div>
              );
            })}
          </div>

          <p id="edit-profile-description" className="resume-note">Review changes before saving. Corrections replace current claims and require confirmation again. Original extraction and assessment history are retained.</p>
          <ResumeEvidenceEditor profile={applyReviewEdits(backendProfile, evidenceEdits, false)}
            includeDetails disabled={saving}
            onChange={(path, value) => setEvidenceEdits((previous) => ({ ...previous, [path]: value }))} />

          <div className="modal-actions">
            <button
              type="button"
              className="dash-btn secondary"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>

            <button type="submit" className="dash-btn primary" disabled={saving}>
              {saving ? "SAVING..." : "Save Changes"}
            </button>
          </div>
        </form>
    </AccessibleModal>
  );
}

export default EditProfileModal;
