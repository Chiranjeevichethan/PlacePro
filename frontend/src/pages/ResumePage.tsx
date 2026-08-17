import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { resumeApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Card, CardSection } from "../components/ui/Card";
import { EmptyState } from "../components/ui/StateBox";
import { useToast } from "../components/ui/Toast";
import { useProfile } from "../context/ProfileContext";
import type { ProfileFromResumeResponse } from "../types";
import { humanize } from "../utils/format";

const ACCEPTED = [".pdf", ".docx"];

export function ResumePage() {
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState<ProfileFromResumeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocrRequired, setOcrRequired] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { notify } = useToast();
  const { switchProfile } = useProfile();

  async function handleFile(file: File | undefined | null) {
    if (!file) return;
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      setError("Unsupported file type. Please upload a .pdf or .docx resume.");
      return;
    }
    setUploading(true);
    setError(null);
    setOcrRequired(false);
    try {
      const res = await resumeApi.fromResume(file);
      setResult(res);
      // Switch the active profile to the newly created draft so the
      // rest of the dashboard (Profile, Prediction, Readiness, etc.)
      // uses this profile instead of the demo-seeded one.
      const newProfileId = res.profile.profile_id;
      if (newProfileId) {
        switchProfile(newProfileId);
      }
      notify("Resume imported — draft profile created. Review it below.", "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed.";
      if (msg.includes("OCR_REQUIRED") || /scanned|no extractable text/i.test(msg)) {
        setOcrRequired(true);
        setError(msg.replace("OCR_REQUIRED: ", ""));
      } else {
        setError(msg);
      }
      setResult(null);
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    void handleFile(e.dataTransfer.files?.[0]);
  }

  const extraction = result?.extraction_summary;
  const needsVerification =
    result?.feature_availability?.filter(
      (f) => f.status === "REQUIRES_MANUAL_INPUT" || f.status === "UNKNOWN",
    ) ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Resume Upload"
        subtitle="Upload your PDF or DOCX resume. PlacePro extracts your information, shows its confidence, and builds a draft profile you review before verifying. Nothing is assumed correct."
      />

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(",")}
        style={{ display: "none" }}
        onChange={(e) => void handleFile(e.target.files?.[0])}
      />

      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        <div className="dz-icon">📄</div>
        <div className="dz-title">
          {uploading ? "Analyzing your resume…" : "Drag & drop your resume here"}
        </div>
        <p className="dz-hint">
          or click to browse · PDF / DOCX · max 5 MB · scanned PDFs are detected and rejected gracefully
        </p>
      </div>

      {uploading && (
        <Card>
          <div className="flex">
            <div className="spinner" />
            <span>Parsing the document, extracting sections and computing confidence…</span>
          </div>
        </Card>
      )}

      {ocrRequired && (
        <div className="notice notice-danger mt-16">
          <strong>OCR required.</strong> {error} This PDF appears to be a
          scanned document — OCR is not implemented yet, so no profile can be
          built from it. Please upload a text-based PDF or a DOCX.
        </div>
      )}

      {error && !ocrRequired && (
        <div className="notice notice-danger mt-16">{error}</div>
      )}

      {result && (
        <>
          <Card title="Extraction Summary" className="mt-16">
            <div className="grid grid-4">
              <Badge tone="info">Words: {result.diagnostics?.word_count ?? 0}</Badge>
              <Badge tone="neutral">Pages: {result.diagnostics?.page_count ?? "—"}</Badge>
              <Badge tone="success">{extraction?.fields_extracted ?? 0} fields extracted</Badge>
              <Badge tone={result.diagnostics?.extraction_completeness >= 60 ? "success" : "warning"}>
                Extraction completeness {result.diagnostics?.extraction_completeness ?? 0}%
              </Badge>
            </div>

            <div className="mt-16">
              <h4 className="mt-0">Confidence</h4>
              <div className="flex flex-wrap">
                {Object.entries(result.confidence ?? {}).slice(0, 8).map(([field, label]) => (
                  <span key={field} className="skill-chip">
                    <span
                      className="dot"
                      style={{
                        background: label === "high" ? "var(--success)" : label === "medium" ? "var(--warning)" : "var(--danger)",
                      }}
                    />
                    {humanize(field)}: {label}
                  </span>
                ))}
                {!Object.keys(result.confidence ?? {}).length && (
                  <span className="muted small">No confidence labels returned.</span>
                )}
              </div>
            </div>

            {result.provenance?.length ? (
              <div className="mt-16">
                <h4 className="mt-0">Provenance (evidence per field)</h4>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th>Source</th>
                        <th>Value</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.provenance.map((p) => (
                        <tr key={p.field}>
                          <td><code>{p.field}</code></td>
                          <td><Badge tone={p.source === "resume" ? "info" : "neutral"}>{p.source}</Badge></td>
                          <td>{String(p.value ?? "—")}</td>
                          <td className="muted small">{p.evidence ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </Card>

          <Card title="Extracted Information" className="mt-16">
            <div className="grid grid-2">
              <div>
                <h4 className="mt-0">Personal</h4>
                {Object.entries(result.profile.personal)
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <div key={k} className="small" style={{ marginBottom: 4 }}>
                      <span className="muted">{humanize(k)}:</span> <strong>{String(v)}</strong>
                    </div>
                  ))}
              </div>
              <div>
                <h4 className="mt-0">Education</h4>
                {Object.entries(result.profile.education)
                  .filter(([, v]) => v !== null && v !== undefined && v !== "")
                  .map(([k, v]) => (
                    <div key={k} className="small" style={{ marginBottom: 4 }}>
                      <span className="muted">{humanize(k)}:</span> <strong>{String(v)}</strong>
                    </div>
                  ))}
              </div>
            </div>

            <CardSection>
              <h4 className="mt-0">Skills</h4>
              <div className="flex flex-wrap">
                {Object.entries(result.profile.skills).map(([cat, skills]) =>
                  skills.length ? (
                    <span key={cat} className="skill-chip">
                      {humanize(cat)}: {skills.join(", ")}
                    </span>
                  ) : null,
                )}
                {!Object.values(result.profile.skills).some((s) => s.length) && (
                  <span className="muted small">No skills detected.</span>
                )}
              </div>
            </CardSection>

            <CardSection>
              <div className="grid grid-3">
                <div>
                  <h4 className="mt-0">Experience ({result.profile.experience.length})</h4>
                  {result.profile.experience.map((e, i) => (
                    <div key={i} className="small" style={{ marginBottom: 6 }}>
                      <strong>{e.role}</strong> @ {e.company} <span className="muted">({e.duration})</span>
                    </div>
                  ))}
                </div>
                <div>
                  <h4 className="mt-0">Internships ({result.profile.internships.length})</h4>
                  {result.profile.internships.map((e, i) => (
                    <div key={i} className="small" style={{ marginBottom: 6 }}>
                      <strong>{e.role}</strong> @ {e.company} <span className="muted">({e.duration})</span>
                    </div>
                  ))}
                </div>
                <div>
                  <h4 className="mt-0">Projects ({result.profile.projects.length})</h4>
                  {result.profile.projects.map((e, i) => (
                    <div key={i} className="small" style={{ marginBottom: 6 }}>
                      <strong>{e.project_name}</strong>{" "}
                      <span className="muted">({e.technologies.join(", ")})</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardSection>

            {needsVerification.length > 0 && (
              <div className="notice notice-warning mt-16">
                <strong>Requires manual verification:</strong>{" "}
                {needsVerification.map((f) => f.field).join(", ")} — these
                could not be confidently extracted and need your input.
              </div>
            )}

            <div className="form-actions">
              <button className="btn btn-primary" onClick={() => navigate("/profile")}>
                Review & edit the draft profile →
              </button>
              <span className="small muted" style={{ marginLeft: 12 }}>
                Imported into profile — all dashboard pages now use this data.
              </span>
            </div>
          </Card>
        </>
      )}

      {!result && !uploading && !error && (
        <EmptyState icon="📄" title="No resume uploaded yet">
          <p>Upload a resume to see extraction results, confidence and provenance here.</p>
        </EmptyState>
      )}
    </div>
  );
}
