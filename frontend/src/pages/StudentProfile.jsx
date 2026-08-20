import { useState, useEffect } from "react";
import IconMark from "../components/IconMark";
import EditProfileModal from "../components/EditProfileModal";

const PROFILE_KEY = "placepro_profile";

const defaultProfile = {
  name: "Bhargav",
  branch: "Information Science and Engineering",
  collegeTier: "Tier 2",
  cgpa: "8.2",
  attendance: "88",
  internships: "2",
  projects: "3",
  certifications: "4",
  githubRepositories: "5",
  linkedinConnections: "120",
};

function loadProfile() {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) {
      return { ...defaultProfile, ...JSON.parse(raw) };
    }
  } catch {
    // Ignore malformed storage and fall back to defaults.
  }
  return defaultProfile;
}

function getValue(obj, path, fallback = "Not provided") {
  const keys = path.split(".");
  let current = obj;
  for (const key of keys) {
    if (current === null || current === undefined) return fallback;
    current = current[key];
  }
  return current === null || current === undefined || current === "" ? fallback : current;
}

function StudentProfile({
  backendProfile = null,
  editOpen = false,
  onRequestEdit,
  onCloseEdit,
}) {
  const [profile, setProfile] = useState(loadProfile);

  useEffect(() => {
    if (backendProfile) {
      const mapped = mapBackendProfile(backendProfile);
      setProfile(mapped);
    } else {
      setProfile(loadProfile());
    }
  }, [backendProfile]);

  const handleSave = (data) => {
    setProfile(data);
    try {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(data));
      window.dispatchEvent(new Event("placepro-profile-updated"));
    } catch {
      // Storage may be unavailable; profile still updates in memory.
    }
    if (onCloseEdit) {
      onCloseEdit();
    }
  };

  function mapBackendProfile(bp) {
    const p = bp.profile || bp;
    const ml = p.ml_inputs || {};
    const edu = p.education || {};
    const pers = p.personal || {};

    return {
      name: getValue(pers, "name"),
      branch: getValue(edu, "branch"),
      collegeTier: getValue(ml, "college_tier"),
      cgpa: getValue(edu, "cgpa", "Not provided"),
      attendance: "Not provided",
      internships: getValue(p, "internships.length", "Not provided"),
      projects: getValue(p, "projects.length", "Not provided"),
      certifications: getValue(p, "certifications.length", "Not provided"),
      githubRepositories: "Not provided",
      linkedinConnections: "Not provided",
      backlogs: getValue(ml, "backlogs", "Not provided"),
      codingSkills: getValue(ml, "coding_skills", "Not provided"),
      dsaScore: getValue(ml, "dsa_score", "Not provided"),
      aptitudeScore: getValue(ml, "aptitude_score", "Not provided"),
      communicationSkills: getValue(ml, "communication_skills", "Not provided"),
      mlKnowledge: getValue(ml, "ml_knowledge", "Not provided"),
      systemDesign: getValue(ml, "system_design", "Not provided"),
      openSourceContributions: getValue(ml, "open_source_contributions", "Not provided"),
      extracurriculars: getValue(ml, "extracurriculars", "Not provided"),
    };
  }

  const academicData = [
    { label: "CGPA", value: profile.cgpa, detail: "out of 10" },
    {
      label: "College Tier",
      value: profile.collegeTier,
      detail: "Institution category",
    },
    {
      label: "Attendance",
      value: profile.attendance === "Not provided" ? "Not provided" : `${profile.attendance}%`,
      detail: "Overall attendance",
    },
    { label: "Backlogs", value: profile.backlogs, detail: "Active backlogs" },
  ];

  const experienceData = [
    {
      label: "Internships",
      value: profile.internships,
      detail: "Completed internships",
    },
    {
      label: "Projects",
      value: profile.projects,
      detail: "Academic & personal projects",
    },
    {
      label: "Certifications",
      value: profile.certifications,
      detail: "Earned certifications",
    },
    { label: "Hackathons", value: "Not provided", detail: "Hackathons participated" },
    {
      label: "GitHub Repositories",
      value: profile.githubRepositories,
      detail: "Public repositories",
    },
    {
      label: "LinkedIn Connections",
      value: profile.linkedinConnections,
      detail: "Professional network",
    },
    { label: "Volunteer Experience", value: "Not provided", detail: "Volunteering activity" },
  ];

  const skillData = [
    { label: "Coding Skill", value: profile.codingSkills },
    { label: "Aptitude Score", value: profile.dsaScore },
    { label: "Communication", value: profile.communicationSkills },
    { label: "Logical Reasoning", value: "Not provided" },
    { label: "Mock Interview", value: "Not provided" },
    { label: "Leadership", value: "Not provided" },
  ];

  const isBackendProfile = Boolean(backendProfile);

  return (
    <div className="profile-page">
      <div className="page-header">
        <h1>Student Profile</h1>
        <p>View student academic and professional information.</p>
      </div>

      <div className="profile-card">
        <div className="profile-card-top">
          <div className="profile-intro">
            <div className="profile-avatar gradient">
              {profile.name && profile.name !== "Not provided" ? profile.name.charAt(0).toUpperCase() : "?"}
            </div>

            <div className="profile-identity">
              <h2>{profile.name}</h2>
              <p>{profile.branch}</p>
              <div className="profile-badges">
                <span className="profile-badge">Student</span>
                <span className="profile-badge">
                  {profile.collegeTier} College
                </span>
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

        {isBackendProfile ? (
          <p className="profile-data-note">
            <strong>Backend Profile:</strong> Data extracted from your resume. Edit to add missing
            fields (e.g., ML skill scores, backlogs, college tier) before prediction.
          </p>
        ) : (
          <p className="profile-data-note">
            <strong>Sample data notice:</strong> The information on this page is
            sample/demo data for illustration. It is not generated by the ML model
            and will be replaced once the backend API is integrated.
          </p>
        )}
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

        <div className="profile-grid">
          {skillData.map((item) => {
            const isProvided = item.value !== "Not provided";
            const numericValue = isProvided ? Number(item.value) : 0;
            return (
              <div key={item.label} className="profile-item">
                <span>{item.label}</span>
                <strong>
                  {isProvided ? `${item.value}<small> / 100</small>` : "Not provided"}
                </strong>
                {isProvided && (
                  <div className="profile-bar">
                    <div
                      className="profile-bar-fill"
                      style={{ width: `${Math.min(numericValue, 100)}%` }}
                    ></div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {editOpen && (
        <EditProfileModal
          profile={profile}
          onSave={handleSave}
          onClose={onCloseEdit}
        />
      )}
    </div>
  );
}

export default StudentProfile;