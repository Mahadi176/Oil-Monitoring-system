import pandas as pd
from modules.analytics import compare_companies, anomaly_findings, train_forecast

def sample(n=35):
    rows=[]
    for company,mult in [('A',1),('B',1.2)]:
        for i,d in enumerate(pd.date_range('2026-01-01',periods=n)):
            litres=(100+i%7)*mult
            rows.append({'Company':company,'Date':d,'Litres':litres,'Oil Rate':100,'Oil Cost':litres*100,'Oil Cost %':20,'Employee Cost':2000,'Transportation Cost':500,'Other Costs':500,'TotalCost':litres*100+3000})
    return pd.DataFrame(rows)

def test_company_comparison():
    c=compare_companies(sample())
    assert len(c)==2 and 'Oil_Cost_%' in c

def test_forecast_chronological_holdout():
    r=train_forecast(sample(),'A','Litres')
    assert r['status']=='ok' and r['n']==35 and len(r['forecast'])==7

def test_short_history_uses_ridge_and_reports_caution():
    r=train_forecast(sample(8),'A','Litres')
    assert r['status']=='ok'
    assert r['n']==8
    assert r['model']=='Ridge Regression'
    assert len(r['forecast'])==7
    assert 'Short-history' in r['reliability_note']

def test_very_short_history_is_explained():
    r=train_forecast(sample(6),'A','Litres')
    assert r['status']=='insufficient'
    assert r['n']==6
    assert 'at least 8' in r['message']

def test_forecast_uses_company_specific_observations():
    r=train_forecast(sample(30),'B','Litres')
    assert r['status']=='ok' and r['n']==30



def test_anomaly_assessment_distinguishes_no_flags_from_insufficient():
    from modules.analytics import anomaly_assessment
    result = anomaly_assessment(sample(30))
    assert result['evaluated_organisations'] == 2
    assert result['insufficient_organisations'] == 0
    assert len(result['coverage']) == 2


def test_isolation_forest_finds_multivariate_operational_candidate():
    from modules.analytics import anomaly_assessment
    frame = sample(30).query("Company == 'A'").copy()
    frame.loc[frame.index[-1], 'Employee Cost'] = 9000
    frame.loc[frame.index[-1], 'Transportation Cost'] = 8000
    frame.loc[frame.index[-1], 'TotalCost'] = frame.loc[frame.index[-1], 'Oil Cost'] + 17500
    result = anomaly_assessment(frame)
    assert result['evaluated_organisations'] == 1
    assert result['coverage'][0]['observations'] == 30
    assert result['coverage'][0]['isolation_forest'] is True
    assert result['findings'], 'The injected extreme operational profile should produce an anomaly candidate.'


def test_short_anomaly_history_reports_insufficient_observations():
    from modules.analytics import anomaly_assessment
    result = anomaly_assessment(sample(6))
    assert result['evaluated_organisations'] == 0
    assert result['insufficient_organisations'] == 2
