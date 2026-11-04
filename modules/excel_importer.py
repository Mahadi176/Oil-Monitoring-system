from __future__ import annotations
from io import BytesIO
import re
import numpy as np
import pandas as pd

REQUIRED=['Date','TotalCost','Litres','Oil Rate','Oil Cost','Oil Cost %','Employee Cost','Transportation Cost','Other Costs']
OPTIONAL=['Production Output','Operating Hours','Number of Employees','Number of Vehicles','Distance Travelled','Electricity Consumption']
ALIASES={'totalcost':'TotalCost','total cost':'TotalCost','litres':'Litres','liters':'Litres','oil rate':'Oil Rate','oil cost':'Oil Cost','oil cost %':'Oil Cost %','oil cost percentage':'Oil Cost %','employee cost':'Employee Cost','transportation cost':'Transportation Cost','transport cost':'Transportation Cost','other costs':'Other Costs','production output':'Production Output','operating hours':'Operating Hours','number of employees':'Number of Employees','number of vehicles':'Number of Vehicles','distance travelled':'Distance Travelled','distance traveled':'Distance Travelled','electricity consumption':'Electricity Consumption','company':'Company','date':'Date'}

def _norm(x): return re.sub(r'\s+',' ',str(x).strip().lower())

def load_excel(uploaded_file):
    if hasattr(uploaded_file,'seek'): uploaded_file.seek(0)
    raw=pd.read_excel(uploaded_file,engine='openpyxl')
    rename={c:ALIASES.get(_norm(c),str(c).strip()) for c in raw.columns}
    df=raw.rename(columns=rename)
    # Detect summary rows, not legitimate daily records.
    if 'Date' not in df: return df, ['Missing required column: Date']
    # Summary rows may label the Company cell while leaving Date blank (common Excel layout).
    labels=df.astype(str).apply(lambda col: col.str.strip().str.lower().str.fullmatch(r'(?:total|monthly total|grand total|summary)',na=False))
    summary=labels.any(axis=1)
    df=df.loc[~summary].copy()
    errors=[f'Missing required column: {c}' for c in REQUIRED if c not in df.columns]
    if errors: return df,errors
    df['Date']=pd.to_datetime(df['Date'],errors='coerce',dayfirst=True)
    if df['Date'].isna().any(): errors.append(f"{int(df['Date'].isna().sum())} row(s) have invalid or missing dates.")
    numeric=REQUIRED[1:]+[c for c in OPTIONAL if c in df]
    for c in numeric: df[c]=pd.to_numeric(df[c],errors='coerce')
    # Excel percentage cells often store 7.5% as 0.075. Standardise to percentage points.
    df['_oil_pct_scaled_from_fraction']=False
    expected_pct=np.where(df['TotalCost']>0,df['Oil Cost']/df['TotalCost']*100,np.nan)
    valid_pct=df['Oil Cost %'].dropna()
    if len(valid_pct) and valid_pct.between(0,1).all() and np.nanmedian(expected_pct)>1:
        df['Oil Cost %']=df['Oil Cost %']*100
        df['_oil_pct_scaled_from_fraction']=True
    for c in numeric:
        bad=df[c].isna()
        if bad.any(): errors.append(f'{c}: {int(bad.sum())} missing/non-numeric value(s).')
        if (df[c].dropna()<0).any(): errors.append(f'{c}: negative values are not allowed.')
    if 'Company' in df:
        df['Company']=df['Company'].astype('string').str.strip()
        names=df['Company'].dropna().unique()
        if len(names)>1: errors.append('One Excel file must contain records for exactly one organisation.')
        # An empty Company column is allowed; the filename then supplies the organisation name.
    if df['Date'].duplicated().any(): errors.append('Duplicate dates found within this file. Resolve them before importing.')
    # Report reconciliation warnings; do not rewrite source values.
    total_parts=df['Oil Cost']+df['Employee Cost']+df['Transportation Cost']+df['Other Costs']
    df['_cost_difference']=df['TotalCost']-total_parts
    df['_oil_pct_expected']=np.where(df['TotalCost']>0,df['Oil Cost']/df['TotalCost']*100,0)
    df['_cost_reconciles']=np.isclose(df['TotalCost'],total_parts,rtol=0.001,atol=1.0)
    df['_oil_pct_valid']=np.isclose(df['Oil Cost %'],df['_oil_pct_expected'],rtol=0.01,atol=0.25)
    return df.reset_index(drop=True),errors

def company_from_file(df,filename):
    if 'Company' in df and df['Company'].dropna().size:
        return str(df['Company'].dropna().iloc[0]).strip()
    stem=filename.rsplit('.',1)[0]
    return re.sub(r'[-_](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec).*$', '', stem, flags=re.I).replace('_',' ').replace('-',' ').strip()
