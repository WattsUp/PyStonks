#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
import numpy as np
from . import security

class Order:
  ## Initialize the order
  #  @param security to trade
  #  @param shares to move, positive for buy, negative for sell
  def __init__(self, security, shares):
    self.security = security
    self.shares = shares
    self.filledShares = 0
    self.value = security.minute[0].close * shares
    self.status = "PLACED"
    self.profit = None

  ## Partially complete the order, records the transaction to the security
  #  @param executed price of the order, positive for buy, negative for sell
  #  @param qty filled
  def partial(self, executedPrice, qty):
    self.status = "PARTIAL"
    partialOrder = Order(self.security, qty)
    partialOrder.status = "PARTIAL"
    partialOrder.profit = self.security._transaction(qty, executedPrice)
    partialOrder.value = executedPrice
    self.filledShares += qty
    return partialOrder

  ## Complete the order, records the transaction to the security
  #  @param executed price of the order, positive for buy, negative for sell
  def complete(self, executedPrice):
    if self.status == "PARTIAL":
      self.shares = self.shares - self.filledShares
    self.filledShares = self.shares
    self.profit = self.security._transaction(self.shares, executedPrice)
    self.value = executedPrice
    self.status = "COMPLETE"

  ## Cancel the order
  def cancel(self):
    self.status = "CANCELED"

class Portfolio:
  ## Initialize the portfolio
  #  @param api alpaca object
  #  @param startDate of the simulation, None will go to the latest data
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

  def __str__(self):
    return "Value: ${:0.2f}, cash: ${:0.2f}, available: ${:0.2f}".format(
      self.value(), self.cash, self.availableFunds())

  ## Advance the current index of the security minute
  def _nextMinute(self):
    for security in self.securities.values():
      security._nextMinute()

  ## Advance the current index of the security day
  def _marketClose(self):
    for security in self.securities.values():
      security._nextDay()

  ## Update the portfolio with aggregate price data
  #  @param securityDataUpdate dict of [O,H,L,C,V] data indexed by symbol
  def _update(self, securityDataUpdate):
    for symbol, security in self.securities.items():
      if symbol in securityDataUpdate.keys():
        security._update(securityDataUpdate[symbol])
      else:
        security._update(None)

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
    shares = abs(np.floor(shares))
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
    if isinstance(self.orders, dict):
      for orderID in self.orders:
        value -= max(0, self.orders[orderID].value)
    else:
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

class PortfolioLive(Portfolio):

  ## Initialize a portfolio object using cash and holdings from the live account
  #  @param api alpaca object
  #  @param orderCallback function when an order is updated
  #  @param marginTrading True allows funds to be borrowed, False limits to cash only
  def __init__(self, api, orderCallback, marginTrading=False):
    super().__init__(api, None, api.getLiveCash(), orderCallback)
    self.api = api
    self.orders = {}
    self.marginTrading = marginTrading

  ## Get the amount of available funds for trading
  #  @return cash - reserved cash in open orders
  def availableFunds(self):
    if self.marginTrading:
      return np.float64(self.api.getLiveBuyingPower())
    else:
      return super().availableFunds()

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
    value = shares * security.minute[0].close
    if not self.marginTrading and (self.cash - value) < 0:
      print("Not performing trade: buy would result in negative cash")
      return
    self.api.submit_order(security.symbol, shares, "buy")

  ## Sell shares of a security
  #  @param security object to sell
  #  @param shares number of shares, None to calculate from value
  #  @param value value of shares to sell (based on current minute closing price)
  def sell(self, security, shares=None, value=None):
    if not shares:
      shares = value / security.minute[0].close
    shares = min(abs(np.floor(shares)), security.shares)
    if shares == 0:
      return
    self.api.submit_order(security.symbol, shares, "sell")

  ## On pushed update of a trade from alpaca, update the order book
  #  @param trade object
  def _onTradeUpdate(self, trade):
    orderID = trade.order["id"]
    security = self.securities[trade.order["symbol"]]
    if trade.event == "new":
      qty = np.float64(trade.order["qty"])
      if trade.order["side"] == "sell":
        qty = -qty
      self.orders[orderID] = Order(security, qty)
      self.orderCallback(self.orders[orderID])
    elif trade.event == "partial_fill":
      order = self.orders[orderID]
      qty = np.float64(trade.qty)
      if trade.order["side"] == "sell":
        qty = -qty
      price = np.float64(trade.price) * qty
      partialOrder = order.partial(price, qty)
      self.cash -= partialOrder.value
      self.orderCallback(partialOrder)
    elif trade.event == "fill":
      order = self.orders[orderID]
      qty = np.float64(trade.qty)
      if trade.order["side"] == "sell":
        qty = -qty
      price = np.float64(trade.price) * qty
      order.complete(price)
      self.cash -= order.value
      self.orderCallback(order)
      self.orders.pop(orderID)
    elif trade.event in ("canceled", "expired"):
      order = self.orders[orderID]
      order.cancel()
      self.orderCallback(order)
      self.orders.pop(orderID)
    else:
      # TODO done_for_day or replaced
      print(trade)
