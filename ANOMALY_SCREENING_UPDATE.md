# Anomaly screening update

The dashboard now separates **no anomaly candidates** from **insufficient data**. It reports the number of organisation-day records, organisations evaluated, univariate metric checks, and organisations screened by Isolation Forest.

Methods:
- Univariate upper-tail screening: IQR and robust median absolute deviation, requiring at least 8 valid observations and at least 3 distinct values for a metric.
- Multivariate screening: Isolation Forest with a fixed 5% contamination setting, applied per organisation only when at least 20 complete daily rows and at least 3 varying operational metrics are available.
- Duplicate date cards are avoided when a univariate flag already exists for that organisation/date.

Isolation Forest results are **exploratory investigation candidates**. The 5% setting controls screening sensitivity; it does not mean that exactly 5% of records are truly faulty. A flag is not proof of waste, leakage, fraud, or equipment failure. Confirm against source invoices and operating logs.

## Checks performed
- QuickBite Food Delivery: 30 daily rows; 6 univariate metric checks; Isolation Forest evaluated. Candidate dates: 2026-11-08 and 2026-11-24.
- Metro Steel: 30 daily rows; 6 univariate metric checks; Isolation Forest evaluated. Existing IQR flags include 2026-11-30; multivariate screening also identified an unusual profile on 2026-11-01.
- Automated project tests: 15 passed.
