/**
 * SkillChip - small rounded chip used to display a skill.
 * Variants: "neutral" (default), "matched" (student has it), "missing" (to learn).
 */
function SkillChip({ skill, variant = "neutral" }) {
  return <span className={`skill-chip ${variant}`}>{skill}</span>;
}

export default SkillChip;
