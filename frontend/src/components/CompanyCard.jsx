/**
 * CompanyCard - one demo company recommendation.
 * Shows company, role, skill match %, required/owned/missing skills,
 * eligibility, and a "View Details" toggle. All data is demo data until a
 * real recommendation backend exists.
 */
import IconMark from "./IconMark";
import SkillChip from "./SkillChip";
import MatchProgress from "./MatchProgress";

function CompanyCard({ company }) {
  const hasDetails = company.tier || company.minCgpa;

  return (
    <div className={`company-card ${company.eligible ? "" : "not-eligible"}`}>
      <div className="company-card-header">
        <div className="company-icon gradient">
          <IconMark name="professional" />
        </div>

        <div className="company-identity">
          <h3>{company.company}</h3>
          <p>{company.role}</p>
        </div>

        <span
          className={`company-eligibility ${company.eligible ? "eligible" : "not-eligible"}`}
        >
          {company.eligibility}
        </span>
      </div>

      <MatchProgress
        percent={company.matchPercent}
        label="Skill Match"
      />

      <div className="company-skills-block">
        <span className="skills-label">Required Skills</span>
        <div className="skill-chip-row">
          {company.requiredSkills.map((skill) => (
            <SkillChip key={skill} skill={skill} />
          ))}
        </div>
      </div>

      <div className="company-skills-block">
        <span className="skills-label">Your Skills</span>
        <div className="skill-chip-row">
          {company.studentSkills.length > 0 ? (
            company.studentSkills.map((skill) => (
              <SkillChip key={skill} skill={skill} variant="matched" />
            ))
          ) : (
            <span className="skills-empty">None matched yet</span>
          )}
        </div>
      </div>

      <div className="company-skills-block">
        <span className="skills-label">Skill Gap</span>
        <div className="skill-chip-row">
          {company.missingSkills.length > 0 ? (
            company.missingSkills.map((skill) => (
              <SkillChip key={skill} skill={skill} variant="missing" />
            ))
          ) : (
            <span className="skills-complete">All required skills covered ✓</span>
          )}
        </div>
      </div>

      {hasDetails && (
        <details className="company-details">
          <summary className="company-details-summary">
            View Details
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </summary>

          <div className="company-details-body">
            <div className="company-detail-row">
              <span>Minimum CGPA</span>
              <strong>{company.minCgpa.toFixed(1)}</strong>
            </div>
            <div className="company-detail-row">
              <span>Open College Tiers</span>
              <strong>{company.tier}</strong>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

export default CompanyCard;
