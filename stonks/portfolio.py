#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import numpy as np
from . import security

class Order:
  ## Initialize the order
  #  @param security to trade
  #  @param shares to move, positive for buy, negative for sell
  def __init__(self, security, shares):
    self.security = security
    self.shares = shares
    self.value = abs(security.minute[0].close * shares)
    self.status = "PLACED"
    self.profit = None

  ## Complete the order, records the transaction to the security
  #  @param executed price of the order
  def complete(self, executedPrice):
    self.profit = self.security._transaction(self.shares, executedPrice)
    self.value = abs(executedPrice)
    self.status = "COMPLETE"

  ## Cancel the order
  def cancel(self):
    self.status = "CANCELED"

class Portfolio:
  ## Initialize the portfolio
  #  @param api alpaca object
  #  @param startDate of the simulation
  #  @param initialCapital to start the wallet off with
  #  @param orderCallback function when an order is updated
  def __init__(self, api, startDate, initialCapital, orderCallback):
    self.securities = {}
    for symbol, data in api.securityData.items():
      self.securities[symbol] = security.Security(
        symbol, data[0], data[1], startDate)

    self.cash = np.float64(initialCapital)
    self.orders = []
    self.orderCallback = orderCallback

  ## Advance the current index of the security minute
  def _nextMinute(self):
    for security in self.securities.values():
      security._nextMinute()

  ## Advance the current index of the security day
  def _marketClose(self):
    for security in self.securities.values():
      security._nextDay()

  ## Process orders, execute on the opening price
  def _processOrders(self):
    for order in self.orders:
      price = order.shares * order.security.minute[0].open
      if price < self.cash:
        self.cash -= price
        order.complete(price)
      else:
        order.cancel()
      self.orderCallback(order)
      self.orders.remove(order)

  ## Sell shares of a security
  #  @param security object to sell
  #  @param shares number of shares, None to calculate from value
  #  @param value value of shares to sell (based on current minute closing price)
  def sell(self, security, shares=None, value=None):
    if not shares:
      shares = value / security.minute[0].close
    shares = -abs(np.floor(shares))
    if shares == 0:
      return
    self.orders.append(Order(security, shares))
    self.orderCallback(self.orders[-1])

  ## Buy shares of a security
  #  @param security object to buy
  #  @param shares number of shares, None to calculate from value
  #  @param value value of shares to buy (based on current minute closing price)

  def buy(self, security, shares=None, value=None):
    if not shares:
      shares = value / security.minute[0].close
    shares = abs(np.floor(shares))
    if shares == 0:
      return
    self.orders.append(Order(security, shares))
    self.orderCallback(self.orders[-1])

  ## Get the amount of available funds for trading
  #  @return cash - reserved cash in open orders
  def availableFunds(self):
    value = self.cash
    for order in self.orders:
      value -= max(0, order.value)
    return value

  ## Get the value of the portfolio
  #  @return cash + held securities valuation
  def value(self):
    value = self.cash
    for security in self.securities.values():
      value += security.value()
    return value
