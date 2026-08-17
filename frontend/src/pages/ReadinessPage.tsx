import { readinessApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { ProgressBar, ProgressRing } from "../components/ui";
import { EmptyState, ErrorState } from "../components/ui/StateBox";
import { useApi } from "../hooks/useApi";
import { humanize } from "../utils/format";

const BREAKDOWN_LABELS: Record<string, string> = {
  technical_skills: "Technical skills",
  projects: "Projects",
  internships: "Internships",
  certifications: "Certifications",
  communication: "Communication",
  profile_completeness: "Profile completeness",
};

export function ReadinessPage() {
  return (
    <ProfileGate requireVerified>
      {({ profileId }) => <ReadinessContent profileId={profileId} />}
    </ProfileGate>
  );
}

function ReadinessContent({ profileId }: { profileId: string }) {
  const { data, loading, error, refetch } = useApi(() => readinessApi.get(profileId));

  return (
    <div className="page">
      <PageHeader
        title="Placement Readiness"
        subtitle={
          <>
            A transparent, rule-based readiness score (0–100) built from verified
            profile information. <strong>Readiness score ≠ ML placement probability</strong>{" "}
            — they measure different things and are never merged.
          </>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : loading ? (
        <div className="grid grid-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card"><div className="skeleton" style={{ height: 120 }} /></div>
          ))}
        </div>
      ) : data ? (
        <>
          <div className="grid grid-3">
            <Card title="Readiness Score">
              <div className="flex" style={{ gap: 18 }}>
                <ProgressRing
                  value={data.readiness_score}
                  caption={data.readiness_level}
                  tone={data.readiness_score >= 60 ? "success" : data.readiness_score >= 40 ? "warning" : "danger"}
                />
                <div className="grow">
                  <h4 className="mt-0">Level</h4>
                  <Badge tone={data.readiness_score >= 60 ? "success" : data.readiness_score >= 40 ? "warning" : "danger"}>
                    {data.readiness_level}
                  </Badge>
                  <p className="small muted mt-8">
                    Profile completeness: {data.profile_completeness.percentage}%
                  </p>
                  {data.profile_completeness.missing_fields.length > 0 && (
                    <p className="small muted">
                      Missing sections: {data.profile_completeness.missing_fields.map(humanize).join(", ")}
                    </p>
                  )}
                </div>
              </div>
            </Card>

            <Card title="Score Breakdown">
              {Object.entries(data.readiness_breakdown).map(([key, value]) => (
                <div className="breakdown-row" key={key}>
                  <div className="bd-head">
                    <span className="bd-label">{BREAKDOWN_LABELS[key] ?? humanize(key)}</span>
                    <span className="bd-value">{value}</span>
                  </div>
                  <ProgressBar value={(value / 30) * 100} tone={value > 0 ? "success" : "neutral"} />
                </div>
              ))}
            </Card>

            <Card title="Strengths">
              {data.strengths.length ? (
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {data.strengths.map((s) => (
                    <li key={s.skill} style={{ marginBottom: 10 }}>
                      <strong>{s.skill}</strong>
                      <div className="small muted">{s.evidence.join(" · ")}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon="💪" title="No strengths yet">
                  <p className="small">Skills need evidence from 2+ sources (projects, internships, resume…) to count as strengths.</p>
                </EmptyState>
              )}
            </Card>
          </div>

          <Card title="Skill Gaps" className="mt-16">
            <p className="small muted">
              A gap means a defined placement requirement was <em>not found in the
              verified profile</em> — it never claims you don't know the skill.
            </p>
            {data.skill_gaps.length ? (
              <div className="grid grid-2">
                {data.skill_gaps.map((g) => (
                  <div key={g.skill} className="req-row">
                    <div className="req-head">
                      <strong>{g.skill}</strong>
                      <Badge tone={g.priority === "HIGH" ? "danger" : g.priority === "MEDIUM" ? "warning" : "neutral"}>
                        {g.priority} priority
                      </Badge>
                    </div>
                    <div className="req-exp">{g.reason}</div>
                    {g.action && <div className="req-exp">→ {g.action}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState icon="🎉" title="No skill gaps">All placement requirements are present.</EmptyState>
            )}
          </Card>

        </>
      ) : null}
    </div>
  );
}
