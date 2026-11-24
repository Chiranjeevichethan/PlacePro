/**
 * PlacePro salary prediction service (Phase 5C).
 *
 * REAL BACKEND INTEGRATION: predictSalary() sends the validated form
 * fields to POST /api/salary-predict (Ridge regression model
 * "placepro-salary-v2", trained on placed students only) and returns the
 * backend's authoritative result. No salary value is ever computed,
 * hard-coded, or substituted in the frontend.
 *
 * The backend response is conditional on placement - it is NOT a guaranteed
 * offer. The UI must present it as an estimate only.
 */
import { buildSalaryPayload, requestSalaryPrediction } from "./api";

/**
 * Format an LPA value for display, e.g. 21.6542 -> "₹21.65 LPA".
 * Rounded to 2 decimals for display only; the underlying value returned by
 * the backend is never altered.
 */
export function formatLpa(value) {
  return `₹${(Math.round(value * 100) / 100).toFixed(2)} LPA`;
}

/**
 * Request a salary estimate from the real backend.
 *
 * `formData` is the salary page's form state (prefilled from the student
 * profile). The payload is mapped to the backend fields (buildSalaryPayload
 * in services/api.js) - branch is normalized to the canonical backend
 * vocabulary ("ISE"/"Information Science..." -> "CSE"). A known profile tier
 * is preserved; a missing tier uses the existing backend fallback.
 * No student id, placement status, or stored salary value is ever
 * sent.
 *
 * Returns { predictedSalaryLpa: number, modelVersion: string | null }.
 * Throws an Error with a user-readable message on any failure (validation,
 * unavailable service, network, or malformed response).
 */
export async function predictSalary(formData = {}) {
  const payload = buildSalaryPayload(formData);

  /* Safety net: the form validates before this point, but never send
     missing/invalid values to the backend. (branch is the only string field
     and must be non-empty; optional college_tier is a category.) */
  const hasInvalidInput = Object.entries(payload).some(([field, value]) => {
    if (field === "branch" || field === 'college_tier') {
      return typeof value !== "string" || value.trim() === "";
    }
    return !Number.isFinite(value);
  });

  if (hasInvalidInput) {
    throw new Error(
      "Some salary inputs are missing or invalid. Please check the form and try again."
    );
  }

  return requestSalaryPrediction(payload);
}
