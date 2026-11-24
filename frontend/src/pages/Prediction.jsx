import StudentForm from "../components/StudentForm";
import RecommendationPanel from "../components/RecommendationPanel";
import ModelExplanation from '../components/ModelExplanation';
import { predictPlacement } from "../services/api";
import { useStudentProfileContext } from "../hooks/useStudentProfileContext";
import { usePredictionResult } from '../hooks/usePredictionResult';

function Prediction({ onNavigate, draft, onDraftChange }) {
  /* The shared profile supplies the prefill (App.jsx merges it into the
     draft) and the student name shown here. */
  const { profile, profileKey, loading, error: profileError } = useStudentProfileContext();
  const { result: prediction, busy: isPredicting, error, run } = usePredictionResult(profileKey, draft, predictPlacement);

  const handlePrediction = async (formData) => {
    if (!loading && !profileError) await run(formData);
  };

  return (
    <div className="prediction-page">
      {/* =========================================
          PAGE HEADER
          ========================================= */}
      <div className="page-header">
        <h1>Placement Prediction</h1>

        <p>
          {profile?.name
            ? `Prefilled from ${profile.name}'s shared Student Profile - complete any missing fields below.`
            : "Enter the student's information to predict their placement probability."}
        </p>
      </div>

      {/* =========================================
          STUDENT FORM
          ========================================= */}
      <div className="prediction-card">
        <h2>Student Information</h2>

        <p className="form-description">
          Enter accurate academic, technical, and personal information.
        </p>

        {loading ? <p>Loading student profile...</p> : profileError ? (
          <p className="error-banner" role="alert">{profileError}</p>
        ) : <StudentForm
          onPredict={handlePrediction}
          isSubmitting={isPredicting}
          draft={draft}
          onDraftChange={onDraftChange}
        />}
      </div>

      {/* =========================================
          ERROR MESSAGE
          ========================================= */}
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {/* =========================================
          LOADING STATE
          ========================================= */}
      {isPredicting && (
        <div className="prediction-result prediction-loading">
          <div
            className="spinner"
            aria-hidden="true"
          ></div>

          <p>Analyzing student profile...</p>
        </div>
      )}

      {/* =========================================
          PREDICTION RESULT
          ========================================= */}
      {prediction && !isPredicting && !loading && !profileError && (
        <>
          <div className="prediction-result">
            <h2>Placement Prediction</h2>
            <p>Based on the submitted form values. Changes to those values require a new prediction.</p>

            <div className="result-body">
              {/* STATUS */}
              <div
                className={`prediction-status ${
                  prediction.status === "LIKELY PLACED"
                    ? "status-placed"
                    : "status-risk"
                }`}
              >
                <span
                  className="status-emoji"
                  aria-hidden="true"
                >
                  {prediction.status === "LIKELY PLACED"
                    ? "OK"
                    : "RISK"}
                </span>

                {prediction.status}
              </div>

              {/* PROBABILITY */}
              <div className="prediction-probability">
                <div className="prediction-percentage">
                  {prediction.probability}%
                </div>

                <div className="prediction-probability-label">
                  Prediction Probability
                </div>
              </div>

              {/* CONFIDENCE */}
              <div className="prediction-probability">
                <div className="prediction-percentage">
                  {prediction.confidence}%
                </div>

                <div className="prediction-probability-label">
                  Model class confidence
                </div>
              </div>

              {/* CONFIDENCE BAR */}
              <div className="confidence-track">
                <div
                  className={`confidence-fill ${
                    prediction.status === "LIKELY PLACED"
                      ? "confidence-placed"
                      : "confidence-risk"
                  }`}
                  style={{
                    width: `${prediction.confidence}%`,
                  }}
                ></div>
              </div>

              {/* MODEL INFORMATION */}
              {prediction.modelVersion && (
                <p className="prediction-model-note">
                  Model: <strong>{prediction.modelVersion}</strong>
                </p>
              )}

              {/* EXISTING RISK RECOMMENDATIONS */}
              {prediction.probability < 50 && (
                <div className="recommendations">
                  <h3>Recommended Improvements</h3>

                  <ul>
                    <li>Improve coding skills</li>
                    <li>Complete more internships</li>
                    <li>Practice DSA and system design</li>
                    <li>Reduce backlogs</li>
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* =========================================
              PLACEPRO INSIGHTS / RECOMMENDATIONS
              ========================================= */}
          <ModelExplanation kind="placement" />
          <RecommendationPanel
            prediction={prediction}
            onNavigate={onNavigate}
          />
        </>
      )}
    </div>
  );
}

export default Prediction;
