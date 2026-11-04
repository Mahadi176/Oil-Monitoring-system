from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

COSTS=['Oil Cost','Employee Cost','Transportation Cost','Other Costs']

def prepare(df):
    if df.empty: return df.copy()
    x=df.copy(); x['Date']=pd.to_datetime(x['record_date'] if 'record_date' in x else x['Date'])
    return x.sort_values(['Company','Date'])

def summary_metrics(df):
    if df.empty: return {}
    return {'organisations':int(df.Company.nunique()),'days':int(df.Date.nunique()),'litres':float(df.Litres.sum()),'oil_cost':float(df['Oil Cost'].sum()),'oil_pct':float(df['Oil Cost'].sum()/df.TotalCost.sum()*100) if df.TotalCost.sum() else 0,'employee_cost':float(df['Employee Cost'].sum()),'transport_cost':float(df['Transportation Cost'].sum()),'other_cost':float(df['Other Costs'].sum()),'total_cost':float(df.TotalCost.sum()),'avg_daily_litres':float(df.groupby(['Company','Date']).Litres.sum().mean())}

def compare_companies(df):
    if df.empty: return pd.DataFrame()
    agg=df.groupby('Company').agg(Days=('Date','nunique'),Litres=('Litres','sum'),Oil_Cost=('Oil Cost','sum'),Employee_Cost=('Employee Cost','sum'),Transportation_Cost=('Transportation Cost','sum'),Other_Costs=('Other Costs','sum'),Total_Cost=('TotalCost','sum'),Avg_Daily_Litres=('Litres','mean'),Avg_Oil_Rate=('Oil Rate','mean')).reset_index()
    agg['Oil_Cost_%']=np.where(agg.Total_Cost>0,agg.Oil_Cost/agg.Total_Cost*100,0)
    if 'Production Output' in df and df['Production Output'].notna().any():
        prod=df.groupby('Company')['Production Output'].sum(min_count=1).rename('Production_Output')
        agg=agg.merge(prod,on='Company',how='left')
        agg['Litres_per_Production_Unit']=np.where(agg.Production_Output>0,agg.Litres/agg.Production_Output,np.nan)
        agg['Cost_per_Production_Unit']=np.where(agg.Production_Output>0,agg.Total_Cost/agg.Production_Output,np.nan)
    return agg

def descriptive_statistics(df):
    cols=['Litres','Oil Cost','Employee Cost','Transportation Cost','Other Costs','TotalCost','Oil Rate']
    cols=[c for c in cols if c in df]
    return df[cols].describe().T if not df.empty else pd.DataFrame()

def anomaly_assessment(df):
    """Return anomaly candidates plus an explicit per-organisation coverage summary.

    Univariate IQR/robust-MAD flags are transparent upper-tail checks. For
    organisations with at least 20 daily rows, Isolation Forest adds an
    exploratory multivariate screen across cost/consumption features. It is
    deliberately labelled as a candidate signal, not proof of waste.
    """
    findings=[]
    coverage=[]
    if df.empty:
        return {'findings': findings, 'coverage': coverage,
                'evaluated_organisations': 0, 'insufficient_organisations': 0}

    metrics=['Litres','Oil Cost','Employee Cost','Transportation Cost','Other Costs','TotalCost']
    for company,g0 in df.groupby('Company'):
        g=g0.copy()
        if 'Date' in g:
            g['Date']=pd.to_datetime(g['Date'],errors='coerce')
        g=g.dropna(subset=['Date']).sort_values('Date')
        metric_checks=0
        eligible_metrics=[]
        iforest_evaluated=False
        for metric in metrics:
            if metric not in g:
                continue
            s=pd.to_numeric(g[metric],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
            if len(s)<8 or s.nunique()<3:
                continue
            metric_checks += 1
            eligible_metrics.append(metric)
            q1,q3=s.quantile([.25,.75]); iqr=q3-q1
            med=s.median(); mad=float(np.median(np.abs(s-med)))
            threshold=max(q3+1.5*iqr,med+3*1.4826*mad)
            flagged=g.loc[pd.to_numeric(g[metric],errors='coerce')>threshold]
            for _,r in flagged.iterrows():
                findings.append({'Company':company,'Metric':metric,'Date':r.Date.strftime('%Y-%m-%d'),
                    'Observed':float(r[metric]),'Expected':float(med),
                    'Severity':'High' if r[metric]>max(threshold*1.5,med*2) else 'Moderate',
                    'Method':'IQR and robust median deviation',
                    'Explanation':f"Observed value exceeds the organisation's historical upper threshold ({threshold:,.2f}). This is a review signal, not proof of waste or fault."})

        # Multivariate screening uses only rows complete across the selected
        # operational metrics; it does not silently impute missing values.
        usable=[m for m in metrics if m in g]
        if len(g)>=20 and len(usable)>=3:
            X=g[usable].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
            complete=X.notna().all(axis=1)
            Xc=X.loc[complete]
            varying=[c for c in usable if Xc[c].nunique()>=2]
            if len(Xc)>=20 and len(varying)>=3:
                from sklearn.ensemble import IsolationForest
                from sklearn.preprocessing import RobustScaler
                scaled=RobustScaler().fit_transform(Xc[varying])
                detector=IsolationForest(n_estimators=300,contamination=0.05,random_state=42)
                labels=detector.fit_predict(scaled)
                detector.decision_function(scaled)
                iforest_evaluated=True
                median_values=Xc[varying].median()
                mad_values=(Xc[varying]-median_values).abs().median().replace(0,np.nan)
                flagged_index=Xc.index[labels==-1]
                for idx in flagged_index:
                    r=g.loc[idx]
                    # Avoid duplicate cards when the same date already has a
                    # clear univariate flag; retain the more interpretable one.
                    date_key=r.Date.strftime('%Y-%m-%d')
                    if any(f['Company']==company and f['Date']==date_key for f in findings):
                        continue
                    deviations=((Xc.loc[idx,varying]-median_values).abs()/mad_values).replace([np.inf,-np.inf],np.nan).dropna().sort_values(ascending=False)
                    contributors=', '.join(deviations.head(2).index.tolist()) or ', '.join(varying[:2])
                    total=float(r['TotalCost']) if pd.notna(r.get('TotalCost')) else 0.0
                    total_median=float(Xc['TotalCost'].median()) if 'TotalCost' in Xc else total
                    findings.append({'Company':company,'Metric':'Multivariate operating profile','Date':date_key,
                        'Observed':total,'Expected':total_median,'Severity':'Moderate',
                        'Method':'Isolation Forest (exploratory multivariate screen)',
                        'Contributors':contributors,
                        'Explanation':f"Isolation Forest identified an unusual combination of operating values. The strongest relative deviations were in {contributors}. Review the source records and operating context; this is an exploratory candidate, not proof of waste or fault."})

        n=len(g)
        coverage.append({'Company':company,'observations':n,'metric_checks':metric_checks,
                         'isolation_forest':iforest_evaluated,
                         'insufficient':metric_checks==0 and n<8})

    findings=sorted(findings,key=lambda x:(x['Severity']!='High',-x['Observed']))
    evaluated=sum(1 for c in coverage if c['metric_checks']>0 or c['isolation_forest'])
    insufficient=sum(1 for c in coverage if c['insufficient'])
    return {'findings':findings,'coverage':coverage,
            'evaluated_organisations':evaluated,'insufficient_organisations':insufficient}


def anomaly_findings(df):
    """Backward-compatible list-only anomaly interface."""
    return anomaly_assessment(df)['findings']

def train_forecast(df, company, target='Litres', horizon=7):
    """Train an organisation-specific, time-ordered forecast.

    Uses all available history for the selected organisation (the caller decides
    whether to pass a date-filtered frame). Eight distinct observations are the
    minimum for a small chronological holdout. Random Forest is only attempted
    with at least 20 observations; shorter histories use Ridge plus a baseline.
    """
    if target not in df.columns:
        return {'status': 'error', 'message': f"Forecast target '{target}' is not available in the imported data."}

    g = df.loc[df['Company'].astype(str) == str(company)].copy()
    if 'Date' in g:
        g['Date'] = pd.to_datetime(g['Date'], errors='coerce')
    elif 'record_date' in g:
        g['Date'] = pd.to_datetime(g['record_date'], errors='coerce')
    else:
        return {'status': 'error', 'message': 'The imported records do not contain a usable date column.'}

    g[target] = pd.to_numeric(g[target], errors='coerce')
    g = g.dropna(subset=['Date', target])
    g = g[np.isfinite(g[target])]
    # One value per date; if source rows exist more than once, daily operational
    # quantities/costs are additive and are aggregated before modelling.
    g = g.groupby('Date', as_index=False)[target].sum().sort_values('Date')
    n = len(g)
    if n < 8:
        return {
            'status': 'insufficient',
            'n': n,
            'minimum': 8,
            'message': (
                f"{company} has {n} valid dated observations for {target}; "
                "at least 8 are required for a small chronological train/test evaluation. "
                "Import more daily records or widen the forecast history."
            )
        }

    g['t'] = (g.Date - g.Date.min()).dt.days
    g['dow'] = g.Date.dt.dayofweek
    X = g[['t', 'dow']].to_numpy(dtype=float)
    y = g[target].to_numpy(dtype=float)

    # Keep at least five training observations and at least two holdout points.
    split = max(5, int(np.floor(n * 0.8)))
    split = min(split, n - 2)
    if split < 5 or n - split < 2:
        return {'status': 'insufficient', 'n': n, 'minimum': 8,
                'message': 'Not enough observations remain for a valid chronological train/test split.'}

    models = {
        'Ridge Regression': make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    }
    if n >= 20:
        models['Random Forest'] = RandomForestRegressor(
            n_estimators=250, min_samples_leaf=2, random_state=42
        )

    results = []
    for name, model in models.items():
        model.fit(X[:split], y[:split])
        prediction = np.maximum(0, model.predict(X[split:]))
        baseline = np.repeat(np.mean(y[max(0, split - 7):split]), len(prediction))
        results.append({
            'name': name,
            'model': model,
            'mae': float(mean_absolute_error(y[split:], prediction)),
            'rmse': float(mean_squared_error(y[split:], prediction) ** 0.5),
            'r2': float(r2_score(y[split:], prediction)) if len(prediction) > 1 else float('nan'),
            'baseline_mae': float(mean_absolute_error(y[split:], baseline)),
        })

    best = min(results, key=lambda item: item['mae'])
    final_model = best['model']
    final_model.fit(X, y)
    last_date = g.Date.max()
    future = pd.date_range(last_date + pd.Timedelta(days=1), periods=int(horizon), freq='D')
    future_x = np.column_stack([(future - g.Date.min()).days, future.dayofweek]).astype(float)
    predicted = np.maximum(0, final_model.predict(future_x))

    if best['name'] == 'Random Forest':
        importances = final_model.feature_importances_
    else:
        importances = np.abs(final_model.named_steps['ridge'].coef_)
    feature_importance = pd.DataFrame({
        'Feature': ['Time index', 'Day of week'],
        'Importance': importances,
    }).sort_values('Importance', ascending=False)

    return {
        'status': 'ok',
        'model': best['name'],
        'mae': best['mae'],
        'rmse': best['rmse'],
        'r2': best['r2'],
        'baseline_mae': best['baseline_mae'],
        'beats_baseline': bool(best['mae'] < best['baseline_mae']),
        'forecast': pd.DataFrame({'Date': future, 'Predicted': predicted}),
        'feature_importance': feature_importance,
        'n': n,
        'holdout': n - split,
        'training': split,
        'target': target,
        'history_start': g.Date.min(),
        'history_end': g.Date.max(),
        'reliability_note': (
            'Short-history exploratory model: interpret cautiously; only Ridge was evaluated.'
            if n < 20 else
            'Exploratory model evaluated on a chronological holdout; performance may change with more history.'
        ),
    }

def cluster_companies(df):
    c=compare_companies(df)
    features=['Avg_Daily_Litres','Oil_Cost_%','Avg_Oil_Rate']
    if len(c)<3 or not all(f in c for f in features): return None,'At least three organisations are required for exploratory clustering.'
    x=c[features].replace([np.inf,-np.inf],np.nan).dropna()
    if len(x)<3 or any(x[f].nunique()<2 for f in features): return None,'Insufficient variation or complete comparable features for clustering.'
    k=min(3,len(x)); model=make_pipeline(StandardScaler(),KMeans(n_clusters=k,random_state=42,n_init=10))
    c.loc[x.index,'Cluster']=model.fit_predict(x)
    return c,None
