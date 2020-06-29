#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import alpaca
import datetime
import numpy as np
import sys

class Simulation:

  ## Initialize simulation by loading the appropriate data
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @param symbol to load, None will load all symbols from watchlist
  def __init__(self, fromDate, toDate=datetime.date.today(), symbol=None):
    self.api = alpaca.Alpaca()
    self.strategy = None
    self.cash = 0
    self.securities = {}
    self.timestamps = self.api.getTimestamps(fromDate, toDate)
    if symbol:
        self.securities[symbol] = self.api.loadSymbol(symbol, self.timestamps)
    else:
      symbols = self.api.getSymbols()
      for symbol in symbols:
        self.securities[symbol] = self.api.loadSymbol(symbol, self.timestamps)
    if len(self.securities.keys()) == 0:
      print("No symbols loaded")
      sys.exit(1)

  ## Setup the initial conditions of the simulation
  #  @param strategy object to simulate
  #  @param initialCapital to start the simulation with
  def setup(self, strategy, initialCapital=10000):
    self.strategy = strategy
    self.cash = np.float64(initialCapital)
    self.strategy._setSecurities(self.securities)

  def run(self):
    for timestamp in self.timestamps[0]:
      print("SIM run", timestamp)
      self.strategy._setCurrentTimestamp(timestamp)
      # self.strategy.processOrders()
      # self.strategy.nextMinute()
  
  def report(self):
    return "Ending value: ${:.2f}".format(self.cash)