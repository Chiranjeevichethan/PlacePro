import { useRef, useState } from "react";
import { createProfileFromResume } from "../services/api";

function Resume({ onProfileCreated }) {
  const inputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFile = (selectedFile) => {
    if (!selectedFile) return;

    if (!/\.(pdf|docx)$/i.test(selectedFile.name)) {
      setError("Please upload a PDF or DOCX resume.");
      setFile(null);
      setResult(null);
      return;
    }

    setError("");
    setResult(null);
    setFile(selectedFile);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);

    const droppedFile = event.dataTransfer.files?.[0];

    if (droppedFile) {
      handleFile(droppedFile);
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      setError("Please select a resume first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await createProfileFromResume(file);
      setResult(response);
    } catch (err) {
      setError(
        err?.message || "Resume processing failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleReview = () => {
    if (result?.profile && onProfileCreated) {
      onProfileCreated(result.profile);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Resume Upload</h1>

        <p>
          Upload your resume and PlacePro will extract your student profile.
        </p>
      </div>

      <div className="resume-upload-card">
        <div
          className={`resume-dropzone ${dragging ? "dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => {
            setDragging(false);
          }}
          onDrop={handleDrop}
          onClick={() => {
            inputRef.current?.click();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          role="button"
          tabIndex={0}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx"
            hidden
            onChange={(event) => {
              handleFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />

          <div className="resume-upload-icon">↑</div>

          <h2>
            {file ? file.name : "Upload your resume"}
          </h2>

          <p>
            Drag & drop your PDF or DOCX here, or click to browse.
          </p>

          <span className="resume-upload-hint">
            Supported formats: PDF, DOCX
          </span>

          {file && (
            <span className="resume-selected-file">
              Selected: {file.name}
            </span>
          )}
        </div>

        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}

        <button
          type="button"
          className="dash-btn primary"
          onClick={handleSubmit}
          disabled={!file || loading}
        >
          {loading ? "ANALYZING RESUME..." : "ANALYZE RESUME"}
        </button>
      </div>

      {result?.profile && (
        <div className="resume-result-card">
          <h2>Resume Analysis Complete</h2>

          <p>
            {result.message ||
              "Your resume has been processed successfully."}
          </p>

          <div className="resume-summary-grid">
            <div>
              <span>Name</span>
              <strong>
                {result.profile.personal?.name || "Not found"}
              </strong>
            </div>

            <div>
              <span>Email</span>
              <strong>
                {result.profile.personal?.email || "Not found"}
              </strong>
            </div>

            <div>
              <span>Branch</span>
              <strong>
                {result.profile.education?.branch || "Not found"}
              </strong>
            </div>

            <div>
              <span>College</span>
              <strong>
                {result.profile.education?.college || "Not found"}
              </strong>
            </div>

            <div>
              <span>CGPA</span>
              <strong>
                {result.profile.education?.cgpa ?? "Not found"}
              </strong>
            </div>

            <div>
              <span>Graduation Year</span>
              <strong>
                {result.profile.education?.graduation_year ||
                  "Not found"}
              </strong>
            </div>

            <div>
              <span>Projects</span>
              <strong>
                {result.profile.projects?.length ?? 0}
              </strong>
            </div>

            <div>
              <span>Internships</span>
              <strong>
                {result.profile.internships?.length ?? 0}
              </strong>
            </div>

            <div>
              <span>Certifications</span>
              <strong>
                {result.profile.certifications?.length ?? 0}
              </strong>
            </div>

            <div>
              <span>Skills</span>
              <strong>
                {Object.keys(result.profile.skills || {}).length}
              </strong>
            </div>
          </div>

          {!result.profile.verified && (
            <div className="resume-draft-notice">
              <strong>Draft Profile</strong>

              <p>
                The information extracted from your resume is currently
                a draft. Review and correct the information before
                confirming your profile.
              </p>
            </div>
          )}

          <button
            type="button"
            className="dash-btn primary"
            onClick={handleReview}
          >
            REVIEW PROFILE
          </button>
        </div>
      )}
    </div>
  );
}

export default Resume;