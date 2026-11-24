/**
 * Company Recommendations page (Phase 4D).
 *
 * Ranked company recommendations from the REAL FastAPI endpoint
 * (GET /api/profile/{id}/recommendations). The backend is the source of
 * truth: companies, group membership, ordering, and every score come from
 * the response. No demo companies, no frontend match/score computation.
 *
 * The student profile summary reuses the ONE shared profile from
 * StudentProfileContext (GET /api/profile/{id}); no second profile fetch and
 * no demo profile values are shown.
 */
import IconMark from "../components/IconMark";
import CompanyCard from "../components/CompanyCard";
import { fetchCompanyRecommendations } from "../services/api";
import { useStudentProfileContext } from "../hooks/useStudentProfileContext";
import { useProfileResource } from '../hooks/useProfileResource';

const loadRecommendations = (id) => fetchCompanyRecommendations(id, 10);

/** Group render order (backend ranking inside each group is kept as-is). */
const RECOMMENDATION_GROUPS = [
  { key: "recommended", title: "Recommended Companies", icon: "placement" },
  { key: "eligible", title: "Eligible Companies", icon: "objective" },
  { key: "incomplete", title: "Incomplete Information", icon: "academic" },
  { key: "not_recommended", title: "Not Recommended", icon: "skills" },
];

function CompanyRecommendations() {
  /* Same canonical profile as every other page. */
  const { profile } = useStudentProfileContext();

  /* Recommendations: loading / success / error, SkillGapAnalysis pattern. */
  const { data, error, loading, refetch } = useProfileResource(loadRecommendations);
  const status = error ? 'error' : loading ? 'loading' : 'success';
  const hasRecommendations = RECOMMENDATION_GROUPS.some(({ key }) =>
    Array.isArray(data?.recommendations?.[key]) && data.recommendations[key].length > 0);

  const summaryItems = profile
    ? [
        { label: "CGPA", value: profile.cgpa === '' ? 'Not set' : profile.cgpa },
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
          <p className="dash-card-note">Company requirements are demonstration data for this application.</p>
          {!hasRecommendations && <p className="skills-empty" role="status">
            No company recommendations are available for this profile.
          </p>}
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
