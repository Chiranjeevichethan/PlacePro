/**
 * Salary Prediction page (Phase 2).
 *
 * DEMO FEATURE: the estimate comes from a transparent deterministic formula in
 * services/salaryPrediction.js - it is NOT a trained ML model and shows no
 * accuracy metrics. A real salary model API can replace the service later
 * without changing this page.
 *
 * Profile fields (CGPA, preferred role, skills, projects, internships,
 * certifications) are PREFILLED from the existing student profile
 * (localStorage "placepro_profile" via useProfile). Edits here stay LOCAL to
 * this page and never write back to the main profile - no second profile
 * system is created.
 */
import { useState } from "react";
import IconMark from "../components/IconMark";
import { predictSalary, formatLpa, COMPANY_TYPE_OPTIONS } from "../services/salaryPrediction";
import { ROLE_SKILLS } from "../data/recommendationData";
import useProfile from "../hooks/useProfile";

const ROLE_OPTIONS = Object.keys(ROLE_SKILLS);

function SalaryPrediction() {
  const profile = useProfile();

  const [form, setForm] = useState(() => ({
    cgpa: profile.cgpa || "",
    preferredRole: profile.preferredRole || ROLE_OPTIONS[0],
    skills: profile.skills || "",
    projects: profile.projects || "",
    internships: profile.internships || "",
    certifications: profile.certifications || "",
    experience: "",
    companyType: "Any",
  }));
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [isEstimating, setIsEstimating] = useState(false);
  const [error, setError] = useState(null);

  const setField = (name, value) => {
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const validate = (data) => {
    const next = {};
    const numeric = (value) => value !== "" && Number.isFinite(Number(value));

    if (
      !numeric(data.cgpa) ||
      Number(data.cgpa) < 0 ||
      Number(data.cgpa) > 10
    ) {
      next.cgpa = "CGPA must be between 0 and 10.";
    }

    if (!ROLE_OPTIONS.includes(data.preferredRole)) {
      next.preferredRole = "Please select a valid role.";
    }

    [
      ["projects", "Projects"],
      ["internships", "Internships"],
      ["certifications", "Certifications"],
      ["experience", "Experience"],
    ].forEach(([field, label]) => {
      if (!numeric(data[field]) || Number(data[field]) < 0) {
        next[field] = `${label} must be 0 or greater.`;
      }
    });

    return next;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);

    const next = validate(form);
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }

    setIsEstimating(true);
    try {
      const estimate = await predictSalary(form);
      setResult(estimate);
    } catch {
      setError(
        "Something went wrong while estimating the salary. Please try again."
      );
    } finally {
      setIsEstimating(false);
    }
  };

  return (
    <div className="salary-page">
      {/* PAGE HEADER */}
      <div className="page-header">
        <h1>Salary Prediction</h1>
        <p>
          Estimate your potential salary based on your academic profile,
          skills, experience, and career preferences.
        </p>
      </div>

      {/* DEMO NOTICE */}
      <div className="demo-banner">
        <span className="demo-chip">Demo Prediction</span>
        <span>
          This is a frontend demo. Connect a trained salary prediction
          model/API for real predictions.
        </span>
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
            <div className="form-group">
              <label htmlFor="salary-cgpa">CGPA</label>
              <input
                id="salary-cgpa"
                type="number"
                value={form.cgpa}
                onChange={(event) => setField("cgpa", event.target.value)}
                placeholder="0 - 10"
                step="0.01"
                className={errors.cgpa ? "invalid" : ""}
              />
              {errors.cgpa && (
                <span className="field-error">{errors.cgpa}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="salary-role">Preferred Role</label>
              <select
                id="salary-role"
                value={form.preferredRole}
                onChange={(event) =>
                  setField("preferredRole", event.target.value)
                }
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group salary-skills-field">
              <label htmlFor="salary-skills">
                Skills (comma separated)
              </label>
              <input
                id="salary-skills"
                type="text"
                value={form.skills}
                onChange={(event) => setField("skills", event.target.value)}
                placeholder="e.g. Python, SQL, Excel"
              />
            </div>

            <div className="form-group">
              <label htmlFor="salary-projects">Projects</label>
              <input
                id="salary-projects"
                type="number"
                value={form.projects}
                onChange={(event) => setField("projects", event.target.value)}
                placeholder="0 or greater"
                min="0"
                className={errors.projects ? "invalid" : ""}
              />
              {errors.projects && (
                <span className="field-error">{errors.projects}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="salary-internships">Internship Experience</label>
              <input
                id="salary-internships"
                type="number"
                value={form.internships}
                onChange={(event) =>
                  setField("internships", event.target.value)
                }
                placeholder="0 or greater"
                min="0"
                className={errors.internships ? "invalid" : ""}
              />
              {errors.internships && (
                <span className="field-error">{errors.internships}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="salary-certifications">Certifications</label>
              <input
                id="salary-certifications"
                type="number"
                value={form.certifications}
                onChange={(event) =>
                  setField("certifications", event.target.value)
                }
                placeholder="0 or greater"
                min="0"
                className={errors.certifications ? "invalid" : ""}
              />
              {errors.certifications && (
                <span className="field-error">{errors.certifications}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="salary-experience">
                Relevant Experience (years)
              </label>
              <input
                id="salary-experience"
                type="number"
                value={form.experience}
                onChange={(event) =>
                  setField("experience", event.target.value)
                }
                placeholder="0 or greater"
                min="0"
                className={errors.experience ? "invalid" : ""}
              />
              {errors.experience && (
                <span className="field-error">{errors.experience}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="salary-company">Target Company Type</label>
              <select
                id="salary-company"
                value={form.companyType}
                onChange={(event) =>
                  setField("companyType", event.target.value)
                }
              >
                {COMPANY_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
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

      {/* ERROR */}
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {/* LOADING */}
      {isEstimating && (
        <div className="prediction-result prediction-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Calculating demo salary estimate...</p>
        </div>
      )}

      {/* RESULT CARD */}
      {result && !isEstimating && (
        <div className="prediction-result salary-result">
          <h2>Estimated Salary (Demo)</h2>

          <div className="result-body">
            <div className="salary-result-top">
              <div className="salary-estimate">
                <div className="prediction-percentage">
                  {formatLpa(result.estimateLpa)}
                </div>
                <div className="prediction-probability-label">
                  Estimated Salary (Demo)
                </div>
              </div>

              <div className="salary-meta">
                <div className="salary-meta-row">
                  <span>Salary Range (Demo)</span>
                  <strong>
                    {formatLpa(result.minLpa)} – {formatLpa(result.maxLpa)}
                  </strong>
                </div>
                <div className="salary-meta-row">
                  <span>Target Role</span>
                  <strong>{result.role}</strong>
                </div>
                <div className="salary-meta-row">
                  <span>Profile Strength</span>
                  <span
                    className={`rating-badge ${result.profileStrength.className}`}
                  >
                    {result.profileStrength.label}
                  </span>
                </div>
              </div>
            </div>

            <div className="salary-range-track">
              <div
                className="salary-range-fill"
                style={{
                  left: `${Math.max(0, (result.minLpa / (result.maxLpa * 1.05)) * 100)}%`,
                  width: `${Math.min(
                    100,
                    ((result.maxLpa - result.minLpa) / (result.maxLpa * 1.05)) * 100
                  )}%`,
                }}
              ></div>
            </div>

            <div className="salary-factors">
              <h3>Key Positive Factors</h3>
              {result.positiveFactors.length > 0 ? (
                <ul className="salary-factor-list positive">
                  {result.positiveFactors.map((factor) => (
                    <li key={factor}>✓ {factor}</li>
                  ))}
                </ul>
              ) : (
                <p className="skills-empty">
                  No strong factors yet - fill in your details above.
                </p>
              )}

              <h3>Improvement Areas</h3>
              {result.improvementAreas.length > 0 ? (
                <ul className="salary-factor-list improve">
                  {result.improvementAreas.map((area) => (
                    <li key={area}>• {area}</li>
                  ))}
                </ul>
              ) : (
                <p className="skills-complete">
                  All covered based on the entered details ✓
                </p>
              )}
            </div>

            <p className="prediction-data-note">
              This is a demo estimation from a simple formula - not produced by
              a trained ML model and not a guarantee of any actual offer.
            </p>
          </div>
        </div>
      )}

      {/* FACTOR BREAKDOWN */}
      {result && !isEstimating && (
        <div className="dash-card salary-breakdown">
          <div className="dash-card-header">
            <IconMark name="accuracy" className="dash-card-icon blue" />
            <h2>Demo Estimation Factors</h2>
          </div>

          <p className="dash-card-note">
            Input strength relative to the demo formula's caps - not statistical
            importance.
          </p>

          <div className="bar-list">
            {result.factorBreakdown.map((factor) => (
              <div key={factor.label} className="bar-row">
                <div className="bar-row-header">
                  <span>{factor.label}</span>
                  <strong>{factor.detail}</strong>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-fill salary-factor-fill"
                    style={{ width: `${factor.level}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default SalaryPrediction;
