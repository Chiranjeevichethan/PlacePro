/**
 * Skill Gap Analysis page (Phase 1B + 1C).
 *
 * Compares the student's current skills against the skills required for a
 * selected target role, and shows learning resources for every missing skill.
 * Matching is demo logic (matched skills / required skills x 100) until a
 * real backend exists.
 */
import { useState } from "react";
import IconMark from "../components/IconMark";
import SkillGapCard from "../components/SkillGapCard";
import LearningResourceCard from "../components/LearningResourceCard";
import { ROLE_SKILLS, LEARNING_RESOURCES } from "../data/recommendationData";
import { getSkillGap } from "../services/recommendation";
import useProfile from "../hooks/useProfile";

const ROLE_OPTIONS = Object.keys(ROLE_SKILLS);

function SkillGapAnalysis() {
  const profile = useProfile();
  const [role, setRole] = useState(profile.preferredRole || ROLE_OPTIONS[0]);

  const gap = getSkillGap(profile, role);

  return (
    <div className="skillgap-page">
      <div className="page-header">
        <h1>Skill Gap Analysis</h1>
        <p>
          Compare your current skills against the skills required for your
          target role, and find resources to close the gap.
        </p>
      </div>

      <div className="info-note">
        <svg
          className="info-note-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>
          <strong>Demo Data:</strong> Skill matching uses a simple comparison
          against a predefined skill list per role. This is not ML output and
          will be replaced once the backend API is integrated.
        </span>
      </div>

      <section className="analysis-section">
        <h2>
          <IconMark name="objective" className="section-title-icon" />
          <span>Target Role</span>
        </h2>

        <div className="dash-card skillgap-role-card">
          <div className="form-group skillgap-role-select">
            <label htmlFor="skillgap-role">Select target role</label>
            <select
              id="skillgap-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {ROLE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="analysis-section">
        <h2>
          <IconMark name="skills" className="section-title-icon" />
          <span>Skill Gap Summary</span>
        </h2>

        <SkillGapCard gap={gap} />
      </section>

      {gap.missingSkills.length > 0 && (
        <section className="analysis-section">
          <h2>
            <IconMark name="academic" className="section-title-icon" />
            <span>Learning Resources</span>
          </h2>

          <p className="skillgap-resources-note">
            Resources for each missing skill. Links open in a new tab.
          </p>

          <div className="resource-grid">
            {gap.missingSkills.map((skill) => (
              <LearningResourceCard
                key={skill}
                skill={skill}
                resources={LEARNING_RESOURCES[skill] || []}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default SkillGapAnalysis;
