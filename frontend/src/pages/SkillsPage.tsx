import { assessmentApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { ProgressBar } from "../components/ui/ProgressBar";
import { EmptyState, ErrorState } from "../components/ui/StateBox";
import { Tooltip } from "../components/ui/Tooltip";
import { useApi } from "../hooks/useApi";
import type { SkillViewEntry } from "../types";

export function SkillsPage() {
  return (
    <ProfileGate>
      {({ profileId }) => <SkillsContent profileId={profileId} />}
    </ProfileGate>
  );
}

function SkillsContent({ profileId }: { profileId: string }) {
  const { data, loading, error, refetch } = useApi(() => assessmentApi.skills(profileId));

  const assessed = data?.skills.filter((s) => s.assessment_score != null) ?? [];
  const unassessed = data?.skills.filter((s) => s.assessment_score == null) ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Verified Skills"
        subtitle={
          <>
            The combined skill view: <strong>resume evidence</strong> (a mention,
            not a score) and <strong>assessment evidence</strong> (a real,
            server-scored result) side by side. Only assessment evidence is
            marked verified.
          </>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : loading ? (
        <div className="grid grid-2">
          <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
        </div>
      ) : data ? (
        <>
          <Card title={`Assessed Skills (${assessed.length})`}>
            {assessed.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Skill</th>
                      <th>Score</th>
                      <th>Level</th>
                      <th>Source</th>
                      <th>Verification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assessed.map((s) => (
                      <SkillRow key={s.skill} s={s} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState icon="📝" title="No assessed skills">
                <p className="small">Take an assessment on the Assessment page to get a real, verified skill score.</p>
              </EmptyState>
            )}
          </Card>

          <Card title={`Skills from profile mentions (${unassessed.length})`} className="mt-16">
            <p className="small muted">
              These skills appear in your verified profile (resume or user
              entry) but have <strong>no assessment score</strong> — a mention
              is evidence of presence, not a numeric skill level.
            </p>
            {unassessed.length ? (
              <div className="flex flex-wrap">
                {unassessed.map((s) => (
                  <span key={s.skill} className="skill-chip">
                    <span
                      className="dot"
                      style={{ background: s.resume_detected ? "var(--info)" : "var(--neutral)" }}
                    />
                    {s.skill}
                    {s.resume_detected && <Tooltip text="Detected from your resume">🧾</Tooltip>}
                    {s.user_entered && <Tooltip text="Entered by you">✏️</Tooltip>}
                  </span>
                ))}
              </div>
            ) : (
              <EmptyState icon="🧩" title="No skills in profile">
                <p className="small">Add skills in the Profile page.</p>
              </EmptyState>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}

function SkillRow({ s }: { s: SkillViewEntry }) {
  return (
    <tr>
      <td>
        <strong>{s.skill}</strong>
        <div className="small muted">
          {s.resume_detected && <span>🧾 resume · </span>}
          {s.user_entered && <span>✏️ user · </span>}
          {!s.resume_detected && !s.user_entered && <span>assessment only</span>}
        </div>
      </td>
      <td style={{ minWidth: 140 }}>
        <div className="flex">
          <div className="grow">
            <ProgressBar value={s.assessment_score ?? 0} tone={(s.assessment_score ?? 0) >= 60 ? "success" : "warning"} />
          </div>
          <span className="small" style={{ minWidth: 42, textAlign: "right" }}>
            {s.assessment_score?.toFixed(0)}
          </span>
        </div>
      </td>
      <td>
        {s.level ? (
          <Badge tone={(s.assessment_score ?? 0) >= 60 ? "success" : "warning"}>{s.level}</Badge>
        ) : (
          <span className="muted small">—</span>
        )}
      </td>
      <td>
        {s.assessment_verified ? (
          <Badge tone="info">assessment</Badge>
        ) : (
          <Badge tone="neutral">{s.resume_detected ? "resume" : "user"}</Badge>
        )}
      </td>
      <td>
        {s.assessment_verified ? (
          <Badge tone="success">verified ✓</Badge>
        ) : (
          <Badge tone="neutral">not verified</Badge>
        )}
      </td>
    </tr>
  );
}
