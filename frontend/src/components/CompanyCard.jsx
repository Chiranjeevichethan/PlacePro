/**
 * CompanyCard - one backend company recommendation (Phase 4D).
 *
 * Consumes the REAL backend RecommendationItem from
 * GET /api/profile/{id}/recommendations:
 *
 *   company_name            -> card header
 *   recommendation_score    -> "Recommendation Score" progress bar
 *   skill_match.score       -> "Skill Match" progress bar
 *   skill_match.required_matched        -> "Your Skills" chips
 *   skill_match.required_missing + preferred_missing -> "Skill Gap" chips
 *   eligibility_status      -> eligibility chip
 *   placement_probability   -> percentage in details (null -> "Not available")
 *   readiness_score/level   -> labeled details rows (never mixed with the
 *                              ML placement probability)
 *   reasons / improvement_actions / missing_information -> details lists
 *
 * Fields with no backend source (role, minCgpa, tier, industry) are removed,
 * not fabricated. All access is defensive: a missing optional field degrades
 * to a hidden section or an explicit "Not available", never a crash and
 * never a substituted value.
 */
import IconMark from "./IconMark";
import SkillChip from "./SkillChip";
import MatchProgress from "./MatchProgress";

/** Safely extract a de-duplicated list of non-empty display strings. */
const toDisplayList = (value) => {
  if (!Array.isArray(value)) return [];
  const cleaned = value
    .filter((item) => typeof item === "string")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return [...new Set(cleaned)];
};

const asFiniteNumber = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

function CompanyCard({ company }) {
  const item = company ?? {};

  const name =
    typeof item.company_name === "string" && item.company_name.trim()
      ? item.company_name
      : "Unknown company";

  /* Eligibility chip: backend status vocabulary, displayed as-is. */
  const eligibility =
    (typeof item.eligibility_status === "string" && item.eligibility_status) ||
    (typeof item.status === "string" && item.status) ||
    "";
  const isEligible = eligibility === "ELIGIBLE";

  const recommendationScore = asFiniteNumber(item.recommendation_score);
  const skillMatchScore = asFiniteNumber(item.skill_match?.score);

  const yourSkills = toDisplayList(item.skill_match?.required_matched);
  const gapSkills = toDisplayList([
    ...(Array.isArray(item.skill_match?.required_missing)
      ? item.skill_match.required_missing
      : []),
    ...(Array.isArray(item.skill_match?.preferred_missing)
      ? item.skill_match.preferred_missing
      : []),
  ]);

  /* placement_probability is 0-1 or null; converted to a percentage only
     when the backend supplies a number. */
  const probabilityValue = asFiniteNumber(item.placement_probability);
  const probabilityText =
    probabilityValue === null
      ? "Not available"
      : `${Math.round(probabilityValue * 100)}%`;

  const readinessScore = asFiniteNumber(item.readiness_score);
  const readinessLevel =
    typeof item.readiness_level === "string" && item.readiness_level.trim()
      ? item.readiness_level
      : null;

  const reasons = toDisplayList(item.reasons);
  const improvementActions = toDisplayList(item.improvement_actions);
  const missingInformation = toDisplayList(item.missing_information);

  const hasProbabilityRow = probabilityValue !== null;
  const hasReadinessRows = readinessScore !== null || readinessLevel !== null;
  const hasLists =
    reasons.length > 0 ||
    improvementActions.length > 0 ||
    missingInformation.length > 0;

  const hasDetails =
    hasProbabilityRow || hasReadinessRows || hasLists;

  return (
    <div className={`company-card ${isEligible ? "" : "not-eligible"}`}>
      <div className="company-card-header">
        <div className="company-icon gradient">
          <IconMark name="professional" />
        </div>

        <div className="company-identity">
          <h3>{name}</h3>
        </div>

        {eligibility && (
          <span
            className={`company-eligibility ${isEligible ? "eligible" : "not-eligible"}`}
          >
            {eligibility}
          </span>
        )}
      </div>

      {recommendationScore !== null && (
        <MatchProgress
          percent={recommendationScore}
          label="Recommendation Score"
        />
      )}

      {skillMatchScore !== null && (
        <MatchProgress percent={skillMatchScore} label="Skill Match" />
      )}

      <div className="company-skills-block">
        <span className="skills-label">Your Skills</span>
        <div className="skill-chip-row">
          {yourSkills.length > 0 ? (
            yourSkills.map((skill) => (
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
          {gapSkills.length > 0 ? (
            gapSkills.map((skill) => (
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
            {hasProbabilityRow && (
              <div className="company-detail-row">
                <span>Placement Probability</span>
                <strong>{probabilityText}</strong>
              </div>
            )}

            {readinessScore !== null && (
              <div className="company-detail-row">
                <span>Readiness Score</span>
                <strong>{readinessScore}</strong>
              </div>
            )}

            {readinessLevel && (
              <div className="company-detail-row">
                <span>Readiness Level</span>
                <strong>{readinessLevel}</strong>
              </div>
            )}

            {reasons.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Reasons</span>
                <ul className="company-detail-list">
                  {reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {improvementActions.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Improvement Actions</span>
                <ul className="company-detail-list">
                  {improvementActions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>
            )}

            {missingInformation.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Missing Information</span>
                <ul className="company-detail-list">
                  {missingInformation.map((info) => (
                    <li key={info}>{info}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

export default CompanyCard;
