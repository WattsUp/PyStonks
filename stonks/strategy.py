#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

from . import portfolio
import datetime

class Strategy:
  params = {}
  paramsAdj = {}

  ## Initialize the strategy
  def __init__(self):
    self.portfolio = None
    self.timestamp = None
    self.silent = False
    self.walkForward = True

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

  ## Setup the strategy's portfolio to match the live account 
  #  @param api alpaca object
  def _setupLive(self, api):
    self.portfolio = portfolio.PortfolioLive(api)

  ## Operate on the next minute data, override this
  def nextMinute(self):
    pass

  ## Operate on the next week data, default is to perform a walk-forward
  #  optimization: optimize for the past week's data, use that for this week
  #  @param sim simulation object to use
  #  @param dateMonday of the current week
  def nextWeek(self, sim, dateMonday):
    if not self.walkForward:
      return
    # Get trading days of last week
    calendar = sim.api.getCalendar(
        dateMonday - datetime.timedelta(weeks=2),
        dateMonday - datetime.timedelta(days=1))

    # Setup simulation with same assets as currently held
    initialSecurities = {"cash": self.portfolio.cash}
    for symbol, security in self.portfolio.securities.items():
      initialSecurities[symbol] = security.shares

    # Optimize and use the highest one for this week
    sortedReports = sim.optimize(
        strategy,
        calendar=calendar,
        progressBar=False,
        initialSecurities=initialSecurities,
        targetMetric="profit")
    print("Walk-forward results", sortedReports[0]["testCase"])
    self.params = sortedReports[0]["params"]

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
  params = {"long": 9, "short": 2}
  paramsAdj = {"long": range(5, 20, 1), "short": range(1, 6, 1)}

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
  # print("Using default crossover strategy")
  strategy = Crossover()
