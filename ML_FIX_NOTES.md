# Forecasting fix notes

## Why the application could report insufficient data

The previous forecasting implementation imposed a hard minimum of 20 distinct dated observations. It also trained on the globally filtered dashboard dataframe. That meant the forecast could be blocked when the dashboard date range was narrowed or when the organisation was not included in the comparison selection, even though more historical records existed in SQLite.

## Changes made

- Forecast organisation selection now lists every imported organisation.
- Forecasting uses all imported history for the selected organisation, not the dashboard's comparison-company/date filters.
- The minimum for a small chronological evaluation is now 8 valid dated observations.
- With 8–19 observations, only Ridge Regression is evaluated and the result is labelled exploratory.
- With 20 or more observations, Ridge Regression and Random Forest are evaluated.
- The result reports the actual number of daily observations, training/test counts, history date range, and baseline comparison.
- Fewer than 8 observations still returns a clear explanation instead of a fabricated forecast.

## Validation performed

- Metro Steel workbook: 30 valid daily records; forecast training succeeds.
- QuickBite Food Delivery workbook: 30 valid daily records; forecast training succeeds.
- Automated project tests: 12 passed.

The local environment used for this fix does not have Streamlit installed, so the full browser UI could not be launched here. Install `requirements.txt` and run `streamlit run app.py` locally to verify the interface.
