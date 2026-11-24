# Historical main training and analysis material

The files described here were preserved from main commit
`67862b38b309bf93c8aca8a2cd450d68041d21d1` when integrating the reviewed
first-deployment release. They are historical reference material, not the
production training pipeline or evidence of current deployment acceptance.

## Production application boundary

The integrated production backend entrypoint is `backend.app.main`, defined in
[backend/app/main.py](../backend/app/main.py). Production startup uses the existing
[container launcher](../backend/container_start.py). Root [main.py](../main.py)
is a historical training script and must not be used to start the application.

The production and Experimental V1 services load their separately approved
artifacts. Retaining historical source does not replace or authorize retraining
those artifacts.

## Preserved historical files

- [main.py](../main.py) and [phase4_model_tuning.py](../phase4_model_tuning.py):
  historical model training, tuning and evaluation scripts.
- [src/feature_analysis.py](../src/feature_analysis.py),
  [src/feature_engineering.py](../src/feature_engineering.py), and
  [src/predictor.py](../src/predictor.py): related historical analysis,
  preprocessing and tuned-model prediction support.
- Files under `outputs/` and `results/`, including `results/results.txt):
  historical plots and aggregate evaluation reports, preserved for reference.

Historical results are not validation of the current served models or evidence
of real-world placement or salary accuracy.

## Excluded inputs and unverified execution

Some scripts expect `data/placement.csv`; that dataset is excluded from the
integrated working tree and index. The historical predictor expects
`models/placepro_tuned_best_model.pkl`, which is not an approved runtime artifact.
Do not restore excluded datasets or obsolete models to make these scripts run.

The training scripts also require dependencies absent from production
[requirements.txt](../requirements.txt). The optional
[requirements-analysis.txt](../requirements-analysis.txt) contains plotting
dependencies, but does not provide XGBoost. Its presence is not verification of
the complete historical training environment.

These scripts are not guaranteed to run. Execution requires a separately
reviewed environment, verified dependency versions and separately authorized
inputs and output locations. Some scripts perform training or filesystem writes
when executed or imported; do not import them as a setup or inference check.

## Docker and CI separation

Historical training source, datasets, obsolete model artifacts and generated
reports must not be included in the production Docker runtime or executed by
default CI. Preserve the runtime allowlist in [Dockerfile](../Dockerfile) and
[.dockerignore](../.dockerignore). The existing
[Linux workflow](../.github/workflows/release-linux.yml) runs the backend test suite,
runtime model inference checks and frontend verification; it must not invoke
these historical scripts.

Do not execute historical training against the integrated application's models
or saved user data. Preserving reference files does not authorize training,
dependency upgrades, dataset restoration or changes to application behavior.
