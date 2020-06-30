#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import math
import numpy as np

# TODO create order object

class Portfolio:
  ## Initialize the portfolio
  #  @param initialCapital to start the wallet off with
  def __init__(self, securities, initialCapital):
    self.timestamp = None
    self.initialCapital = initialCapital
    self.securities = securities
    self.cash = np.float64(initialCapital)
    self.orders = []

  ## Set the current index of the dataFrame
  #  @param timestamp of the current index
  def _setCurrentTimestamp(self, timestamp):
    self.timestamp = timestamp
    for security in self.securities.values():
      security._setCurrentIndex(timestamp)

  ## Process orders, execute on the opening price
  def _processOrders(self):
    for order in self.orders:
      security = order["security"]
      shares = abs(order["shares"])
      if order["side"] == "sell":
        shares *= -1
      price = shares * security.minute[0].open
      if price < self.cash:
        self.cash -= price
        security.shares -= shares
      # TODO  self.log("CANCEL  {:4} order for {:3} shares of {:5}".format(order["side"], abs(shares), security.symbol))
      # else:
      #   self.log("SUCCESS {:4} order for {:3} shares of {:5}".format(order["side"], abs(shares), security.symbol))
      self.orders.remove(order)

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

  ## Get the amount of available funds for trading
  #  @return cash - reservedCash in open orders
  def availableFunds(self):
    value = self.cash
    for order in self.orders:
      value -= order.reservedCash
    return value

  ## Get the value of the portfolio
  #  @return cash + held securities valuation
  def value(self):
    value = self.cash
    for security in self.securities.values():
      value += security.value()
    return value
