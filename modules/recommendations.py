def actions_for(metric):
    mapping={
      'Litres':['Verify the daily reading and compare it with production output and operating hours.','Inspect equipment efficiency and transfer lines using approved safety procedures.','Review operating schedules and investigate possible leakage before drawing conclusions.'],
      'Oil Cost':['Check the recorded litres and unit oil rate; separate price effects from usage changes.','Review procurement timing and supplier invoices.','Compare oil cost per production unit where production data is available.'],
      'Transportation Cost':['Review delivery routes, vehicle utilisation, and trip scheduling.','Check fuel efficiency and maintenance records.','Compare cost per kilometre if distance data is recorded.'],
      'Employee Cost':['Review overtime, shift scheduling, and resource allocation.','Check whether workload or production levels changed in the same period.'],
      'Other Costs':['Inspect procurement and maintenance invoices for the flagged period.','Identify recurring purchases and compare them with operational activity.'],
      'TotalCost':['Break down the increase by cost category before choosing an intervention.','Compare workload, operating hours, and production before interpreting the change.'],
      'Multivariate operating profile':['Review the listed contributing metrics on the flagged date and compare them with source invoices or operating logs.','Check whether production volume, operating hours, staffing, or delivery activity changed on that date.','Confirm the source entries before taking corrective action; a multivariate flag is an investigation lead, not proof of waste.']}
    return mapping.get(metric,['Verify the source record and review relevant operational context.'])
