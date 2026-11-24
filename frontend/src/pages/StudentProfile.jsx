import { useRef, useState } from "react";
import IconMark from "../components/IconMark";
import EditProfileModal from "../components/EditProfileModal";
import ResumeUploadModal from "../components/ResumeUploadModal";
import { verifyStudentProfile } from "../services/api";
import { createRetryIntent } from '../services/retryIntent';
import { useStudentProfileContext } from "../hooks/useStudentProfileContext";
import { getVolunteerExperienceDisplay } from '../services/profileConfig';

function StudentProfile({
  editOpen = false,
  onRequestEdit,
  onCloseEdit,
  resumeOpen = false,
  onRequestResume,
  onCloseResume,
}) {
  const {
    profileId,
    profile,
    rawProfile,
    loading,
    error,
    profileMissing,
    refetch,
    applyUpdatedProfile,
    resumeDraft,
    setPendingResumeDraft,
    clearPendingResumeDraft,
  } = useStudentProfileContext();

  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState(null);
  const verificationInFlight = useRef(false);
  const [retryIntent] = useState(createRetryIntent);

  /* Editing a profile resets the backend's `verified` flag (documented
     contract). This confirmation uses the existing POST /api/profile/verify
     endpoint so readiness, predictions and recommendations work again. */
  const handleVerify = () => {
    if (!rawProfile || verificationInFlight.current) return;
    verificationInFlight.current = true;

    setVerifying(true);
    setVerifyError(null);

    verifyStudentProfile(rawProfile, retryIntent(rawProfile))
      .then((data) => applyUpdatedProfile(data))
      .catch((err) =>
        setVerifyError(
          err?.message ?? "Unable to confirm the profile. Please try again."
        )
      )
      .finally(() => { verificationInFlight.current = false; setVerifying(false); });
  };

  /* Refetch the authoritative profile after a successful verify so the
     "Verified" badge reflects the backend's stored state. */
  const handleResumeVerified = (data) => {
    const verifiedProfileId = data?.profile?.profile_id;
    clearPendingResumeDraft();
    onCloseResume?.();
    refetch(verifiedProfileId);
  };

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

  const volunteerDisplay = getVolunteerExperienceDisplay(rawProfile);
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
          value: volunteerDisplay.value,
          detail: volunteerDisplay.detail,
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
            onClick={() => refetch()}
          >
            Retry
          </button>
          {profileMissing && <button type="button" className="dash-btn secondary"
            onClick={onRequestResume}>Create Profile from Resume</button>}
        </div>
      )}
      {!loading && !error && !profile && <div className="profile-section">
        <h2>Create your student profile</h2>
        <p>Upload a PDF or DOCX resume, review the extraction and confirm your information.</p>
        <button type="button" className="dash-btn primary" onClick={onRequestResume}>Create Profile from Resume</button>
      </div>}

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
                  <h2>{profile.name || "Student"}</h2>
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

              <div className="profile-card-actions">
                <button
                  type="button"
                  className="dash-btn secondary"
                  onClick={onRequestResume}
                  disabled={verifying}
                  title="Extract a resume, review selected changes and confirm before updating this profile."
                >
                  Update from Resume
                </button>

                <button
                  type="button"
                  className="dash-btn secondary profile-edit-btn"
                  onClick={onRequestEdit}
                >
                  Edit Profile
                </button>
              </div>
            </div>
          </div>

          {!profile.verified && (
            <div className="info-note" role="status">
              <span>
                This profile has unverified changes. Confirm it to refresh
                readiness, predictions and recommendations.
              </span>
              <button
                type="button"
                className="dash-btn primary"
                onClick={handleVerify}
                disabled={verifying || !rawProfile}
              >
                {verifying ? "CONFIRMING..." : "Confirm Profile"}
              </button>
            </div>
          )}

          {verifyError && (
            <div className="error-banner" role="alert">
              {verifyError}
            </div>
          )}

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

            <p className="form-description">
              These values are shared with Placement Prediction and Salary
              Prediction. Fields shown as “Not set” are still missing — use
              Edit Profile to provide them once.
            </p>

            {profile.skills.length > 0 && (
              <div className="profile-skills-row">
                {profile.skills.map((skill) => (
                  <span key={skill} className="skill-chip matched">
                    {skill}
                  </span>
                ))}
              </div>
            )}

            {Array.isArray(rawProfile?.assessment_evidence) && rawProfile.assessment_evidence.length > 0 && (
              <div aria-label="Recorded assessments">
                <h3>Recorded Assessments</h3>
                <p className="form-description">
                  Assessment results are saved separately from your resume skills and self-reported scores.
                </p>
                <div className="profile-grid">
                  {rawProfile.assessment_evidence.map((entry) => (
                    <div className="profile-item" key={entry.assessment_id}>
                      <span>{entry.skill}</span>
                      <strong>{entry.score}% · {entry.level}</strong>
                      <small>Attempt {entry.attempt} · {entry.verified ? "Recorded assessment" : "Unverified"}</small>
                    </div>
                  ))}
                </div>
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

      {editOpen && !loading && !error && profile && rawProfile && (
        <EditProfileModal
          key={profileId}
          profileId={profileId}
          profile={profile}
          backendProfile={rawProfile}
          onSaved={applyUpdatedProfile}
          onReload={() => { onCloseEdit?.(); refetch(); }}
          onClose={onCloseEdit}
        />
      )}

      {resumeOpen && !loading && (!error || profileMissing) && (
        <ResumeUploadModal
          key={profileId}
          resumeDraft={resumeDraft}
          preservedProfile={rawProfile}
          onDraftCreated={(result) => setPendingResumeDraft(result.draftProfile)}
          onVerified={handleResumeVerified}
          onClose={onCloseResume}
        />
      )}
    </div>
  );
}

export default StudentProfile;
