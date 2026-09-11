/**
 * Skill Gap Analysis page (Phase 4C).
 *
 * Placement readiness + skill-gap analysis from the REAL FastAPI readiness
 * endpoint (GET /api/profile/{id}/readiness). The backend is the source of
 * truth: the readiness score, matched skills (strengths), and missing skills
 * (skill gaps) are displayed exactly as returned. Learning resources are a
 * frontend catalog shown only for skills the backend reports as missing.
 */
import { useCallback, useEffect, useState } from "react";
import IconMark from "../components/IconMark";
import SkillGapCard from "../components/SkillGapCard";
import LearningResourceCard from "../components/LearningResourceCard";
import { LEARNING_RESOURCES } from "../data/recommendationData";
import { fetchStudentReadiness } from "../services/api";
import { DEMO_PROFILE_ID } from "../services/profileConfig";

function SkillGapAnalysis() {
  const [status, setStatus] = useState("loading");
  const [readiness, setReadiness] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;

    fetchStudentReadiness(DEMO_PROFILE_ID)
      .then((data) => {
        if (!active) return;
        setReadiness(data);
        setError(null);
        setStatus("success");
      })
      .catch((err) => {
        if (!active) return;
        setReadiness(null);
        setError(
          err?.message ?? "Unable to load readiness data. Please try again."
        );
        setStatus("error");
      });

    return () => {
      active = false;
    };
  }, [attempt]);

  const refetch = useCallback(() => {
    setStatus("loading");
    setReadiness(null);
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  const missingSkills =
    readiness?.skill_gaps?.map((entry) => entry.skill) ?? [];

  return (
    <div className="skillgap-page">
      <div className="page-header">
        <h1>Skill Gap Analysis</h1>
        <p>
          Placement readiness and skill gaps from your verified student
          profile, so you know exactly what to work on.
        </p>
      </div>

      {status === "loading" && (
        <div className="profile-section profile-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading readiness analysis...</p>
        </div>
      )}

      {status === "error" && (
        <div className="profile-section profile-error-state">
          <div className="error-banner" role="alert">
            {error}
          </div>
          <button type="button" className="dash-btn primary" onClick={refetch}>
            Retry
          </button>
        </div>
      )}

      {status === "success" && readiness && (
        <>
          <section className="analysis-section">
            <h2>
              <IconMark name="skills" className="section-title-icon" />
              <span>Skill Gap Summary</span>
            </h2>

            <SkillGapCard readiness={readiness} />
          </section>

          {missingSkills.length > 0 && (
            <section className="analysis-section">
              <h2>
                <IconMark name="academic" className="section-title-icon" />
                <span>Learning Resources</span>
              </h2>

              <p className="skillgap-resources-note">
                Frontend-provided resources for the missing skills reported by
                the readiness service. Links open in a new tab.
              </p>

              <div className="resource-grid">
                {missingSkills.map((skill) => (
                  <LearningResourceCard
                    key={skill}
                    skill={skill}
                    resources={LEARNING_RESOURCES[skill] || []}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default SkillGapAnalysis;