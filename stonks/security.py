#!/usr/bin/env python
## Interface to Alpaca API
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import datetime
import numpy as np

class OHLCV:
  ## Initialize a OHLCV object, data storage
  #  @para list of [open, high, low, close, volume]
  def __init__(self, list):
    self.open = list[0]
    self.high = list[1]
    self.low = list[2]
    self.close = list[3]
    self.volume = list[4]

class Candles:
  ## Initialize candles object, accessor of candle data
  #  @param dataFrame pandas.DataFrame of OHLCV data with timestamp indexing
  #  @param minute True if dataFrame is minute data, False if dataFrame is daily data
  def __init__(self, dataFrame, minute=True):
    self.dataFrame = dataFrame
    self.minute = minute
    self.currentIndex = 0
    self.firstOpen = dataFrame.loc[dataFrame["open"].first_valid_index()].open

  ## Advance the currentIndex
  def _next(self):
    self.currentIndex += 1

  ## Index accessor, get historical candle data
  #  @param key integer <= 0, 0 is currentIndex, -1 is previous candle...
  def __getitem__(self, key):
    if key > 0:
      raise ValueError("Key index must be <= 0")
    index = self.currentIndex + key
    if not self.minute:
      # The zero index is yesterday as today is not finished yet
      index = index - 1
    if index < 0:
      raise ValueError("(self.currentIndex + key) index must be >= 0")

    if np.isnan(self.dataFrame.values[index][0]):
      return OHLCV([self.firstOpen, self.firstOpen,
                    self.firstOpen, self.firstOpen, 0])
    return OHLCV(self.dataFrame.values[index])

class Security:
  ## Initialize Security object collection of minute and daily candle data
  #  @param symbol name of stored symbol
  #  @param minuteData pandas.DataFrame of minute candle data
  #  @param dayData pandas.DataFrame of daily candle data
  def __init__(self, symbol, minuteData, dayData):
    self.symbol = symbol
    self.minute = Candles(minuteData, minute=True)
    self.day = Candles(dayData, minute=False)
    self.shares = 0
    self.cost = 0
    self.lifeTimeProfit = 0

  ## Setup the initial conditions of the simulation
  #  @param shares to start the security with
  def setup(self, shares=0):
    self.shares = shares
    self.cost = 0
    self.lifeTimeProfit = 0
    self.minute.currentIndex = 0
    self.day.currentIndex = 0

  ## Advance the current index of the minute candles
  def _nextMinute(self):
    self.minute._next()

  ## Advance the current index of the day candles
  def _nextDay(self):
    self.day._next()

  ## Get the value of held shares
  #  @param shares * most recent close price
  def value(self):
    try:
      return self.shares * self.minute[0].close
    except IndexError:
      return self.shares * self.minute[-1].close

  ## Trade shares of the security
  #  @param shares to move, positive for buy, negative for sell
  #  @param executed price of the order
  def _transaction(self, shares, executedPrice):
    profit = None
    if shares > 0:
      self.cost += abs(executedPrice)
    else:
      price = self.cost * abs(shares) / self.shares
      self.cost -= price
      profit = abs(executedPrice) - price
      self.lifeTimeProfit += profit
    self.shares += shares
    if self.shares < 0:
      raise ValueError("Holding negative shares of " + self.symbol)
    return profit
