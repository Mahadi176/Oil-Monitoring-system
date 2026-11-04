from modules.optimisation import simulate_savings

def test_scenario_uses_selected_period_length():
    rows,result=simulate_savings({'Oil Cost':1000,'Employee Cost':1000,'Transportation Cost':1000,'Other Costs':1000},{'Oil Cost':10},period_days=30)
    assert result['savings']==100
    assert result['monthly_savings']>90 and result['annualised_savings']==result['monthly_savings']*12
