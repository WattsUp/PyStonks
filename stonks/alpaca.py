#!/usr/bin/env python
## Interface to Alpaca API
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import alpaca_trade_api
import calendar as cal
import datetime
import feather
import numpy as np
import os
import pandas as pd
import pytz
from . import security

est = pytz.timezone("America/New_York")

class Alpaca:
  WATCHLIST_NAME = "stonks list"

  ## Setup trading environment
  #  @param paper True will execute on paper trades, false will use a live account
  def __init__(self, paper=True):
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY_PAPER")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_PAPER")
    base_url = "https://paper-api.alpaca.markets"

    if not paper:
      ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
      ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
      base_url = "https://api.alpaca.markets"
    self.api = alpaca_trade_api.REST(ALPACA_API_KEY,
                                     ALPACA_SECRET_KEY,
                                     base_url,
                                     api_version="v2")
    self.nextOpen = None
    self.nextClose = None
    self.open = None

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
      print(
          "Could not find suitable watchlist, create one named '{}'".format(
              self.WATCHLIST_NAME))
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
  #  @param pandas.DataFrame date indexed, open & close times
  #  @return pandas.DataFrame of timestamp index open, high, low, close, volume data
  def _loadMinuteBars(self, symbol, date, calendar):
    # print("Loading {} monthly candles for {}".format(symbol, date))
    start = date.replace(day=1)
    end = datetime.date(start.year, start.month,
                        cal.monthrange(start.year, start.month)[-1])

    filename = "datacache/{}.{}.{}.feather".format(
      symbol, start.year, start.month)
    candles = pd.DataFrame()
    if os.path.exists(filename):
      candles = pd.read_feather(filename)
      candles.set_index("timestamp", inplace=True)
      candles.index = candles.index.tz_convert(est)
      start = candles.index[-1].to_pydatetime()

    today = datetime.date.today()
    if not candles.empty and (
      date.year != today.year or date.month != today.month):
      # Data is for a previous month, no need to compare to online
      return candles

    while True:
      response = self.api.polygon.historic_agg_v2(
          symbol, 1, "minute", start.isoformat(), end.isoformat(), limit=50000).df
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

    # Only keep rows when the market is open
    timestamps = self.getTimestamps(self.getCalendar(date.replace(day=1), end))
    candles = candles.reindex(timestamps)
    earliestOpen = candles.loc[candles["open"].first_valid_index()].open

    # Fill in any holes
    for index in candles[pd.isnull(candles).any(axis=1)].index:
      intIndex = candles.index.get_loc(index)
      if intIndex == 0:
        closePrice = earliestOpen
      else:
        closePrice = candles.iloc[intIndex - 1].close
      row = candles.loc[index]
      row.open = closePrice
      row.high = closePrice
      row.low = closePrice
      row.close = closePrice
      row.volume = 0
    candles.index.name = "timestamp"

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
      candles.set_index("timestamp", inplace=True)
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

    for index in candles[pd.isnull(candles).any(axis=1)].index:
      intIndex = candles.index.get_loc(index)
      closePrice = candles.iloc[intIndex - 1].close
      row = candles.loc[index]
      row.open = closePrice
      row.high = closePrice
      row.low = closePrice
      row.close = closePrice
      row.volume = 0

    if not os.path.exists("datacache"):
      os.mkdir("datacache")
    candles.reset_index().to_feather(filename)

    return candles

  ## Load the OHLCV data of a symbol between specified dates, inclusive range
  #  @param symbol to fetch data for
  #  @param calendar pandas.DataFrame date indexed, open & close times
  #  @return Data
  def loadSymbol(self, symbol, calendar):
    print("Loading {:>5}".format(symbol), end="", flush=True)
    fromDate = calendar.index[0]
    toDate = calendar.index[-1]
    timestamps = self.getTimestamps(calendar)

    # Get the yearly daily bar data for the contained years
    start = fromDate.replace(month=1, day=1)
    candlesDays = pd.DataFrame()
    while start <= toDate:
      candles = self._loadDayBars(symbol, start)
      candlesDays = pd.concat([candlesDays, candles])
      start = datetime.date(start.year + 1, 1, 1)
      print(".", end="", flush=True)
    candlesDays = candlesDays.reindex(calendar.index)
    if candlesDays.empty:
      print("no data, before historic data")
      return None

    # Get the monthly minute bar data for the contained months
    start = candlesDays["open"].first_valid_index().replace(day=1)
    candlesMinutes = pd.DataFrame()
    while start <= toDate:
      candles = self._loadMinuteBars(symbol, start, calendar)
      candlesMinutes = pd.concat([candlesMinutes, candles])
      start = datetime.date(
        start.year + (start.month // 12), start.month % 12 + 1, 1)
      print(".", end="", flush=True)
    candlesMinutes = candlesMinutes.reindex(timestamps)

    print("complete", flush=True)

    return security.Security(symbol, candlesMinutes, candlesDays)

  ## Get the trading calendar between two dates
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @return pandas.DataFrame date indexed, open & close times
  def getCalendar(self, fromDate, toDate=datetime.date.today()):
    toDate = min(toDate, datetime.date.today())
    calendar = self.api.get_calendar(
        start=fromDate.isoformat(),
        end=toDate.isoformat())
    dates = [pd.to_datetime(est.localize(a.date)) for a in calendar]
    opens = [a.open for a in calendar]
    closes = [a.close for a in calendar]
    df = pd.DataFrame(data={"open": opens, "close": closes}, index=dates)
    return df

  ## Get the timestamps when the market is open
  #  @param calendar pandas.DataFrame date indexed, open & close times or pd.Series of a single row of that DataFrame
  #  @return list of timestamps when the market is open
  def getTimestamps(self, calendar):
    latestTimestamp = pytz.utc.localize(
      datetime.datetime.utcnow()) - datetime.timedelta(minutes=1)
    timestamps = []

    if type(calendar) == pd.DataFrame:
      for index, row in calendar.iterrows():
        start = est.localize(datetime.datetime.combine(index, row.open))
        end = est.localize(datetime.datetime.combine(index, row.close))
        timestamp = start
        while timestamp < end and timestamp < latestTimestamp:
          timestamps.append(timestamp)
          timestamp = timestamp + datetime.timedelta(minutes=1)
    elif type(calendar) == pd.Series:
      start = est.localize(
          datetime.datetime.combine(
              calendar.name, calendar.open))
      end = est.localize(
          datetime.datetime.combine(
              calendar.name, calendar.close))
      timestamp = start
      while timestamp < end and timestamp < latestTimestamp:
        timestamps.append(timestamp)
        timestamp = timestamp + datetime.timedelta(minutes=1)
    return pd.DatetimeIndex(timestamps)

  ## Check if the market is open or not
  #  @return True if market is open, False otherwise
  def isOpen(self):
    if not self.nextOpen or not self.nextClose:
      print("API fetch")
      clock = self.api.get_clock()
      self.nextOpen = clock.next_open
      self.nextClose = clock.next_close
      self.open = clock.is_open
      return self.open

    now = pytz.utc.localize(datetime.datetime.utcnow())
    if self.open:
      # Previous check was open, is it closed now?
      if now >= self.nextClose:
        print("API fetch")
        clock = self.api.get_clock()
        self.nextOpen = clock.next_open
        self.nextClose = clock.next_close
        self.open = clock.is_open
    else:
      # Previous check was closed, is it open now?
      if now >= self.nextOpen:
        print("API fetch")
        clock = self.api.get_clock()
        self.nextOpen = clock.next_open
        self.nextClose = clock.next_close
        self.open = clock.is_open

    return self.open
