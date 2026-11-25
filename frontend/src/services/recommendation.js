/**
 * PlacePro demo matching service for company recommendations and skill gap
 * analysis.
 *
 * IMPORTANT: This is a TEMPORARY DEMO implementation. The matching below is a
 * simple transparent calculation (matched skills / required skills x 100) -
 * it is NOT an ML recommendation model. It will be replaced once the
 * backend/recommendation API is integrated (same pattern as api.js).
 */
import {
  ROLE_SKILLS,
  DEMO_COMPANIES,
  DEMO_STUDENT_SKILLS,
} from "../data/recommendationData";

const normalize = (value) => String(value || "").trim().toLowerCase();

/** Split a comma-separated skills string into a clean, de-duplicated array. */
export function parseSkills(raw) {
  if (Array.isArray(raw)) {
    return [...new Set(raw.map(normalize).filter(Boolean))];
  }
  return [...new Set(
    String(raw || "")
      .split(",")
      .map(normalize)
      .filter(Boolean)
  )];
}

/** Pretty-case a normalized skill for display (e.g. "html/css" -> "HTML/CSS"). */
export function displaySkill(skill) {
  const match = Object.keys(ROLE_SKILLS)
    .flatMap((role) => ROLE_SKILLS[role])
    .find((known) => normalize(known) === normalize(skill));
  return match || skill;
}

/** Demo skill match: matched skills / required skills x 100. */
export function computeMatch(studentSkills, requiredSkills) {
  const student = studentSkills.map(normalize);
  const matched = requiredSkills.filter((skill) =>
    student.includes(normalize(skill))
  );
  const percent = requiredSkills.length
    ? Math.round((matched.length / requiredSkills.length) * 100)
    : 0;

  return {
    matchedSkills: matched,
    missingSkills: requiredSkills.filter(
      (skill) => !student.includes(normalize(skill))
    ),
    matchPercent: percent,
  };
}

/** Returns the skill list for a role, from the demo role table. */
export function getRoleSkills(role) {
  return ROLE_SKILLS[role] || [];
}

/**
 * Demo company recommendations for a student profile.
 *
 * Uses the transparent skill match plus a simple CGPA/tier eligibility check.
 * Not an ML model.
 */
export function getCompanyRecommendations(profile) {
  const studentSkills = profile?.skills?.length
    ? parseSkills(profile.skills)
    : DEMO_STUDENT_SKILLS.map(normalize);

  const cgpa = Number(profile?.cgpa);
  const hasCgpa = Number.isFinite(cgpa) && cgpa > 0;

  return DEMO_COMPANIES.map((company) => {
    const { matchedSkills, missingSkills, matchPercent } = computeMatch(
      studentSkills,
      company.requiredSkills
    );

    const meetsCgpa = hasCgpa ? cgpa >= company.minCgpa : true;
    const eligibility = meetsCgpa ? "Eligible" : "CGPA below requirement";

    return {
      ...company,
      studentSkills: matchedSkills,
      missingSkills,
      matchPercent,
      eligibility,
      eligible: meetsCgpa,
    };
  }).sort((a, b) => b.matchPercent - a.matchPercent);
}

/**
 * Demo skill gap analysis for a target role: current vs required skills.
 * Falls back to the demo skill list when the profile has no skills yet.
 */
export function getSkillGap(profile, role) {
  const requiredSkills = getRoleSkills(role);
  const currentSkills = profile?.skills?.length
    ? parseSkills(profile.skills).map(displaySkill)
    : [...DEMO_STUDENT_SKILLS];

  const { matchedSkills, missingSkills, matchPercent } = computeMatch(
    currentSkills,
    requiredSkills
  );

  return {
    role,
    currentSkills,
    requiredSkills,
    matchedSkills,
    missingSkills,
    matchPercent,
    demo: true,
  };
}
