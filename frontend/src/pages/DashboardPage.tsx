import { Link } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { ProgressBar, ProgressRing } from "../components/ui";
import { EmptyState, ErrorState, SkeletonCard } from "../components/ui/StateBox";
import { StatCard } from "../components/ui/StatCard";
import { useProfile } from "../context/ProfileContext";
import { useApi } from "../hooks/useApi";
import {
  assessmentApi,
  companiesApi,
  readinessApi,
  recommendationsApi,
} from "../api";
import { ASSESSMENT_SKILLS } from "../config/demo";
import { humanize, score } from "../utils/format";

export function DashboardPage() {
  return (
    <ProfileGate>
      {({ profileId }) => <DashboardContent profileId={profileId} />}
    </ProfileGate>
  );
}

function DashboardContent({ profileId }: { profileId: string }) {
  const { profile, completion } = useProfile();
  const summary = useApi(() => readinessApi.placementSummary(profileId));
  const skills = useApi(() => assessmentApi.skills(profileId));
  const assessments = useApi(() => assessmentApi.history(profileId));
  const eligibility = useApi(() => companiesApi.eligibilityAll(profileId));
  const recommendations = useApi(() => recommendationsApi.get(profileId, 4));

  const anyLoading =
    summary.loading || skills.loading || assessments.loading ||
    eligibility.loading || recommendations.loading;
  const anyError =
    summary.error || skills.error || assessments.error ||
    eligibility.error || recommendations.error;

  const profilePct = completion?.profile_complete
    ? 100
    : completion?.missing_fields?.length
      ? 100 - Math.round((completion.missing_fields.length / 16) * 100)
      : 0;

  // Override with canonical readiness completeness when available
  const completenessPct = summary.data?.readiness_breakdown
    ? Math.round(
        (summary.data.readiness_breakdown.profile_completeness / 20) * 100,
      )
    : profilePct;

  const assessedSkills =
    skills.data?.skills.filter((s) => s.assessment_score != null) ?? [];
  const assessmentProgress = Math.round(
    (assessedSkills.length / ASSESSMENT_SKILLS.length) * 100,
  );

  const allRecs = recommendations.data
    ? [
        ...recommendations.data.recommendations.recommended,
        ...recommendations.data.recommendations.eligible,
        ...recommendations.data.recommendations.incomplete,
        ...recommendations.data.recommendations.not_recommended,
      ]
    : [];

  const improvementActions =
    summary.data?.improvement_plan?.slice(0, 4) ?? [];

  return (
    <div className="page">
      <PageHeader
        title={`Welcome${profile?.personal?.name ? `, ${profile.personal.name.split(" ")[0]}` : ""} 👋`}
        subtitle="Your placement readiness at a glance — model estimate, readiness, skills and recommended companies."
        actions={
          profile?.verified ? (
            <Badge tone="success">✅ Verified profile</Badge>
          ) : (
            <Badge tone="warning">Unverified profile</Badge>
          )
        }
      />

      {anyError ? (
        <ErrorState
          error={anyError}
          onRetry={() => {
            summary.refetch();
            skills.refetch();
            assessments.refetch();
            eligibility.refetch();
            recommendations.refetch();
          }}
        />
      ) : anyLoading ? (
        <div className="grid grid-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} lines={2} />
          ))}
        </div>
      ) : (
        <>
          {/* Top stats */}
          <div className="grid grid-4 mb-16">
            <StatCard
              label="Profile Completion"
              value={`${completenessPct}%`}
              sub={completion?.missing_fields?.length
                ? `${completion.missing_fields.length} field(s) still missing`
                : "All ML fields available"}
            >
              <ProgressBar value={completenessPct} tone={completenessPct >= 80 ? "success" : "warning"} />
            </StatCard>

            <StatCard
              label="Placement Probability"
              value={
                summary.data?.placement_probability != null
                  ? `${Math.round(summary.data.placement_probability * 100)}%`
                  : "—"
              }
              sub={
                summary.data?.prediction
                  ? `Model estimate: ${summary.data.prediction}`
                  : "Model not run — complete the profile"
              }
            />

            <StatCard
              label="Readiness Score"
              value={score(summary.data?.readiness_score)}
              sub={summary.data?.readiness_level ?? "—"}
            >
              <ProgressBar
                value={summary.data?.readiness_score ?? 0}
                tone={readinessTone(summary.data?.readiness_score ?? 0)}
              />
            </StatCard>

            <StatCard
              label="Assessment Progress"
              value={`${assessedSkills.length}/${ASSESSMENT_SKILLS.length}`}
              sub="skills assessed"
            >
              <ProgressBar value={assessmentProgress} />
            </StatCard>
          </div>

          <div className="grid grid-2">
            {/* Readiness ring */}
            <Card title="Readiness">
              <div className="flex" style={{ gap: 18 }}>
                <ProgressRing
                  value={summary.data?.readiness_score ?? 0}
                  caption={summary.data?.readiness_level ?? "score"}
                  tone={readinessTone(summary.data?.readiness_score ?? 0)}
                />
                <div className="grow">
                  <h4 className="mt-0">Strengths</h4>
                  {summary.data?.strengths?.length ? (
                    <ul className="mt-0" style={{ marginLeft: 18, paddingLeft: 4 }}>
                      {summary.data.strengths.slice(0, 4).map((s) => (
                        <li key={s.skill} className="small">
                          <strong>{s.skill}</strong>{" "}
                          <span className="muted">({s.evidence.join(", ")})</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted small">No multi-source strengths yet.</p>
                  )}
                  <Link to="/readiness" className="small">View full analysis →</Link>
                </div>
              </div>
            </Card>

            {/* Skill gaps preview */}
            <Card title="Skill Gaps" actions={<Link className="btn btn-sm btn-ghost" to="/readiness">View all</Link>}>
              {summary.data?.skill_gaps?.length ? (
                <ul className="mt-0" style={{ marginLeft: 18, paddingLeft: 4 }}>
                  {summary.data.skill_gaps.slice(0, 5).map((g) => (
                    <li key={g.skill} className="small" style={{ marginBottom: 6 }}>
                      <strong>{g.skill}</strong>{" "}
                      <Badge tone={g.priority === "HIGH" ? "danger" : g.priority === "MEDIUM" ? "warning" : "neutral"}>
                        {g.priority}
                      </Badge>
                      <div className="muted">{g.reason}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon="🎉" title="No skill gaps">No missing placement skills.</EmptyState>
              )}
            </Card>

            {/* Recommended companies */}
            <Card title="Recommended Companies" actions={<Link className="btn btn-sm btn-ghost" to="/recommendations">All →</Link>}>
              {allRecs.length ? (
                <div className="flex flex-wrap">
                  {allRecs.slice(0, 4).map((r) => (
                    <div key={r.company_id} className="rec-card card" style={{ flex: "1 1 220px", margin: 0 }}>
                      <div className="rec-header">
                        <span className="rec-company">{r.company_name}</span>
                        <Badge tone={r.status === "RECOMMENDED" ? "success" : r.status === "NOT_RECOMMENDED" ? "danger" : "warning"}>
                          {humanize(r.status)}
                        </Badge>
                      </div>
                      <div className="rec-meta">
                        Score {r.recommendation_score?.toFixed(1)} · Skill match{" "}
                        {r.skill_match?.score?.toFixed(0)}%
                        {r.placement_probability != null &&
                          ` · ML ${Math.round(r.placement_probability * 100)}%`}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState icon="🏢" title="No recommendations yet">Complete and verify your profile first.</EmptyState>
              )}
            </Card>

            {/* Improvement actions */}
            <Card title="Top Improvement Actions" actions={<Link className="btn btn-sm btn-ghost" to="/improvement-plan">Full plan →</Link>}>
              {improvementActions.length ? (
                <ol className="mt-0" style={{ marginLeft: 18, paddingLeft: 4 }}>
                  {improvementActions.map((item) => (
                    <li key={item.priority} className="small" style={{ marginBottom: 8 }}>
                      <strong>{item.skill}</strong> — {item.action}
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyState icon="🛠️" title="Nothing to improve">Your plan is clear. 🎉</EmptyState>
              )}
            </Card>
          </div>

        </>
      )}
    </div>
  );
}

function readinessTone(v: number): "success" | "warning" | "danger" {
  if (v >= 60) return "success";
  if (v >= 40) return "warning";
  return "danger";
}
