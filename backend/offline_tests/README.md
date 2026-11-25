# Explicit offline salary analysis

This suite is outside the default `backend/tests` testpaths. It preserves the
population and held-out-quality assertions without shipping training rows.
Use the installed project Python environment and explicitly supply approved
original data; never download or restore data just to make a release test pass.

```powershell
$env:PLACEPRO_SALARY_ANALYSIS_DATA = "C:\approved-data\placement.csv"
.\.venv\Scripts\python.exe -B -m pytest backend/offline_tests/ -q -p no:cacheprovider
```

On Linux, set the same variable to the approved dataset's path and use
`python -B -m pytest backend/offline_tests/ -q -p no:cacheprovider` in the project
environment. A missing or mismatched dataset fails explicitly. The default
backend suite does not invoke this analysis or need this variable.

The aggregate-only summary at `backend/tests/fixtures/salary_training_summary.json`
records the dataset, served salary model and original training-script SHA-256
hashes, UTC verification date, selected columns, population and calculation method.
The original two local CSV copies were verified byte-identical. The analysis
recomputes all numeric support bounds, salary bounds and population counts and
checks them against that summary. Model hashes are checked in both test suites.
No identifiers or student rows appear in the summary.

The quality test retains the original 20% split, `random_state=42`, MAE < 1 LPA,
RMSE < 1.3 LPA and R² > 0.5 assertions. It loads the existing artifact, never
trains, provisions accounts or writes source data/models. This evaluation does
not establish real-world placement or salary accuracy. No salary value is used
as a placement-classifier feature or target.
