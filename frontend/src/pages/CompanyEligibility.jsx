/**
 * Company Eligibility page (Phase 4E).
 *
 * Requirement-based eligibility from the REAL FastAPI endpoints:
 *   GET /api/profile/{id}/eligibility            -> grouped summaries
 *   GET /api/profile/{id}/eligibility/{company}  -> per-requirement details
 *
 * The backend is the source of truth: group membership, statuses, counts,
 * requirement buckets, values, reasons, and actions are displayed exactly
 * as returned. No eligibility is computed here, no demo data exists, and
 * unknown information is shown as "Not verified" — never as a failure.
 *
 * Eligibility is requirement-based only: no placement probability, ML
 * prediction, recommendation score, or readiness score is used or shown.
 */
import { useCallback, useEffect, useState } from "react";
import IconMark from "../components/IconMark";
import {
  fetchCompanyEligibility,
  fetchCompanyEligibilityDetail,
} from "../services/api";
import { DEMO_PROFILE_ID } from "../services/profileConfig";

/* ------------------------------------------------------------------ */
/* Safe display helpers                                                 */
/* ------------------------------------------------------------------ */

/** De-duplicated list of non-empty display strings from an unknown value. */
const toDisplayList = (value) => {
  if (!Array.isArray(value)) return [];
  const cleaned = value
    .filter((item) => typeof item === "string")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return [...new Set(cleaned)];
};

/** A count that can be shown as-is (finite, non-negative integer). */
const asCount = (value) => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
};

/** Format student_value: null -> "Not verified"; never undefined/NaN/[obj]. */
const formatStudentValue = (value) => {
  if (value === null || value === undefined) return "Not verified";
  if (typeof value === "string") return value.trim() || "Not verified";
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "Not verified";
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return "Not verified";
};

/** Format required_value: scalar as-is, array as a readable list, null ->
    "Not specified"; never undefined/NaN/[object Object]. */
const formatRequiredValue = (value) => {
  if (value === null || value === undefined) return "Not specified";
  if (Array.isArray(value)) {
    const parts = value
      .filter(
        (item) =>
          typeof item === "string" ||
          (typeof item === "number" && Number.isFinite(item))
      )
      .map((item) => String(item));
    return parts.length > 0 ? parts.join(", ") : "Not specified";
  }
  if (typeof value === "string") return value.trim() || "Not specified";
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "Not specified";
  }
  return "Not specified";
};

/**
 * One requirement row inside the details view. Group bucket (passed /
 * failed / unknown) decides the status presentation — the row itself never
 * re-derives PASS/FAIL/UNKNOWN.
 */
function RequirementRow({ result, bucket }) {
  const item = result ?? {};
  const requirement =
    typeof item.requirement === "string" && item.requirement.trim()
      ? item.requirement
      : "Requirement";

  const explanation =
    typeof item.explanation === "string" && item.explanation.trim()
      ? item.explanation
      : null;

  const action =
    typeof item.action === "string" && item.action.trim()
      ? item.action
      : null;

  const mandatory = item.mandatory !== false; // backend default is true

  const statusClass =
    bucket === "passed"
      ? "passed"
      : bucket === "failed"
        ? "failed"
        : "unknown";

  return (
    <li className={`eligibility-requirement ${statusClass}`}>
      <div className="eligibility-requirement-head">
        <strong className="eligibility-requirement-name">{requirement}</strong>
        <span
          className={`eligibility-requirement-status ${statusClass}`}
          title={bucket === "unknown" ? "Missing information" : undefined}
        >
          {bucket === "passed" ? "PASS" : bucket === "failed" ? "FAIL" : "UNKNOWN"}
        </span>
        {!mandatory && (
          <span className="eligibility-requirement-preferred">Preferred</span>
        )}
      </div>

      <div className="eligibility-requirement-values">
        <span className="eligibility-value-pair">
          <span className="eligibility-value-label">Your value</span>
          <strong>{formatStudentValue(item.student_value)}</strong>
        </span>
        <span className="eligibility-value-pair">
          <span className="eligibility-value-label">Required</span>
          <strong>{formatRequiredValue(item.required_value)}</strong>
        </span>
      </div>

      {explanation && (
        <p className="eligibility-requirement-explanation">{explanation}</p>
      )}
      {action && <p className="eligibility-requirement-action">{action}</p>}
    </li>
  );
}

/**
 * Collapsible detail view for one company. Loads lazily on first open and
 * follows the page's loading / error / retry pattern.
 */
function CompanyEligibilityDetail({ companyId }) {
  const [open, setOpen] = useState(false);
  const [detailStatus, setDetailStatus] = useState("idle"); // idle|loading|success|error
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  /* attempt 0 = not yet requested. The fetch runs when the panel is first
     opened (open becomes true) and again whenever Retry bumps attempt. */
  const [attempt, setAttempt] = useState(0);

  const load = useCallback(() => {
    setDetailStatus("loading");
    setDetailError(null);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!open) return undefined;

    let active = true;

    fetchCompanyEligibilityDetail(DEMO_PROFILE_ID, companyId)
      .then((data) => {
        if (!active) return;
        setDetail(data);
        setDetailError(null);
        setDetailStatus("success");
      })
      .catch((err) => {
        if (!active) return;
        setDetail(null);
        setDetailError(
          err?.message ??
            "Unable to load company eligibility details. Please try again."
        );
        setDetailStatus("error");
      });

    return () => {
      active = false;
    };
  }, [open, attempt, companyId]);

  /* Loading UI is switched here (an event handler), not inside the fetch
     effect, so the effect stays a pure fetch trigger. First open (or a
     reopen after an error) shows the loading state; a reopen after success
     keeps the previously loaded details visible while the refetch runs. */
  const handleToggle = (event) => {
    const isOpen = event.currentTarget.open;
    setOpen(isOpen);
    if (isOpen && detailStatus !== "success") {
      setDetailStatus("loading");
      setDetailError(null);
    }
  };

  const passed = toDisplayArray(detail?.requirements?.passed);
  const failed = toDisplayArray(detail?.requirements?.failed);
  const unknown = toDisplayArray(detail?.requirements?.unknown);

  const missingInformation = toDisplayList(detail?.missing_information);
  const explanations = toDisplayList(detail?.explanation);

  return (
    <details
      className="company-details"
      onToggle={handleToggle}
    >
      <summary className="company-details-summary">
        View Eligibility Details
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
        {detailStatus === "loading" && (
          <p className="eligibility-detail-loading">
            <span className="spinner" aria-hidden="true"></span>
            Loading eligibility details...
          </p>
        )}

        {detailStatus === "error" && (
          <div className="eligibility-detail-error">
            <div className="error-banner" role="alert">
              {detailError}
            </div>
            <button
              type="button"
              className="dash-btn primary"
              onClick={load}
            >
              Retry
            </button>
          </div>
        )}

        {detailStatus === "success" && detail && (
          <>
            {explanations.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Summary</span>
                <ul className="company-detail-list">
                  {explanations.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>
            )}

            {missingInformation.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Missing Information</span>
                <div className="skill-chip-row">
                  {missingInformation.map((info) => (
                    <span className="skill-chip missing" key={info}>
                      {info}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {unknown.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">
                  Unknown Requirements (missing information — not failures)
                </span>
                <ul className="eligibility-requirement-list">
                  {unknown.map((result, index) => (
                    <RequirementRow
                      key={`${result?.requirement ?? "unknown"}-${index}`}
                      result={result}
                      bucket="unknown"
                    />
                  ))}
                </ul>
              </div>
            )}

            {failed.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Failed Requirements</span>
                <ul className="eligibility-requirement-list">
                  {failed.map((result, index) => (
                    <RequirementRow
                      key={`${result?.requirement ?? "failed"}-${index}`}
                      result={result}
                      bucket="failed"
                    />
                  ))}
                </ul>
              </div>
            )}

            {passed.length > 0 && (
              <div className="company-skills-block">
                <span className="skills-label">Passed Requirements</span>
                <ul className="eligibility-requirement-list">
                  {passed.map((result, index) => (
                    <RequirementRow
                      key={`${result?.requirement ?? "passed"}-${index}`}
                      result={result}
                      bucket="passed"
                    />
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </details>
  );
}

/** Array.isArray guard that keeps the bucket iteration type-safe. */
function toDisplayArray(value) {
  return Array.isArray(value) ? value : [];
}

/**
 * One backend eligibility summary card. Counts and reasons are
 * the backend's values — never recomputed from requirement arrays.
 */
function EligibilitySummaryCard({ summary }) {
  const item = summary ?? {};

  const company = item.company ?? {};
  const name =
    typeof company.company_name === "string" && company.company_name.trim()
      ? company.company_name
      : "Unknown company";

  const industry =
    typeof company.industry === "string" && company.industry.trim()
      ? company.industry
      : null;

  const roles = toDisplayList(company.roles);

  const status =
    typeof item.status === "string" && item.status.trim()
      ? item.status
      : "UNKNOWN";

  const passedCount = asCount(item.passed_count);
  const failedCount = asCount(item.failed_count);
  const unknownCount = asCount(item.unknown_count);

  const majorReasons = toDisplayList(item.major_reasons);

  const statusClass =
    status === "ELIGIBLE"
      ? "eligible"
      : status === "NOT_ELIGIBLE"
        ? "not-eligible"
        : "incomplete";

  const hasCounts =
    passedCount !== null || failedCount !== null || unknownCount !== null;

  return (
    <div className="company-card">
      <div className="company-card-header">
        <div className="company-icon gradient">
          <IconMark name="company" />
        </div>

        <div className="company-identity">
          <h3>{name}</h3>
          {industry && <p>{industry}</p>}
          {roles.length > 0 && (
            <p className="company-roles">{roles.join(" · ")}</p>
          )}
        </div>

        <span className={`company-eligibility ${statusClass}`}>{status}</span>
      </div>

      {hasCounts && (
        <div className="eligibility-counts">
          {passedCount !== null && (
            <span className="eligibility-count passed">
              <strong>{passedCount}</strong> passed
            </span>
          )}
          {failedCount !== null && (
            <span className="eligibility-count failed">
              <strong>{failedCount}</strong> failed
            </span>
          )}
          {unknownCount !== null && (
            <span className="eligibility-count unknown">
              <strong>{unknownCount}</strong> not verified
            </span>
          )}
        </div>
      )}

      {majorReasons.length > 0 && (
        <div className="company-skills-block">
          <span className="skills-label">Why</span>
          <ul className="company-detail-list">
            {majorReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <CompanyEligibilityDetail companyId={company.company_id} />
    </div>
  );
}

/** Group render order per Phase 4E: Eligible, Incomplete, Not Eligible. */
const ELIGIBILITY_GROUPS = [
  { key: "eligible", title: "Eligible Companies", icon: "objective" },
  { key: "incomplete", title: "Incomplete Information", icon: "academic" },
  { key: "not_eligible", title: "Not Eligible Companies", icon: "skills" },
];

function CompanyEligibility() {
  /* Page-level state: loading / success / error, SkillGapAnalysis pattern. */
  const [status, setStatus] = useState("loading");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  /* attempt 0 = initial load. Only attempt is a dependency: status must not
     re-trigger the fetch (status transitions loading→success/error would
     otherwise loop the request). Retry bumps attempt to refetch. */
  const [attempt, setAttempt] = useState(0);

  const refetch = useCallback(() => {
    setStatus("loading");
    setData(null);
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let active = true;

    fetchCompanyEligibility(DEMO_PROFILE_ID)
      .then((response) => {
        if (!active) return;
        setData(response);
        setError(null);
        setStatus("success");
      })
      .catch((err) => {
        if (!active) return;
        setData(null);
        setError(
          err?.message ?? "Unable to load company eligibility. Please try again."
        );
        setStatus("error");
      });

    return () => {
      active = false;
    };
  }, [attempt]);

  return (
    <div className="eligibility-page">
      <div className="page-header">
        <h1>Company Eligibility</h1>
        <p>
          Requirement-based eligibility for every active company, based only
          on your verified profile — no ML predictions involved.
        </p>
      </div>

      {status === "loading" && (
        <div className="profile-section profile-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading company eligibility...</p>
        </div>
      )}

      {status === "error" && (
        <div className="profile-section profile-error-state">
          <div className="error-banner" role="alert">
            {error}
          </div>
          <button type="button" className="dash-btn primary" onClick={refetch}>
            Retry
          </button>
        </div>
      )}

      {status === "success" && data && (
        <>
          {ELIGIBILITY_GROUPS.map(({ key, title, icon }) => {
            const items = Array.isArray(data[key]) ? data[key] : [];

            /* Backend group membership is authoritative: empty groups are
               not rendered and nothing is fabricated to fill them. */
            if (items.length === 0) return null;

            return (
              <section className="analysis-section" key={key}>
                <h2>
                  <IconMark name={icon} className="section-title-icon" />
                  <span>{title}</span>
                </h2>

                <div className="company-grid">
                  {items.map((summary, index) => (
                    <EligibilitySummaryCard
                      key={
                        summary?.company?.company_id ??
                        `summary-${key}-${index}`
                      }
                      summary={summary}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}

export default CompanyEligibility;
