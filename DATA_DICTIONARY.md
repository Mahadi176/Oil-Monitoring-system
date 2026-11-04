# Data dictionary

| Excel field | Stored field | Meaning |
|---|---|---|
| Date | record_date | Local calendar date of the daily record |
| TotalCost | total_cost | Total operating cost in the workbook's currency (dashboard labels BDT) |
| Litres | litres | Daily oil consumption in litres |
| Oil Rate | oil_rate | Unit price per litre |
| Oil Cost | oil_cost | Daily oil expense |
| Oil Cost % | oil_cost_pct | Oil expense as a percentage of total cost |
| Employee Cost | employee_cost | Employee expense |
| Transportation Cost | transportation_cost | Transportation expense |
| Other Costs | other_costs | Other operating expenses |
| Optional fields | matching snake_case columns | Production and operational context, if available |

Company is obtained from the Company column when present, otherwise from the workbook filename.
