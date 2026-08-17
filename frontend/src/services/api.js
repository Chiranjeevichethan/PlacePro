/**
 * PlacePro API service.
 *
 * IMPORTANT: This is a TEMPORARY DEMO implementation. It returns a mock
 * prediction computed from the student form data so the frontend flow can be
 * tested end-to-end. It is NOT real ML output.
 *
 * Once the backend/ML teammate provides the API, replace the body of
 * `predictPlacement` with a real request, for example:
 *
 *   const response = await fetch("<api-url>", {
 *     method: "POST",
 *     headers: { "Content-Type": "application/json" },
 *     body: JSON.stringify(data),
 *   });
 *   if (!response.ok) throw new Error("Prediction request failed");
 *   return response.json();
 *
 * The exact endpoint (e.g. POST /predict) and URL will be provided by the
 * backend teammate later.
 */

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const toNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const scoreOutOf100 = (value) => clamp(toNumber(value), 0, 100) / 100;

const countScore = (value, max) => clamp(toNumber(value), 0, 10) / max;

/**
 * Temporary demo prediction.
 *
 * Combines the student's inputs into a single demo probability. The weights
 * below are arbitrary and only used to make the demo respond to the form —
 * they are NOT derived from the ML models.
 */
export async function predictPlacement(formData) {
  // Small delay so loading states are visible in the UI.
  await new Promise((resolve) => setTimeout(resolve, 700));

  const cgpaScore = clamp(toNumber(formData.cgpa), 0, 10) / 10;
  const attendanceScore = scoreOutOf100(formData.attendance);
  const hasVolunteer = formData.volunteerExperience === "Yes" ? 1 : 0;

  const factors = [
    cgpaScore * 0.25,
    scoreOutOf100(formData.codingSkill) * 0.14,
    scoreOutOf100(formData.aptitudeScore) * 0.12,
    scoreOutOf100(formData.communicationSkill) * 0.08,
    scoreOutOf100(formData.logicalReasoning) * 0.08,
    scoreOutOf100(formData.mockInterview) * 0.08,
    attendanceScore * 0.07,
    countScore(formData.internships, 3) * 0.06,
    countScore(formData.projects, 4) * 0.05,
    countScore(formData.certifications, 4) * 0.03,
    countScore(formData.hackathons, 3) * 0.03,
    hasVolunteer * 0.01,
  ];

  const baseScore = factors.reduce((sum, factor) => sum + factor, 0);
  const backlogPenalty = toNumber(formData.backlogs) * 0.03;

  const probability = Math.round(clamp(baseScore * 100 - backlogPenalty, 5, 98));

  return {
    probability,
    status: probability >= 50 ? "LIKELY PLACED" : "PLACEMENT RISK",
    demo: true,
  };
}
