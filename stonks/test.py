#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
from . import simulation
from . import strategy as st

## Main function
def main():
  toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  fromDate = toDate - datetime.timedelta(days=5)
  # fromDate = toDate.replace(year=(toDate.year - 1))

  sim = simulation.Simulation(fromDate, toDate)

  # st.strategy.silent = True
  sim.setup(st.strategy, initialCapital=25000)
  sim.run()
  print(sim.report())
  sim.plot()


if __name__ == "__main__":
  main()
