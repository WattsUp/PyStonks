#!/usr/bin/env python
## Interface to Alpaca API
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import alpaca_trade_api
import asyncio
import calendar as cal
from colorama import Fore, Style, init as ColoramaInit
import concurrent.futures
import datetime
import feather
import numpy as np
import os
import pandas as pd
import pytz

ColoramaInit(autoreset=True)
est = pytz.timezone("America/New_York")

class Alpaca:
  WATCHLIST_NAME = "stonks list"

  ## Setup trading environment
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @param paper True will execute on paper trades, false will use a live account
  def __init__(self, fromDate, toDate=datetime.date.today(),
               symbol=None, paper=True, live=False):
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
    self.tradingMinutesElapsed = None
    self.tradingMinutesRemaining = None
    self.securityData = {}

    calendar = self.getCalendar(fromDate, toDate)
    timestamps = self.getTimestamps(calendar)
    if symbol:
      symbols = [symbol]
    else:
      symbols = self.getSymbols()

    with concurrent.futures.ThreadPoolExecutor() as executor:
      for symbol in symbols:
        executor.submit(self.loadSymbol, symbol, calendar, timestamps)
    if len(self.securityData.keys()) == 0:
      print("No symbols loaded")
      sys.exit(1)

    if live:
      self.conn = alpaca_trade_api.StreamConn(
          ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url, data_stream="polygon")
      self.conn.register(r"AM.*", self._onMinuteBars)
      self.conn.register(r"trade_updates", self._onTradeUpdates)
      self.conn.register(r"account_updates", self._onAccountUpdates)
      self.conn.register(r".*", self._onData)
      self.liveChannels = ["trade_updates", "account_updates"]
      for symbol in symbols:
        self.liveChannels.append("AM." + symbol)

  ## On push update of aggregate minute data
  #  @param conn connection object
  #  @param channel notification came in from
  #  @param bar aggregate data
  async def _onMinuteBars(self, conn, channel, bar):
    data = [bar.open, bar.high, bar.low, bar.close, bar.volume]
    self.securityDataUpdate[bar.symbol] = data

  ## On push update of trade updates
  #  @param conn connection object
  #  @param channel notification came in from
  #  @param trade data
  async def _onTradeUpdates(self, conn, channel, trade):
    self.liveStrategy.portfolio._onTradeUpdate(trade)

  ## On push update of account updates
  #  @param conn connection object
  #  @param channel notification came in from
  #  @param account data
  async def _onAccountUpdates(self, conn, channel, account):
    print("  account", account, datetime.datetime.now())
    # TODO update cash (deposits/withdrawals)

  ## On push update of other information that is not a data stream
  #  @param conn connection object
  #  @param channel notification came in from
  #  @param data
  async def _onData(self, conn, channel, data):
    if not (channel in ("AM", "Q", "A", "T", "trade_updates",
                        "status", "listening", "authorized")):
      print("onData", channel, data)

  ## Wrapper to run a periodic function every minute, at 5 seconds after 0
  async def _coroutine(self):
    minuteProcessed = True
    lastMinute = datetime.datetime.now().replace(microsecond=0).minute
    while True:
      now = datetime.datetime.now().replace(microsecond=0)
      if now.minute != lastMinute:
        minuteProcessed = False
      lastMinute = now.minute

      if not minuteProcessed and now.second >= 5:
        self.liveStrategy.portfolio._update(self.securityDataUpdate)
        self.securityDataUpdate = {}
        self.liveStrategy.portfolio._nextMinute()
        tradingMinutes = self.getTradingMinutes()
        self.liveStrategy.tradingMinutesElapsed = tradingMinutes[0]
        self.liveStrategy.tradingMinutesLeft = tradingMinutes[1]

        if self.isOpen():
          status = "Open"
          self.liveStrategy.timestamp = now
          self.liveStrategy.nextMinute()
        else:
          status = "Closed"

        currentValue = self.liveStrategy.portfolio.value()
        dailyProfit = currentValue - self.liveLastEquity
        dailyProfitPercent = dailyProfit / currentValue * 100
        color = Fore.WHITE
        if dailyProfit > 0:
          color = Fore.GREEN
        elif dailyProfit < 0:
          color = Fore.RED
        print(f"{now} "
              f"{status:6} "
              f"${currentValue:10.2f} "
              f"{color}${dailyProfit:8.2f} {dailyProfitPercent:8.3f}%")

        minuteProcessed = True
      await asyncio.sleep(1)

  ## Run alpaca live streaming
  #  @param strategy to operate on live data
  #  @param marginTrading True allows funds to be borrowed, False limits to cash only
  def runLive(self, strategy, marginTrading=False):
    if self.conn is None:
      print("Must setup alpaca with live=True")
      sys.exit(1)
    strategy._setupLive(self, marginTrading=marginTrading)
    asyncio.ensure_future(self._coroutine())
    self.securityDataUpdate = {}
    self.liveStrategy = strategy
    self.liveLastEquity = np.float64(self.api.get_account().last_equity)
    self.conn.run(self.liveChannels)

  ## Get the amount of cash as reported by alpaca
  #  @return USD
  def getLiveCash(self):
    return float(self.api.get_account().cash)

  ## Get the buying power as reported by alpaca
  #  @return USD
  def getLiveBuyingPower(self):
    return float(self.api.get_account().buying_power)

  ## Get the positions held as reported by alpaca
  #  @return dict of (shares, average entry price) indexed by symbol
  def getLivePositions(self):
    securities = {}
    for position in self.api.list_positions():
      securities[position.symbol] = (np.float64(
        position.qty), np.float64(position.avg_entry_price))
    return securities

  ## Submit an order to alpaca
  #  @param symbol to order
  #  @param shares quantity to order
  #  @param side to order: "buy" or "sell"
  def submit_order(self, symbol, shares, side):
    self.api.submit_order(
      symbol=symbol,
      side=side,
      type="market",
      qty=shares,
      time_in_force="day"
    )

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
      print("year holes")
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
  #  @param timestamps list of datetime objects for each minute market is open
  #  @return (candlesMinutes, candlesDays) both pandas.dataframe
  def loadSymbol(self, symbol, calendar, timestamps):
    fromDate = calendar.index[0]
    toDate = calendar.index[-1]

    # Get the yearly daily bar data for the contained years
    start = fromDate.replace(month=1, day=1)
    candlesDays = pd.DataFrame()
    while start <= toDate:
      candles = self._loadDayBars(symbol, start)
      candlesDays = pd.concat([candlesDays, candles])
      start = datetime.date(start.year + 1, 1, 1)
    candlesDays = candlesDays.reindex(calendar.index)
    if candlesDays.empty or np.isnan(candlesDays["open"][-1]):
      print(candlesDays)
      print("{:5} no data, before historic data".format(symbol))
      return

    # Get the monthly minute bar data for the contained months
    start = candlesDays["open"].first_valid_index().replace(day=1)
    candlesMinutes = pd.DataFrame()
    while start <= toDate:
      candles = self._loadMinuteBars(symbol, start, calendar)
      candlesMinutes = pd.concat([candlesMinutes, candles])
      start = datetime.date(
        start.year + (start.month // 12), start.month % 12 + 1, 1)
    candlesMinutes = candlesMinutes.reindex(timestamps)

    # print("{:5} loaded".format(symbol))

    self.securityData[symbol] = (candlesMinutes, candlesDays)

  def updateSecurities(self):
    today = datetime.date.today().isoformat()
    for symbol, (candlesMinutes, candlesDays) in self.securityData.items():
      response = self.api.polygon.historic_agg_v2(
          symbol, 1, "minute", today, today).df
      response.index = response.index.tz_convert(est)
      candlesMinutes.update(response)
      candlesMinutes = pd.concat([candlesMinutes, response])
      candlesMinutes = candlesMinutes[~candlesMinutes.index.duplicated()]

      response = self.api.polygon.historic_agg_v2(
          symbol, 1, "day", today, today).df
      response.index = response.index.tz_convert(est)
      candlesDays.update(response)
      candlesDays = pd.concat([candlesDays, response])
      candlesDays = candlesDays[~candlesDays.index.duplicated()]
      self.securityData[symbol] = (candlesMinutes, candlesDays)

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

    if isinstance(calendar, pd.DataFrame):
      for index, row in calendar.iterrows():
        start = est.localize(datetime.datetime.combine(index, row.open))
        end = est.localize(datetime.datetime.combine(index, row.close))
        timestamp = start
        while timestamp < end and timestamp < latestTimestamp:
          timestamps.append(timestamp)
          timestamp = timestamp + datetime.timedelta(minutes=1)
    elif isinstance(calendar, pd.Series):
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
      clock = self.api.get_clock()
      self.nextOpen = clock.next_open
      self.nextClose = clock.next_close
      self.open = clock.is_open
      return self.open

    now = pytz.utc.localize(datetime.datetime.utcnow())
    if self.open:
      # Previous check was open, is it closed now?
      if now >= self.nextClose:
        clock = self.api.get_clock()
        self.nextOpen = clock.next_open
        self.nextClose = clock.next_close
        self.open = clock.is_open
    else:
      # Previous check was closed, is it open now?
      if now >= self.nextOpen:
        clock = self.api.get_clock()
        self.nextOpen = clock.next_open
        self.nextClose = clock.next_close
        self.open = clock.is_open

    return self.open

  ## Get the number of minutes since the market opened and the number of minutes left
  #  @return (tradingMinutesElapsed, tradingMinutesRemaining)
  def getTradingMinutes(self):
    if self.tradingMinutesElapsed is None:
      calendar = self.getCalendar(datetime.date.today())
      start = est.localize(
          datetime.datetime.combine(
              calendar.index[0],
              calendar.open[0]))
      end = est.localize(
          datetime.datetime.combine(
              calendar.index[0],
              calendar.close[0]))
      self.tradingMinutesElapsed = 0
      self.tradingMinutesRemaining = 0
      now = pytz.utc.localize(
          datetime.datetime.utcnow()).replace(
          second=0, microsecond=0)
      timestamp = start
      while timestamp < end:
        if timestamp < now:
          self.tradingMinutesElapsed += 1
        else:
          self.tradingMinutesRemaining += 1
        timestamp = timestamp + datetime.timedelta(minutes=1)
      return (self.tradingMinutesElapsed, self.tradingMinutesRemaining)

    self.tradingMinutesElapsed += 1
    self.tradingMinutesRemaining -= 1
    return (self.tradingMinutesElapsed, self.tradingMinutesRemaining)
