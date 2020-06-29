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
import os
import pandas as pd
import pytz

est = pytz.timezone("US/Eastern")

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
    self.currentIndex = self.dataFrame.index.get_loc(timestamp)

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
    return self.dataFrame.iloc[index]

class Data:
  ## Initialize data object collection of minute and daily candle data
  #  @param symbol name of stored symbol
  #  @param minuteData pandas.DataFrame of minute candle data
  #  @param dayData pandas.DataFrame of daily candle data
  def __init__(self, symbol, minuteData, dayData):
    self.symbol = symbol
    self.minute = Candles(minuteData, minute=True)
    self.day = Candles(dayData, minute=False)

  ## Set the current index of the dataFrame
  #  @param timestamp of the current index
  def setCurrentIndex(self, timestamp):
    self.minute._setCurrentIndex(timestamp)
    self.day._setCurrentIndex(timestamp.date())

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
  def _loadMinuteBarsMonth(self, symbol, date):
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
      start = candles.index[-1].to_pydatetime()

    while True:
      response = self.api.polygon.historic_agg_v2(
          symbol, 1, "minute", start.isoformat(), end.isoformat()).df
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
  def _loadDayBarsYear(self, symbol, date):
    # print("Loading {} yearly candles for {}".format(symbol, date))
    start = date.replace(month=1, day=1)
    end = datetime.date(start.year + 1, 1, 1)

    filename = "datacache/{}.{}.feather".format(symbol, start.year)
    candles = pd.DataFrame()
    if os.path.exists(filename):
      candles = pd.read_feather(filename)
      candles.set_index('timestamp', inplace=True)
      start = candles.index[-1].to_pydatetime()

    while True:
      response = self.api.polygon.historic_agg_v2(
          symbol, 1, "day", start.isoformat(), end.isoformat()).df
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
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @return Data
  def loadSymbol(self, symbol, fromDate, toDate=datetime.date.today()):
    print("Loading", symbol, end="", flush=True)

    # Get the monthly minute bar data for the contained months
    start = fromDate.replace(day=1)
    candlesMinutes = pd.DataFrame()
    while start <= toDate:
      candlesMinutes = pd.concat(
        [candlesMinutes, self._loadMinuteBarsMonth(symbol, start)])
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
        [candlesDays, self._loadDayBarsYear(symbol, start)])
      start = datetime.date(start.year + 1, 1, 1)
      print(".", end="", flush=True)
    candlesDays = candlesDays[candlesDays.index >= fromDatetime]
    candlesDays = candlesDays[candlesDays.index <= toDatetime]

    print("complete", flush=True)

    return Data(symbol, candlesMinutes, candlesDays)

  ## Get timestamps of trading days between fromdate and to date every minute
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @return list of datetime objects
  def getTimestamps(self, fromDate, toDate=datetime.date.today()):
    latestTimestamp = pytz.utc.localize(datetime.datetime.utcnow()) - datetime.timedelta(minutes=1)
    toDate = min(toDate, datetime.date.today())
    timestamps = []
    calendar = self.api.get_calendar(start=fromDate, end=toDate)
    for day in calendar:
      start = est.localize(datetime.datetime.combine(day.date, day.open))
      end = est.localize(datetime.datetime.combine(day.date, day.close))
      day = start
      while day < end and day < latestTimestamp:
        timestamps.append(day)
        day = day + datetime.timedelta(minutes=1)

    return timestamps
