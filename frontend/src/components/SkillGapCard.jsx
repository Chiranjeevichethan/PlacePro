/**
 * SkillGapCard - summary card for one target role in skill gap analysis.
 * Shows current, required, matched, and missing skills with a match bar.
 * Uses demo matching logic until a real backend exists.
 */
import SkillChip from "./SkillChip";
import MatchProgress from "./MatchProgress";

function SkillGapCard({ gap }) {
  return (
    <div className="dash-card skill-gap-card">
      <div className="skill-gap-card-header">
        <div>
          <span className="skill-gap-role-label">Target Role</span>
          <h3>{gap.role}</h3>
        </div>
        <span className="demo-chip">DEMO</span>
      </div>

      <MatchProgress percent={gap.matchPercent} label="Skill Match" />

      <div className="skill-gap-grid">
        <div className="company-skills-block">
          <span className="skills-label">Matched Skills</span>
          <div className="skill-chip-row">
            {gap.matchedSkills.length > 0 ? (
              gap.matchedSkills.map((skill) => (
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
            {gap.missingSkills.length > 0 ? (
              gap.missingSkills.map((skill) => (
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
          {gap.currentSkills.map((skill) => (
            <SkillChip key={skill} skill={skill} />
          ))}
        </div>
        <span className="skills-label">Required Skills</span>
        <div className="skill-chip-row">
          {gap.requiredSkills.map((skill) => (
            <SkillChip key={skill} skill={skill} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default SkillGapCard;
