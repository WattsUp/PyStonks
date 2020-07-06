#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

from . import alpaca
import concurrent.futures
import datetime
import itertools
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
  #  @param initialCapital to start the simulation with
  def __init__(self, fromDate, toDate=datetime.date.today(),
               symbol=None, preStart=50, initialCapital=10000):
    preStartFromDate = fromDate - datetime.timedelta(days=preStart)
    self.api = alpaca.Alpaca(preStartFromDate, toDate=toDate, symbol=symbol)
    self.initialCapital = initialCapital
    # self.securities = {}
    # self.securitiesPrice = {}
    # self.securitiesShares = {}
    # self.securitiesProfit = {}
    self.calendar = self.api.getCalendar(fromDate, toDate)
    self.timestamps = []
    self.dates = []
    self.reports = []

  ## Run a simulation, expects setup to be called just before
  #  @param strategy to run
  #  @param startDate of the simulation
  #  @param progressBar will output a dot every so often until complete when True
  #  @param recordPlotStats will log statistics for plotting when True
  #  @param testCase information to add to the report
  #  @param initialSecurities to start the simulations with
  #  @return report of the run
  def run(self, strategy, calendar=None,
          progressBar=True, recordPlotStats=True, testCase=None, initialSecurities=None):
    if calendar is None:
      calendar = self.calendar
    dailyReturn = []
    closingValue = []

    if initialSecurities and "cash" in initialSecurities.keys():
      initialCapital = initialSecurities["cash"]
      initialSecurities.pop("cash", None)
    else:
      initialCapital = self.initialCapital

    startDate = est.localize(
        datetime.datetime.combine(
            calendar.index[0],
            calendar.open[0]))
    strategy._setup(self.api, startDate, initialCapital,
                    initialSecurities=initialSecurities)

    progressTick = max(1, np.floor(len(self.calendar.index) / 40))
    i = 0
    lastWeekNumber = None

    start = datetime.datetime.now()
    for index, row in calendar.iterrows():
      weekNumber = index.isocalendar()[1]
      if weekNumber != lastWeekNumber:
        dateMonday = index - datetime.timedelta(days=index.weekday())
        strategy.nextWeek(self, dateMonday)
        lastWeekNumber = weekNumber
      timestamps = self.api.getTimestamps(row)
      for timestamp in timestamps:
        strategy.timestamp = timestamp
        strategy.portfolio._processOrders()

        strategy.nextMinute()

        # if recordPlotStats:
        #   self.timestamps.append(timestamp)
        #   for security in self.securities.values():
        #     self.securitiesPrice[security.symbol].append(
        #       security.minute[0].close)
        #     self.securitiesShares[security.symbol].append(
        #       security.shares)
        #     self.securitiesProfit[security.symbol].append(
        #       security.lifeTimeProfit)
        strategy.portfolio._nextMinute()

      value = strategy.portfolio.value()
      if len(closingValue) > 0:
        dailyReturn.append((value / closingValue[-1] - 1) * 100)
      else:
        dailyReturn.append(0)
      closingValue.append(value)
      if recordPlotStats:
        self.dates.append(index)
      strategy.portfolio._marketClose()
      i = (i + 1) % progressTick
      if i == 0 and progressBar:
        print(".", end="", flush=True)

    report = {}
    report["duration"] = datetime.datetime.now() - start
    if progressBar:
      print("complete")

    if recordPlotStats:
      report["close"] = closingValue
      report["daily"] = dailyReturn
    report["testCase"] = testCase
    report["params"] = strategy.params

    avgDailyReturn = np.mean(dailyReturn)
    stddev = np.std(dailyReturn)
    if stddev == 0:
      report["sharpe"] = 0
    else:
      sharpe = avgDailyReturn / stddev * np.sqrt(252)
      report["sharpe"] = sharpe

    negativeReturns = np.array([a for a in dailyReturn if a < 0])
    downsideVariance = np.sum(negativeReturns**2) / len(dailyReturn)
    if downsideVariance == 0:
      report["sortino"] = 0
    else:
      sortino = avgDailyReturn / np.sqrt(downsideVariance) * np.sqrt(252)
      report["sortino"] = sortino

    profit = closingValue[-1] - initialCapital
    report["profit"] = profit
    profitPercent = profit / initialCapital
    report["profit-percent"] = profitPercent
    # (PeriodPercent + 1)^(number of periods in a trading year)
    profitPercentYr = np.power(
      (profitPercent + 1), 252 / len(closingValue)) - 1
    report["profit-percent-yr"] = profitPercentYr

    self.reports.append(report)
    return report

  ## Runner function for optimizing, sets the params of the strategy
  #  @param strategy object to test
  #  @param calendar of the simulation
  #  @param paramCombination combination of parameters to execute strategy with
  #  @param progressBar will print a dot upon completing
  #  @param initialSecurities to start the simulations with
  #  @return report object
  def _optimizeRunner(self, strategy, calendar,
                      paramCombination, progressBar=True, initialSecurities=None):
    i = 0
    testCase = "["
    for param in strategy.paramsAdj.keys():
      testCase += "{}={:4},".format(param, paramCombination[i])
      strategy.params[param] = paramCombination[i]
      i += 1
    testCase += "]"
    strategy.silent = True
    strategy.walkForward = False
    report = self.run(
        strategy,
        calendar=calendar,
        progressBar=False,
        recordPlotStats=False,
        testCase=testCase,
        initialSecurities=initialSecurities)
    if progressBar:
      print(".", end="", flush=True)
    return report

  ## Optimize a single parameter of a strategy by running though its possible values and checking a metric
  #  @param strategy object to test
  #  @param calendar of the simulation
  #  @param targetMetric to output value for
  #  @param progressBar will print a dot upon completing a test case
  #  @param initialSecurities to start the simulations with
  #  @return list of top 5 reports sorted by targetMetric
  def optimize(self, strategy, calendar=None,
               targetMetric="sortino", progressBar=True, initialSecurities=None):
    if not bool(strategy.paramsAdj):
      print("No adjustable parameters, add ranges to 'paramsAdj'")
      return
    paramsLists = []
    self.reports = []
    for param in strategy.paramsAdj.values():
      paramsLists.append(list(param))

    reports = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
      futures = []
      for combination in itertools.product(*paramsLists):
        futures.append(
            executor.submit(
                self._optimizeRunner,
                strategy,
                calendar,
                combination,
                progressBar=progressBar,
                initialSecurities=initialSecurities))
      for future in concurrent.futures.as_completed(futures):
        reports.append(future.result())

    if progressBar:
      print("complete")
    sortedReports = sorted(
        reports,
        key=lambda x: x[targetMetric],
        reverse=True)[:5]
    return sortedReports

  ## Print a report of the last run
  #  @param report object to print, None will print the latest
  def printReport(self, report=None):
    if not report:
      report = self.reports[-1]
    print("Test duration:   {}".format(report["duration"]))
    print("Sharpe ratio:    {:11.3f}".format(report["sharpe"]))
    print("Sortino ratio:   {:11.3f}".format(report["sortino"]))
    print("Closing value:  ${:10.2f}".format(report["close"][-1]))
    print("Closing profit: ${:10.2f} = {:.2f}% = {:.2f}%(yr)\n".format(
        report["profit"], report["profit-percent"] * 100, report["profit-percent-yr"] * 100))

  def plot(self, symbol=None):
    fig, (ax1, ax2) = pyplot.subplots(2, 1, sharex=True)
    if symbol:
      # # Plot on first subplot
      # ax1.set_ylabel("Closing Price ($)")
      # ax1.plot(
      #     self.securitiesPrice[symbol],
      #     color="black",
      #     zorder=0,
      #     label=symbol)
      # bottom, top = ax1.get_ylim()
      # offset = (top - bottom) / 20
      # # Buy and sell markers
      # tradeBuyIndex = []
      # tradeSellIndex = []
      # tradesBuy = []
      # tradesSell = []
      # prevShares = 0
      # for i in range(len(self.timestamps)):
      #   shares = self.securitiesShares[symbol][i]
      #   if (shares - prevShares) > 0:
      #     tradesBuy.append(self.securitiesPrice[symbol][i] - offset)
      #     tradeBuyIndex.append(i)
      #   elif (shares - prevShares) < 0:
      #     tradesSell.append(self.securitiesPrice[symbol][i] + offset)
      #     tradeSellIndex.append(i)
      #   prevShares = shares
      # ax1.scatter(
      #     tradeBuyIndex,
      #     tradesBuy,
      #     color="g",
      #     marker="^",
      #     zorder=1,
      #     label="buy")
      # ax1.scatter(
      #     tradeSellIndex,
      #     tradesSell,
      #     color="r",
      #     marker="v",
      #     zorder=2,
      #     label="sell")
      # ax1.legend()

      # # Setup second subplot and x axis
      # ax2.axhline(0, color="black")
      # ax2.set_xlabel("Timestamp")
      # ax2.set_xticks(np.arange(len(self.timestamps)), minor=True)
      # minorPeriod = int(np.ceil(len(self.timestamps) / 60))
      # ax1.xaxis.set_minor_locator(pyplot.MultipleLocator(minorPeriod))
      # majorPeriod = minorPeriod * 5
      # ax1.xaxis.set_major_locator(pyplot.MultipleLocator(majorPeriod))
      # labels = ["HIDDEN"]
      # for a in self.timestamps[0::majorPeriod]:
      #   labels.append(a.replace(tzinfo=None))
      # labels.append(self.timestamps[-1].replace(tzinfo=None))
      # ax2.set_xlim(0, len(self.timestamps))
      # ax2.set_xticklabels(labels, rotation=30, horizontalalignment="right")

      # # Plot on second subplot
      # ax2.set_ylabel("Transaction Profit")
      # profitsIndex = []
      profits = []
      # prevProfit = 0
      # for i in range(len(self.timestamps)):
      #   profit = self.securitiesProfit[symbol][i]
      #   if (profit - prevProfit) != 0:
      #     profits.append(profit - prevProfit)
      #     profitsIndex.append(i)
      #   prevProfit = profit
      # profitColor = ["r" if i < 0 else "g" for i in profits]
      # ax2.scatter(profitsIndex, profits, color=profitColor)
    else:
      # Plot on first subplot
      ax1.axhline(self.initialCapital, color="black")
      ax1.set_ylabel("Closing Value ($)")
      ax1.plot(self.reports[-1]["close"])

      # Setup second subplot and x axis
      ax2.axhline(0, color="black")
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
      ax2.plot(self.reports[-1]["daily"])

    ax1.grid(b=True, which="both")
    ax2.grid(b=True, which="both")
    ax1.grid(which="major", linestyle="-", linewidth="0.5")
    ax1.grid(which="minor", linestyle=":", linewidth="0.5")
    ax2.grid(which="major", linestyle="-", linewidth="0.5")
    ax2.grid(which="minor", linestyle=":", linewidth="0.5")
    fig.tight_layout()
    pyplot.show()
