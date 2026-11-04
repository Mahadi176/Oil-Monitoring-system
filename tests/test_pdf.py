import pandas as pd
from modules.pdf_generator import build_pdf

def test_pdf_contains_report_bytes():
    df=pd.DataFrame([{'Company':'Org A','Date':pd.Timestamp('2026-01-01'),'Litres':10,'TotalCost':1000,'Oil Cost':200,'Oil Cost %':20,'Employee Cost':400,'Transportation Cost':200,'Other Costs':200}])
    content=build_pdf(df,['Org A'],'2026-01-01 to 2026-01-01',[])
    assert content.startswith(b'%PDF') and len(content)>5000
