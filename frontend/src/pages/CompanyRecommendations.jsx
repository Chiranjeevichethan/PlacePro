/**
 * Company Recommendations page (Phase 1A).
 *
 * Shows a demo student profile summary and demo company recommendations with
 * a transparent skill match (matched skills / required skills x 100).
 * All data is DEMO data until a real recommendation backend exists.
 */
import IconMark from "../components/IconMark";
import CompanyCard from "../components/CompanyCard";
import { getCompanyRecommendations } from "../services/recommendation";
import useProfile from "../hooks/useProfile";

function CompanyRecommendations() {
  const profile = useProfile();
  const recommendations = getCompanyRecommendations(profile);

  const summaryItems = [
    { label: "CGPA", value: profile.cgpa || "—" },
    {
      label: "Skills",
      value: profile.skills ? `${profile.skills.split(",").length} listed` : "Demo set",
    },
    { label: "Projects", value: profile.projects || "—" },
    { label: "Internships", value: profile.internships || "—" },
    { label: "Certifications", value: profile.certifications || "—" },
    {
      label: "Preferred Role",
      value: profile.preferredRole || "Not set",
    },
  ];

  return (
    <div className="companies-page">
      <div className="page-header">
        <h1>Company Recommendations</h1>
        <p>
          Discover companies that match your skills, academic profile, and
          career goals.
        </p>
      </div>

      <div className="info-note">
        <svg
          className="info-note-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>
          <strong>Demo Recommendation:</strong> Matches are calculated with a
          simple skill comparison (matched skills / required skills) on demo
          data. This is not an ML recommendation model and will be replaced
          once the backend API is integrated.
        </span>
      </div>

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

      <section className="analysis-section">
        <h2>
          <IconMark name="placement" className="section-title-icon" />
          <span>Recommended Companies</span>
        </h2>

        <div className="company-grid">
          {recommendations.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      </section>
    </div>
  );
}

export default CompanyRecommendations;
