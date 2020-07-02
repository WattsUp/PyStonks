#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

from . import alpaca
import datetime
from matplotlib import pyplot
import numpy as np
import pytz
import sys

est = pytz.timezone("America/New_York")

class Simulation:

  ## Initialize simulation by loading the appropriate data
  #  @param fromDate datetime.date start date (inclusive)
  #  @param toDate datetime.date end date (inclusive)
  #  @param symbol to load, None will load all symbols from watchlist
  #  @param preStart number of days to prepend, note: calendar days not trading days
  def __init__(self, fromDate, toDate=datetime.date.today(),
               symbol=None, preStart=50):
    self.api = alpaca.Alpaca()
    self.strategy = None
    self.cash = 0
    self.securities = {}
    self.securitiesPrice = {}
    self.securitiesShares = {}
    self.securitiesProfit = {}
    preStartFromDate = fromDate - datetime.timedelta(days=preStart)
    loadCalendar = self.api.getCalendar(preStartFromDate, toDate)
    self.calendar = self.api.getCalendar(fromDate, toDate)
    self.timestamps = []
    self.dates = []
    self.closingValue = []
    self.dailyReturn = []
    self.startDate = est.localize(
        datetime.datetime.combine(
            self.calendar.index[0],
            self.calendar.open[0]))
    if symbol:
      security = self.api.loadSymbol(symbol, loadCalendar)
      if security:
        self.securities[symbol] = security
        self.securitiesPrice[symbol] = []
        self.securitiesShares[symbol] = []
        self.securitiesProfit[symbol] = []
    else:
      symbols = self.api.getSymbols()
      for symbol in symbols:
        security = self.api.loadSymbol(symbol, loadCalendar)
        if security:
          self.securities[symbol] = security
          self.securitiesPrice[symbol] = []
          self.securitiesShares[symbol] = []
          self.securitiesProfit[symbol] = []
    if len(self.securities.keys()) == 0:
      print("No symbols loaded")
      sys.exit(1)

  ## Setup the initial conditions of the simulation
  #  @param strategy object to simulate
  #  @param initialCapital to start the simulation with
  def setup(self, strategy, initialCapital=10000):
    self.initialCapital = initialCapital
    self.strategy = strategy
    self.strategy._setup(self.securities, initialCapital)
    for security in self.securities.values():
      security.setup(startDate=self.startDate)
    for symbol in self.securities.keys():
      self.securitiesPrice[symbol] = []
      self.securitiesShares[symbol] = []
      self.securitiesProfit[symbol] = []
    self.timestamps = []
    self.dates = []
    self.closingValue = []
    self.dailyReturn = []

  ## Run a simulation, expects setup to be called just before
  #  @return datetime.datetime elapsed time of executing the test
  def run(self, progressBar=True):
    start = datetime.datetime.now()
    progressTick = max(1, np.floor(len(self.calendar.index) / 40))
    i = 0
    for index, row in self.calendar.iterrows():
      timestamps = self.api.getTimestamps(row)
      for timestamp in timestamps:
        self.strategy.timestamp = timestamp
        self.strategy.portfolio._processOrders()

        self.strategy.nextMinute()

        self.timestamps.append(timestamp)
        for security in self.securities.values():
          self.securitiesPrice[security.symbol].append(
            security.minute[0].close)
          self.securitiesShares[security.symbol].append(
            security.shares)
          self.securitiesProfit[security.symbol].append(
            security.lifeTimeProfit)
        self.strategy.portfolio._nextMinute()

      value = self.strategy.portfolio.value()
      if len(self.closingValue) > 0:
        self.dailyReturn.append((value / self.closingValue[-1] - 1) * 100)
      else:
        self.dailyReturn.append(0)
      self.closingValue.append(value)
      self.dates.append(index)
      self.strategy.portfolio._marketClose()
      i = (i + 1) % progressTick
      if i == 0 and progressBar:
        print(".", end="", flush=True)

    return datetime.datetime.now() - start

  ## Optimize a single parameter of a strategy by running though its possible values and checking a metric
  #  @param strategy object to test
  #  @param paramName to manipulate
  #  @param paramRange to iterate through
  #  @param targetMetric to output value for
  def optimize(self, strategy, paramName, paramRange, targetMetric="sortino"):
    for i in paramRange:
      strategy.params[paramName] = i
      self.setup(strategy)
      self.run(progressBar=True)
      print("[{}={:3} -> {}={:6.3f}]".format(paramName, i,
                                             targetMetric, self.report()[targetMetric]))

  ## Optimize a single parameter of a strategy by running though its possible values and checking a metric
  #  @param strategy object to test
  #  @param param1Name to manipulate
  #  @param param1Range to iterate through
  #  @param param2Name to manipulate
  #  @param param2Range to iterate through
  #  @param targetMetric to output value for
  def optimize2(self, strategy, param1Name, param1Range,
                param2Name, param2Range, targetMetric="sortino"):
    for i in param1Range:
      strategy.params[param1Name] = i
      for ii in param2Range:
        strategy.params[param2Name] = ii
        self.setup(strategy)
        self.run(progressBar=True)
        print("[{}={:3}, {}={:3} -> {}={:6.3f}]".format(param1Name, i,
                                                        param2Name, ii, targetMetric, self.report()[targetMetric]))

  ## Generate a report of the simulation with statistics
  #  @return dictionary of statistics
  def report(self):
    report = {}
    avgDailyReturn = np.mean(self.dailyReturn)
    stddev = np.std(self.dailyReturn)
    if stddev == 0:
      report["sharpe"] = 0
    else:
      sharpe = avgDailyReturn / stddev * np.sqrt(252)
      report["sharpe"] = sharpe

    negativeReturns = np.array([a for a in self.dailyReturn if a < 0])
    downsideVariance = np.sum(negativeReturns**2) / len(self.dailyReturn)
    if downsideVariance == 0:
      report["sortino"] = 0
    else:
      sortino = avgDailyReturn / np.sqrt(downsideVariance) * np.sqrt(252)
      report["sortino"] = sortino

    report["close"] = self.closingValue[-1]
    profit = self.closingValue[-1] - self.initialCapital
    report["profit"] = profit
    profitPercent = profit / self.initialCapital
    report["profit-percent"] = profitPercent
    # (PeriodPercent + 1)^(number of periods in a trading year)
    profitPercentYr = np.power(
      (profitPercent + 1), 252 / len(self.closingValue)) - 1
    report["profit-percent-yr"] = profitPercentYr
    return report

  ## Generate and print a report of the last run
  def printReport(self):
    report = self.report()
    print("Sharpe ratio:    {:11.3f}".format(report["sharpe"]))
    print("Sortino ratio:   {:11.3f}".format(report["sortino"]))
    print("Closing value:  ${:10.2f}".format(report["close"]))
    print("Closing profit: ${:10.2f} = {:.2f}% = {:.2f}%(yr)\n".format(
        report["profit"], report["profit-percent"] * 100, report["profit-percent-yr"] * 100))

  def plot(self, symbol=None):
    fig, (ax1, ax2) = pyplot.subplots(2, 1, sharex=True)
    if symbol:
      # Plot on first subplot
      ax1.set_ylabel("Closing Price ($)")
      ax1.plot(
          self.securitiesPrice[symbol],
          color='black',
          zorder=0,
          label=symbol)
      bottom, top = ax1.get_ylim()
      offset = (top - bottom) / 20
      # Buy and sell markers
      tradeBuyIndex = []
      tradeSellIndex = []
      tradesBuy = []
      tradesSell = []
      prevShares = 0
      for i in range(len(self.timestamps)):
        shares = self.securitiesShares[symbol][i]
        if (shares - prevShares) > 0:
          tradesBuy.append(self.securitiesPrice[symbol][i] - offset)
          tradeBuyIndex.append(i)
        elif (shares - prevShares) < 0:
          tradesSell.append(self.securitiesPrice[symbol][i] + offset)
          tradeSellIndex.append(i)
        prevShares = shares
      ax1.scatter(
          tradeBuyIndex,
          tradesBuy,
          color="g",
          marker="^",
          zorder=1,
          label="buy")
      ax1.scatter(
          tradeSellIndex,
          tradesSell,
          color="r",
          marker="v",
          zorder=2,
          label="sell")
      ax1.legend()

      # Setup second subplot and x axis
      ax2.axhline(0, color='black')
      ax2.set_xlabel("Timestamp")
      ax2.set_xticks(np.arange(len(self.timestamps)), minor=True)
      minorPeriod = int(np.ceil(len(self.timestamps) / 60))
      ax1.xaxis.set_minor_locator(pyplot.MultipleLocator(minorPeriod))
      majorPeriod = minorPeriod * 5
      ax1.xaxis.set_major_locator(pyplot.MultipleLocator(majorPeriod))
      labels = ["HIDDEN"]
      for a in self.timestamps[0::majorPeriod]:
        labels.append(a.replace(tzinfo=None))
      labels.append(self.timestamps[-1].replace(tzinfo=None))
      ax2.set_xlim(0, len(self.timestamps))
      ax2.set_xticklabels(labels, rotation=30, horizontalalignment="right")

      # Plot on second subplot
      ax2.set_ylabel("Transaction Profit")
      profitsIndex = []
      profits = []
      prevProfit = 0
      for i in range(len(self.timestamps)):
        profit = self.securitiesProfit[symbol][i]
        if (profit - prevProfit) != 0:
          profits.append(profit - prevProfit)
          profitsIndex.append(i)
        prevProfit = profit
      profitColor = ['r' if i < 0 else 'g' for i in profits]
      ax2.scatter(profitsIndex, profits, color=profitColor)
    else:
      # Plot on first subplot
      ax1.axhline(self.initialCapital, color='black')
      ax1.set_ylabel("Closing Value ($)")
      ax1.plot(self.closingValue)

      # Setup second subplot and x axis
      ax2.axhline(0, color='black')
      ax2.set_xlabel("Timestamp")
      ax2.set_xticks(np.arange(len(self.dates)), minor=True)
      minorPeriod = int(np.ceil(len(self.dates) / 60))
      ax1.xaxis.set_minor_locator(pyplot.MultipleLocator(minorPeriod))
      majorPeriod = minorPeriod * 5
      ax1.xaxis.set_major_locator(pyplot.MultipleLocator(majorPeriod))
      labels = ["HIDDEN"]
      for a in self.dates[0::majorPeriod]:
        labels.append(a.date())
      labels.append(self.dates[-1].date())
      ax2.set_xlim(0, len(self.dates))
      ax2.set_xticklabels(labels, rotation=30, horizontalalignment="right")

      # Plot on second subplot
      ax2.set_ylabel("Daily Return (%)")
      ax2.plot(self.dailyReturn)

    ax1.grid(b=True, which="both")
    ax2.grid(b=True, which="both")
    ax1.grid(which='major', linestyle='-', linewidth='0.5')
    ax1.grid(which='minor', linestyle=':', linewidth='0.5')
    ax2.grid(which='major', linestyle='-', linewidth='0.5')
    ax2.grid(which='minor', linestyle=':', linewidth='0.5')
    fig.tight_layout()
    pyplot.show()
