/**
 * Skill Gap Analysis page (Phase 4C).
 *
 * Placement readiness + skill-gap analysis from the REAL FastAPI readiness
 * endpoint (GET /api/profile/{id}/readiness). The backend is the source of
 * truth: the readiness score, matched skills (strengths), and missing skills
 * (skill gaps) are displayed exactly as returned. Learning resources are a
 * frontend catalog shown only for skills the backend reports as missing.
 */
import IconMark from "../components/IconMark";
import SkillGapCard from "../components/SkillGapCard";
import LearningResourceCard from "../components/LearningResourceCard";
import { getLearningResources } from "../data/recommendationData";
import { fetchStudentReadiness } from "../services/api";
import { useProfileResource } from '../hooks/useProfileResource';
import { resolveSkillGapDisplay } from "../services/skillGapDisplay.js";

function SkillGapAnalysis() {
  /* The readiness analysis belongs to the CURRENT student: use the shared
     profile id (after a resume is verified it is no longer the demo id). */
  const { data: readiness, error, loading, refetch } = useProfileResource(fetchStudentReadiness);
  const view = resolveSkillGapDisplay({ readiness, loading, error });
  const { missingSkills = [] } = view;

  const resourceCards = missingSkills.map((skill) => ({
    skill,
    resources: getLearningResources(skill),
  }));

  return (
    <div className="skillgap-page">
      <div className="page-header">
        <h1>Skill Gap Analysis</h1>
        <p>
          Placement readiness and skill gaps from your verified student
          profile, so you know exactly what to work on.
        </p>
      </div>

      {view.state === "loading" && (
        <div className="profile-section profile-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading readiness analysis...</p>
        </div>
      )}

      {view.state === "error" && (
        <div className="profile-section profile-error-state">
          <div className="error-banner" role="alert">
            {view.error}
          </div>
          <button type="button" className="dash-btn primary" onClick={refetch}>
            Retry
          </button>
        </div>
      )}

      {view.state === "unavailable" && (
        <div className="profile-section profile-error-state">
          <div className="error-banner" role="alert">
            The readiness service returned incomplete analysis data. Please retry.
          </div>
          <button type="button" className="dash-btn primary" onClick={refetch}>
            Retry
          </button>
        </div>
      )}

      {view.state === "ready" && readiness && (
        <>
          <section className="analysis-section">
            <h2>
              <IconMark name="skills" className="section-title-icon" />
              <span>Skill Gap Summary</span>
            </h2>

            <SkillGapCard readiness={readiness} />
            <p className="dash-card-note">Readiness measures preparation evidence, not placement probability. A missing or insufficient skill means the profile has not yet demonstrated it; it does not prove you lack the ability.</p>
            {view.hasNoGaps && (
              <div className="analysis-card" role="status">
                <p>{view.emptyMessage}</p>
              </div>
            )}
            {view.profileIncomplete && !view.hasNoGaps && (
              <p className="dash-card-note" role="status">
                Your profile still has sections to complete. Recommendations reflect the information currently available and may change when you add details.
              </p>
            )}
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
                {resourceCards.map(({ skill, resources }) => (
                  <LearningResourceCard
                    key={skill}
                    skill={skill}
                    resources={resources}
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
