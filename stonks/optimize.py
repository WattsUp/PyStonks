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
  toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  fromDate = toDate - datetime.timedelta(weeks=10)
  sim = simulation.Simulation(fromDate, toDate, symbol=symbol)
  targetMetric = "sortino"
  # initialSecurities = {"TSLA": 0, "cash": 10000}
  # calendar = sim.api.getCalendar(fromDate, fromDate + datetime.timedelta(weeks=2))
  # sortedReports = sim.optimize(strategy, calendar=calendar, initialSecurities=initialSecurities)
  sortedReports = sim.optimize(strategy)#, singleThreaded=True)
  print("Top five test cases")
  for report in sortedReports:
    print("{} {}={:6.3f}".format(
      report["testCase"], targetMetric, report[targetMetric]))

## Main function
def main():
  quickTest(st.strategy, symbol="TSLA")


if __name__ == "__main__":
  main()
