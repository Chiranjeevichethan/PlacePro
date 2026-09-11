import { useState } from "react";
import StudentForm from "../components/StudentForm";
import RecommendationPanel from "../components/RecommendationPanel";
import { predictPlacement } from "../services/api";

function Prediction() {
  const [prediction, setPrediction] = useState(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [error, setError] = useState(null);

  const handlePrediction = async (formData) => {
    setError(null);
    setPrediction(null);
    setIsPredicting(true);

    try {
      const result = await predictPlacement(formData);
      setPrediction(result);
    } catch (err) {
      setError(
        err?.message ??
          "Something went wrong while generating the prediction. Please try again."
      );
    } finally {
      setIsPredicting(false);
    }
  };

  return (
    <div className="prediction-page">
      {/* =========================================
          PAGE HEADER
          ========================================= */}
      <div className="page-header">
        <h1>Placement Prediction</h1>

        <p>
          Enter the student's information to predict their placement
          probability.
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

        <StudentForm
          onPredict={handlePrediction}
          isSubmitting={isPredicting}
        />
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
      {prediction && !isPredicting && (
        <>
          <div className="prediction-result">
            <h2>Placement Prediction</h2>

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
                  Confidence
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
          <RecommendationPanel
            prediction={prediction}
          />
        </>
      )}
    </div>
  );
}

export default Prediction;
