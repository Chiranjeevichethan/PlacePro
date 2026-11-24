import { useEffect, useState } from "react";
import ExperimentalV1Form from "../components/ExperimentalV1Form";
import { predictExperimentalV1 } from "../services/api";
import { useStudentProfileContext } from '../hooks/useStudentProfileContext.js';
import { usePredictionResult } from '../hooks/usePredictionResult.js';

function ExperimentalV1Prediction() {
  const { rawProfile, profileId, profileKey, loading, refreshing, error: profileError, refetch } = useStudentProfileContext();
  const [inputRevision, setInputRevision] = useState(0);
  const { result: prediction, busy: isPredicting, error, run } =
    usePredictionResult(profileKey, inputRevision, predictExperimentalV1);
  useEffect(() => {
    if (!profileId) return;
    const refresh = () => { void refetch(profileId); };
    refresh();
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [profileId, refetch]);

  return (
    <div className="prediction-page experimental-v1-page">
      <div className="page-header">
        <h1>Experimental V1 Prediction</h1>
        <p>
          Prefilled from your saved Student Profile. Complete any missing fields below.
        </p>
      </div>

      <div className="prediction-card">
        <h2>Student Information</h2>
        <p className="form-description">
          Enter accurate academic, technical, and personal information.
        </p>
        <p className="form-description" role="note">
          <strong>Experimental V1 — synthetic data only.</strong> Uses 11 supported features;
          DSA, ML Knowledge, System Design, Open Source Contributions and Extracurricular Activities
          are validated but excluded from this model because matching training data is unavailable.
          Results are not validated real-world placement probabilities.
        </p>

        {(loading || refreshing) && <p role="status">Refreshing saved profile...</p>}
        {profileError && <div className="error-banner" role="alert">
          {profileError}
          <button type="button" className="dash-btn secondary" onClick={() => refetch(profileId)}>Retry profile</button>
        </div>}
        <ExperimentalV1Form
          key={profileId || 'empty'}
          profile={rawProfile}
          onValuesChange={() => setInputRevision((previous) => previous + 1)}
          onPredict={run}
          isSubmitting={isPredicting}
        />
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {isPredicting && (
        <div className="prediction-result prediction-loading">
          <div className="spinner" aria-hidden="true"></div>
          <p>Analyzing student profile with Experimental V1...</p>
        </div>
      )}

      {prediction && !isPredicting && (
        <div className="prediction-result">
          <h2>Experimental V1 Result</h2>
          <p>Synthetic model output based on the submitted student profile.</p>

          <div className="result-body">
            <div
              className={`prediction-status ${
                prediction.status === "LIKELY PLACED"
                  ? "status-placed"
                  : "status-risk"
              }`}
            >
              <span className="status-emoji" aria-hidden="true">
                {prediction.status === "LIKELY PLACED" ? "OK" : "RISK"}
              </span>
              {prediction.status}
            </div>

            <div className="prediction-probability">
              <div className="prediction-percentage">
                {prediction.probability}%
              </div>
              <div className="prediction-probability-label">
                Synthetic Model Placement Score
              </div>
            </div>

            <div className="prediction-probability">
              <div className="prediction-percentage">
                {prediction.confidence}%
              </div>
              <div className="prediction-probability-label">
                Model Class Confidence
              </div>
            </div>

            <div className="confidence-track">
              <div
                className={`confidence-fill ${
                  prediction.status === "LIKELY PLACED"
                    ? "confidence-placed"
                    : "confidence-risk"
                }`}
                style={{ width: `${prediction.confidence}%` }}
              />
            </div>

            <p className="prediction-model-note">
              Model: <strong>{prediction.modelVersion}</strong>
            </p>

            <div className="form-description">
              <strong>Experimental model — synthetic dataset</strong>
              <p>{prediction.syntheticDataNotice}</p>
              <p>
                This result is for experimental pipeline evaluation only.
                It is not a validated real-world placement probability.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ExperimentalV1Prediction;
