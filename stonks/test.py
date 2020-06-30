#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
import simulation
import strategy as st

## Main function
def main():
  # toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  # fromDate = toDate.replace(year=(toDate.year - 1))

  # toDate = datetime.date(2019, 12, 31)
  # fromDate = datetime.date(2017, 1, 1)
  # sim = simulation.Simulation(fromDate, toDate)
  
  toDate = datetime.date(2019, 12, 31)
  fromDate = datetime.date(2019, 12, 1)
  sim = simulation.Simulation(fromDate, toDate, symbol="TSLA")

  sim.setup(st.strategy, initialCapital=25000)
  sim.run()
  print(sim.report())
  sim.plot()
  # sim.plot(symbol="TSLA")f

if __name__ == "__main__":
  main()
