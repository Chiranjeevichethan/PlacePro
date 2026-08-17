import { useState } from "react";
import { profilesApi } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProfileGate } from "../components/ProfileGate";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { ProgressRing } from "../components/ui/ProgressRing";
import { EmptyState } from "../components/ui/StateBox";
import { useToast } from "../components/ui/Toast";
import { useProfile } from "../context/ProfileContext";
import type { PredictionResponse } from "../types";
import { formatDate, humanize } from "../utils/format";

export function PredictionPage() {
  return (
    <ProfileGate requireVerified>
      {({ profileId }) => <PredictionContent profileId={profileId} />}
    </ProfileGate>
  );
}

function PredictionContent({ profileId }: { profileId: string }) {
  const { profile, refresh } = useProfile();
  const { notify } = useToast();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PredictionResponse | null>(null);

  async function run() {
    setRunning(true);
    try {
      // Always fetch the latest profile state first so we never
      // send stale data to the prediction endpoint.
      await refresh();
      const res = await profilesApi.predict(profileId);
      setResult(res);
      if (!res.ready_for_prediction) {
        notify("Prediction needs more profile fields.", "warning");
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : "Prediction failed.", "error");
    } finally {
      setRunning(false);
    }
  }

  const probability = result?.placement_probability;

  return (
    <div className="page">
      <PageHeader
        title="Placement Prediction"
        subtitle={
          <>
            This is a <strong>model-estimated placement probability</strong> from
            the Phase 8 ML model — an estimate, never a guarantee. It is separate
            from the rule-based readiness score.
          </>
        }
        actions={
          <button className="btn btn-primary" onClick={() => void run()} disabled={running}>
            {running ? "Running model…" : "Run prediction"}
          </button>
        }
      />

      {!profile?.verified && (
        <div className="notice notice-warning mb-16">
          Verify your profile first — predictions require a verified, complete profile.
        </div>
      )}

      {!result && (
        <EmptyState icon="🎯" title="No prediction yet">
          <p>Click “Run prediction” to get the model's placement estimate for your verified profile.</p>
        </EmptyState>
      )}

      {result && !result.ready_for_prediction && (
        <Card>
          <h3>Prediction not available</h3>
          <p className="muted">{result.reason ?? "The profile is missing information the model needs."}</p>
          {result.missing_fields?.length > 0 && (
            <div className="flex flex-wrap">
              {result.missing_fields.map((f) => (
                <span key={f} className="skill-chip">⚠️ {humanize(f)}</span>
              ))}
            </div>
          )}
          <p className="small muted mt-16">
            The model is never called with missing inputs — nothing is invented.
          </p>
        </Card>
      )}

      {result && result.ready_for_prediction && (
        <div className="grid grid-2">
          <Card title="Model Estimate">
            <div className="flex" style={{ gap: 20 }}>
              <ProgressRing
                value={Math.round((probability ?? 0) * 100)}
                caption="probability"
                tone={(probability ?? 0) >= 0.6 ? "success" : "warning"}
              />
              <div className="grow">
                <h4 className="mt-0">
                  <Badge tone={result.prediction === "PLACED" ? "success" : "neutral"}>
                    {result.prediction}
                  </Badge>
                </h4>
                <p className="small muted">
                  Placement probability: <strong>{probability != null ? `${(probability * 100).toFixed(1)}%` : "—"}</strong>
                  <br />
                  Model confidence: {result.confidence != null ? `${(result.confidence * 100).toFixed(1)}%` : "—"}
                  <br />
                  Model version: <code>{result.model_version ?? "—"}</code>
                </p>
              </div>
            </div>
            <div className="notice notice-info mt-16">
              <strong>What this means:</strong> this is the ML model's estimate
              based on the 16 Phase 8 features. It is an estimate — not a
              placement guarantee.
            </div>
          </Card>

          <Card title="Prediction History">
            {profile?.prediction_history?.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Probability</th>
                      <th>Prediction</th>
                      <th>Model</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...profile.prediction_history].reverse().map((h, i) => (
                      <tr key={i}>
                        <td className="muted">{formatDate(h.timestamp)}</td>
                        <td>{(h.placement_probability * 100).toFixed(1)}%</td>
                        <td><Badge tone={h.prediction === "PLACED" ? "success" : "neutral"}>{h.prediction}</Badge></td>
                        <td className="mono small">{h.model_version}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState icon="🕐" title="No prediction history">Run a prediction to see history here.</EmptyState>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
