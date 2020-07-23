#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
from . import simulation
from . import strategy as st

## Setup a test over the past 10 weeks, optimize a parameter
#  @param strategy to test
#  @param symbol of strategy to test on, None for all from watchlist
def quickTest(strategy, symbol=None):
  toDate = datetime.date.today() - datetime.timedelta(days=1)
  # toDate = datetime.date(2020,4,30)
  fromDate = toDate - datetime.timedelta(weeks=2)
  # fromDate = datetime.date(2020, 1, 1)
  sim = simulation.Simulation(fromDate, toDate, symbol=symbol,
                              initialCapital=20000, preStart=100)
  # initialSecurities = {"TSLA": 0, "cash": 10000}
  # calendar = sim.api.getCalendar(fromDate, fromDate + datetime.timedelta(weeks=2))
  # sortedReports = sim.optimize(strategy, calendar=calendar, initialSecurities=initialSecurities)
  print(f"{type(st.strategy).__name__} "
        f"{fromDate} to {toDate} ")
  for param, value in st.strategy.params.items():
    if param in st.strategy.paramsAdj:
      print(f"{param}={st.strategy.paramsAdj[param]}")
    else:
      print(f"{param}={value}")
  sortedReports = sim.optimize(strategy, singleThreaded=True)
  print(f"{type(st.strategy).__name__} "
        f"{fromDate} to {toDate} ")
  for param, value in st.strategy.params.items():
    if param in st.strategy.paramsAdj:
      print(f"{param}={st.strategy.paramsAdj[param]}")
    else:
      print(f"{param}={value}")
  print("Top ten test cases")
  for report in sortedReports:
    print("{} P${:10.2f} S{:6.3f}".format(
      report["testCase"], report["profit"], report["sortino"]))

## Main function
def main():
  quickTest(st.strategy)  # , symbol="TSLA")


if __name__ == "__main__":
  main()
