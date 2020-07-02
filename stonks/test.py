#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
from . import simulation
from . import strategy as st

## Setup a test over the past year, run, print report, and plot portfolio
#  @param strategy to test
#  @param symbol of strategy to test on, None for all from watchlist
def quickTest(strategy, symbol=None):
  toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  fromDate = toDate.replace(year=(toDate.year - 1))
  sim = simulation.Simulation(fromDate, toDate, symbol=symbol)
  sim.setup(strategy)
  sim.run()
  print(sim.report())
  sim.plot()


## Main function
def main():
  st.strategy.silent = True
  quickTest(st.strategy)


if __name__ == "__main__":
  main()
