def simulate_savings(totals, reductions, period_days=30):
    rows=[]; total=0.0; base=0.0
    for key,label in [('Oil Cost','Oil'),('Employee Cost','Employee'),('Transportation Cost','Transportation'),('Other Costs','Other')]:
        amount=float(totals.get(key,0) or 0); pct=float(reductions.get(key,0) or 0)
        pct=min(100,max(0,pct)); saving=amount*pct/100
        rows.append({'Category':label,'Current Cost':amount,'Reduction %':pct,'Hypothetical Savings':saving,'Revised Cost':amount-saving})
        total+=saving; base+=amount
    days=max(1,int(period_days)); monthly=total/days*30.4375
    return rows,{'savings':total,'revised_cost':base-total,'monthly_savings':monthly,'annualised_savings':monthly*12}
