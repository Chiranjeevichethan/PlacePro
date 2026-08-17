import { Link } from "react-router-dom";
import { assessmentApi, readinessApi, recommendationsApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { EmptyState, ErrorState } from "../components/ui/StateBox";
import { useApi } from "../hooks/useApi";
import { ASSESSMENT_SKILLS } from "../config/demo";

interface PlanItem {
  category: string;
  icon: string;
  title: string;
  detail: string;
  priority: number;
  source: string;
}

export function ImprovementPlanPage() {
  return (
    <ProfileGate requireVerified>
      {({ profileId }) => <ImprovementPlanContent profileId={profileId} />}
    </ProfileGate>
  );
}

function ImprovementPlanContent({ profileId }: { profileId: string }) {
  const readiness = useApi(() => readinessApi.get(profileId));
  const skills = useApi(() => assessmentApi.skills(profileId));
  const recommendations = useApi(() => recommendationsApi.get(profileId));

  if (readiness.error) {
    return (
      <div className="page">
        <PageHeader title="Improvement Plan" />
        <ErrorState error={readiness.error} onRetry={readiness.refetch} />
      </div>
    );
  }

  const loading = readiness.loading || skills.loading || recommendations.loading;

  const items: PlanItem[] = [];

  if (!loading) {
    const gaps = readiness.data?.skill_gaps ?? [];
    const assessed = new Set(
      (skills.data?.skills ?? [])
        .filter((s) => s.assessment_score != null)
        .map((s) => s.skill),
    );
    const plan = readiness.data?.improvement_plan ?? [];
    const completeness = readiness.data?.profile_completeness;

    // 1. Complete assessment (skills that can be assessed but have no score)
    for (const skill of ASSESSMENT_SKILLS) {
      if (!assessed.has(skill)) {
        items.push({
          category: "Complete assessment",
          icon: "📝",
          title: `Take the ${skill} assessment`,
          detail: "A verified assessment score strengthens your technical evidence and satisfies company skill requirements.",
          priority: gaps.some((g) => g.skill === skill) ? 1 : 3,
          source: "assessment",
        });
      }
    }

    // 2. Improve technical skill (from readiness skill gaps)
    for (const gap of gaps) {
      items.push({
        category: "Improve technical skill",
        icon: "🧠",
        title: gap.skill,
        detail: gap.action || gap.reason,
        priority: gap.priority === "HIGH" ? 1 : gap.priority === "MEDIUM" ? 2 : 3,
        source: "readiness",
      });
    }

    // 3. Readiness improvement plan entries (dedupe against gaps)
    const gapSkills = new Set(gaps.map((g) => g.skill));
    for (const item of plan) {
      if (gapSkills.has(item.skill)) continue;
      items.push({
        category: "Improvement action",
        icon: "🛠️",
        title: item.skill,
        detail: item.action,
        priority: item.priority,
        source: "readiness",
      });
    }

    // 4. Profile completeness
    if (completeness && completeness.percentage < 100) {
      items.push({
        category: "Improve profile completeness",
        icon: "📋",
        title: `Complete profile sections (${completeness.percentage}%)`,
        detail: completeness.missing_fields.length
          ? `Missing sections: ${completeness.missing_fields.join(", ")}`
          : "Add the remaining profile sections.",
        priority: 2,
        source: "readiness",
      });
    }

    // 5. Recommendation improvement actions
    const allRecs = [
      ...(recommendations.data?.recommendations.recommended ?? []),
      ...(recommendations.data?.recommendations.eligible ?? []),
      ...(recommendations.data?.recommendations.incomplete ?? []),
      ...(recommendations.data?.recommendations.not_recommended ?? []),
    ];
    for (const rec of allRecs) {
      for (const action of rec.improvement_actions ?? []) {
        items.push({
          category: "Company requirement",
          icon: "🏢",
          title: `${rec.company_name}: ${action}`,
          detail: action,
          priority: 2,
          source: "recommendation",
        });
      }
    }

    items.sort((a, b) => a.priority - b.priority || a.title.localeCompare(b.title));
  }

  const categories = [...new Set(items.map((i) => i.category))];

  return (
    <div className="page">
      <PageHeader
        title="Improvement Plan"
        subtitle="A prioritized action list built from your readiness skill gaps, assessment status, profile completeness and company recommendations. Priorities: 1 = do first."
      />

      {loading ? (
        <div className="grid grid-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card"><div className="skeleton" style={{ height: 90 }} /></div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon="🎉" title="You're all set!">
          <p>No improvement actions found — every placement requirement is present and assessed.</p>
        </EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap mb-16">
            {categories.map((c) => (
              <span key={c} className="skill-chip">{c}</span>
            ))}
          </div>

          <div className="grid grid-2">
            {items.map((item, i) => (
              <Card key={i} className="rec-card" title={
                <span className="flex" style={{ gap: 8 }}>
                  <span>{item.icon}</span>
                  {item.title}
                </span>
              }>
                <div className="flex flex-wrap">
                  <Badge tone="info">{item.category}</Badge>
                  <Badge tone={item.priority === 1 ? "danger" : item.priority === 2 ? "warning" : "neutral"}>
                    Priority {item.priority}
                  </Badge>
                </div>
                <p className="small muted mt-8">{item.detail}</p>
              </Card>
            ))}
          </div>

          <div className="notice notice-info mt-16">
            <strong>Sources:</strong> readiness skill-gap analysis, Phase 17
            assessment coverage, and Phase 14 recommendation improvement
            actions. Every item traces back to server-computed data.
          </div>

          <div className="form-actions">
            <Link className="btn" to="/readiness">Readiness analysis</Link>
            <Link className="btn" to="/assessment">Take an assessment</Link>
            <Link className="btn" to="/profile">Edit profile</Link>
          </div>
        </>
      )}
    </div>
  );
}
