/**
 * Salary Prediction page (Phase 5C).
 *
 * REAL BACKEND FEATURE: the estimate comes from POST /api/salary-predict
 * (Ridge regression model "placepro-salary-v1", trained on PLACED students
 * only) via services/salaryPrediction.js. The backend response is
 * authoritative: no salary value, range, confidence, or factor weight is
 * computed, substituted, or hard-coded in the frontend.
 *
 * The form collects exactly the 16 model inputs and is PREFILLED from the
 * existing student profile (localStorage "placepro_profile" via useProfile).
 * Edits here stay LOCAL to this page and never write back to the main
 * profile - no second profile system is created.
 *
 * The salary estimate is conditional on placement: the page labels it as an
 * estimate and states that it is not a guaranteed offer.
 */
import { useState } from "react";
import { predictSalary, formatLpa } from "../services/salaryPrediction";
import { BRANCH_OPTIONS, TIER_OPTIONS } from "../services/profileConfig";
import useProfile from "../hooks/useProfile";

/**
 * Numeric model inputs with the sanity bounds mirrored from the profile
 * editor (EDIT_RANGES). The backend remains authoritative for validation -
 * any stricter range it enforces comes back as a readable HTTP 422 message.
 */
const NUMERIC_FIELDS = [
  { name: "cgpa", label: "CGPA (0 - 10)", min: 0, max: 10, step: "0.01", placeholder: "0 - 10" },
  { name: "backlogs", label: "Backlogs", min: 0, step: "1", placeholder: "e.g. 0" },
  { name: "codingSkills", label: "Coding Skill (0 - 10)", min: 0, max: 10, step: "0.1", placeholder: "0 - 10" },
  { name: "dsaScore", label: "DSA Score (0 - 10)", min: 0, max: 10, step: "0.1", placeholder: "0 - 10" },
  { name: "aptitudeScore", label: "Aptitude Score (0 - 100)", min: 0, max: 100, step: "1", placeholder: "0 - 100" },
  { name: "communicationSkills", label: "Communication Skill (0 - 10)", min: 0, max: 10, step: "0.1", placeholder: "0 - 10" },
  { name: "mlKnowledge", label: "ML Knowledge (0 - 10)", min: 0, max: 10, step: "0.1", placeholder: "0 - 10" },
  { name: "systemDesign", label: "System Design (0 - 10)", min: 0, max: 10, step: "0.1", placeholder: "0 - 10" },
  { name: "internships", label: "Internships", min: 0, step: "1", placeholder: "e.g. 0" },
  { name: "projects", label: "Projects", min: 0, step: "1", placeholder: "e.g. 0" },
  { name: "certifications", label: "Certifications", min: 0, step: "1", placeholder: "e.g. 0" },
  { name: "hackathons", label: "Hackathons", min: 0, step: "1", placeholder: "e.g. 0" },
  { name: "openSourceContributions", label: "Open Source Contributions (0 - 2)", min: 0, max: 2, step: "1", placeholder: "0 - 2" },
  { name: "extracurriculars", label: "Extracurricular Activities (0 - 3)", min: 0, max: 3, step: "1", placeholder: "0 - 3" },
];

/** Prefill the 16 model inputs from the flat student profile mirror. */
const buildInitialForm = (profile) => ({
  branch: profile.branch || "",
  collegeTier: profile.collegeTier || "",
  cgpa: profile.cgpa || "",
  backlogs: profile.backlogs || "",
  codingSkills: profile.codingSkills || "",
  dsaScore: profile.dsaScore || "",
  aptitudeScore: profile.aptitudeScore || "",
  communicationSkills: profile.communicationSkills || "",
  mlKnowledge: profile.mlKnowledge || "",
  systemDesign: profile.systemDesign || "",
  internships: profile.internshipsCount
    ? String(profile.internshipsCount)
    : "",
  projects: profile.projectsCount ? String(profile.projectsCount) : "",
  certifications: profile.certificationsCount
    ? String(profile.certificationsCount)
    : "",
  hackathons: profile.hackathonsCount ? String(profile.hackathonsCount) : "",
  openSourceContributions: profile.openSourceContributions || "",
  extracurriculars: profile.extracurriculars || "",
});

function SalaryPrediction() {
  const profile = useProfile();

  const [form, setForm] = useState(() => buildInitialForm(profile));
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [isEstimating, setIsEstimating] = useState(false);
  const [error, setError] = useState(null);

  /* The stored profile usually holds a canonical branch ("CSE"), but older
     mirrors may hold a legacy spelling ("Information Science and
     Engineering"). Keep it selectable; the service maps it to "CSE". */
  const branchOptions =
    form.branch && !BRANCH_OPTIONS.some((option) => option.value === form.branch)
      ? [{ value: form.branch, label: form.branch }, ...BRANCH_OPTIONS]
      : BRANCH_OPTIONS;

  const tierOptions =
    form.collegeTier && !TIER_OPTIONS.some((option) => option.value === form.collegeTier)
      ? [{ value: form.collegeTier, label: form.collegeTier }, ...TIER_OPTIONS]
      : TIER_OPTIONS;

  const setField = (name, value) => {
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
    // A changed input invalidates the previous failed attempt's message.
    setError(null);
  };

  const validate = (data) => {
    const next = {};

    if (!data.branch) {
      next.branch = "Please select a branch.";
    }
    if (!data.collegeTier) {
      next.collegeTier = "Please select a college tier.";
    }

    NUMERIC_FIELDS.forEach(({ name, label, min, max }) => {
      const raw = data[name];
      const value = Number(raw);

      if (raw === "" || raw === null || !Number.isFinite(value)) {
        next[name] = `${label.replace(/\s*\(.*\)$/, "")} is required.`;
      } else if (value < min) {
        next[name] = `${label.replace(/\s*\(.*\)$/, "")} must be ${min} or greater.`;
      } else if (max !== undefined && value > max) {
        next[name] = `${label.replace(/\s*\(.*\)$/, "")} must be ${min} - ${max}.`;
      }
    });

    return next;
  };

  const runPrediction = async () => {
    setError(null);
    setResult(null);

    const next = validate(form);
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }

    setIsEstimating(true);
    try {
      const estimate = await predictSalary(form);
      setResult(estimate);
    } catch (err) {
      // Backend error messages are user-readable (422/503/500/network).
      setError(
        err?.message ??
          "Unable to calculate the salary estimate. Please try again."
      );
    } finally {
      setIsEstimating(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    runPrediction();
  };

  const renderSelect = (name, label, options) => {
    const hasError = Boolean(errors[name]);

    return (
      <div className="form-group" key={name}>
        <label htmlFor={`salary-${name}`}>{label}</label>
        <select
          id={`salary-${name}`}
          value={form[name]}
          onChange={(event) => setField(name, event.target.value)}
          className={hasError ? "invalid" : ""}
        >
          <option value="">Select</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {hasError && <span className="field-error">{errors[name]}</span>}
      </div>
    );
  };

  const renderNumberField = ({
    name,
    label,
    min,
    max,
    step,
    placeholder,
  }) => {
    const hasError = Boolean(errors[name]);

    return (
      <div className="form-group" key={name}>
        <label htmlFor={`salary-${name}`}>{label}</label>
        <input
          id={`salary-${name}`}
          type="number"
          value={form[name]}
          onChange={(event) => setField(name, event.target.value)}
          placeholder={placeholder}
          min={min}
          max={max}
          step={step}
          className={hasError ? "invalid" : ""}
        />
        {hasError && <span className="field-error">{errors[name]}</span>}
      </div>
    );
  };

  return (
    <div className="salary-page">
      {/* PAGE HEADER */}
      <div className="page-header">
        <h1>Salary Prediction</h1>
        <p>
          Estimate your potential salary based on your academic profile and
          technical skills.
        </p>
      </div>

      {/* INPUT FORM */}
      <div className="prediction-card">
        <h2>Salary Details</h2>
        <p className="form-description">
          Prefilled from your Student Profile. Changes here are used only for
          this estimate and do not modify your profile.
        </p>

        <form onSubmit={handleSubmit} noValidate>
          <div className="salary-form-grid">
            {renderSelect("branch", "Branch", branchOptions)}
            {renderSelect("collegeTier", "College Tier", tierOptions)}
            {NUMERIC_FIELDS.map(renderNumberField)}
          </div>

          {Object.keys(errors).length > 0 && (
            <div className="form-error-summary">
              Please fix the highlighted fields before estimating.
            </div>
          )}

          <button
            type="submit"
            className="predict-button"
            disabled={isEstimating}
          >
            {isEstimating && (
              <span className="button-spinner" aria-hidden="true"></span>
            )}
            <span>
              {isEstimating ? "ESTIMATING..." : "ESTIMATE SALARY"}
            </span>
          </button>
        </form>
      </div>

      {/* ERROR + RETRY */}
      {error && !isEstimating && (
        <>
          <div className="error-banner" role="alert">
            {error}
          </div>
          <button
            type="button"
            className="dash-btn primary"
            onClick={runPrediction}
          >
            Try Again
          </button>
        </>
      )}

      {/* LOADING */}
      {isEstimating && (
        <div className="prediction-result prediction-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Calculating salary estimate...</p>
        </div>
      )}

      {/* RESULT CARD */}
      {result && !isEstimating && (
        <div className="prediction-result salary-result">
          <h2>Estimated Salary</h2>

          <div className="result-body">
            <div className="salary-result-top">
              <div className="salary-estimate">
                <div className="prediction-percentage">
                  {formatLpa(result.predictedSalaryLpa)}
                </div>
                <div className="prediction-probability-label">
                  Estimated Salary (LPA)
                </div>
              </div>

              <div className="salary-meta">
                {result.modelVersion && (
                  <div className="salary-meta-row">
                    <span>Model</span>
                    <strong>{result.modelVersion}</strong>
                  </div>
                )}
                <div className="salary-meta-row">
                  <span>Source</span>
                  <strong>Backend salary model</strong>
                </div>
              </div>
            </div>

            <p className="prediction-data-note">
              Estimated salary based on your current profile. Actual offers may
              vary. The salary estimate is conditional on placement and is not
              a guaranteed offer.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default SalaryPrediction;
