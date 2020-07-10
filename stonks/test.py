#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
import importlib
from . import simulation
from . import strategy as st

## Setup a test over the past year, run, print report, and plot portfolio
#  @param symbol of strategy to test on, None for all from watchlist
def quickTest(symbol=None):
  toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  fromDate = toDate.replace(year=(toDate.year - 1))
  sim = simulation.Simulation(fromDate, toDate, symbol=symbol)
  st.strategy.walkForward = False
  sim.run(st.strategy)
  sim.printReport()
  sim.plot(symbol=symbol)

## Reload the strategy module and run a test, primarily for interactive development
#  @param sim simulation object
def reloadAndTest(sim):
  importlib.reload(st)
  sim.setup(st.strategy)
  print("Elapsed test duration: {}".format(
      sim.run(progressBar=(not st.strategy.silent))))
  sim.printReport()


## Main function
def main():
  st.strategy.silent = True
  quickTest(symbol="TSLA")


if __name__ == "__main__":
  main()
