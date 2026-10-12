import { useState } from "react";
import IconMark from "./IconMark";

/**
 * Prediction form: collects EXACTLY the 16 inputs of the production
 * placement model (placepro-final-v1). Score fields are constrained to
 * the training-distribution ranges below; count fields accept any
 * non-negative integer (no upper limit).
 *
 * codingSkill / communicationSkill keep the existing 0–100 UI scale;
 * the API service converts them to the model's 0–10 scale.
 */
const RANGES = {
  cgpa: { min: 4, max: 10, step: 0.01, label: "CGPA" },
  backlogs: { min: 0, max: null, step: 1, label: "Backlogs" },
  codingSkill: { min: 0, max: 100, step: 1, label: "Coding Skill" },
  dsaScore: { min: 1, max: 10, step: 0.1, label: "DSA Score" },
  aptitudeScore: { min: 20, max: 100, step: 1, label: "Aptitude Score" },
  communicationSkill: {
    min: 0,
    max: 100,
    step: 1,
    label: "Communication Skill",
  },
  mlKnowledge: { min: 0, max: 10, step: 0.1, label: "ML Knowledge" },
  systemDesign: { min: 0, max: 10, step: 0.1, label: "System Design" },
  internships: { min: 0, max: null, step: 1, label: "Internships" },
  projects: { min: 0, max: null, step: 1, label: "Projects" },
  certifications: { min: 0, max: null, step: 1, label: "Certifications" },
  hackathons: { min: 0, max: null, step: 1, label: "Hackathons" },
  openSourceContributions: {
    min: 0,
    max: null,
    step: 1,
    label: "Open Source Contributions",
  },
  extracurricular: {
    min: 0,
    max: null,
    step: 1,
    label: "Extracurricular Activities",
  },
};

const REQUIRED_SELECTS = ["branch", "collegeTier"];

// Count fields must be whole numbers (no upper limit — any non-negative
// integer is accepted, including values above the training-data maximums).
const INTEGER_FIELDS = [
  "backlogs",
  "internships",
  "projects",
  "certifications",
  "hackathons",
  "openSourceContributions",
  "extracurricular",
];

const initialFormData = {
  branch: "",
  collegeTier: "",
  cgpa: "",
  backlogs: "",
  codingSkill: "",
  dsaScore: "",
  aptitudeScore: "",
  communicationSkill: "",
  mlKnowledge: "",
  systemDesign: "",
  internships: "",
  projects: "",
  certifications: "",
  hackathons: "",
  openSourceContributions: "",
  extracurricular: "",
};

const formSections = [
  {
    title: "Academic Profile",
    icon: "academic",
    kicker: "Core student and academic details",
    fields: [
      {
        name: "branch",
        label: "Branch",
        type: "select",
        options: [
          "Information Science",
          "Computer Science",
          "Information Technology",
          "Electronics",
          "Electrical",
          "Mechanical",
          "Civil",
        ],
        placeholder: "Select Branch",
      },
      {
        name: "collegeTier",
        label: "College Tier",
        type: "select",
        options: [
          { value: "1", label: "Tier 1" },
          { value: "2", label: "Tier 2" },
          { value: "3", label: "Tier 3" },
        ],
        placeholder: "Select Tier",
      },
      {
        name: "cgpa",
        label: "CGPA",
        type: "number",
        placeholder: "4 - 10",
        step: "0.01",
      },
      { name: "backlogs", label: "Backlogs", type: "number", placeholder: "No. of active backlogs", min: "0", step: "1" },
    ],
  },
  {
    title: "Technical Skills",
    icon: "technical",
    kicker: "Coding, DSA and build experience",
    fields: [
      {
        name: "codingSkill",
        label: "Coding Skill (0 - 100)",
        type: "number",
        placeholder: "0 - 100",
      },
      {
        name: "dsaScore",
        label: "DSA Score (1 - 10)",
        type: "number",
        placeholder: "1 - 10",
        step: "0.1",
      },
      {
        name: "mlKnowledge",
        label: "ML Knowledge (0 - 10)",
        type: "number",
        placeholder: "0 - 10",
        step: "0.1",
      },
      {
        name: "systemDesign",
        label: "System Design (0 - 10)",
        type: "number",
        placeholder: "0 - 10",
        step: "0.1",
      },
      { name: "projects", label: "Projects", type: "number", placeholder: "No. of projects completed", min: "0", step: "1" },
      {
        name: "certifications",
        label: "Certifications",
        type: "number",
        placeholder: "No. of certifications earned",
        min: "0",
        step: "1",
      },
    ],
  },
  {
    title: "Aptitude & Soft Skills",
    icon: "aptitude",
    kicker: "Assessment scores used in readiness analysis",
    fields: [
      {
        name: "aptitudeScore",
        label: "Aptitude Score (20 - 100)",
        type: "number",
        placeholder: "20 - 100",
      },
      {
        name: "communicationSkill",
        label: "Communication Skill (0 - 100)",
        type: "number",
        placeholder: "0 - 100",
      },
    ],
  },
  {
    title: "Professional & Activities",
    icon: "professional",
    kicker: "Experience, competitions and campus participation",
    fields: [
      {
        name: "internships",
        label: "Internships",
        type: "number",
        placeholder: "No. of internships completed",
        min: "0",
        step: "1",
      },
      { name: "hackathons", label: "Hackathons", type: "number", placeholder: "No. of hackathons participated", min: "0", step: "1" },
      {
        name: "openSourceContributions",
        label: "Open Source Contributions",
        type: "number",
        placeholder: "No. of open-source contributions",
        min: "0",
        step: "1",
      },
      {
        name: "extracurricular",
        label: "Extracurricular Activities",
        type: "number",
        placeholder: "No. of activities participated",
        min: "0",
        step: "1",
      },
    ],
  },
];

function StudentForm({ onPredict, isSubmitting = false }) {
  const [formData, setFormData] = useState(initialFormData);
  const [errors, setErrors] = useState({});

  const validate = (data) => {
    const nextErrors = {};

    Object.entries(RANGES).forEach(([field, { min, max, label }]) => {
      const raw = data[field];
      const value = Number(raw);

      if (raw === "" || !Number.isFinite(value)) {
        nextErrors[field] = `${label} is required.`;
      } else if (value < min || (max !== null && value > max)) {
        nextErrors[field] =
          max !== null
            ? `${label} must be between ${min} and ${max}.`
            : `${label} must be at least ${min}.`;
      } else if (INTEGER_FIELDS.includes(field) && !Number.isInteger(value)) {
        nextErrors[field] = `${label} must be a whole number.`;
      }
    });

    REQUIRED_SELECTS.forEach((field) => {
      if (data[field] === "") {
        nextErrors[field] = "Please select an option.";
      }
    });

    return nextErrors;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;

    setFormData((prev) => ({ ...prev, [name]: value }));

    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const nextErrors = validate(formData);

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setErrors({});
    onPredict(formData);
  };

  const renderField = (field) => {
    const hasError = Boolean(errors[field.name]);

    return (
      <div key={field.name} className="form-group">
        <label htmlFor={field.name}>{field.label}</label>

        {field.type === "select" ? (
          <select
            id={field.name}
            name={field.name}
            value={formData[field.name]}
            onChange={handleChange}
            className={hasError ? "invalid" : ""}
          >
            <option value="">{field.placeholder}</option>
            {field.options.map((option) => {
              const value = typeof option === "string" ? option : option.value;
              const label = typeof option === "string" ? option : option.label;

              return (
                <option key={value} value={value}>
                  {label}
                </option>
              );
            })}
          </select>
        ) : (
          <input
            id={field.name}
            type="number"
            name={field.name}
            value={formData[field.name]}
            onChange={handleChange}
            placeholder={field.placeholder}
            min={field.min}
            max={field.max ?? undefined}
            step={field.step}
            className={hasError ? "invalid" : ""}
          />
        )}

        {hasError && <span className="field-error">{errors[field.name]}</span>}
      </div>
    );
  };

  return (
    <form className="student-form" onSubmit={handleSubmit} noValidate>
      {Object.keys(errors).length > 0 && (
        <div className="form-error-summary">
          Please fix the highlighted fields before predicting.
        </div>
      )}

      <div className="form-sections">
        {formSections.map((section) => (
          <section key={section.title} className="form-section-card">
            <div className="form-section-header">
              <h3>
                <IconMark name={section.icon} className="section-title-icon" />
                <span>{section.title}</span>
              </h3>
              <p>{section.kicker}</p>
            </div>

            <div className="form-grid">{section.fields.map(renderField)}</div>
          </section>
        ))}
      </div>

      <button type="submit" className="predict-button" disabled={isSubmitting}>
        {isSubmitting && <span className="button-spinner" aria-hidden="true"></span>}
        <span>{isSubmitting ? "PREDICTING..." : "PREDICT PLACEMENT"}</span>
      </button>
    </form>
  );
}

export default StudentForm;
