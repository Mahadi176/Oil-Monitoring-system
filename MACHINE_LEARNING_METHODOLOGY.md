# Machine-learning methodology

The forecasting module aggregates valid numeric daily records per organisation and target metric. It uses all available imported history for the selected organisation, independent of the dashboard's comparison-company and reporting-period filters.

At least 8 distinct dated observations are required to create a small chronological train/test evaluation. With 8–19 observations, Ridge Regression is evaluated against a recent-mean baseline. From 20 observations onward, Ridge Regression and Random Forest are both evaluated, and the lower holdout-MAE model is selected. The split preserves chronological order, with at least five training records and at least two test records.

The selected model is refit on all available observations to produce a seven-day point forecast. MAE, RMSE, R², and baseline MAE are reported from the holdout. Short-history results are explicitly marked exploratory and should not be interpreted as reliable long-term predictions. Eight observations is a technical minimum for a demonstration, not a claim of strong predictive validity. More months of data and external operational variables are needed for stronger academic conclusions.
