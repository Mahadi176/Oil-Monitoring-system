# Project summary

This release redesigns the original personal/manual oil tracker into an organisation-focused operational analytics application. It uses individual Excel workbooks as the import source, SQLite as persistent storage, Streamlit as the user interface, Pandas/NumPy for processing, Scikit-learn for forecasting and clustering, Plotly for interactive dashboard charts, and fpdf2 + Matplotlib for PDF reports.

The release implements hashed five-digit demo PIN authentication, multi-file validation/import, duplicate handling, company/date persistence, descriptive analysis, multi-company comparison, chronological Ridge/Random Forest evaluation, IQR-based anomaly flags, K-Means exploration, operational checklists, hypothetical savings simulation, and PDF export.

Known gaps relative to the full master prompt: SHAP explanations are not included; the anomaly detector is statistical IQR/robust-median rather than Isolation Forest; model results are generated on demand rather than saved in dedicated ML result tables; future operational inputs are not modelled; automated UI/browser testing has not been performed. The dashboard and all modules should be extended and validated with real organisational datasets before treating outputs as research findings.
