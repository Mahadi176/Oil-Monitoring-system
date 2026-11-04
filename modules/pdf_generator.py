from __future__ import annotations
from io import BytesIO
from datetime import datetime
import pandas as pd
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def build_pdf(data: pd.DataFrame, selected, period_label, findings, forecast_results=None, scenario=None):
    pdf=FPDF(); pdf.set_auto_page_break(True,margin=14); pdf.add_page()
    def clean(value): return str(value).encode('latin-1','replace').decode('latin-1')
    def mc(value, height=5):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw,height,clean(value))
    def heading(value,size=11):
        pdf.set_x(pdf.l_margin); pdf.set_font('Helvetica','B',size); pdf.cell(0,8,clean(value),new_x='LMARGIN',new_y='NEXT')

    pdf.set_font('Helvetica','B',17); pdf.cell(0,11,'Intelligent Oil Monitoring & Optimisation Report',new_x='LMARGIN',new_y='NEXT')
    pdf.set_font('Helvetica',size=9); pdf.cell(0,6,f"Generated: {datetime.now():%Y-%m-%d %H:%M} | Period: {clean(period_label)}",new_x='LMARGIN',new_y='NEXT')
    mc('Organisations: '+', '.join(selected))
    mc('Interpretation note: observed anomalies are investigation signals, not proof of waste or equipment failure. Forecasts depend on available historical data.')
    heading('Executive summary',12)
    total=float(data.TotalCost.sum()) if not data.empty else 0
    litres=float(data.Litres.sum()) if not data.empty else 0
    oil=float(data['Oil Cost'].sum()) if not data.empty else 0
    mc(f'Records: {len(data)} | Organisations: {data.Company.nunique()} | Oil consumption: {litres:,.2f} L | Total operating cost: BDT {total:,.2f} | Oil cost share: {(oil/total*100 if total else 0):.2f}%')

    if not data.empty:
        # Actual-data charts are rendered into the report.
        chart=BytesIO(); agg_chart=data.groupby('Company')['Litres'].sum().sort_values(ascending=False)
        fig,ax=plt.subplots(figsize=(8,3.2)); agg_chart.plot(kind='bar',ax=ax); ax.set_ylabel('Litres'); ax.set_title('Oil consumption by organisation'); fig.tight_layout(); fig.savefig(chart,format='png',dpi=140); plt.close(fig); chart.seek(0)
        pdf.set_x(pdf.l_margin); pdf.image(chart,x=pdf.l_margin,w=pdf.epw); pdf.ln(2)
        trend=BytesIO(); fig,ax=plt.subplots(figsize=(8,3.0))
        for company,g in data.groupby('Company'):
            daily=g.groupby('Date')['Litres'].sum().sort_index(); ax.plot(daily.index,daily.values,label=str(company))
        ax.set_title('Daily oil consumption trend'); ax.set_ylabel('Litres'); ax.legend(fontsize=7); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(trend,format='png',dpi=140); plt.close(fig); trend.seek(0)
        pdf.set_x(pdf.l_margin); pdf.image(trend,x=pdf.l_margin,w=pdf.epw); pdf.ln(2)

        recon_total=data['Oil Cost']+data['Employee Cost']+data['Transportation Cost']+data['Other Costs']
        recon_pass=int((abs(data['TotalCost']-recon_total)<=1.0).sum())
        pct_expected=(data['Oil Cost']/data['TotalCost'].replace(0,float('nan'))*100)
        pct_pass=int(((data['Oil Cost %']-pct_expected).abs()<=.25).fillna(False).sum())
        heading('Data quality assessment')
        mc(f'Cost reconciliation within BDT 1 tolerance: {recon_pass}/{len(data)} records. Oil percentage check within 0.25 percentage points: {pct_pass}/{len(data)} records. These checks flag possible inconsistencies; source values are not rewritten.')
        heading('Organisation comparison')
        agg=data.groupby('Company').agg(Days=('Date','nunique'),Litres=('Litres','sum'),Oil=('Oil Cost','sum'),Employee=('Employee Cost','sum'),Transport=('Transportation Cost','sum'),Other=('Other Costs','sum'),Total=('TotalCost','sum')).reset_index()
        widths=[34,12,21,21,21,21,21,22]
        pdf.set_font('Helvetica','B',7)
        for h,w in zip(['Organisation','Days','Litres','Oil','Employee','Transport','Other','Total'],widths): pdf.cell(w,7,h,border=1)
        pdf.ln(); pdf.set_font('Helvetica',size=7)
        for _,r in agg.iterrows():
            vals=[r.Company,int(r.Days),f"{r.Litres:,.0f}",f"{r.Oil:,.0f}",f"{r.Employee:,.0f}",f"{r.Transport:,.0f}",f"{r.Other:,.0f}",f"{r.Total:,.0f}"]
            for v,w in zip(vals,widths): pdf.cell(w,6,clean(v)[:26],border=1)
            pdf.ln()
        heading('Cost-category totals')
        pdf.set_font('Helvetica',size=8)
        for metric in ['Oil Cost','Employee Cost','Transportation Cost','Other Costs']:
            mc(f'{metric}: BDT {data[metric].sum():,.2f} ({(data[metric].sum()/total*100 if total else 0):.2f}% of total cost)')
        heading('Statistical summary')
        pdf.set_font('Helvetica',size=8)
        for metric in ['Litres','Oil Cost','Employee Cost','Transportation Cost','Other Costs','TotalCost']:
            mc(f"{metric}: mean {data[metric].mean():,.2f}; median {data[metric].median():,.2f}; min {data[metric].min():,.2f}; max {data[metric].max():,.2f}; std {data[metric].std():,.2f}")

    pdf.add_page(); heading('Warnings and recommended actions',12); pdf.set_font('Helvetica',size=8)
    if not findings: mc('No statistical anomaly flags were produced for the selected data, or the available observations were insufficient.')
    action_map={'Litres':['Verify the reading and compare with production output and operating hours.','Inspect equipment and transfer lines using approved procedures.'],'Oil Cost':['Separate oil price effects from changes in litres consumed.','Review procurement timing and supplier invoices.'],'Transportation Cost':['Review routes, vehicle utilisation, and trip scheduling.'],'Employee Cost':['Review overtime and shift scheduling; do not infer that workforce reductions are warranted.'],'Other Costs':['Inspect procurement and maintenance invoices.'],'TotalCost':['Break down the increase by category and compare workload.']}
    for f in findings[:40]:
        pdf.set_font('Helvetica','B',9); mc(f"{f['Severity']} | {f['Company']} | {f['Metric']} | {f['Date']} | observed {f['Observed']:,.2f}, historical median {f['Expected']:,.2f}")
        pdf.set_font('Helvetica',size=8); mc(f['Explanation'],4)
        for action in action_map.get(f['Metric'],['Verify the source record and operating context.']): mc('Action to consider: '+action,4)
    heading('Forecasting and limitations'); pdf.set_font('Helvetica',size=8)
    if forecast_results:
        for company,res in forecast_results.items():
            if res.get('status')=='ok': mc(f"{company}: {res['target']} forecast with {res['model']}; MAE {res['mae']:.2f}; RMSE {res['rmse']:.2f}; R2 {res['r2']:.3f}; baseline MAE {res['baseline_mae']:.2f}.")
            else: mc(f"{company}: {res.get('message','Forecast unavailable')}")
    mc('Method: daily organisation-level records are aggregated from uploaded Excel data. Missing dates are not assumed to be zero. Forecast validation uses a chronological holdout and is compared with a training-period mean baseline. Small datasets may not support reliable ML. Correlation and anomaly detection do not establish causation.')
    if scenario: mc(f"Hypothetical cost-reduction scenario: savings BDT {scenario['savings']:,.2f} for selected reporting-period cost totals; monthly equivalent BDT {scenario['monthly_savings']:,.2f}; annualised equivalent BDT {scenario['annualised_savings']:,.2f}. This is a user-defined arithmetic scenario, not a prediction or guarantee.")
    return bytes(pdf.output())
