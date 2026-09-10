/**
 * PlacePro demo salary estimation service (Phase 2).
 *
 * IMPORTANT: This is a TEMPORARY DEMO implementation - same pattern as
 * services/api.js. The calculation below is a simple, transparent, DETERMINISTIC
 * formula (base salary per role + small adjustments for CGPA, projects,
 * internships, certifications, experience, skills). It is NOT a trained ML
 * model and produces NO accuracy metrics.
 *
 * FUTURE BACKEND INTEGRATION (do not change the exported API):
 *   Replace the body of `predictSalary()` with a real request to the salary
 *   model endpoint provided by the backend teammate, for example:
 *
 *     const response = await fetch("<api-url>/api/salary-predict", {
 *       method: "POST",
 *       headers: { "Content-Type": "application/json" },
 *       body: JSON.stringify(profile),
 *     });
 *     if (!response.ok) throw new Error("Salary prediction request failed");
 *     return response.json();
 *
 * Until then every result returned here must be shown with the
 * "Estimated Salary (Demo)" label used in SalaryPrediction.jsx.
 */
import { ROLE_SKILLS } from "../data/recommendationData";
import { parseSkills, displaySkill } from "./recommendation";

// Demo base salaries (LPA = lakhs per annum) per target role. Arbitrary demo
// values - NOT derived from any trained model or real market dataset.
const ROLE_BASE_LPA = {
  "Data Analyst": 4.5,
  "Data Scientist": 6.5,
  "Software Developer": 5.5,
  "Full Stack Developer": 5.5,
  "ML Engineer": 7.0,
};

// Demo adjustment for the target company type. Arbitrary demo values.
const COMPANY_TYPE_ADJUSTMENT_LPA = {
  Any: 0,
  "Service-Based": 0,
  Startup: 0.2,
  MNC: 0.3,
  "Product-Based": 0.5,
};

export const COMPANY_TYPE_OPTIONS = Object.keys(COMPANY_TYPE_ADJUSTMENT_LPA);

/** Format an LPA value for display, e.g. 6.249 -> "₹6.2 LPA". */
export function formatLpa(value) {
  return `₹${(Math.round(value * 10) / 10).toFixed(1)} LPA`;
}

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const toCount = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
};

/**
 * Deterministic demo salary estimation.
 *
 * Every adjustment below is capped so extreme inputs cannot produce absurd
 * values. The adjustment amounts are documented demo assumptions.
 */
export async function predictSalary(input = {}) {
  // Small delay so the UI loading state is visible (same pattern as api.js).
  await new Promise((resolve) => setTimeout(resolve, 600));

  const role = input.preferredRole || "Data Analyst";
  const baseLpa = ROLE_BASE_LPA[role] ?? 5.0;

  const cgpa = Number(input.cgpa);
  const hasCgpa = Number.isFinite(cgpa);
  const projects = toCount(input.projects);
  const internships = toCount(input.internships);
  const certifications = toCount(input.certifications);
  const experience = toCount(input.experience);
  const companyType = COMPANY_TYPE_ADJUSTMENT_LPA[input.companyType]
    ? input.companyType
    : "Any";

  const studentSkills = parseSkills(input.skills).map(displaySkill);
  const roleSkills = ROLE_SKILLS[role] || [];
  const matchedSkills = roleSkills.filter((skill) =>
    studentSkills.includes(skill)
  );

  // --- Demo adjustments (each capped, values are documented assumptions) ---
  // CGPA: +0.15 LPA per point above 6.0, capped at +0.6
  const cgpaAdjust = hasCgpa ? clamp((cgpa - 6) * 0.15, 0, 0.6) : 0;
  // Projects: +0.1 LPA each, capped at 4 projects (+0.4)
  const projectAdjust = Math.min(projects, 4) * 0.1;
  // Internships: +0.3 LPA each, capped at 3 (+0.9)
  const internshipAdjust = Math.min(internships, 3) * 0.3;
  // Certifications: +0.15 LPA each, capped at 4 (+0.6)
  const certificationAdjust = Math.min(certifications, 4) * 0.15;
  // Relevant experience: +0.4 LPA per year, capped at 3 years (+1.2)
  const experienceAdjust = Math.min(experience, 3) * 0.4;
  // Skills: +0.15 LPA per relevant skill matched, capped at 5 (+0.75)
  const skillAdjust = Math.min(matchedSkills.length, 5) * 0.15;
  // Target company type: fixed demo adjustment
  const companyAdjust = COMPANY_TYPE_ADJUSTMENT_LPA[companyType];

  const estimateLpa =
    Math.round(
      (baseLpa +
        cgpaAdjust +
        projectAdjust +
        internshipAdjust +
        certificationAdjust +
        experienceAdjust +
        skillAdjust +
        companyAdjust) *
        10
    ) / 10;

  // Demo range: ±10% around the point estimate (floored at ₹1 LPA).
  const minLpa = Math.max(1, Math.round(estimateLpa * 0.9 * 10) / 10);
  const maxLpa = Math.round(estimateLpa * 1.1 * 10) / 10;

  // --- Factor breakdown for the "Demo Estimation Factors" section ---
  // `level` is how strong each INPUT is relative to the cap the demo formula
  // uses (0-100). It is NOT a statistical importance weight.
  const factorBreakdown = [
    {
      label: "CGPA",
      detail: hasCgpa ? `${cgpa} / 10` : "Not provided",
      level: hasCgpa ? clamp((cgpa / 10) * 100, 0, 100) : 0,
    },
    {
      label: "Skills",
      detail: `${matchedSkills.length} of ${roleSkills.length} relevant skills`,
      level: roleSkills.length
        ? clamp((matchedSkills.length / roleSkills.length) * 100, 0, 100)
        : 0,
    },
    {
      label: "Projects",
      detail: `${projects} project${projects === 1 ? "" : "s"}`,
      level: clamp((Math.min(projects, 4) / 4) * 100, 0, 100),
    },
    {
      label: "Internships",
      detail: `${internships} internship${internships === 1 ? "" : "s"}`,
      level: clamp((Math.min(internships, 3) / 3) * 100, 0, 100),
    },
    {
      label: "Certifications",
      detail: `${certifications} certification${certifications === 1 ? "" : "s"}`,
      level: clamp((Math.min(certifications, 4) / 4) * 100, 0, 100),
    },
    {
      label: "Experience",
      detail: `${experience} year${experience === 1 ? "" : "s"}`,
      level: clamp((Math.min(experience, 3) / 3) * 100, 0, 100),
    },
  ];

  // --- Profile strength: average input strength across the factors above ---
  const strengthScore = Math.round(
    factorBreakdown.reduce((sum, factor) => sum + factor.level, 0) /
      factorBreakdown.length
  );
  const profileStrength =
    strengthScore >= 80
      ? { label: "Excellent", className: "rating-excellent" }
      : strengthScore >= 60
        ? { label: "Good", className: "rating-good" }
        : strengthScore >= 40
          ? { label: "Average", className: "rating-average" }
          : { label: "Entry-Level", className: "rating-low" };

  // --- Key factors: derived ONLY from the values actually entered ---
  const positiveFactors = [];
  const improvementAreas = [];

  if (hasCgpa && cgpa >= 7.5) {
    positiveFactors.push(`Strong CGPA (${cgpa} / 10)`);
  } else if (hasCgpa && cgpa < 7) {
    improvementAreas.push("Raise CGPA above 7.0");
  }

  if (matchedSkills.length > 0) {
    positiveFactors.push(
      `Relevant skills: ${matchedSkills.slice(0, 3).join(", ")}`
    );
  }
  const missingSkills = roleSkills.filter(
    (skill) => !studentSkills.includes(skill)
  );
  if (missingSkills.length > 0) {
    improvementAreas.push(`Learn: ${missingSkills.slice(0, 3).join(", ")}`);
  }

  if (projects >= 2) {
    positiveFactors.push(`${projects} projects completed`);
  } else {
    improvementAreas.push("Build more projects");
  }

  if (internships > 0) {
    positiveFactors.push(
      `${internships} internship${internships === 1 ? "" : "s"} completed`
    );
  } else {
    improvementAreas.push("Gain internship experience");
  }

  if (certifications >= 2) {
    positiveFactors.push(`${certifications} certifications earned`);
  } else {
    improvementAreas.push("Add more relevant certifications");
  }

  if (experience > 0) {
    positiveFactors.push(
      `${experience} year${experience === 1 ? "" : "s"} relevant experience`
    );
  } else {
    improvementAreas.push("Gain relevant work experience");
  }

  return {
    estimateLpa,
    minLpa,
    maxLpa,
    role,
    companyType,
    profileStrength,
    factorBreakdown,
    positiveFactors,
    improvementAreas,
    demo: true,
  };
}
