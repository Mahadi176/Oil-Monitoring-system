# Intelligent Oil Consumption Monitoring, Predictive Analytics and Multi-Organisation Cost Optimisation System

A Streamlit decision-support dashboard for importing one Excel workbook per organisation, storing daily operational records in SQLite, comparing organisations, performing statistical analysis, generating carefully evaluated forecasts, flagging unusual observations, simulating hypothetical savings, and producing PDF reports.

## Stack
Python · Streamlit · SQLite · Pandas · NumPy · Scikit-learn · Plotly · OpenPyXL · fpdf2

## Features
- Username + exactly five-digit numeric PIN; PINs are PBKDF2-HMAC-SHA256 hashed with random salts. Failed attempts trigger a temporary lockout. A five-digit PIN is only for a controlled demonstration and is not production-grade authentication.
- Multiple **individual** Excel files can be selected at once. Each file must represent one organisation; combined multi-company workbooks are not supported.
- Required daily fields: Date, TotalCost, Litres, Oil Rate, Oil Cost, Oil Cost %, Employee Cost, Transportation Cost, Other Costs. Company may be read from a Company column or inferred from the filename. Optional production and operational fields are supported.
- Validation preview, monthly summary row exclusion, financial reconciliation checks, oil percentage checks, duplicate detection, persistent SQLite storage, import history, and explicit replacement confirmation.
- Multi-organisation comparisons, reporting-period filters, descriptive statistics, trend charts, distributions, and correlation heatmap.
- Ridge and Random Forest forecasting with chronological holdout evaluation against a simple baseline; Isolation Forest is not required for the first release, and anomaly screening combines transparent IQR/robust-median checks with an exploratory Isolation Forest multivariate screen (when at least 20 complete daily observations are available).
- Explainable operational checklists beside warnings; cost-reduction simulator; PDF reporting.

## Run in VS Code (Windows)
Use Python 3.11 or 3.12.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Create a username and five-digit PIN. Upload `.xlsx` files from the left sidebar. One file per organisation. Use the validation preview, then confirm import. Records persist in `data/oil_monitor.db`.

## Excel template
See `templates/organisation_daily_template.xlsx`. Each row is one daily record. Do not include monthly totals; if a row's Date cell is literally `Total`, `Monthly Total`, `Grand Total`, or `Summary`, the importer ignores it. Do not put multiple organisations in one workbook. Avoid duplicate dates for an organisation; duplicates are skipped unless the explicit replacement option is selected.

## Data and analytical safeguards
- `TotalCost` should equal Oil Cost + Employee Cost + Transportation Cost + Other Costs.
- `Oil Cost %` should equal Oil Cost / TotalCost × 100.
- Discrepancies are flagged; source cost values are not silently corrected. If Excel stores a percentage-formatted cell as a fraction (for example, 0.075 for 7.5%), the importer standardises that derived percentage field to percentage points for consistent analysis and identifies this in the preview.
- Missing dates are not assumed to be zero. Missing optional operational fields remain null.
- Outliers are flagged for review, not deleted. An anomaly does not prove waste, leakage, or a fault.
- Forecasts require at least 8 valid dated observations for a selected organisation and use a chronological holdout. Ridge Regression is used for 8–19 observations; Random Forest is additionally evaluated from 20 observations onward. MAE, RMSE, R², and baseline MAE are shown; short-history results are explicitly labelled exploratory. Point forecasts are not confidence intervals. Forecasting uses all imported history for the chosen organisation, independently of the dashboard comparison filters.
- Correlation does not establish causation. K-Means is exploratory and only shown when at least three organisations have comparable features.
- Cost-savings outputs are user-defined hypothetical arithmetic scenarios, not guaranteed savings or ML predictions.

## Database
SQLite file defaults to `data/oil_monitor.db`. Set `OIL_MONITOR_DB` to change the location. Back up this file regularly. SQLite is appropriate for a single-instance academic demonstration, not a high-concurrency multi-instance production deployment.

## Tests
```bash
python -m pytest -q
```

## Project structure
- `app.py`: Streamlit dashboard and UI flow
- `database/`: schema, connection, and persistence queries
- `modules/`: Excel importer, analytics, recommendations, simulator, PDF generator
- `tests/`: authentication, persistence, import, and analytics tests
- `templates/`: Excel template

## Known limitations
The app is software-only. It does not connect to physical sensors, diagnose equipment faults, or verify source spreadsheets against independent records. Anomaly screening combines transparent statistical thresholds with an unsupervised Isolation Forest candidate screen; neither method is a labelled supervised model. SHAP-based explanations and saved model-result history are not implemented in this release; predictive outputs are generated on demand from the selected data.

## Release verification
The source package was syntax-compiled and its automated unit/integration suite passed (10 tests). The supplied Metro Steel workbook was also validated: its monthly summary row was excluded, 30 daily records were imported into a temporary SQLite database, and a PDF report was generated from those records. The Streamlit browser interface was not launched in the build environment because Streamlit was not preinstalled and package installation was blocked by unavailable network access; install `requirements.txt` locally before running the dashboard.
