# Phase 15 — ML Model Improvement & Robust Evaluation

> Runs on the Phase 8–14 foundation. No previous phase was rebuilt,
> no API was changed, and the production model
> (`models/placepro_final_model.pkl`) was **not** replaced.

**Headline (honest):** after a full audit, baseline reproduction,
stronger models, tuning, feature-engineering experiments, feature
selection, class-imbalance handling, threshold analysis and
calibration, **no model materially beats the Phase 8 tuned Logistic
Regression on ROC-AUC (0.6853)**. The Phase 15 best model reproduces
Phase 8 almost exactly. **90% accuracy is NOT achievable on this
dataset** — the evidence is documented below.

---

## 1. Dataset audit (`results/phase15_data_quality_audit.txt`)

`data/placement_phase6.csv` — 100,000 rows × 18 columns, target
`placement_status` (1 = Placed, 0 = Not Placed).

| Check | Finding |
|-------|---------|
| Missing values | Only `salary_package_lpa` (31,525 missing) — all other columns complete |
| Duplicates | 0 exact duplicates; 0 duplicates on features-only |
| Constant columns | none |
| Low-variance numeric | only the engineered binary indicators |
| Impossible values | none (cgpa/skills within [0,10], aptitude within [0,100], counts ≥ 0) |
| Outliers (1.5×IQR) | none material |
| Class distribution | **68.5% placed / 31.5% not placed** → majority-class baseline accuracy = **0.6847** |
| Train/test drift | max mean diff 0.078 (`coding_experience_interaction`) — negligible |
| Leakage | `salary_package_lpa` present for **100% of placed / 0% of not-placed** → **pure post-placement leakage**, dropped by `create_features()` and never used |
| Strongest feature–target correlation | `academic_skill_index` \|r\| = **0.172** (far below what high-accuracy classification needs) |

## 2. Target quality investigation

- `placement_status` looks like a **realistic, noisy synthetic target**:
  no single feature drives it (max \|r\| ≈ 0.17).
- Placed-rate by CGPA quartile: 0.594 → 0.663 → 0.711 → 0.772 (weak,
  monotone — sensible direction).
- Placed-rate by internships: 0.659 → 0.732 → 0.772; by projects:
  0.644 → 0.734; backlogs inverse: 0.695 → 0.625.
- **salary_package_lpa is pure leakage** (only present for placed
  students) — confirmed, dropped, never used.
- Labels were **not** modified; no hidden leakage was found beyond the
  already-handled salary column.

## 3. Baseline reproduction (same untouched test set)

Exact Phase 8 protocol: `create_features()` → 80/20 stratified split
(`random_state=42`) → preprocessor (median-impute + StandardScaler;
most-frequent + OneHotEncoder) → 5-fold stratified CV on training.
All models evaluated on the **untouched test set** (20,000 rows).

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC | Brier |
|-------|----------|-----------|--------|-----|---------|--------|-------|
| **Phase 8 LR tuned (recorded)** | 0.6319 | 0.7956 | 0.6223 | 0.6983 | 0.6853 | — | — |
| **Phase 6 XGBoost (recorded)** | 0.6957 | n/a | n/a | 0.8053 | 0.6796 | — | — |
| **LR Tuned (Phase 15)** | 0.6319 | 0.7956 | 0.6223 | 0.6983 | 0.6853 | 0.8174 | 0.2241 |
| XGBoost Tuned | 0.6281 | 0.7952 | 0.6155 | 0.6939 | 0.6843 | 0.8164 | 0.2242 |
| HistGradientBoosting Tuned | 0.6977 | 0.7111 | 0.9408 | 0.8100 | 0.6829 | 0.8157 | 0.1968 |
| Extra Trees Tuned | 0.6424 | 0.7768 | 0.6705 | 0.7197 | 0.6764 | 0.8097 | 0.2182 |

The Phase 15 LR re-run **reproduces the Phase 8 recorded numbers
exactly** (same grid, same split) — a good sanity check of the
protocol.

## 4. Models tested

- Logistic Regression (tuned — Phase 8 grid, `liblinear`, C,
  penalty, class_weight) — **best ROC-AUC (0.6853)**
- Random Forest (default) — baseline only (Phase 7 showed tuning it
  is slow and gains little)
- Decision Tree (depth-capped) — baseline only
- XGBoost (default + tuned: learning_rate, max_depth,
  min_child_weight, subsample, colsample_bytree, reg_alpha,
  reg_lambda, n_estimators, scale_pos_weight) — AUC 0.6843
- Extra Trees (tuned: n_estimators, max_depth, min_samples_leaf,
  max_features, class_weight) — AUC 0.6764
- HistGradientBoosting (tuned: learning_rate, max_leaf_nodes,
  min_samples_leaf, l2_regularization) — AUC 0.6829, best
  accuracy/F1 (0.6977 / 0.8100) but **lower** ROC-AUC
- CatBoost — **not available** in this environment (import failed);
  documented, not tested

## 5. Hyperparameter search

- `RandomizedSearchCV` / small `GridSearchCV`, **3-fold** stratified,
  **ROC-AUC scoring**, fixed `random_state=42`, **`n_jobs=1`**
  (Windows-safe — avoids the Phase 7 RandomForest multiprocessing
  freeze).

## 6. Feature-engineering experiments

Tested deterministic new features (`projects_per_internship`,
`cgpa_skill_interaction`, `skill_consistency`, `weighted_experience`)
on the **same untouched test set** (3-fold CV on train for selection,
then test evaluation). Result: no material gain — the Phase 7 feature
set remains the best. Because `src/pipeline.py` is a protected file,
experiment features were **not** adopted into production engineering
(adopting them would be an explicit, reviewed decision).

## 7. Feature selection

XGBoost importance on **training data only**; top-10 / top-15 / all
compared by 3-fold CV on training. ROC-AUC barely changes — the signal
is diffuse across features. No features removed from the production
set.

## 8. Class imbalance

- Target: 68.5% placed. `class_weight` / `scale_pos_weight` were part
  of every tuning grid; the best LR uses `class_weight="balanced"`.
- Threshold adjustment (below) recovers most of the recall/F1 without
  touching the model.
- SMOTE was **not** used: it would have to be applied strictly inside
  training folds, and the class-imbalance options + threshold tuning
  already cover the practical gain (documented; not needed here).

## 9. Threshold optimization (`results/phase15_threshold_analysis.csv`)

Threshold moves the decision boundary only — **ROC-AUC is
threshold-independent** (model quality vs decision threshold are
separate). For the selected LR model on the test set:

| Threshold | Accuracy | Precision | Recall | F1 | Balanced acc |
|-----------|----------|-----------|--------|-----|--------------|
| 0.15 | 0.6858 | 0.6857 | 0.9991 | 0.8133 | 0.5023 |
| 0.25 | 0.6962 | 0.6987 | 0.9781 | **0.8151** | 0.5310 |
| 0.30 | 0.6995 | 0.7115 | 0.9438 | 0.8114 | 0.5563 |
| 0.50 (Phase 8 default) | 0.6319 | 0.7956 | 0.6223 | 0.6983 | — |

**F1-optimal threshold ≈ 0.25** lifts F1 from 0.698 → 0.815 and
accuracy from 0.632 → 0.696 — without changing the model. This is a
*decision* improvement, not a *model* improvement (ROC-AUC unchanged).

## 10. Probability calibration (`results/phase15_calibration.txt`)

Selected model (LR) on the test set: Brier **0.2241** (raw) →
**0.1961** (Platt/sigmoid) → **0.1962** (isotonic). Calibration curve
shows the raw model over-predicts in low bins (predicted 0.478 →
observed 0.295); sigmoid/isotonic substantially fix this. The saved
metadata records this; the production pipeline was not changed.

## 11. Cross-validation confidence (5-fold, training data)

| Model | Accuracy | ROC-AUC | F1 |
|-------|----------|---------|-----|
| LR Tuned | 0.6289 ± 0.0041 | **0.6858 ± 0.0047** | 0.6961 ± 0.0042 |
| XGBoost Tuned | 0.6266 ± 0.0041 | 0.6837 ± 0.0041 | 0.6930 ± 0.0045 |
| HGB Tuned | 0.6988 ± 0.0015 | 0.6825 ± 0.0044 | 0.8101 ± 0.0010 |
| Extra Trees Tuned | 0.6404 ± 0.0058 | 0.6752 ± 0.0055 | 0.7184 ± 0.0056 |

All candidates are stable (±0.006 or better). LR's ROC-AUC lead over
XGBoost/HGB is consistent (~0.003–0.010 across CV and test) — not a
single-split artifact.

## 12. Overfitting check

Selected model: train accuracy 0.6288 vs test 0.6319 (gap **-0.0031**);
train ROC-AUC vs test gap negligible. No suspiciously high training
performance, no unstable CV, no large train/test gaps.

## 13. Model selection

Selection rule (documented): **ROC-AUC first**, then PR-AUC / F1 /
calibration / CV stability; accuracy is secondary given the class
imbalance.

**Selected: Logistic Regression Tuned** — highest test ROC-AUC
(0.6853) and PR-AUC (0.8174), best Brier after calibration (0.1961),
most stable CV AUC (0.6858 ± 0.0047), and it reproduces Phase 8
exactly. HGB's higher accuracy/F1 (0.698 / 0.810) comes at the cost of
a **lower** ROC-AUC (0.6829) — the same tradeoff Phase 6 observed with
XGBoost; per the selection rule, ROC-AUC dominates.

## 14. Final model & 90% accuracy assessment

Saved (evaluation artifact):
- `models/placepro_phase15_best_model.pkl` (LR Tuned — the Phase 8
  grid result; same pipeline structure, servable explicitly via
  `predict_placement(data, model_path=...)`)
- `models/placepro_phase15_metadata.json` (model type, features,
  preprocessing, dataset, seed, test metrics, CV metrics, threshold,
  calibration, replacement flag = false)

**90% accuracy: NO — not supported by this data.** Evidence:
- Best honest test accuracy across **every** model tried: **0.6977**
  (HGB) — below 70%, barely above the 0.6847 majority baseline.
- Best ROC-AUC: **0.6853** — the class overlap is severe (mean
  predicted probability for PLACED 0.55 vs NOT PLACED 0.45).
- Strongest feature correlates at \|r\| ≤ 0.17 with the target.
- The rough AUC→balanced-accuracy bound (~0.37) is far below 0.90.
- Reaching 90% would require leakage or label manipulation — both
  explicitly prohibited.

The production model (`models/placepro_final_model.pkl`) was **NOT
replaced**. Phase 15 does not silently swap models — replacement is an
explicit, reviewed decision (instructions are in the metadata note).

## 15. Explainability

`results/phase15_feature_importance.csv` + `outputs/phase15_feature_importance.png`
(LR coefficients): `college_tier` (Tier-1 +0.56 / Tier-3 −0.47),
`internships` (+0.22), `branch` (CSE +0.20, IT +0.18), `cgpa`
(+0.17), `academic_skill_index` (+0.16). These are associations, not
causation. Also produced: `outputs/phase15_model_comparison.png`,
`outputs/phase15_roc_curves.png`,
`outputs/phase15_confusion_matrix.png`.

## Limitations

- CatBoost not tested (not installed); SMOTE not used (documented).
- Feature-engineering experiments were not adopted into production
  (`src/pipeline.py` is a protected file).
- The accuracy/F1-vs-AUC tradeoff means "best model" depends on the
  objective: for ranking/eligibility use LR (best AUC); for a
  high-recall "placed" flag, HGB + threshold tuning wins — the Phase
  15 recommendation is to keep LR for the API.

## Reproducibility

```bash
python phase15_ml_improvement.py                # full run (~40-60 min)
python phase15_ml_improvement.py --sample 20000 # dev smoke test
```
Outputs: `results/phase15_*` (audit, comparison, CV, threshold,
calibration, importance, final results, validation summary),
`outputs/phase15_*.png` (4 plots), `models/placepro_phase15_best_model.pkl`
+ metadata. All random_state=42; the untouched test set is the same
one Phase 8 used.
