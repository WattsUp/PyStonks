#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

class Strategy:
  ## Initialize the strategy
  def __init__(self):
    print("strategy")
    self.timestamp = {}

  ## Set the securities used by the strategy
  #  @param securities dictionary of symbol key, alpaca.Data value
  def _setSecurities(self, securities):
    self.securities = securities

  ## Set the current index of the dataFrame
  #  @param timestamp of the current index
  def _setCurrentTimestamp(self, timestamp):
    self.timestamp = timestamp
    for security in self.securities:
      security._setCurrentIndex(timestamp)

  ## Operate on the next minute data, override this
  def nextMinute(self):
    pass

  ## Log a message
  #  @param msg message to log
  #  @param dt datetime object to timestamp with
  def log(self, msg, dt=None):
    dt = dt or self.timestamp
    print("{} {}".format(dt, msg))

class Crossover(Strategy):
  params = {"long": 200, "short": 50}

  def nextMinute(self):
    self.log("Crossover")


## If customStrategy exists, use it, else use crossover strategy
import imp
try:
  imp.find_module("customStrategy")
  import customStrategy
  strategy = customStrategy.strategy
except ImportError:
  strategy = Crossover()
