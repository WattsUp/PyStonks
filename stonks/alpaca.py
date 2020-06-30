#!/usr/bin/env python
## Interface to Alpaca API
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import alpaca_trade_api
import calendar
import datetime
import feather
import numpy as np
import os
import pandas as pd
import pytz

est = pytz.timezone("America/New_York")

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
    self._setCurrentIndex(dataFrame.index[0])

  ## Set the current index of the dataFrame
  #  @param timestamp of the current index
  def _setCurrentIndex(self, timestamp):
    if self.minute:
      if timestamp.time() > datetime.time(9, 30):
        self.currentIndex += 1
      else:
        self.currentIndex = self.dataFrame.index.get_loc(timestamp)
    else:
      if timestamp.time() == datetime.time(9, 30):
        self.currentIndex = self.dataFrame.index.get_loc(
          timestamp.replace(hour=0, minute=0))

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

  ## Setup the initial conditions of the simulation
  #  @param shares to start the security with
  def setup(self, shares=0):
    self.shares = shares

  ## Set the current index of the dataFrame
  #  @param timestamp of the current index
  def _setCurrentIndex(self, timestamp):
    self.minute._setCurrentIndex(timestamp)
    self.day._setCurrentIndex(timestamp)

  ## Get the value of held shares
  #  @param shares * most recent close price
  def value(self):
    return self.shares * self.minute[0].close

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
    self.shares += shares
    if self.shares < 0:
      raise ValueError("Holding negative shares of " + self.symbol)
    return profit

class Alpaca:
  WATCHLIST_NAME = "stonks list"

  ## Setup trading environment
  #  @param paper True will execute on paper trades, false will use a live account
  def __init__(self, paper=True):
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY_PAPER")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_PAPER")
    base_url = 'https://paper-api.alpaca.markets'

    if not paper:
      ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
      ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
      base_url = "https://api.alpaca.markets"
    self.api = alpaca_trade_api.REST(ALPACA_API_KEY,
                                     ALPACA_SECRET_KEY,
                                     base_url,
                                     api_version='v2')

  ## Add symbols to the watchlist
  #  @param symbols list of symbols to add
  def addSymbols(self, symbols):
    watchlists = self.api.get_watchlists()
    watchlistID = None
    if len(watchlists) == 1:
      watchlistID = watchlists[0].id
    else:
      for watchlist in watchlists:
        if watchlist.name.lower() == self.WATCHLIST_NAME:
          watchlistID = watchlist.id
    if watchlistID is None:
      self.api.add_watchlist(self.WATCHLIST_NAME)

    existingSymbols = self.getSymbols()
    for symbol in symbols:
      if symbol not in existingSymbols:
        try:
          self.api.add_to_watchlist(watchlistID, symbol)
        except BaseException:
          print("Could not add {} to watchlist".format(symbol))

    print("Current symbols")
    print(self.getSymbols())

  ## Get list of symbols from Alpaca watchlist and current positions
  #  @param includePositions True will add currently held positions
  #  @param list of symbols
  def getSymbols(self, includePositions=False):
    watchlists = self.api.get_watchlists()
    watchlistID = None
    if len(watchlists) == 1:
      watchlistID = watchlists[0].id
    else:
      for watchlist in watchlists:
        if watchlist.name.lower() == self.WATCHLIST_NAME:
          watchlistID = watchlist.id
    if watchlistID is None:
      print("Could not find suitable watchlist, create one named 'Stonks List'")
      sys.exit(1)

    watchlist = self.api.get_watchlist(watchlistID)
    symbols = [asset["symbol"] for asset in watchlist.assets]

    if includePositions:
      # Also add symbols currently held
      for position in self.api.list_positions():
        if position.symbol not in symbols:
          symbols.append(position.symbol)
    return symbols

  ## Load the minute OHLCV data of a symbol for a given month, saves the data for faster fetching next time
  #  @param symbol to fetch data for
  #  @param date in the given month
  #  @return pandas.DataFrame of timestamp index open, high, low, close, volume data
  def _loadMinuteBars(self, symbol, date):
    # print("Loading {} monthly candles for {}".format(symbol, date))
    start = date.replace(day=1)
    end = datetime.date(start.year, start.month,
                        calendar.monthrange(start.year, start.month)[-1])

    filename = "datacache/{}.{}.{}.feather".format(
      symbol, start.year, start.month)
    candles = pd.DataFrame()
    if os.path.exists(filename):
      candles = pd.read_feather(filename)
      candles.set_index('timestamp', inplace=True)
      candles.index = candles.index.tz_convert(est)
      start = candles.index[-1].to_pydatetime()

    today = datetime.date.today()
    if candles.empty or (
      date.year == today.year and date.month == today.month):
      # Data is for current month, update from online
      while True:
        response = self.api.polygon.historic_agg_v2(
            symbol, 1, "minute", start.isoformat(), end.isoformat()).df
        if response.empty:
          return candles
        response.index = response.index.tz_convert(est)
        candles.update(response)
        candles = pd.concat([candles, response])
        candles = candles[~candles.index.duplicated()]

        previousStart = start
        start = candles.index[-1].to_pydatetime()
        if previousStart == start:
          break

    if not os.path.exists("datacache"):
      os.mkdir("datacache")
    candles.reset_index().to_feather(filename)

    return candles

  ## Load the day OHLCV data of a symbol for a given year, saves the data for faster fetching next time
  #  @param symbol to fetch data for
  #  @param date in the given year
  #  @return pandas.DataFrame of timestamp index open, high, low, close, volume data
  def _loadDayBars(self, symbol, date):
    # print("Loading {} yearly candles for {}".format(symbol, date))
    start = date.replace(month=1, day=1)
    end = datetime.date(start.year + 1, 1, 1)

    filename = "datacache/{}.{}.feather".format(symbol, start.year)
    candles = pd.DataFrame()
    if os.path.exists(filename):
      candles = pd.read_feather(filename)
      candles.set_index('timestamp', inplace=True)
      candles.index = candles.index.tz_convert(est)
      start = candles.index[-1].to_pydatetime()

    today = datetime.date.today()
    if not candles.empty and date.year != today.year:
      # Data is for a previous year, no need to compare to online
      return candles

    while True:
      try:
        response = self.api.polygon.historic_agg_v2(
            symbol, 1, "day", start.isoformat(), end.isoformat()).df
      except TypeError:
        return candles
      response.index = response.index.tz_convert(est)
      candles.update(response)
      candles = pd.concat([candles, response])
      candles = candles[~candles.index.duplicated()]

      previousStart = start
      start = candles.index[-1].to_pydatetime()
      if previousStart == start:
        break

    if not os.path.exists("datacache"):
      os.mkdir("datacache")
    candles.reset_index().to_feather(filename)

    return candles

  ## Load the OHLCV data of a symbol between specified dates, inclusive range
  #  @param symbol to fetch data for
  #  @param (list of datetime objects, list of date objects)
  #  @return Data
  def loadSymbol(self, symbol, timestamps):
    print("Loading {:>5}".format(symbol), end="", flush=True)
    fromDate = timestamps[1][0].date()
    toDate = timestamps[1][-1].date()

    # Get the monthly minute bar data for the contained months
    start = fromDate.replace(day=1)
    candlesMinutes = pd.DataFrame()
    while start <= toDate:
      candlesMinutes = pd.concat(
        [candlesMinutes, self._loadMinuteBars(symbol, start)])
      start = datetime.date(
        start.year + (start.month // 12), start.month % 12 + 1, 1)
      print(".", end="", flush=True)

    # Filter out data outside of fromdate and todate
    est = pytz.timezone("US/Eastern")
    fromDatetime = est.localize(
        datetime.datetime.combine(fromDate, datetime.time(0, 0, 0)))
    toDatetime = est.localize(
        datetime.datetime.combine(toDate, datetime.time(23, 59, 59)))
    candlesMinutes = candlesMinutes[candlesMinutes.index >= fromDatetime]
    candlesMinutes = candlesMinutes[candlesMinutes.index <= toDatetime]

    # Get the yearly daily bar data for the contained years
    start = fromDate.replace(month=1, day=1)
    candlesDays = pd.DataFrame()
    while start <= toDate:
      candlesDays = pd.concat(
        [candlesDays, self._loadDayBars(symbol, start)])
      start = datetime.date(start.year + 1, 1, 1)
      print(".", end="", flush=True)
    candlesDays = candlesDays[candlesDays.index >= fromDatetime]
    candlesDays = candlesDays[candlesDays.index <= toDatetime]

    # Fill in missing minute data
    missingTimestamps = [
        timestamp for timestamp in timestamps[0] if timestamp not in candlesMinutes.index]
    if len(missingTimestamps) > 0:
      print("filling minute holes...", end="", flush=True)
      requiredCandles = pd.DataFrame(np.nan, index=pd.to_datetime(missingTimestamps), columns=[
          "open", "high", "low", "close", "volume"])
      requiredCandles.index.name = "timestamp"
      firstOpen = candlesMinutes.iat[0, 0]

      for index, row in requiredCandles.iterrows():
        prevRows = candlesMinutes[candlesMinutes.index < index]
        if prevRows.empty:
          value = firstOpen
        else:
          value = prevRows.iloc[-1]["close"]
        row["open"] = value
        row["high"] = value
        row["low"] = value
        row["close"] = value
        row["volume"] = 0
      requiredCandles.index = requiredCandles.index.tz_convert(est)
      candlesMinutes.index = candlesMinutes.index.tz_convert(est)
      candlesMinutes = candlesMinutes.append(requiredCandles)
      candlesMinutes = candlesMinutes.sort_index()

      # Save updated data
      start = timestamps[0][0].replace(day=1, hour=0, minute=0)
      while start <= timestamps[0][-1]:
        end = est.localize(datetime.datetime(start.year, start.month, calendar.monthrange(
          start.year, start.month)[-1], 23, 59, 59))

        filename = "datacache/{}.{}.{}.feather".format(
          symbol, start.year, start.month)
        candles = candlesMinutes[candlesMinutes.index >= start]
        candles = candles[candles.index <= end]
        candles.reset_index().to_feather(filename)

        start = start.replace(
          year=(start.year + (start.month // 12)), month=(start.month % 12 + 1))

    # Fill in missing daily data
    missingTimestamps = [
        timestamp for timestamp in timestamps[1] if timestamp not in candlesDays.index]
    if len(missingTimestamps) > 0:
      print("filling day holes...", end="", flush=True)
      requiredCandles = pd.DataFrame(np.nan, index=pd.to_datetime(missingTimestamps), columns=[
          "open", "high", "low", "close", "volume"])
      requiredCandles.index.name = "timestamp"
      firstOpen = candlesDays.iat[0, 0]

      for index, row in requiredCandles.iterrows():
        prevRows = candlesDays[candlesDays.index < index]
        if prevRows.empty:
          value = firstOpen
        else:
          value = prevRows.iloc[-1]["close"]
        row["open"] = value
        row["high"] = value
        row["low"] = value
        row["close"] = value
        row["volume"] = 0
      candlesDays = candlesDays.append(requiredCandles)
      candlesDays = candlesDays.sort_index()

      # Save updated data
      start = timestamps[1][0].replace(month=1, day=1, hour=0, minute=0)
      while start <= timestamps[1][-1]:
        end = est.localize(datetime.datetime(start.year + 1, 1, 1))

        filename = "datacache/{}.{}.feather".format(symbol, start.year)
        candles = candlesDays[candlesDays.index >= start]
        candles = candles[candles.index < end]
        candles.reset_index().to_feather(filename)

        start = start.replace(year=(start.year + 1))

    print("complete", flush=True)

    return Security(symbol, candlesMinutes, candlesDays)

  ## Get timestamps of trading days between fromdate and to date every minute
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @return (list of datetime objects (minutes), list of datetime objects (days))
  def getTimestamps(self, fromDate, toDate=datetime.date.today()):
    latestTimestamp = pytz.utc.localize(
      datetime.datetime.utcnow()) - datetime.timedelta(minutes=1)
    toDate = min(toDate, datetime.date.today())
    timestamps = []
    calendar = self.api.get_calendar(start=fromDate, end=toDate)
    dates = []
    for day in calendar:
      dates.append(est.localize(
          datetime.datetime.combine(day.date, datetime.time(0, 0, 0))))
      start = est.localize(datetime.datetime.combine(day.date, day.open))
      end = est.localize(datetime.datetime.combine(day.date, day.close))
      day = start
      while day < end and day < latestTimestamp:
        timestamps.append(day)
        day = day + datetime.timedelta(minutes=1)

    return (timestamps, dates)
