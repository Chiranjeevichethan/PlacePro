import { useState } from "react";
import { companiesApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Modal } from "../components/ui/Modal";
import { EmptyState, ErrorState, Spinner } from "../components/ui/StateBox";
import { useApi } from "../hooks/useApi";
import type { CompanyEligibilityResponse, CompanyEligibilitySummary } from "../types";
import { humanize } from "../utils/format";

type GroupKey = "eligible" | "not_eligible" | "incomplete";

const GROUP_META: Record<GroupKey, { label: string; tone: "success" | "danger" | "warning"; icon: string }> = {
  eligible: { label: "Eligible", tone: "success", icon: "✅" },
  not_eligible: { label: "Not Eligible", tone: "danger", icon: "⛔" },
  incomplete: { label: "Incomplete", tone: "warning", icon: "⚠️" },
};

export function CompaniesPage() {
  return (
    <ProfileGate requireVerified>
      {({ profileId }) => <CompaniesContent profileId={profileId} />}
    </ProfileGate>
  );
}

function CompaniesContent({ profileId }: { profileId: string }) {
  const { data, loading, error, refetch } = useApi(() => companiesApi.eligibilityAll(profileId));
  const [detail, setDetail] = useState<{ companyId: string; name: string } | null>(null);
  const [detailData, setDetailData] = useState<CompanyEligibilityResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  async function openDetail(summary: CompanyEligibilitySummary) {
    setDetail({ companyId: summary.company.company_id, name: summary.company.company_name });
    setDetailData(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const res = await companiesApi.eligibilityFor(profileId, summary.company.company_id);
      setDetailData(res);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "Could not load company detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Company Eligibility"
        subtitle={
          <>
            Your eligibility for the active demo companies, driven only by each
            company's configured requirements (Phase 13). Missing information is
            <strong> UNKNOWN</strong>, never treated as failure. Requirements are
            sample/demo — not real hiring criteria.
          </>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : loading ? (
        <div className="grid grid-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card"><div className="skeleton" style={{ height: 100 }} /></div>
          ))}
        </div>
      ) : data ? (
        <>
          {(Object.keys(GROUP_META) as GroupKey[]).map((group) => {
            const items = data[group];
            const meta = GROUP_META[group];
            return (
              <Card
                key={group}
                title={`${meta.icon} ${meta.label} (${items.length})`}
                className="mt-16"
              >
                {items.length ? (
                  <div className="grid grid-2">
                    {items.map((summary) => (
                      <CompanyCard key={summary.company.company_id} summary={summary} onDetail={() => void openDetail(summary)} />
                    ))}
                  </div>
                ) : (
                  <EmptyState icon="🗂️" title={`No ${meta.label.toLowerCase()} companies`}>
                    <p className="small">Nothing to show in this group.</p>
                  </EmptyState>
                )}
              </Card>
            );
          })}
        </>
      ) : null}

      <Modal
        open={detail !== null}
        title={detail?.name ?? "Company"}
        onClose={() => setDetail(null)}
      >
        {detailLoading && <Spinner label="Loading requirements…" />}
        {detailError && <div className="notice notice-danger">{detailError}</div>}
        {detailData && (
          <>
            <div className="mb-8">
              <Badge tone={detailData.status === "ELIGIBLE" ? "success" : detailData.status === "NOT_ELIGIBLE" ? "danger" : "warning"}>
                {humanize(detailData.status)}
              </Badge>
            </div>
            {detailData.explanation.map((line, i) => (
              <p key={i} className="small">{line}</p>
            ))}
            <RequirementGroup label="Passed" tone="success" items={detailData.requirements.passed} />
            <RequirementGroup label="Failed" tone="danger" items={detailData.requirements.failed} />
            <RequirementGroup label="Unknown" tone="warning" items={detailData.requirements.unknown} />
          </>
        )}
      </Modal>
    </div>
  );
}

function CompanyCard({
  summary,
  onDetail,
}: {
  summary: CompanyEligibilitySummary;
  onDetail: () => void;
}) {
  const meta = GROUP_META[summary.status as GroupKey] ?? GROUP_META.incomplete;
  return (
    <div className="rec-card card" style={{ margin: 0 }}>
      <div className="rec-header">
        <div>
          <div className="rec-company">{summary.company.company_name}</div>
          <div className="rec-meta">
            {summary.company.industry ?? ""}
            {summary.company.roles?.length ? ` · ${summary.company.roles.join(", ")}` : ""}
          </div>
        </div>
        <Badge tone={meta.tone}>{humanize(summary.status)}</Badge>
      </div>
      <div className="flex flex-wrap">
        <Badge tone="success">{summary.passed_count} passed</Badge>
        <Badge tone="danger">{summary.failed_count} failed</Badge>
        <Badge tone="warning">{summary.unknown_count} unknown</Badge>
      </div>
      {summary.major_reasons?.slice(0, 2).map((r, i) => (
        <p key={i} className="small muted" style={{ marginBottom: 4 }}>{r}</p>
      ))}
      <button className="btn btn-sm" onClick={onDetail}>View requirements</button>
    </div>
  );
}

function RequirementGroup({
  label,
  tone,
  items,
}: {
  label: string;
  tone: "success" | "danger" | "warning";
  items: Array<{ requirement: string; status: string; mandatory: boolean; explanation: string; student_value?: number | string | null; required_value?: number | string | number[] | string[] | null }>;
}) {
  if (!items.length) return null;
  return (
    <div className="mt-16">
      <h4 className="mt-0">
        {label} ({items.length})
      </h4>
      {items.map((r) => (
        <div key={r.requirement} className="req-row">
          <div className="req-head">
            <strong>
              {r.requirement}
              {!r.mandatory && <span className="muted small"> (preferred)</span>}
            </strong>
            <Badge tone={tone}>{r.status}</Badge>
          </div>
          <div className="req-exp">{r.explanation}</div>
        </div>
      ))}
    </div>
  );
}
