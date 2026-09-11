import { useEffect, useState } from "react";
import { updateStudentProfile } from "../services/api";
import {
  BRANCH_OPTIONS,
  DEMO_PROFILE_ID,
  EDIT_RANGES,
  TIER_OPTIONS,
  buildEditState,
  buildProfilePayload,
} from "../services/profileConfig";

/**
 * Editable fields are exactly the fields supported by the backend PUT
 * schema (PersonalInfo.name, EducationInfo.branch/cgpa, MlInputs,
 * and the AdditionalInfo subset below). Server-controlled fields
 * (provenance, verified, prediction history, assessment evidence) and
 * structural resume sections are NOT editable here.
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

const REQUIRED_TEXT = ["name"];
const REQUIRED_SELECTS = ["branch", "collegeTier"];

function EditProfileModal({ profile, backendProfile, onSaved, onClose = () => {} }) {
  const [form, setForm] = useState(() => buildEditState(profile));
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === "Escape" && !saving) onClose();
    };

    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, saving]);

  const setField = (name, value) => {
    setForm((prev) => ({ ...prev, [name]: value }));
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

    REQUIRED_TEXT.forEach((field) => {
      if (!String(form[field] ?? "").trim()) {
        next[field] = "This field is required.";
      }
    });

    REQUIRED_SELECTS.forEach((field) => {
      if (!form[field]) {
        next[field] = "Please select an option.";
      }
    });

    Object.entries(EDIT_RANGES).forEach(([field, { min, max, label }]) => {
      const value = form[field];

      if (String(value ?? "").trim() === "") return; // empty = unchanged

      if (!numeric(value)) {
        next[field] = `${label} must be a number.`;
      } else if (Number(value) < min || Number(value) > max) {
        next[field] = `${label} must be between ${min} and ${max}.`;
      }
    });

    ["githubRepositories", "linkedinConnections"].forEach((field) => {
      const value = form[field];
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

    const next = validate();
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }

    setErrors({});
    setSubmitError(null);
    setSaving(true);

    try {
      const payload = buildProfilePayload(backendProfile, form);
      const data = await updateStudentProfile(DEMO_PROFILE_ID, payload);
      onSaved?.(data);
      onClose();
    } catch (err) {
      // Keep the modal open and the existing profile data untouched.
      setSubmitError(
        err?.message ?? "Unable to save profile changes. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      onClick={saving ? undefined : onClose}
      role="presentation"
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-profile-title"
        onClick={(event) => event.stopPropagation()}
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

              return (
                <div key={field.name} className="form-group">
                  <label htmlFor={`edit-${field.name}`}>{field.label}</label>

                  {field.type === "select" ? (
                    <select
                      id={`edit-${field.name}`}
                      name={field.name}
                      value={value}
                      onChange={(event) =>
                        setField(field.name, event.target.value)
                      }
                      className={hasError ? "invalid" : ""}
                    >
                      <option value="">{field.placeholder}</option>
                      {field.options.map((option) => {
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
                      value={value}
                      onChange={(event) =>
                        setField(field.name, event.target.value)
                      }
                      placeholder={field.placeholder}
                      step={field.step}
                      className={hasError ? "invalid" : ""}
                      autoFocus={field.name === "name"}
                    />
                  )}

                  {hasError && (
                    <span className="field-error">{errors[field.name]}</span>
                  )}
                </div>
              );
            })}
          </div>

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
      </div>
    </div>
  );
}

export default EditProfileModal;
