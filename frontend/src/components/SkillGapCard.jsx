/**
 * SkillGapCard - placement readiness summary card (Phase 4C).
 *
 * Consumes the REAL backend readiness response (GET
 * /api/profile/{id}/readiness) directly:
 *
 *   readiness_score, readiness_level,
 *   strengths:    [{ skill, category?, evidence? }]  -> "Matched Skills"
 *   skill_gaps:   [{ skill, category, priority, reason }] -> "Missing Skills"
 *
 * The backend is the source of truth: no percentage, skill list, or label is
 * computed or substituted here. The backend response has NO "role" and NO
 * required-skills list, so the old "Target Role" heading is replaced by the
 * backend readiness level and required skills show an explicit "Not
 * available" state instead of invented data. All fields are read defensively
 * so a missing optional backend field can never crash the card.
 */
import SkillChip from "./SkillChip";
import MatchProgress from "./MatchProgress";

/* Defensive readers: the backend schema guarantees most fields, but a
   missing/optional field must degrade to a "Not available" state, not crash. */
const toSkillNames = (entries) =>
  (Array.isArray(entries) ? entries : [])
    .map((entry) => entry?.skill)
    .filter((skill) => typeof skill === "string" && skill.length > 0);

function SkillGapCard({ readiness }) {
  const score = Number(readiness?.readiness_score);
  const level =
    typeof readiness?.readiness_level === "string" &&
    readiness.readiness_level.length > 0
      ? readiness.readiness_level
      : "Not available";

  const matchedSkills = toSkillNames(readiness?.strengths);
  const missingSkills = toSkillNames(readiness?.skill_gaps);

  return (
    <div className="dash-card skill-gap-card">
      <div className="skill-gap-card-header">
        <div>
          <span className="skill-gap-role-label">Readiness Status</span>
          <h3>{level}</h3>
        </div>
      </div>

      <MatchProgress
        percent={Number.isFinite(score) ? score : 0}
        label="Readiness Score"
      />

      <div className="skill-gap-grid">
        <div className="company-skills-block">
          <span className="skills-label">Matched Skills</span>
          <div className="skill-chip-row">
            {matchedSkills.length > 0 ? (
              matchedSkills.map((skill) => (
                <SkillChip key={skill} skill={skill} variant="matched" />
              ))
            ) : (
              <span className="skills-empty">No matched skills yet</span>
            )}
          </div>
        </div>

        <div className="company-skills-block">
          <span className="skills-label">Missing Skills</span>
          <div className="skill-chip-row">
            {missingSkills.length > 0 ? (
              missingSkills.map((skill) => (
                <SkillChip key={skill} skill={skill} variant="missing" />
              ))
            ) : (
              <span className="skills-complete">
                All required skills covered ✓
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="skill-gap-footer">
        <span className="skills-label">Current Skills</span>
        <div className="skill-chip-row">
          {matchedSkills.length > 0 ? (
            matchedSkills.map((skill) => <SkillChip key={skill} skill={skill} />)
          ) : (
            <span className="skills-empty">Not available</span>
          )}
        </div>
        <span className="skills-label">Required Skills</span>
        <div className="skill-chip-row">
          {/* Not provided by the readiness API — shown as unavailable rather
              than reconstructed from old demo data. */}
          <span className="skills-empty">Not available</span>
        </div>
      </div>
    </div>
  );
}

export default SkillGapCard;
