#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

from . import portfolio

class Strategy:
  params = {}
  paramsAdj = {}

  ## Initialize the strategy
  def __init__(self):
    self.portfolio = None
    self.timestamp = None
    self.silent = False

  ## Set the securities used by the strategy
  #  @param api alpaca object
  #  @param startDate of the simulation
  #  @param initialCapital to start the simulation with
  #  @param initialSecurities to start the simulations with
  def _setup(self, api, startDate, initialCapital, initialSecurities=None):
    self.portfolio = portfolio.Portfolio(
        api, startDate, initialCapital, self.orderUpdate)
    if initialSecurities:
      for symbol, shares in initialSecurities.items():
        self.portfolio.securities[symbol].shares = shares

  ## Operate on the next minute data, override this
  def nextMinute(self):
    pass

  ## Log a message
  #  @param msg message to log
  #  @param dt datetime object to timestamp with
  def log(self, msg, dt=None):
    if self.silent:
      return
    dt = dt or self.timestamp
    print("{} {}".format(dt, msg))

  ## Callback for updating an order
  #  @param order that was updated
  def orderUpdate(self, order):
    shares = abs(order.shares)
    symbol = order.security.symbol
    side = "buy" if (order.shares > 0) else "sell"
    value = order.value
    profit = order.profit
    if profit:
      self.log("{:8} {:4} order for {:4.0f} shares of {:5} for ${:10.2f} => ${:7.2f} profit".format(
          order.status, side, shares, symbol, value, profit))
    else:
      self.log("{:8} {:4} order for {:4.0f} shares of {:5} for ${:10.2f}".format(
          order.status, side, shares, symbol, value))

# TODO add a walk forward routine
# Starting with the starte a week ago, optimize params for that week
# Proceed with the best algorithm it should have used last week

class Crossover(Strategy):
  params = {"long": 20, "short": 5}
  paramsAdj = {"long": range(5, 50, 1), "short": range(2, 10, 1)}

  def nextMinute(self):
    if len(self.portfolio.orders) != 0:
      return

    smaLong = 0
    smaShort = 0
    security = next(iter(self.portfolio.securities.values()))
    for i in range(-self.params["long"], 0):
      smaLong += security.minute[i].close
    smaLong /= self.params["long"]

    smaShort = 0
    for i in range(-self.params["short"], 0):
      smaShort += security.minute[i].close
    smaShort /= self.params["short"]
    if security.shares == 0 and smaShort > smaLong:
      self.portfolio.buy(security, value=self.portfolio.availableFunds())
    elif security.shares != 0 and smaShort < smaLong:
      self.portfolio.sell(security, shares=security.shares)


## If customStrategy exists, use it, else use crossover strategy
import imp
import importlib
try:
  # imp.find_module("customStrategy")
  from . import customStrategy
  importlib.reload(customStrategy)
  strategy = customStrategy.strategy
except ImportError:
  print("Using default crossover strategy")
  strategy = Crossover()
