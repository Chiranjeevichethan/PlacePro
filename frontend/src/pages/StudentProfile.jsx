import IconMark from "../components/IconMark";
import EditProfileModal from "../components/EditProfileModal";
import { useStudentProfile } from "../hooks/useProfile";

function StudentProfile({
  editOpen = false,
  onRequestEdit,
  onCloseEdit,
}) {
  const {
    profile,
    rawProfile,
    loading,
    error,
    refetch,
    applyUpdatedProfile,
  } = useStudentProfile();

  const academicData = profile
    ? [
        { label: "CGPA", value: profile.cgpa || "Not set", detail: "out of 10" },
        {
          label: "College Tier",
          value: profile.collegeTierDisplay,
          detail: "Institution category",
        },
        {
          label: "Attendance",
          value: profile.attendance ? `${profile.attendance}%` : "Not set",
          detail: "Overall attendance",
        },
        {
          label: "Backlogs",
          value: profile.backlogs,
          detail: "Active backlogs",
        },
      ]
    : [];

  const experienceData = profile
    ? [
        {
          label: "Internships",
          value: profile.internshipsCount,
          detail: "Completed internships",
        },
        {
          label: "Projects",
          value: profile.projectsCount,
          detail: "Academic & personal projects",
        },
        {
          label: "Certifications",
          value: profile.certificationsCount,
          detail: "Earned certifications",
        },
        {
          label: "Hackathons",
          value: profile.hackathonsCount,
          detail: "Hackathons participated",
        },
        {
          label: "GitHub Repositories",
          value: profile.githubRepositories || "Not set",
          detail: "Public repositories",
        },
        {
          label: "LinkedIn Connections",
          value: profile.linkedinConnections || "Not set",
          detail: "Professional network",
        },
        {
          label: "Volunteer Experience",
          value: profile.volunteerExperience || "Not set",
          detail: "Volunteering activity",
        },
        {
          label: "Open Source Contributions",
          value: profile.openSourceContributions || "Not set",
          detail: "Community contributions",
        },
      ]
    : [];

  return (
    <div className="profile-page">
      <div className="page-header">
        <h1>Student Profile</h1>
        <p>View student academic and professional information.</p>
      </div>

      {/* =========================================
          LOADING STATE
          ========================================= */}
      {loading && (
        <div className="profile-section profile-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading student profile...</p>
        </div>
      )}

      {/* =========================================
          ERROR STATE
          ========================================= */}
      {!loading && error && (
        <div className="profile-section profile-error-state">
          <div className="error-banner" role="alert">
            {error}
          </div>
          <button
            type="button"
            className="dash-btn primary"
            onClick={refetch}
          >
            Retry
          </button>
        </div>
      )}

      {/* =========================================
          PROFILE (backend data only — no demo fallback)
          ========================================= */}
      {!loading && !error && profile && (
        <>
          <div className="profile-card">
            <div className="profile-card-top">
              <div className="profile-intro">
                <div className="profile-avatar gradient">
                  {profile.name ? profile.name.charAt(0).toUpperCase() : "?"}
                </div>

                <div className="profile-identity">
                  <h2>{profile.name || "Unnamed Student"}</h2>
                  <p>{profile.branchDisplay}</p>
                  <div className="profile-badges">
                    <span className="profile-badge">Student</span>
                    <span className="profile-badge">
                      {profile.collegeTierDisplay} College
                    </span>
                    {profile.verified && (
                      <span className="profile-badge">Verified</span>
                    )}
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="dash-btn secondary profile-edit-btn"
                onClick={onRequestEdit}
              >
                Edit Profile
              </button>
            </div>
          </div>

          <div className="profile-section">
            <h2>
              <IconMark name="academic" className="section-title-icon" />
              <span>Academic Information</span>
            </h2>

            <div className="profile-grid">
              {academicData.map((item) => (
                <div key={item.label} className="profile-item">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <small>{item.detail}</small>
                </div>
              ))}
            </div>
          </div>

          <div className="profile-section">
            <h2>
              <IconMark name="experience" className="section-title-icon" />
              <span>Experience & Activities</span>
            </h2>

            <div className="profile-grid">
              {experienceData.map((item) => (
                <div key={item.label} className="profile-item">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <small>{item.detail}</small>
                </div>
              ))}
            </div>
          </div>

          <div className="profile-section">
            <h2>
              <IconMark name="skills" className="section-title-icon" />
              <span>Skills & Assessments</span>
            </h2>

            {profile.skills.length > 0 && (
              <div className="profile-skills-row">
                {profile.skills.map((skill) => (
                  <span key={skill} className="skill-chip matched">
                    {skill}
                  </span>
                ))}
              </div>
            )}

            <div className="profile-grid">
              <div className="profile-item">
                <span>Coding Skill</span>
                <strong>
                  {profile.codingSkills || "Not set"}
                  {profile.codingSkills && <small> / 10</small>}
                </strong>
              </div>

              <div className="profile-item">
                <span>DSA Score</span>
                <strong>
                  {profile.dsaScore || "Not set"}
                  {profile.dsaScore && <small> / 10</small>}
                </strong>
              </div>

              <div className="profile-item">
                <span>Aptitude Score</span>
                <strong>
                  {profile.aptitudeScore || "Not set"}
                  {profile.aptitudeScore && <small> / 100</small>}
                </strong>
              </div>

              <div className="profile-item">
                <span>Communication</span>
                <strong>
                  {profile.communicationSkills || "Not set"}
                  {profile.communicationSkills && <small> / 10</small>}
                </strong>
              </div>

              <div className="profile-item">
                <span>ML Knowledge</span>
                <strong>
                  {profile.mlKnowledge || "Not set"}
                  {profile.mlKnowledge && <small> / 10</small>}
                </strong>
              </div>

              <div className="profile-item">
                <span>System Design</span>
                <strong>
                  {profile.systemDesign || "Not set"}
                  {profile.systemDesign && <small> / 10</small>}
                </strong>
              </div>
            </div>
          </div>
        </>
      )}

      {editOpen && profile && rawProfile && (
        <EditProfileModal
          profile={profile}
          backendProfile={rawProfile}
          onSaved={applyUpdatedProfile}
          onClose={onCloseEdit}
        />
      )}
    </div>
  );
}

export default StudentProfile;
