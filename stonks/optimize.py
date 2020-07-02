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
#  @param paramName to manipulate
#  @param paramRange to iterate through
#  @param symbol of strategy to test on, None for all from watchlist
def quickTest(strategy, paramName, paramRange, symbol=None):
  toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  fromDate = toDate - datetime.timedelta(weeks=10)
  sim = simulation.Simulation(fromDate, toDate, symbol=symbol)
  strategy.silent = True
  sim.optimize(strategy, paramName=paramName, paramRange=paramRange)

## Setup a test over the past 10 weeks, optimize two parameters
#  @param strategy to test
#  @param param1Name to manipulate
#  @param param1Range to iterate through
#  @param param2Name to manipulate
#  @param param2Range to iterate through
#  @param symbol of strategy to test on, None for all from watchlist
def quickTest2(strategy, param1Name, param1Range,
               param2Name, param2Range, symbol=None):
  toDate = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
  fromDate = toDate - datetime.timedelta(weeks=10)
  sim = simulation.Simulation(fromDate, toDate, symbol=symbol)
  strategy.silent = True
  sim.optimize2(
      strategy,
      param1Name=param1Name,
      param1Range=param1Range,
      param2Name=param2Name,
      param2Range=param2Range)


## Main function
def main():
  quickTest2(st.strategy, "long", range(10, 100, 10),
             "short", range(1, 20, 2), symbol="TSLA")


if __name__ == "__main__":
  main()
