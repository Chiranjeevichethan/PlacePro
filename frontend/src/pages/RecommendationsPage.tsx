import { recommendationsApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { EmptyState, ErrorState } from "../components/ui/StateBox";
import { useApi } from "../hooks/useApi";
import type { RecommendationGroups, RecommendationItem } from "../types";
import { humanize } from "../utils/format";

const GROUP_META: Record<keyof RecommendationGroups, { label: string; tone: "success" | "warning" | "info" | "danger"; icon: string }> = {
  recommended: { label: "Recommended", tone: "success", icon: "⭐" },
  eligible: { label: "Eligible", tone: "info", icon: "✅" },
  incomplete: { label: "Incomplete", tone: "warning", icon: "⚠️" },
  not_recommended: { label: "Not Recommended", tone: "danger", icon: "🚫" },
};

export function RecommendationsPage() {
  return (
    <ProfileGate requireVerified>
      {({ profileId }) => <RecommendationsContent profileId={profileId} />}
    </ProfileGate>
  );
}

function RecommendationsContent({ profileId }: { profileId: string }) {
  const { data, loading, error, refetch } = useApi(() => recommendationsApi.get(profileId));

  return (
    <div className="page">
      <PageHeader
        title="Company Recommendations"
        subtitle={
          <>
            Ranked recommendations for your verified profile, computed
            server-side from five transparent signals (eligibility, skill
            match, readiness, model-estimated probability, completeness).
            Nothing is fabricated — missing data simply lowers the score.
          </>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : loading ? (
        <div className="grid grid-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card"><div className="skeleton" style={{ height: 140 }} /></div>
          ))}
        </div>
      ) : data ? (
        <>
          {(Object.keys(GROUP_META) as Array<keyof RecommendationGroups>).map((group) => {
            const items = data.recommendations[group];
            const meta = GROUP_META[group];
            if (!items.length) return null;
            return (
              <Card key={group} title={`${meta.icon} ${meta.label} (${items.length})`} className="mt-16">
                <div className="grid grid-2">
                  {items.map((r) => (
                    <RecommendationCard key={r.company_id} item={r} />
                  ))}
                </div>
              </Card>
            );
          })}
          {!Object.values(data.recommendations).some((g) => g.length) && (
            <EmptyState icon="🏢" title="No recommendations">
              <p className="small">Verify your profile and complete the ML fields to get recommendations.</p>
            </EmptyState>
          )}
        </>
      ) : null}
    </div>
  );
}

function RecommendationCard({ item }: { item: RecommendationItem }) {
  return (
    <div className="rec-card card" style={{ margin: 0 }}>
      <div className="rec-header">
        <div>
          <div className="rec-company">{item.company_name}</div>
          <div className="rec-meta">Score {item.recommendation_score.toFixed(1)}</div>
        </div>
        <Badge tone={item.status === "RECOMMENDED" ? "success" : item.status === "NOT_RECOMMENDED" ? "danger" : "warning"}>
          {humanize(item.status)}
        </Badge>
      </div>

      <div className="flex flex-wrap">
        <Badge tone={item.eligibility_status === "ELIGIBLE" ? "success" : item.eligibility_status === "NOT_ELIGIBLE" ? "danger" : "warning"}>
          {humanize(item.eligibility_status)}
        </Badge>
        <Badge tone="info">Skill match {item.skill_match?.score?.toFixed(0)}%</Badge>
        <Badge tone="neutral">Readiness {item.readiness_score}</Badge>
        {item.placement_probability != null && (
          <Badge tone="info">ML {Math.round(item.placement_probability * 100)}%</Badge>
        )}
      </div>

      {item.reasons?.length > 0 && (
        <ul className="small mt-8" style={{ margin: 0, paddingLeft: 18 }}>
          {item.reasons.slice(0, 4).map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}

      {item.skill_match && (
        <div className="small">
          <div>
            <span className="muted">Required matched: </span>
            {item.skill_match.required_matched.length
              ? item.skill_match.required_matched.map((s) => <span key={s} className="text-success">{s} </span>)
              : "—"}
          </div>
          {item.skill_match.required_missing.length > 0 && (
            <div>
              <span className="muted">Required missing: </span>
              {item.skill_match.required_missing.map((s) => (
                <span key={s} className="text-warning">{s} </span>
              ))}
            </div>
          )}
        </div>
      )}

      {item.improvement_actions?.length > 0 && (
        <div className="req-row" style={{ background: "var(--info-bg)" }}>
          <div className="req-exp">
            <strong className="text-info">To improve:</strong>{" "}
            {item.improvement_actions.join(" · ")}
          </div>
        </div>
      )}

      {item.missing_information?.length > 0 && (
        <div className="small muted">
          Missing info: {item.missing_information.join(", ")}
        </div>
      )}
    </div>
  );
}
