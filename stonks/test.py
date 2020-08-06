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
  fromDate = datetime.date(2020,1,1)
  # fromDate = datetime.date(2017, 1, 1)
  toDate = datetime.date(2020, 7, 31)
  # toDate = datetime.date(2019, 12, 31)
  # toDate = datetime.date.today() - datetime.timedelta(days=1)
  # fromDate = toDate  - datetime.timedelta(days=3)
  sim = simulation.Simulation(
      fromDate,
      toDate,
      symbol=symbol,
      initialCapital=30000,
      preStart=100)
  st.strategy.walkForward = False
  print(f"{type(st.strategy).__name__} "
        f"{fromDate} to {toDate} "
        f"WF={st.strategy.walkForward} {st.strategy.optimizeTarget} {st.strategy.optimizeDuration}")
  for param, value in st.strategy.params.items():
    if param in st.strategy.paramsAdj and st.strategy.walkForward:
      print(f"{param}={st.strategy.paramsAdj[param]}")
    else:
      print(f"{param}={value}")
  sim.run(st.strategy)
  for security in st.strategy.portfolio.securities.values():
    print(f"{security.symbol:5} Lifetime profit ${security.lifeTimeProfit:10.2f} W/L${security.wins:7.2f}/${security.losses:7.2f}")
  print(f"{type(st.strategy).__name__} "
        f"{fromDate} to {toDate} "
        f"WF={st.strategy.walkForward} {st.strategy.optimizeTarget} {st.strategy.optimizeDuration}")
  for param, value in st.strategy.params.items():
    if param in st.strategy.paramsAdj and st.strategy.walkForward:
      print(f"{param}={st.strategy.paramsAdj[param]}")
    else:
      print(f"{param}={value}")
  sim.printReport()
  print(
    f"Winning sells: {len(st.strategy.portfolio.winners)}, losing sells: {len(st.strategy.portfolio.losers)}")
  sim.plot(symbol=symbol)

## Setup a simulation object with standard settings
#  @param symbol of strategy to test on, None for all from watchlist
def quickSetup(symbol=None):
  toDate = datetime.date.today()
  fromDate = datetime.date(2020, 7, 20)
  sim = simulation.Simulation(
      fromDate,
      toDate,
      symbol=symbol,
      initialCapital=30000,
      preStart=100)
  return sim

## Reload the strategy module and run a test, primarily for interactive development
#  @param sim simulation object
def reloadAndTest(sim):
  importlib.reload(st)
  st.strategy.silent = True
  print(f"{type(st.strategy).__name__} "
        f"WF={st.strategy.walkForward}")
  for param, value in st.strategy.params.items():
    if param in st.strategy.paramsAdj and st.strategy.walkForward:
      print(f"{param}={st.strategy.paramsAdj[param]}")
    else:
      print(f"{param}={value}")
  sim.run(st.strategy)
  print(f"{type(st.strategy).__name__} "
        f"WF={st.strategy.walkForward}")
  for param, value in st.strategy.params.items():
    if param in st.strategy.paramsAdj and st.strategy.walkForward:
      print(f"{param}={st.strategy.paramsAdj[param]}")
    else:
      print(f"{param}={value}")
  sim.printReport()
  print(
    f"Winning sells: {len(st.strategy.portfolio.winners)}, losing sells: {len(st.strategy.portfolio.losers)}")
  sim.plot(symbol="TSLA")


## Main function
def main():
  st.strategy.silent = True
  quickTest()  # symbol="TSLA")


if __name__ == "__main__":
  main()
