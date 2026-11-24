import { displayIntegerOrNull } from "./performanceDisplay.js";

const NO_GAPS_MESSAGE =
  "No skill gaps were identified from the information currently available in your profile. This reflects profile evidence and does not mean every skill has been mastered.";
const INCOMPLETE_NO_GAPS_MESSAGE =
  "No skill gaps were identified from the information currently available in your profile. Some profile sections still need information, so this analysis may change as you add details; it does not mean every skill has been mastered.";

export function resolveSkillGapDisplay({ readiness, loading = false, error = null }) {
  if (error) return { state: "error", error };
  if (loading) return { state: "loading" };

  const completeness = readiness?.profile_completeness;
  const missingFields = completeness?.missing_fields;
  const completenessPercentage = displayIntegerOrNull(completeness?.percentage);
  const gaps = readiness?.skill_gaps;

  if (
    !Array.isArray(gaps) ||
    !Array.isArray(missingFields) ||
    completenessPercentage === null ||
    completenessPercentage < 0 ||
    completenessPercentage > 100 ||
    gaps.some((entry) => typeof entry?.skill !== "string" || entry.skill.trim() === "")
  ) {
    return { state: "unavailable" };
  }

  const missingSkills = [...new Set(gaps.map((entry) => entry.skill))];
  const profileIncomplete = missingFields.length > 0 || completenessPercentage < 100;
  const hasNoGaps = gaps.length === 0;

  return {
    state: "ready",
    missingSkills,
    profileIncomplete,
    hasNoGaps,
    emptyMessage: hasNoGaps
      ? profileIncomplete
        ? INCOMPLETE_NO_GAPS_MESSAGE
        : NO_GAPS_MESSAGE
      : null,
  };
}
