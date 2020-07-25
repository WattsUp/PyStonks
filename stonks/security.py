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
  #  @param startDate to set currentIndex to, None will go to end of list (for live)
  def __init__(self, dataFrame, minute=True, startDate=None):
    self.index = dataFrame.index
    self.values = dataFrame.values
    self.minute = minute
    self.currentIndex = 0
    self.firstOpen = dataFrame.loc[dataFrame["open"].first_valid_index()].open
    self.reset(startDate)

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
      print(self.currentIndex, key, index)
      raise ValueError("(self.currentIndex + key) index must be >= 0")

    if np.isnan(self.values[index][0]):
      return OHLCV([self.firstOpen, self.firstOpen,
                    self.firstOpen, self.firstOpen, 0])
    return OHLCV(self.values[index])

  ## Calculate the average of the previous duration data points
  #  @param duration to average over
  #  @param price to calculate: open, high, low, close, volume
  #  @return average of [(duration - 1) to now] data points
  def sma(self, duration, price="close"):
    if price == "open":
      column = 0
    elif price == "high":
      column = 1
    elif price == "low":
      column = 2
    elif price == "close":
      column = 3
    elif price == "volume":
      column = 4
    
    if duration < 1:
      raise ValueError("Key index must be >= 1")

    values = self.values[self.currentIndex - duration + 1: self.currentIndex+1]
    values = np.transpose(values)[column]
    return np.average(values)

  ## Reset the current index to the start date or 0
  #  @param startDate to set currentIndex to, None will go to end of list (for live)
  def reset(self, startDate=None):
    if startDate:
      if not self.minute:
        startDate = startDate.replace(hour=0, minute=0)
      self.currentIndex = self.index.get_loc(startDate)
    else:
      self.currentIndex = len(self.index) - 1
  
  def _append(self, bar):
    if bar is None:
      previousClose = self.values[-1][3]
      bar = [previousClose, previousClose, previousClose, previousClose, 0]
    self.values = np.append(self.values, [bar], axis=0)

class Security:
  ## Initialize Security object collection of minute and daily candle data
  #  @param symbol name of stored symbol
  #  @param minuteData pandas.DataFrame of minute candle data
  #  @param dayData pandas.DataFrame of daily candle data
  #  @param startDate to set currentIndex to, None will go to end of list (for live)
  def __init__(self, symbol, minuteData, dayData, startDate):
    self.symbol = symbol
    self.minute = Candles(minuteData, minute=True, startDate=startDate)
    self.day = Candles(dayData, minute=False, startDate=startDate)
    self.shares = 0
    self.cost = 0
    self.lifeTimeProfit = 0
    self.availableShares = 0
    self.indicators = None

  def _update(self, latestBar):
    self.minute._append(latestBar)

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
      # print("end of list")
      return self.shares * self.minute[-1].close

  ## Trade shares of the security
  #  @param shares to move
  #  @param executed price of the order, positive for buy, negative for sell
  def _transaction(self, shares, executedPrice):
    profit = None
    if executedPrice > 0:
      self.cost += executedPrice
      self.shares += shares
      self.availableShares += shares
    else:
      price = self.cost * shares / self.shares
      self.cost -= price
      profit = abs(executedPrice) - price
      self.lifeTimeProfit += profit
      self.shares -= shares
    if self.shares < 0:
      raise ValueError("Holding negative shares of " + self.symbol)
    return profit
