/**
 * Company Recommendations page (Phase 4D).
 *
 * Ranked company recommendations from the REAL FastAPI endpoint
 * (GET /api/profile/{id}/recommendations). The backend is the source of
 * truth: companies, group membership, ordering, and every score come from
 * the response. No demo companies, no frontend match/score computation.
 *
 * The student profile summary uses the already-integrated profile API
 * (GET /api/profile/{id}, Phase 4B) — the recommendations endpoint does not
 * provide profile data, and no demo profile values are shown.
 */
import { useCallback, useEffect, useState } from "react";
import IconMark from "../components/IconMark";
import CompanyCard from "../components/CompanyCard";
import { fetchCompanyRecommendations, fetchStudentProfile } from "../services/api";
import { DEMO_PROFILE_ID, flattenBackendProfile } from "../services/profileConfig";

/** Group render order (backend ranking inside each group is kept as-is). */
const RECOMMENDATION_GROUPS = [
  { key: "recommended", title: "Recommended Companies", icon: "placement" },
  { key: "eligible", title: "Eligible Companies", icon: "objective" },
  { key: "incomplete", title: "Incomplete Information", icon: "academic" },
  { key: "not_recommended", title: "Not Recommended", icon: "skills" },
];

function CompanyRecommendations() {
  /* Recommendations: loading / success / error, SkillGapAnalysis pattern. */
  const [status, setStatus] = useState("loading");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);

  /* Profile summary from the existing (Phase 4B) profile API. Optional:
     if it fails, the summary section is hidden and recommendations still
     render — no demo profile values are ever substituted. */
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    let active = true;

    fetchCompanyRecommendations(DEMO_PROFILE_ID, 10)
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
          err?.message ?? "Unable to load recommendations. Please try again."
        );
        setStatus("error");
      });

    return () => {
      active = false;
    };
  }, [attempt]);

  useEffect(() => {
    let active = true;

    fetchStudentProfile(DEMO_PROFILE_ID)
      .then((response) => {
        if (active) setProfile(flattenBackendProfile(response.profile));
      })
      .catch(() => {
        if (active) setProfile(null);
      });

    return () => {
      active = false;
    };
  }, []);

  const refetch = useCallback(() => {
    setStatus("loading");
    setData(null);
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  const summaryItems = profile
    ? [
        { label: "CGPA", value: profile.cgpa || "Not set" },
        {
          label: "Skills",
          value: profile.skills?.length
            ? `${profile.skills.length} listed`
            : "None listed",
        },
        { label: "Projects", value: profile.projectsCount },
        { label: "Internships", value: profile.internshipsCount },
        { label: "Certifications", value: profile.certificationsCount },
        { label: "College Tier", value: profile.collegeTierDisplay || "Not set" },
      ]
    : [];

  return (
    <div className="companies-page">
      <div className="page-header">
        <h1>Company Recommendations</h1>
        <p>
          Discover companies that match your skills, academic profile, and
          career goals.
        </p>
      </div>

      {/* =========================================
          LOADING STATE
          ========================================= */}
      {status === "loading" && (
        <div className="profile-section profile-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading company recommendations...</p>
        </div>
      )}

      {/* =========================================
          ERROR STATE
          ========================================= */}
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

      {/* =========================================
          BACKEND-DERIVED RECOMMENDATIONS
          (no demo fallback: nothing renders without backend data)
          ========================================= */}
      {status === "success" && data && (
        <>
          {summaryItems.length > 0 && (
            <section className="analysis-section">
              <h2>
                <IconMark name="profile" className="section-title-icon" />
                <span>Student Profile Summary</span>
              </h2>

              <div className="profile-grid profile-grid-6">
                {summaryItems.map((item) => (
                  <div key={item.label} className="profile-item">
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
            </section>
          )}

          {RECOMMENDATION_GROUPS.map(({ key, title, icon }) => {
            const items = Array.isArray(data.recommendations?.[key])
              ? data.recommendations[key]
              : [];

            /* Empty groups are not rendered. */
            if (items.length === 0) return null;

            return (
              <section className="analysis-section" key={key}>
                <h2>
                  <IconMark name={icon} className="section-title-icon" />
                  <span>{title}</span>
                </h2>

                <div className="company-grid">
                  {items.map((company) => (
                    <CompanyCard key={company?.company_id ?? company?.company_name} company={company} />
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

export default CompanyRecommendations;
