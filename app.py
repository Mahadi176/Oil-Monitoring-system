from __future__ import annotations
from datetime import date
from io import BytesIO
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.schema import init_db
from database.queries import create_user, authenticate, username_for, organisations, load_records, import_records, log_import_error, import_history
from modules.excel_importer import load_excel, company_from_file
from modules.analytics import prepare, summary_metrics, compare_companies, descriptive_statistics, anomaly_findings, anomaly_assessment, train_forecast, cluster_companies, COSTS
from modules.recommendations import actions_for
from modules.optimisation import simulate_savings
from modules.pdf_generator import build_pdf

st.set_page_config(page_title='Intelligent Oil Monitor',page_icon='🛢️',layout='wide',initial_sidebar_state='expanded')
init_db()

st.markdown('''<style>
:root{--navy:#14213D;--blue:#2563EB;--teal:#0D9488;--cyan:#06B6D4;--violet:#7C3AED;--bg:#F4F7FB}
.block-container{padding-top:1.0rem;padding-bottom:1.2rem;max-width:1600px}
[data-testid="stMetric"]{background:linear-gradient(135deg,#fff,#f6f9ff);border:1px solid #e4eaf3;padding:12px 14px;border-radius:14px;box-shadow:0 2px 8px rgba(20,33,61,.05)}
[data-testid="stMetricLabel"]{color:#52627b;font-weight:600}
[data-testid="stMetricValue"]{color:#14213D;font-weight:750}
section[data-testid="stSidebar"]{background:#f4f7fb}
div[data-testid="stTabs"] button{font-weight:650}
div[data-testid="stAlert"]{border-radius:12px}
.small-muted{color:#64748b;font-size:.82rem}
</style>''',unsafe_allow_html=True)

# Authentication: retain a simple login experience; PIN is hashed with PBKDF2.
if 'user_id' not in st.session_state:
    st.markdown("<div style='padding:12px 0 2px'><h1 style='color:#14213D;margin-bottom:0'>🛢️ Intelligent Oil Monitoring</h1><p style='color:#64748b'>Predictive analytics · Multi-organisation benchmarking · Cost optimisation</p></div>",unsafe_allow_html=True)
    login, register = st.columns([1,1],gap='large')
    with login:
        st.subheader('Sign in')
        with st.form('login'):
            u=st.text_input('Username'); p=st.text_input('Five-digit PIN',type='password',max_chars=5)
            ok=st.form_submit_button('Sign in',use_container_width=True)
        if ok:
            uid=authenticate(u,p)
            if uid is None: st.error('Invalid username or PIN, or the account is temporarily locked.')
            else: st.session_state.user_id=uid; st.rerun()
    with register:
        st.subheader('Create account')
        with st.form('register'):
            nu=st.text_input('Choose username'); npin=st.text_input('Create five-digit PIN',type='password',max_chars=5); cpin=st.text_input('Confirm PIN',type='password',max_chars=5)
            create=st.form_submit_button('Create account',use_container_width=True)
        if create:
            if npin!=cpin: st.error('PINs do not match.')
            else:
                success,msg=create_user(nu,npin); (st.success if success else st.error)(msg)
    st.info('A five-digit PIN is used for the controlled academic demonstration. It is not suitable for protecting sensitive production data.')
    st.stop()

uid=int(st.session_state.user_id)
try: username=username_for(uid)
except Exception: st.session_state.pop('user_id',None); st.rerun()

# Sidebar import workflow
with st.sidebar:
    st.markdown('## 🛢️ Oil Monitor')
    st.caption(f'Signed in as **{username}**')
    if st.button('Log out',use_container_width=True): st.session_state.clear(); st.rerun()
    st.divider()
    st.markdown('### Excel data import')
    uploads=st.file_uploader('Upload individual organisation workbooks',type=['xlsx','xlsm'],accept_multiple_files=True,help='Each selected Excel file must represent one organisation. Combined multi-company workbooks are not supported.')
    if st.button('Validate selected files',disabled=not uploads,use_container_width=True):
        previews=[]
        for f in uploads:
            try:
                frame,errs=load_excel(f)
                company=company_from_file(frame,f.name)
                previews.append({'filename':f.name,'company':company,'data':frame,'errors':errs})
                if errs: log_import_error(uid,f.name,company,errs)
            except Exception as e:
                previews.append({'filename':f.name,'company':None,'data':pd.DataFrame(),'errors':[str(e)]})
        st.session_state.import_previews=previews
    previews=st.session_state.get('import_previews',[])
    if previews:
        st.markdown('#### Validation preview')
        for i,item in enumerate(previews):
            if item['errors']: st.error(f"{item['filename']}: {' '.join(item['errors'])}")
            else:
                dfp=item['data']; st.success(f"{item['filename']} · {item['company']} · {len(dfp)} daily rows")
                rec=int((~dfp['_cost_reconciles']).sum()); pct=int((~dfp['_oil_pct_valid']).sum())
                if bool(dfp.get('_oil_pct_scaled_from_fraction',pd.Series(dtype=bool)).any()): st.info('Excel percentage cells were stored as fractions (for example, 0.075); the preview converts them to percentage points (7.5%) for consistent analysis.')
                if rec or pct: st.warning(f'{rec} cost reconciliation issue(s); {pct} oil percentage issue(s). Source cost values are not changed.')
                st.dataframe(dfp.head(4),use_container_width=True,hide_index=True)
        valid=[x for x in previews if not x['errors']]
        existing=organisations(uid); existing_names={o['name'] for o in existing}
        if valid:
            # Detect dates already in DB and require explicit opt-in to replace.
            current=load_records(uid)
            conflicts=[]
            for item in valid:
                if item['company'] in existing_names and not current.empty:
                    dates=set(pd.to_datetime(current.loc[current.Company==item['company'],'record_date']).dt.strftime('%Y-%m-%d'))
                    overlap=set(pd.to_datetime(item['data'].Date).dt.strftime('%Y-%m-%d')) & dates
                    if overlap: conflicts.append((item['company'],len(overlap)))
            replace=st.checkbox('Explicitly replace existing organisation/date records',value=False,disabled=not conflicts,help='Only select this when you intentionally want to update previously imported dates.')
            if conflicts: st.warning('Existing date conflicts: '+', '.join(f'{n}: {c}' for n,c in conflicts)+'. Without replacement, duplicates are skipped.')
            if st.button('Import validated files',use_container_width=True):
                totals={'imported':0,'skipped':0}
                for item in valid:
                    frame=item['data'].drop(columns=['_cost_difference','_oil_pct_expected','_cost_reconciles','_oil_pct_valid','_oil_pct_scaled_from_fraction'],errors='ignore')
                    try:
                        result=import_records(uid,item['company'],frame,item['filename'],replace_existing=replace)
                        totals['imported']+=result['imported']; totals['skipped']+=result['skipped']
                    except Exception as e: log_import_error(uid,item['filename'],item['company'],[str(e)]); st.error(f"Import failed for {item['filename']}: {e}")
                st.success(f"Imported {totals['imported']} new record(s); skipped {totals['skipped']} duplicate(s).")
                st.session_state.pop('import_previews',None); st.rerun()
    st.divider()
    st.caption('Expected columns: Date, Company (optional if filename identifies it), TotalCost, Litres, Oil Rate, Oil Cost, Oil Cost %, Employee Cost, Transportation Cost, Other Costs. Optional production/operational fields are supported.')

# Load data and compact global filters
raw=load_records(uid)
if raw.empty:
    st.title('Intelligent Oil Consumption Monitoring System')
    st.caption('Upload one Excel workbook per organisation using the sidebar to begin.')
    st.info('No organisation data has been imported yet. Your imported records will remain in SQLite after application restarts.')
    hist=import_history(uid)
    if not hist.empty:
        st.subheader('Recent import activity'); st.dataframe(hist,use_container_width=True,hide_index=True)
    st.stop()

data=raw.rename(columns={'record_date':'Date','total_cost':'TotalCost','litres':'Litres','oil_rate':'Oil Rate','oil_cost':'Oil Cost','oil_cost_pct':'Oil Cost %','employee_cost':'Employee Cost','transportation_cost':'Transportation Cost','other_costs':'Other Costs','production_output':'Production Output','operating_hours':'Operating Hours','number_of_employees':'Number of Employees','number_of_vehicles':'Number of Vehicles','distance_travelled':'Distance Travelled','electricity_consumption':'Electricity Consumption'})
data=prepare(data)
org_names=sorted(data.Company.unique().tolist())

st.markdown("<div style='display:flex;align-items:center;justify-content:space-between;gap:12px'><div><h1 style='color:#14213D;margin:0;font-size:1.75rem'>Intelligent Oil Consumption Monitoring</h1><div style='color:#64748b'>Data analytics · Machine learning · Operational decision support</div></div><div style='text-align:right;color:#64748b;font-size:.85rem'>SQLite connected<br>"+str(len(org_names))+" organisations</div></div>",unsafe_allow_html=True)
st.divider()
f1,f2,f3=st.columns([1.4,1.1,1.0])
with f1: selected=st.multiselect('Organisations',org_names,default=org_names[:min(5,len(org_names))])
with f2: start_date=st.date_input('From',value=data.Date.min().date())
with f3: end_date=st.date_input('To',value=data.Date.max().date())
if start_date>end_date: st.error('Start date must be on or before end date.'); st.stop()
filtered=data[(data.Company.isin(selected))&(data.Date.dt.date>=start_date)&(data.Date.dt.date<=end_date)].copy()
data_signature=int(pd.util.hash_pandas_object(filtered[['Company','Date','Litres','TotalCost','Oil Cost','Transportation Cost']],index=False).sum()) if not filtered.empty else 0
if filtered.empty: st.warning('No records match the selected organisations and reporting period.'); st.stop()

# Header KPIs
m=summary_metrics(filtered)
st.markdown('### Performance overview')
kpis=st.columns(7)
for col,label,value in zip(kpis,['Oil consumption','Oil expenses','Oil cost share','Employee cost','Transport cost','Other costs','Total operating cost'],[f"{m['litres']:,.0f} L",f"৳{m['oil_cost']:,.0f}",f"{m['oil_pct']:.1f}%",f"৳{m['employee_cost']:,.0f}",f"৳{m['transport_cost']:,.0f}",f"৳{m['other_cost']:,.0f}",f"৳{m['total_cost']:,.0f}"]): col.metric(label,value)

# Compact analytics sections
tab_overview,tab_statistics,tab_ai,tab_reports,tab_data=st.tabs(['📊 Comparative dashboard','📈 Statistical analysis','🤖 AI insights & optimisation','📄 PDF reports','🗂️ Data quality & imports'])

with tab_overview:
    comp=compare_companies(filtered)
    st.markdown('#### Organisation benchmark')
    left,right=st.columns([1.05,1.45],gap='medium')
    with left:
        show_cols=['Company','Days','Litres','Avg_Daily_Litres','Oil_Cost','Employee_Cost','Transportation_Cost','Other_Costs','Total_Cost','Oil_Cost_%']
        if 'Production_Output' in comp.columns: show_cols += ['Production_Output','Litres_per_Production_Unit','Cost_per_Production_Unit']
        show=comp[show_cols].copy()
        show=show.rename(columns={'Company':'Organisation','Avg_Daily_Litres':'Avg daily L','Oil_Cost':'Oil cost','Employee_Cost':'Employee','Transportation_Cost':'Transport','Other_Costs':'Other','Total_Cost':'Total cost','Oil_Cost_%':'Oil %','Production_Output':'Production','Litres_per_Production_Unit':'L / production unit','Cost_per_Production_Unit':'Cost / production unit'})
        st.dataframe(show.style.format({'Litres':'{:,.1f}','Oil cost':'৳{:,.0f}','Employee':'৳{:,.0f}','Transport':'৳{:,.0f}','Other':'৳{:,.0f}','Total cost':'৳{:,.0f}','Oil %':'{:.1f}%'}),use_container_width=True,hide_index=True,height=300)
    with right:
        metric=st.selectbox('Chart metric',['Litres','Oil_Cost','Employee_Cost','Transportation_Cost','Other_Costs','Total_Cost','Oil_Cost_%'],format_func=lambda x:{'Litres':'Oil consumption (L)','Oil_Cost':'Oil expense (BDT)','Employee_Cost':'Employee cost (BDT)','Transportation_Cost':'Transportation cost (BDT)','Other_Costs':'Other costs (BDT)','Total_Cost':'Total operating cost (BDT)','Oil_Cost_%':'Oil expense share (%)'}[x])
        fig=px.bar(comp,x='Company',y=metric,color='Company',text_auto='.2s',title='Selected metric by organisation')
        fig.update_layout(height=300,showlegend=False,margin=dict(l=10,r=10,t=45,b=10),xaxis_title='',yaxis_title='')
        st.plotly_chart(fig,use_container_width=True)
    st.markdown('#### Cost structure and daily trends')
    c1,c2=st.columns(2)
    with c1:
        cost_long=filtered.groupby('Company')[COSTS].sum().reset_index().melt('Company',var_name='Cost category',value_name='BDT')
        fig=px.bar(cost_long,x='Company',y='BDT',color='Cost category',barmode='stack',title='Operating cost breakdown')
        fig.update_layout(height=310,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    with c2:
        daily=filtered.groupby(['Date','Company'],as_index=False).agg(Litres=('Litres','sum'),TotalCost=('TotalCost','sum'))
        ymetric=st.selectbox('Daily trend',['Litres','TotalCost'],format_func=lambda x:'Oil consumption (L)' if x=='Litres' else 'Total cost (BDT)')
        fig=px.line(daily,x='Date',y=ymetric,color='Company',markers=True,title='Daily operating trend')
        fig.update_layout(height=310,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    st.caption('Comparisons use the selected reporting period. Different production scales may make raw totals unsuitable as efficiency rankings.')

with tab_statistics:
    st.markdown('#### Descriptive statistics')
    stats=descriptive_statistics(filtered)
    a,b=st.columns([1.2,1])
    with a: st.dataframe(stats.style.format('{:,.2f}'),use_container_width=True,height=330)
    with b:
        hist_metric=st.selectbox('Distribution metric',['Litres','Oil Cost','Employee Cost','Transportation Cost','Other Costs','TotalCost'])
        fig=px.histogram(filtered,x=hist_metric,color='Company',marginal='box',barmode='overlay',opacity=.75,title=f'{hist_metric} distribution')
        fig.update_layout(height=330,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    st.markdown('#### Correlation (pooled selected records)')
    corr_cols=['Litres','Oil Rate','Oil Cost','Employee Cost','Transportation Cost','Other Costs','TotalCost']
    corr=filtered[corr_cols].corr(numeric_only=True)
    fig=px.imshow(corr,text_auto='.2f',zmin=-1,zmax=1,color_continuous_scale='RdBu',title='Pearson correlation matrix')
    fig.update_layout(height=480,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    st.caption('Correlation describes linear association only; it does not establish causation. Missing dates are not treated as zero.')

with tab_ai:
    st.markdown("<div style='background:#f2efff;border:1px solid #ddd6fe;border-radius:14px;padding:12px 16px;margin-bottom:12px'><b style='color:#5b21b6'>AI INSIGHTS, WARNINGS & OPTIMISATION CENTRE</b><div style='color:#5b6475;font-size:.85rem'>Model predictions, statistical anomaly flags, and operational actions are kept separate from descriptive analytics.</div></div>",unsafe_allow_html=True)
    anomaly_result=anomaly_assessment(filtered)
    findings=anomaly_result['findings']
    coverage=anomaly_result['coverage']
    evaluated_count=anomaly_result['evaluated_organisations']
    insufficient_names=[f"{c['Company']} ({c['observations']} days)" for c in coverage if c['insufficient']]
    if coverage:
        total_days=sum(c['observations'] for c in coverage)
        total_checks=sum(c['metric_checks'] for c in coverage)
        iso_count=sum(1 for c in coverage if c['isolation_forest'])
        st.caption(f"Anomaly screening coverage: {total_days} organisation-day records · {evaluated_count}/{len(coverage)} organisations evaluated · {total_checks} univariate metric checks · Isolation Forest applied to {iso_count} organisation(s).")
    col_a,col_b=st.columns([1.1,1])
    with col_a:
        st.markdown('#### Intelligent warnings')
        if not findings:
            if evaluated_count:
                st.success('No anomaly candidates crossed the configured screening thresholds for the evaluated organisations. This does not prove that every record is normal.')
            else:
                st.info('Insufficient observations to evaluate anomalies. At least 8 usable daily records are needed for univariate checks; 20 complete daily records are needed for the multivariate Isolation Forest screen.')
        elif insufficient_names:
            st.info('Some organisations were too small for anomaly evaluation: ' + ', '.join(insufficient_names))
        for f in findings[:12]:
            colour='#dc2626' if f['Severity']=='High' else '#d97706'
            with st.container(border=True):
                st.markdown(f"**{f['Company']} · {f['Metric']}**  <span style='color:{colour};font-weight:700'>[{f['Severity']}]</span>",unsafe_allow_html=True)
                st.caption(f"{f['Date']} | Observed: {f['Observed']:,.2f} | Historical median: {f['Expected']:,.2f} | Method: {f['Method']}")
                if f.get('Contributors'): st.caption('Variables contributing to the unusual profile: ' + f['Contributors'])
                st.write(f['Explanation'])
                st.markdown('**Suggested checks**')
                for action in actions_for(f['Metric']): st.markdown(f'- {action}')
    with col_b:
        st.markdown('#### Predictive insights')
        forecast_company=st.selectbox('Forecast organisation',org_names,key='forecast_org')
        forecast_target=st.selectbox('Forecast target',['Litres','TotalCost','Oil Cost','Employee Cost','Transportation Cost','Other Costs'])
        # Forecasts use all imported history for this organisation, independently
        # of the dashboard's comparison-company and reporting-date filters.
        forecast_history=data[data.Company==forecast_company].copy()
        forecast_signature=int(pd.util.hash_pandas_object(forecast_history[['Company','Date',forecast_target]],index=False).sum()) if not forecast_history.empty else 0
        if st.button('Train, evaluate & forecast',key='forecast_button'):
            res=train_forecast(forecast_history,forecast_company,forecast_target,7)
            st.session_state['forecast_result']=(forecast_company,forecast_target,forecast_signature,res)
        stored=st.session_state.get('forecast_result')
        if stored and stored[0]==forecast_company and stored[1]==forecast_target and stored[2]==forecast_signature:
            res=stored[3]
            if res['status']!='ok': st.warning(res['message'])
            else:
                st.metric('Selected model',res['model']); q1,q2,q3=st.columns(3); q1.metric('MAE',f"{res['mae']:.2f}"); q2.metric('RMSE',f"{res['rmse']:.2f}"); q3.metric('R²',f"{res['r2']:.3f}")
                st.caption(f"{res['n']} daily observations ({res['history_start']:%Y-%m-%d} to {res['history_end']:%Y-%m-%d}) · {res['training']} training / {res['holdout']} chronological test records · baseline MAE {res['baseline_mae']:.2f} · {'beats' if res['beats_baseline'] else 'does not beat'} baseline")
                st.info(res['reliability_note'])
                fig=go.Figure(); hist=forecast_history.groupby('Date',as_index=False)[forecast_target].sum().tail(30)
                fig.add_trace(go.Scatter(x=hist.Date,y=hist[forecast_target],mode='lines+markers',name='Observed'))
                fig.add_trace(go.Scatter(x=res['forecast'].Date,y=res['forecast'].Predicted,mode='lines+markers',name='Forecast',line=dict(dash='dash')))
                fig.update_layout(height=260,margin=dict(l=5,r=5,t=20,b=5)); st.plotly_chart(fig,use_container_width=True)
                fi=res.get('feature_importance')
                if fi is not None:
                    st.caption('Model feature contribution (relative importance for Random Forest; absolute coefficient magnitude for Ridge):')
                    figfi=px.bar(fi,x='Importance',y='Feature',orientation='h')
                    figfi.update_layout(height=150,margin=dict(l=5,r=5,t=5,b=5)); st.plotly_chart(figfi,use_container_width=True)
                st.caption('Point forecasts are estimates, not guarantees or formal prediction intervals.')
        else: st.info(f"Select any imported organisation and train a model. Forecasting uses all available history for that organisation, regardless of the dashboard comparison filters. At least 8 valid daily observations are required; Random Forest is added when 20 or more are available. Available records: {len(forecast_history)}.")
    st.divider(); st.markdown('#### Organisation clustering')
    clustered,msg=cluster_companies(filtered)
    if msg: st.caption(msg)
    else:
        st.dataframe(clustered[['Company','Avg_Daily_Litres','Oil_Cost_%','Avg_Oil_Rate','Cluster']],use_container_width=True,hide_index=True)
        st.caption('Exploratory K-Means clustering on standardised average daily litres, oil cost share, and average oil rate; clusters are not quality rankings.')
    st.divider(); st.markdown('#### Hypothetical cost-reduction simulator')
    st.caption('Scenario arithmetic only — not an ML prediction or guaranteed saving.')
    totals={k:float(filtered[k].sum()) for k in COSTS}
    s1,s2,s3,s4=st.columns(4)
    reductions={}
    for col,key,label in zip([s1,s2,s3,s4],COSTS,['Oil reduction %','Employee reduction %','Transport reduction %','Other reduction %']):
        reductions[key]=col.slider(label,0,50,0,1,key='sim_'+key)
    rows,scenario=simulate_savings(totals,reductions,(end_date-start_date).days+1)
    st.dataframe(pd.DataFrame(rows).style.format({'Current Cost':'৳{:,.0f}','Reduction %':'{:.0f}%','Hypothetical Savings':'৳{:,.0f}','Revised Cost':'৳{:,.0f}'}),use_container_width=True,hide_index=True)
    sc1,sc2,sc3,sc4=st.columns(4); sc1.metric('Potential savings in period',f"৳{scenario['savings']:,.0f}"); sc2.metric('Monthly equivalent',f"৳{scenario['monthly_savings']:,.0f}"); sc3.metric('Annualised equivalent',f"৳{scenario['annualised_savings']:,.0f}"); sc4.metric('Revised category costs',f"৳{scenario['revised_cost']:,.0f}")
    st.session_state['scenario_result']=scenario

with tab_reports:
    st.markdown('#### Generate an evidence-based PDF report')
    st.write(f"Selected organisations: {', '.join(selected)}")
    st.write(f'Reporting period: {start_date} to {end_date} · {len(filtered)} daily organisation records')
    report_findings=anomaly_findings(filtered)
    forecast_dict={}
    for company in selected:
        saved=st.session_state.get('forecast_result')
        if saved and saved[0]==company and saved[2]==int(pd.util.hash_pandas_object(data[data.Company==company][['Company','Date',saved[1]]],index=False).sum()): forecast_dict[company]=saved[3]
    scenario=st.session_state.get('scenario_result')
    if st.button('Generate PDF report',type='primary'):
        pdf=build_pdf(filtered,selected,f'{start_date} to {end_date}',report_findings,forecast_dict,scenario)
        st.session_state.pdf_bytes=pdf
    if st.session_state.get('pdf_bytes'):
        st.download_button('Download PDF report',st.session_state.pdf_bytes,file_name='intelligent_oil_monitor_report.pdf',mime='application/pdf',use_container_width=True)
    st.caption('The report uses the selected database records and available analytical outputs. Forecast results are included only when trained in this session; unsupported metrics are not fabricated.')

with tab_data:
    st.markdown('#### Data quality checks')
    q1,q2,q3,q4=st.columns(4)
    cost_sum=filtered['Oil Cost']+filtered['Employee Cost']+filtered['Transportation Cost']+filtered['Other Costs']
    recon=pd.Series(np.isclose(filtered.TotalCost,cost_sum,rtol=.001,atol=1.0),index=filtered.index)
    pct_expected=(filtered['Oil Cost']/filtered.TotalCost.replace(0,float('nan'))*100)
    pct_ok=pd.Series(np.isclose(filtered['Oil Cost %'],pct_expected,rtol=.01,atol=.25,equal_nan=False),index=filtered.index)
    q1.metric('Records in selection',f'{len(filtered):,}'); q2.metric('Cost reconciliation pass',f'{int(recon.sum())}/{len(recon)}'); q3.metric('Oil % check pass',f'{int(pct_ok.fillna(False).sum())}/{len(pct_ok)}'); q4.metric('Organisations',len(selected))
    issues=filtered.loc[~(recon & pct_ok.fillna(False)),['Company','Date','TotalCost','Oil Cost','Oil Cost %','Employee Cost','Transportation Cost','Other Costs']].copy()
    if issues.empty: st.success('Selected records pass the displayed cost reconciliation and oil percentage checks.')
    else: st.warning('Some source rows do not reconcile. The system flags these values and does not silently rewrite them.'); st.dataframe(issues,use_container_width=True,hide_index=True)
    st.markdown('#### Imported daily records'); st.dataframe(filtered.sort_values(['Company','Date'],ascending=[True,False]),use_container_width=True,height=350,hide_index=True)
    st.markdown('#### Import history'); hist=import_history(uid)
    if not hist.empty: st.dataframe(hist,use_container_width=True,hide_index=True)
    st.download_button('Download selected records as CSV',filtered.to_csv(index=False).encode('utf-8'),file_name='oil_monitor_selected_records.csv',mime='text/csv')

st.caption('Academic decision-support system · Anomaly flags are not diagnoses · Forecast reliability depends on data volume, quality, and operating conditions.')
