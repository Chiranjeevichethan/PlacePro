# PlacePro — Phase 11: Verified Profile → Placement Prediction

Date: August 2026
Branch: `phase11-resume-prediction-integration`

## 1. Goal

Connect the **verified student profile** (Phase 10) to the existing
**Phase 8 prediction pipeline**. The final model
(`models/placepro_final_model.pkl`) and `src/pipeline.py` are used as-is —
no second model, no retraining, no duplicated feature engineering, no change
to the meaning of the ML features.

```
Resume
  ↓  Phase 9 extraction
Extracted profile
  ↓  Phase 10 verification
Verified profile            ← required (verified == true)
  ↓  Phase 10 ML feature mapping
Completeness check          ← all 16 features present?
  ├─ incomplete → missing_fields returned (nothing invented)
  └─ complete   → src.pipeline.predict_placement()
                    ↓
            placement_probability / PLACED | NOT PLACED / confidence
                    ↓
            recorded in profile.prediction_history
```

## 2. Prediction flow (`POST /api/profile/{profile_id}/predict`)

1. Load profile — unknown / invalid id → `404`.
2. **Verification requirement** — if `verified != true`, the model is NOT
   called:

   ```json
   { "ready_for_prediction": false, "prediction": null,
     "placement_probability": null, "confidence": null, "model_version": null,
     "reason": "Student profile must be verified first." }
   ```

3. **Feature completeness** — the Phase 10 mapping (`ml_feature_mapping`)
   builds the 16 model inputs. If any are missing, the model is NOT called:

   ```json
   { "ready_for_prediction": false, "prediction": null,
     "placement_probability": null,
     "missing_fields": ["aptitude_score", "coding_skills", "dsa_score", "…"] }
   ```

4. **Predict** — calls the existing Phase 8 `prediction_service.predict`
   → `src.pipeline.predict_placement()` with the mapped features.

## 3. Feature completeness & missing-feature handling

- Reuses `ml_feature_mapping.check_profile_completion` (Phase 10) — the
  exact 16 features from `src.pipeline.RAW_FEATURE_COLUMNS`.
- **Never invented**: no auto-0, no dataset-mean imputation, no guessing
  from resume wording, no "Python → coding_skill_score", no "projects →
  aptitude", no college-name → tier inference. Only verified values are used.
- The `missing_fields` list tells the frontend exactly what the student
  still needs to enter.

## 4. Model integration

- Model: `models/placepro_final_model.pkl` (fixed path — the client can
  **never** choose a model path).
- Implementation: `src/pipeline.py` is the **only** prediction
  implementation; the profile flow reuses the Phase 8
  `prediction_service.predict()` wrapper.
- No second preprocessing/feature-engineering implementation exists.

## 5. Response format

Success (`200`):

```json
{
  "ready_for_prediction": true,
  "prediction": "PLACED",
  "placement_probability": 0.68,
  "confidence": 0.68,
  "model_version": "placepro-final-v1",
  "prediction_history": [
    {"timestamp": "…", "model_version": "placepro-final-v1",
     "placement_probability": 0.68, "prediction": "PLACED"}
  ]
}
```

Guards return `ready_for_prediction: false` with `reason` and/or
`missing_fields` (HTTP 200 — semantic response, not an exception). Unknown
profile ids return `404`. No unnecessary internal model details are exposed.

## 6. Prediction history

- Every successful prediction appends one entry to the profile:
  `timestamp` (ISO-8601 UTC), `model_version`, `placement_probability`,
  `prediction`.
- History is **server-controlled**: verify/update ignore any
  `prediction_history` sent by the client (cannot be forged).
- The uploaded resume itself is **never stored**.
- History is returned in the predict response and persisted on the profile
  (`GET /api/profile/{id}`).

## 7. Security

- Fixed model path — no arbitrary model paths, no client-supplied filenames.
- Profile ids validated (`^[A-Za-z0-9\-_]+$`) — path traversal rejected.
- No filesystem paths exposed in responses; errors are generic.
- Prediction history cannot be injected by clients.

## 8. Accuracy warning (do not overclaim)

The current validated model has approximately:

| Metric | Value |
|--------|-------|
| Accuracy | **~63%** (0.6319 on the untouched test set) |
| ROC-AUC | **~0.685** |

**90% accuracy is NOT claimed.** The metrics are the actual Phase 8
results and were not changed to make the project look better. The model's
real value is its ranking quality (ROC-AUC) and calibrated probabilities,
not raw accuracy.

## 9. API summary (all phases)

| Endpoint | Phase |
|----------|-------|
| `GET /health` | 8 |
| `POST /api/predict` | 8 |
| `POST /api/resume/upload` | 9 |
| `POST /api/profile/from-resume` | 10 |
| `PUT /api/profile/{id}` | 10 |
| `POST /api/profile/verify` | 10 |
| `GET /api/profile/{id}` | 10 |
| `POST /api/profile/{id}/predict` | **11** |

## 10. Limitations

- Prediction quality is bounded by the dataset (accuracy ~63%) — see §8.
- All 16 features must be present; 10 of them require manual input.
- File-based profile store (no auth / multi-user isolation yet).
- Batch prediction, eligibility, recommendations, skill gaps, dashboards
  and the frontend are explicitly **out of scope** for Phase 11.

## 11. Testing

```bash
python backend/tests/test_predict_profile.py    # 38 checks (service + HTTP)
uvicorn backend.app.main:app --reload           # required for HTTP part
```

Covers: unverified rejection, verified-incomplete missing fields,
verified-complete success, probability range, label validity, model
version, history recording, multiple predictions, invalid ids, and
regression for `/api/predict`, `/api/resume/upload`, all Phase 10 profile
endpoints and `/health`.
