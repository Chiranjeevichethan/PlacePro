import { useEffect, useMemo, useState } from "react";
import { profilesApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Card, CardSection } from "../components/ui/Card";
import { Modal } from "../components/ui/Modal";
import { EmptyState } from "../components/ui/StateBox";
import { useToast } from "../components/ui/Toast";
import { useProfile } from "../context/ProfileContext";
import type {
  Achievements,
  CertificationEntry,
  EducationInfo,
  ExperienceEntry,
  InternshipEntry,
  MlInputs,
  PersonalInfo,
  ProjectEntry,
  SkillSet,
  StudentProfile,
} from "../types";
import { humanize } from "../utils/format";

const SKILL_CATEGORIES: Array<keyof SkillSet> = [
  "programming_languages",
  "frameworks",
  "databases",
  "cloud",
  "ai_ml",
  "web_technologies",
  "tools",
  "other_skills",
];

const ML_FIELDS: Array<{ key: keyof MlInputs; label: string; type: "text" | "number" }> = [
  { key: "college_tier", label: "College Tier", type: "text" },
  { key: "backlogs", label: "Backlogs", type: "number" },
  { key: "coding_skills", label: "Coding Skills (0-10)", type: "number" },
  { key: "dsa_score", label: "DSA Score (0-10)", type: "number" },
  { key: "aptitude_score", label: "Aptitude Score (0-100)", type: "number" },
  { key: "communication_skills", label: "Communication Skills (0-10)", type: "number" },
  { key: "ml_knowledge", label: "ML Knowledge (0-10)", type: "number" },
  { key: "system_design", label: "System Design (0-10)", type: "number" },
  { key: "open_source_contributions", label: "Open Source Contributions", type: "number" },
  { key: "extracurriculars", label: "Extracurriculars", type: "number" },
];

function cloneProfile(p: StudentProfile): StudentProfile {
  return JSON.parse(JSON.stringify(p)) as StudentProfile;
}

export function ProfilePage() {
  const { profile, completion, profileId, refresh } = useProfile();
  const [draft, setDraft] = useState<StudentProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ ok: boolean; message: string } | null>(null);
  const { notify } = useToast();

  useEffect(() => {
    if (profile) setDraft(cloneProfile(profile));
  }, [profile]);

  const dirty = useMemo(() => {
    if (!profile || !draft) return false;
    return JSON.stringify(profile) !== JSON.stringify(draft);
  }, [profile, draft]);

  if (!profile || !draft) return null;

  function setSection<K extends keyof StudentProfile>(key: K, value: StudentProfile[K]) {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
  }

  function setPersonal(patch: Partial<PersonalInfo>) {
    setDraft((d) => (d ? { ...d, personal: { ...d.personal, ...patch } } : d));
  }

  function setEducation(patch: Partial<EducationInfo>) {
    setDraft((d) => (d ? { ...d, education: { ...d.education, ...patch } } : d));
  }

  function setMlInput(patch: Partial<MlInputs>) {
    setDraft((d) => (d ? { ...d, ml_inputs: { ...d.ml_inputs, ...patch } } : d));
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    try {
      await profilesApi.update(profileId, draft);
      await refresh();
      notify("Profile saved. Re-confirm to verify it.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Save failed.", "error");
    } finally {
      setSaving(false);
    }
  }

  async function verify() {
    if (!draft) return;
    setVerifying(true);
    try {
      const res = await profilesApi.verify(draft);
      await refresh();
      setVerifyResult({ ok: true, message: res.message });
      notify("Profile verified ✅", "success");
    } catch (err) {
      setVerifyResult({ ok: false, message: err instanceof Error ? err.message : "Verification failed." });
      notify("Verification failed.", "error");
    } finally {
      setVerifying(false);
    }
  }

  const resumePaths = new Set(profile.provenance?.resume ?? []);
  const userPaths = new Set(profile.provenance?.user ?? []);
  const missing = completion?.missing_fields ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Student Profile"
        subtitle="Review the extracted information, edit anything that is wrong, then explicitly verify the profile. Editing resets verification."
        actions={
          profile.verified ? (
            <Badge tone="success">✅ Verified</Badge>
          ) : (
            <Badge tone="warning">Unverified — review & confirm</Badge>
          )
        }
      />

      {/* Verification banner */}
      {!profile.verified && (
        <div className="notice notice-warning mb-16">
          <strong>This profile is not verified.</strong> Readiness, prediction,
          eligibility and assessment features require an explicitly confirmed
          profile. Review the sections below, then use the <em>Verify profile</em> button.
        </div>
      )}
      {profile.verified && (
        <div className="notice notice-success mb-16">
          <strong>Verified.</strong> Readiness, prediction, eligibility and
          assessment features are unlocked. Any edit will reset verification.
        </div>
      )}

      {/* Personal */}
      <Card title="Personal Information">
        <div className="grid grid-3">
          <StringField label="Full name" value={draft.personal.name} onChange={(v) => setPersonal({ name: v })} required />
          <StringField label="Email" value={draft.personal.email} onChange={(v) => setPersonal({ email: v })} required />
          <StringField label="Phone" value={draft.personal.phone} onChange={(v) => setPersonal({ phone: v })} />
          <StringField label="Location" value={draft.personal.location} onChange={(v) => setPersonal({ location: v })} />
          <StringField label="LinkedIn" value={draft.personal.linkedin} onChange={(v) => setPersonal({ linkedin: v })} />
          <StringField label="GitHub" value={draft.personal.github} onChange={(v) => setPersonal({ github: v })} />
          <StringField label="Portfolio" value={draft.personal.portfolio} onChange={(v) => setPersonal({ portfolio: v })} />
        </div>
      </Card>

      {/* Education */}
      <Card title="Education">
        <div className="grid grid-3">
          <StringField label="Degree" value={draft.education.degree} onChange={(v) => setEducation({ degree: v })} />
          <StringField label="Branch" value={draft.education.branch} onChange={(v) => setEducation({ branch: v })} />
          <StringField label="College" value={draft.education.college} onChange={(v) => setEducation({ college: v })} />
          <NumberField label="CGPA" value={draft.education.cgpa} onChange={(v) => setEducation({ cgpa: v })} step={0.1} />
          <NumberField label="Graduation year" value={draft.education.graduation_year} onChange={(v) => setEducation({ graduation_year: v })} />
        </div>
      </Card>

      {/* Skills */}
      <Card title="Skills">
        <div className="grid grid-2">
          {SKILL_CATEGORIES.map((cat) => (
            <SkillListEditor
              key={cat}
              label={humanize(cat)}
              values={draft.skills[cat]}
              onChange={(values) => setSection("skills", { ...draft.skills, [cat]: values })}
            />
          ))}
        </div>
        <CardSection>
          <p className="small muted">
            Resume-extracted skills carry the 🧾 resume badge; skills you add
            are user-entered. A mention is not a score — verified assessment
            scores live on the Skills page.
          </p>
        </CardSection>
      </Card>

      {/* Experience */}
      <Card title="Experience">
        <EntriesEditor<ExperienceEntry>
          entries={draft.experience}
          empty={{ company: "", role: "", duration: "", technologies: [] }}
          onChange={(entries) => setSection("experience", entries)}
          fields={[
            { key: "company", label: "Company" },
            { key: "role", label: "Role" },
            { key: "duration", label: "Duration" },
          ]}
        />
      </Card>

      {/* Internships */}
      <Card title="Internships">
        <EntriesEditor<InternshipEntry>
          entries={draft.internships}
          empty={{ company: "", role: "", duration: "", technologies: [] }}
          onChange={(entries) => setSection("internships", entries)}
          fields={[
            { key: "company", label: "Company" },
            { key: "role", label: "Role" },
            { key: "duration", label: "Duration" },
          ]}
        />
      </Card>

      {/* Projects */}
      <Card title="Projects">
        <EntriesEditor<ProjectEntry>
          entries={draft.projects}
          empty={{ project_name: "", description: "", technologies: [] }}
          onChange={(entries) => setSection("projects", entries)}
          fields={[
            { key: "project_name", label: "Project name" },
            { key: "description", label: "Description" },
          ]}
        />
      </Card>

      {/* Certifications */}
      <Card title="Certifications">
        <EntriesEditor<CertificationEntry>
          entries={draft.certifications}
          empty={{ name: "", issuer: "", year: undefined }}
          onChange={(entries) => setSection("certifications", entries)}
          fields={[
            { key: "name", label: "Name" },
            { key: "issuer", label: "Issuer" },
            { key: "year", label: "Year", type: "number" },
          ]}
        />
      </Card>

      {/* Achievements */}
      <Card title="Achievements">
        <div className="grid grid-3">
          {(["hackathons", "awards", "coding_achievements"] as Array<keyof Achievements>).map((key) => (
            <SimpleListEditor
              key={key}
              label={humanize(key)}
              values={draft.achievements[key]}
              onChange={(values) =>
                setSection("achievements", { ...draft.achievements, [key]: values })
              }
            />
          ))}
        </div>
      </Card>

      {/* ML inputs */}
      <Card title="ML Input Fields (manual entry)">
        <p className="small muted">
          These Phase 8 model features cannot be read from a resume. They are
          entered manually and mapped to the model — nothing is invented.
        </p>
        <div className="grid grid-3">
          {ML_FIELDS.map(({ key, label, type }) =>
            type === "text" ? (
              <StringField
                key={key}
                label={label}
                value={draft.ml_inputs[key] as string | null | undefined}
                onChange={(v) => setMlInput({ [key]: v } as Partial<MlInputs>)}
              />
            ) : (
              <NumberField
                key={key}
                label={label}
                value={draft.ml_inputs[key] as number | null | undefined}
                onChange={(v) => setMlInput({ [key]: v } as Partial<MlInputs>)}
              />
            ),
          )}
        </div>
        {missing.length > 0 && (
          <div className="notice notice-warning mt-16">
            <strong>Missing for prediction:</strong>{" "}
            {missing.map((m) => humanize(m)).join(", ")}
          </div>
        )}
      </Card>

      {/* Provenance */}
      <Card title="Field Provenance">
        <div className="grid grid-2">
          <div>
            <h4 className="mt-0">🧾 From resume ({resumePaths.size})</h4>
            {resumePaths.size ? (
              <div className="flex flex-wrap">
                {[...resumePaths].sort().map((p) => (
                  <span key={p} className="skill-chip">{p}</span>
                ))}
              </div>
            ) : (
              <p className="muted small">No resume-derived fields.</p>
            )}
          </div>
          <div>
            <h4 className="mt-0">✏️ User-edited ({userPaths.size})</h4>
            {userPaths.size ? (
              <div className="flex flex-wrap">
                {[...userPaths].sort().map((p) => (
                  <span key={p} className="skill-chip">{p}</span>
                ))}
              </div>
            ) : (
              <p className="muted small">No user-edited fields.</p>
            )}
          </div>
        </div>
      </Card>

      {/* Actions */}
      <div className="form-actions">
        <button className="btn btn-primary" onClick={() => void save()} disabled={saving || !dirty}>
          {saving ? "Saving…" : dirty ? "Save changes" : "No changes"}
        </button>
        <button className="btn" onClick={() => setVerifyOpen(true)} disabled={saving}>
          Verify profile
        </button>
      </div>

      {/* Verification modal */}
      <Modal
        open={verifyOpen}
        title="Verify your profile"
        onClose={() => {
          setVerifyOpen(false);
          setVerifyResult(null);
        }}
        footer={
          verifyResult ? (
            <button className="btn" onClick={() => { setVerifyOpen(false); setVerifyResult(null); }}>
              Close
            </button>
          ) : (
            <>
              <button className="btn" onClick={() => setVerifyOpen(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={() => void verify()} disabled={verifying}>
                {verifying ? "Verifying…" : "Confirm & verify"}
              </button>
            </>
          )
        }
      >
        {verifyResult ? (
          <div className={`notice ${verifyResult.ok ? "notice-success" : "notice-danger"}`}>
            {verifyResult.message}
          </div>
        ) : (
          <>
            <p>
              Verifying makes the reviewed information the <strong>verified</strong>{" "}
              baseline used by readiness, prediction, eligibility and assessments.
            </p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              <li>Name and email are required (both present: {draft.personal.name ? "✅" : "❌"} / {draft.personal.email ? "✅" : "❌"}).</li>
              <li>
                {missing.length === 0
                  ? "✅ All ML-required fields are available — prediction will work."
                  : `⚠️ ${missing.length} ML-required field(s) still missing — prediction will be blocked until filled.`}
              </li>
              <li>Editing this profile later resets verification.</li>
            </ul>
          </>
        )}
      </Modal>
    </div>
  );
}

// ---------- Field editors ----------

function StringField({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value?: string | null;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <div className="field">
      <label>
        {label}
        {required && <span className="text-danger"> *</span>}
      </label>
      <input
        className="input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={required ? "Required to verify" : ""}
      />
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step,
}: {
  label: string;
  value?: number | null;
  onChange: (v: number | null) => void;
  step?: number;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        className="input"
        type="number"
        step={step}
        value={value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          onChange(raw === "" ? null : Number(raw));
        }}
      />
    </div>
  );
}

function SkillListEditor({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [text, setText] = useState("");

  function add() {
    const v = text.trim();
    if (!v) return;
    if (!values.includes(v)) onChange([...values, v]);
    setText("");
  }

  return (
    <div className="field">
      <label>{label}</label>
      <div className="flex">
        <input
          className="input grow"
          value={text}
          placeholder={`Add ${label.toLowerCase()}…`}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <button className="btn btn-sm" onClick={add}>Add</button>
      </div>
      <div className="flex flex-wrap mt-8">
        {values.map((v) => (
          <span key={v} className="skill-chip">
            {v}
            <button
              className="btn-ghost"
              style={{ border: "none", background: "none", cursor: "pointer", padding: 0, fontSize: 12 }}
              aria-label={`Remove ${v}`}
              onClick={() => onChange(values.filter((x) => x !== v))}
            >
              ✕
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

function SimpleListEditor({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [text, setText] = useState("");

  function add() {
    const v = text.trim();
    if (!v) return;
    if (!values.includes(v)) onChange([...values, v]);
    setText("");
  }

  return (
    <div className="field">
      <label>{label} ({values.length})</label>
      <div className="flex">
        <input className="input grow" value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <button className="btn btn-sm" onClick={add}>Add</button>
      </div>
      <ul style={{ margin: "8px 0 0", paddingLeft: 18 }} className="small">
        {values.map((v, i) => (
          <li key={v}>
            {v}{" "}
            <button
              className="btn-ghost"
              style={{ border: "none", background: "none", cursor: "pointer", padding: 0, color: "var(--danger)" }}
              onClick={() => onChange(values.filter((_, j) => j !== i))}
            >
              remove
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface EntryField {
  key: string;
  label: string;
  type?: "text" | "number";
}

function EntriesEditor<T extends object>({
  entries,
  empty,
  onChange,
  fields,
}: {
  entries: T[];
  empty: T;
  onChange: (entries: T[]) => void;
  fields: EntryField[];
}) {
  return (
    <div>
      {entries.length === 0 && (
        <EmptyState icon="➕" title="Nothing here yet">
          <p className="small">Add an entry below.</p>
        </EmptyState>
      )}
      {entries.map((entry, i) => (
        <div key={i} className="card-section" style={{ borderTop: i === 0 ? "none" : undefined, paddingTop: i === 0 ? 0 : undefined }}>
          <div className="grid grid-3">
            {fields.map((f) => (
              <div className="field" key={f.key}>
                <label>{f.label}</label>
                <input
                  className="input"
                  type={f.type ?? "text"}
                  value={(entry as Record<string, unknown>)[f.key] as string | number | undefined ?? ""}
                  onChange={(e) => {
                    const next = [...entries];
                    const value =
                      f.type === "number" && e.target.value !== ""
                        ? Number(e.target.value)
                        : e.target.value;
                    next[i] = { ...entry, [f.key]: value };
                    onChange(next);
                  }}
                />
              </div>
            ))}
          </div>
          <button
            className="btn btn-sm btn-danger"
            onClick={() => onChange(entries.filter((_, j) => j !== i))}
          >
            Remove
          </button>
        </div>
      ))}
      <button className="btn btn-sm mt-8" onClick={() => onChange([...entries, { ...empty }])}>
        + Add entry
      </button>
    </div>
  );
}
