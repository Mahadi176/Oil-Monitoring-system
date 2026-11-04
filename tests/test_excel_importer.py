from io import BytesIO
import pandas as pd
from modules.excel_importer import load_excel, company_from_file

def make_xlsx():
    df=pd.DataFrame({'Date':['01/11/2026','02/11/2026'],'Company':['Test Co','Test Co'],'TotalCost':[1000,1100],'Litres':[10,11],'Oil Rate':[100,100],'Oil Cost ':[500,550],'Oil Cost %':[50,50],'Employee Cost':[200,200],'Transportation Cost':[200,250],'Other Costs':[100,100]})
    b=BytesIO(); df.to_excel(b,index=False); b.seek(0); return b

def test_load_xlsx_and_trailing_space_column():
    df,errors=load_excel(make_xlsx())
    assert not errors
    assert len(df)==2 and df['Oil Cost'].iloc[0]==500
    assert company_from_file(df,'test.xlsx')=='Test Co'

def test_financial_reconciliation_flags_without_mutating():
    b=make_xlsx(); raw=pd.read_excel(b); raw.loc[0,'TotalCost']=900
    b2=BytesIO(); raw.to_excel(b2,index=False); b2.seek(0)
    df,errors=load_excel(b2)
    assert not errors
    assert not bool(df.loc[0,'_cost_reconciles'])
    assert df.loc[0,'TotalCost']==900

def test_monthly_total_row_removed_and_fraction_percent_normalised():
    df=pd.DataFrame({
        'Date':['01/11/2026','02/11/2026',None],
        'Company':['Test Co','Test Co','Monthly Total'],
        'TotalCost':[1000,1000,2000], 'Litres':[10,10,20], 'Oil Rate':[100,100,None],
        'Oil Cost':[200,200,400], 'Oil Cost %':[.2,.2,.2], 'Employee Cost':[400,400,800],
        'Transportation Cost':[200,200,400], 'Other Costs':[200,200,400]
    })
    b=BytesIO(); df.to_excel(b,index=False); b.seek(0)
    clean,errors=load_excel(b)
    assert not errors and len(clean)==2
    assert clean['Oil Cost %'].tolist()==[20.0,20.0]
    assert clean['_oil_pct_valid'].all()
