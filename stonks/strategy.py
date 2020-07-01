#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import portfolio

class Strategy:
  ## Initialize the strategy
  def __init__(self):
    self.portfolio = None
    self.timestamp = None

  ## Set the securities used by the strategy
  #  @param securities dictionary of symbol key, alpaca.Data value
  def _setup(self, securities, initialCapital):
    self.portfolio = portfolio.Portfolio(
        securities, initialCapital, self.orderUpdate)

  ## Operate on the next minute data, override this
  def nextMinute(self):
    pass

  ## Log a message
  #  @param msg message to log
  #  @param dt datetime object to timestamp with
  def log(self, msg, dt=None):
    dt = dt or self.timestamp
    # print("{} {}".format(dt, msg))

  ## Callback for updating an order
  #  @param order that was updated
  def orderUpdate(self, order):
    shares = abs(order.shares)
    symbol = order.security.symbol
    side = "buy" if (order.shares > 0) else "sell"
    value = order.value
    profit = order.profit
    if profit:
      self.log("{:8} {:4} order for {:3} shares of {:5} for ${:10.2f} => ${:7.2f} profit".format(
          order.status, side, shares, symbol, value, profit))
    else:
      self.log("{:8} {:4} order for {:3} shares of {:5} for ${:10.2f}".format(
          order.status, side, shares, symbol, value))

class Crossover(Strategy):
  params = {"long": 200, "short": 50}

  def nextMinute(self):
    pass
    # if len(self.portfolio.orders) != 0:
    #   return

    # smaLong = 0
    # smaShort = 0
    # security = next(iter(self.portfolio.securities.values()))
    # for i in range(-self.params["long"], 0):
    #   smaLong += security.minute[i].close
    # smaLong /= self.params["long"]

    # smaShort = 0
    # for i in range(-self.params["short"], 0):
    #   smaShort += security.minute[i].close
    # smaShort /= self.params["short"]
    # if security.shares == 0 and smaShort > smaLong:
    #   self.portfolio.buy(security, value=self.portfolio.availableFunds())
    # elif security.shares != 0 and smaShort < smaLong:
    #   self.portfolio.sell(security, shares=security.shares)


## If customStrategy exists, use it, else use crossover strategy
import imp
try:
  imp.find_module("customStrategy")
  import customStrategy
  strategy = customStrategy.strategy
except ImportError:
  strategy = Crossover()
