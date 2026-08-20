import { useEffect, useState } from "react";

const TIERS = ["Tier 1", "Tier 2", "Tier 3"];

const FIELDS = [
  { name: "name", label: "Name", type: "text", placeholder: "Full name" },
  {
    name: "branch",
    label: "Branch",
    type: "text",
    placeholder: "e.g. Information Science",
  },
  { name: "collegeTier", label: "College Tier", type: "select", options: TIERS },
  {
    name: "cgpa",
    label: "CGPA",
    type: "number",
    placeholder: "0 - 10",
    step: "0.01",
  },
  {
    name: "attendance",
    label: "Attendance (%)",
    type: "number",
    placeholder: "0 - 100",
  },
  { name: "internships", label: "Internships", type: "number", min: "0" },
  { name: "projects", label: "Projects", type: "number", min: "0" },
  { name: "certifications", label: "Certifications", type: "number", min: "0" },
  {
    name: "githubRepositories",
    label: "GitHub Repositories",
    type: "number",
    min: "0",
  },
  {
    name: "linkedinConnections",
    label: "LinkedIn Connections",
    type: "number",
    min: "0",
  },
];

const COUNT_FIELDS = [
  "internships",
  "projects",
  "certifications",
  "githubRepositories",
  "linkedinConnections",
];

function EditProfileModal({ profile, onSave, onClose = () => {} }) {
  const [form, setForm] = useState(() => ({ ...profile }));
  const [errors, setErrors] = useState({});

  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === "Escape") onClose();
    };

    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

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

    if (!form.name.trim()) {
      next.name = "Please enter a valid name.";
    }

    if (!form.branch.trim()) {
      next.branch = "Please enter a valid branch.";
    }

    if (!numeric(form.cgpa) || Number(form.cgpa) < 0 || Number(form.cgpa) > 10) {
      next.cgpa = "CGPA must be between 0 and 10.";
    }

    if (
      !numeric(form.attendance) ||
      Number(form.attendance) < 0 ||
      Number(form.attendance) > 100
    ) {
      next.attendance = "Attendance must be between 0 and 100.";
    }

    COUNT_FIELDS.forEach((field) => {
      if (!numeric(form[field]) || Number(form[field]) < 0) {
        next[field] = "Please enter a valid non-negative number.";
      }
    });

    return next;
  };

  const normalizeNumber = (value) => String(Number(value));

  const handleSubmit = (event) => {
    event.preventDefault();

    const next = validate();
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }

    onSave({
      name: form.name.trim(),
      branch: form.branch.trim(),
      collegeTier: form.collegeTier,
      cgpa: normalizeNumber(form.cgpa),
      attendance: normalizeNumber(form.attendance),
      internships: normalizeNumber(form.internships),
      projects: normalizeNumber(form.projects),
      certifications: normalizeNumber(form.certifications),
      githubRepositories: normalizeNumber(form.githubRepositories),
      linkedinConnections: normalizeNumber(form.linkedinConnections),
    });
  };

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
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
          <div className="modal-fields">
            {FIELDS.map((field) => {
              const hasError = Boolean(errors[field.name]);

              return (
                <div key={field.name} className="form-group">
                  <label htmlFor={`edit-${field.name}`}>{field.label}</label>

                  {field.type === "select" ? (
                    <select
                      id={`edit-${field.name}`}
                      name={field.name}
                      value={form[field.name]}
                      onChange={(event) =>
                        setField(field.name, event.target.value)
                      }
                      className={hasError ? "invalid" : ""}
                    >
                      {field.options.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={`edit-${field.name}`}
                      type={field.type}
                      name={field.name}
                      value={form[field.name]}
                      onChange={(event) =>
                        setField(field.name, event.target.value)
                      }
                      placeholder={field.placeholder}
                      step={field.step}
                      min={field.min}
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
            >
              Cancel
            </button>

            <button type="submit" className="dash-btn primary">
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default EditProfileModal;
