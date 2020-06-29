#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import math

class Strategy:
  ## Initialize the strategy
  def __init__(self):
    print("strategy")
    self.timestamp = {}
    self.orders = []

  ## Set the securities used by the strategy
  #  @param securities dictionary of symbol key, alpaca.Data value
  def _setSecurities(self, securities):
    self.securities = securities

  ## Set the current index of the dataFrame
  #  @param timestamp of the current index
  def _setCurrentTimestamp(self, timestamp):
    self.timestamp = timestamp
    for security in self.securities.values():
      security._setCurrentIndex(timestamp)

  ## Operate on the next minute data, override this
  def nextMinute(self):
    pass

  ## Sell shares of a security
  #  @param security object to sell
  #  @param shares number of shares, None to calculate from value
  #  @param value value of shares to sell (based on current minute closing price)
  def sell(self, security, shares=None, value=None):
    if not shares:
      shares = math.floor(value / security.minute[0].close)
    self.orders.append(
      {"security": security, "shares": shares, "side": "sell"})


  ## Buy shares of a security
  #  @param security object to buy
  #  @param shares number of shares, None to calculate from value
  #  @param value value of shares to buy (based on current minute closing price)
  def buy(self, security, shares=None, value=None):
    if not shares:
      shares = math.floor(value / security.minute[0].close)
    self.orders.append({"security": security, "shares": shares, "side": "buy"})

  ## Log a message
  #  @param msg message to log
  #  @param dt datetime object to timestamp with
  def log(self, msg, dt=None):
    dt = dt or self.timestamp
    print("{} {}".format(dt, msg))

class Crossover(Strategy):
  params = {"long": 200, "short": 50}

  def nextMinute(self):
    pass
    # self.log("Crossover")


## If customStrategy exists, use it, else use crossover strategy
import imp
try:
  imp.find_module("customStrategy")
  import customStrategy
  strategy = customStrategy.strategy
except ImportError:
  strategy = Crossover()
