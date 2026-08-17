import { useState } from "react";
import IconMark from "./IconMark";

const RANGES = {
  age: { min: 15, max: 60, label: "Age" },
  cgpa: { min: 0, max: 10, label: "CGPA" },
  internships: { min: 0, max: null, label: "Internships" },
  projects: { min: 0, max: null, label: "Projects" },
  certifications: { min: 0, max: null, label: "Certifications" },
  codingSkill: { min: 0, max: 100, label: "Coding Skill" },
  aptitudeScore: { min: 0, max: 100, label: "Aptitude Score" },
  communicationSkill: { min: 0, max: 100, label: "Communication Skill" },
  logicalReasoning: { min: 0, max: 100, label: "Logical Reasoning" },
  hackathons: { min: 0, max: null, label: "Hackathons" },
  githubRepositories: { min: 0, max: null, label: "GitHub Repositories" },
  linkedinConnections: { min: 0, max: null, label: "LinkedIn Connections" },
  mockInterview: { min: 0, max: 100, label: "Mock Interview Score" },
  attendance: { min: 0, max: 100, label: "Attendance" },
  backlogs: { min: 0, max: null, label: "Backlogs" },
  extracurricular: { min: 0, max: null, label: "Extracurricular Activities" },
  leadership: { min: 0, max: 100, label: "Leadership Score" },
  sleepHours: { min: 0, max: 24, label: "Sleep Hours" },
  studyHours: { min: 0, max: 24, label: "Study Hours" },
};

const REQUIRED_SELECTS = ["gender", "branch", "collegeTier", "volunteerExperience"];

const initialFormData = {
  age: "",
  gender: "",
  branch: "",
  collegeTier: "",
  cgpa: "",
  internships: "",
  projects: "",
  certifications: "",
  codingSkill: "",
  aptitudeScore: "",
  communicationSkill: "",
  logicalReasoning: "",
  hackathons: "",
  githubRepositories: "",
  linkedinConnections: "",
  mockInterview: "",
  attendance: "",
  backlogs: "",
  extracurricular: "",
  leadership: "",
  volunteerExperience: "",
  sleepHours: "",
  studyHours: "",
};

const formSections = [
  {
    title: "Academic Profile",
    icon: "academic",
    kicker: "Core student and academic details",
    fields: [
      { name: "age", label: "Age", type: "number", placeholder: "15 - 60" },
      {
        name: "gender",
        label: "Gender",
        type: "select",
        options: ["Male", "Female", "Other"],
        placeholder: "Select Gender",
      },
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
      { name: "cgpa", label: "CGPA", type: "number", placeholder: "0 - 10", step: "0.01" },
      { name: "attendance", label: "Attendance (%)", type: "number", placeholder: "0 - 100" },
      { name: "backlogs", label: "Backlogs", type: "number", min: "0" },
    ],
  },
  {
    title: "Technical Skills",
    icon: "technical",
    kicker: "Portfolio, coding and build experience",
    fields: [
      { name: "codingSkill", label: "Coding Skill", type: "number", placeholder: "0 - 100" },
      { name: "projects", label: "Projects", type: "number", min: "0" },
      { name: "certifications", label: "Certifications", type: "number", min: "0" },
      { name: "githubRepositories", label: "GitHub Repositories", type: "number", min: "0" },
    ],
  },
  {
    title: "Aptitude & Soft Skills",
    icon: "aptitude",
    kicker: "Assessment scores used in readiness analysis",
    fields: [
      { name: "aptitudeScore", label: "Aptitude Score", type: "number", placeholder: "0 - 100" },
      {
        name: "communicationSkill",
        label: "Communication Skill",
        type: "number",
        placeholder: "0 - 100",
      },
      { name: "logicalReasoning", label: "Logical Reasoning", type: "number", placeholder: "0 - 100" },
      { name: "mockInterview", label: "Mock Interview Score", type: "number", placeholder: "0 - 100" },
      { name: "leadership", label: "Leadership Score", type: "number", placeholder: "0 - 100" },
    ],
  },
  {
    title: "Professional & Activities",
    icon: "professional",
    kicker: "Experience, networking and campus participation",
    fields: [
      { name: "internships", label: "Internships", type: "number", min: "0" },
      { name: "hackathons", label: "Hackathons", type: "number", min: "0" },
      { name: "linkedinConnections", label: "LinkedIn Connections", type: "number", min: "0" },
      { name: "extracurricular", label: "Extracurricular Activities", type: "number", min: "0" },
      {
        name: "volunteerExperience",
        label: "Volunteer Experience",
        type: "select",
        options: ["Yes", "No"],
        placeholder: "Select",
      },
    ],
  },
  {
    title: "Study Habits",
    icon: "habits",
    kicker: "Daily rhythm and preparation consistency",
    fields: [
      { name: "sleepHours", label: "Sleep Hours", type: "number", placeholder: "0 - 24", step: "0.5" },
      { name: "studyHours", label: "Study Hours / Day", type: "number", placeholder: "0 - 24", step: "0.5" },
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
            type={field.type}
            name={field.name}
            value={formData[field.name]}
            onChange={handleChange}
            placeholder={field.placeholder}
            min={field.min}
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
