#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

# import algorithms
# import exchange
# import portfolio
# import math
# from matplotlib import dates
# from matplotlib import pyplot
# import mplfinance
# import pandas
# import statistics

import alpaca
import datetime
import strategy as st

def run(api, strategy, timestamps):
  for timestamp in timestamps:
    pass
    # datas = api.getDatas(timestamp)
    # strategy._setDatas(datas, timestamp)
    # strategy.nextMinute()

## Main function
def main():
  api = alpaca.Alpaca()
  fromDate = datetime.date(2019, 6, 1)
  toDate = datetime.date(2020, 6, 30)

  symbol = api.loadSymbol("AMD", fromDate, toDate=toDate)
  timestamps = api.getTimestamps(fromDate, toDate=toDate)
  symbol.setCurrentIndex(timestamps[-1])
  print(symbol.minute[0])
  print(symbol.day[0])

  # run(api, st.strategy, timestamps)

  # period = 500

  # exchange.init(symbols, period=period, historyDays=algorithms.KIPPslowDays)
  # p = portfolio.Portfolio(3000)

  # dataDates = []
  # dataOpen = []
  # dataHigh = []
  # dataLow = []
  # dataClose = []

  # dailyProfit = [0]
  # dailyPercent = [0]
  # dailyMovement = [0]

  # for i in range(period):
  #   if (i % 5) == 0:
  #     p.fund(150)

  #   exchange.openMarket()
  #   print(exchange.today)

  #   dataDates.append(pandas.to_datetime(exchange.today))
  #   dataOpen.append(p.value(time="open"))
  #   dataLow.append(p.value(time="low"))

  #   algorithms.KIPP(symbols, p)

  #   dataClose.append(p.value(time="close"))
  #   dataHigh.append(p.value(time="high"))
  #   dailyProfit.append(dataClose[-1] - p.investment)
  #   dailyMovement.append(dailyProfit[-1] - dailyProfit[-2])
  #   dailyPercent.append((dailyMovement[-1] / p.value()) * 100)
  #   print("Closed with movement of ${:5.2f}".format(dailyMovement[-1]))
  #   exchange.closeMarket()

  # closeRatio = dataClose[-1] / p.investment
  # percentageYr = math.log(closeRatio) * 252 / period / math.log(2)
  # gains = dataClose[-1]
  # print("Ended with gain of ${:.2f} with ${:.2f} invested at {:.1f}% {:.1f}%(yr)".format(
  #   gains, p.investment, (closeRatio - 1) * 100, percentageYr * 100))

  # riskFreeReturn = 3
  # print("Average daily return: {}".format(statistics.mean(dailyPercent)))
  # sharpe = (statistics.mean(dailyPercent) - riskFreeReturn)/statistics.stdev(dailyPercent)
  # print("Sharpe Ratio: {}".format(sharpe))

  # data = {
  #     "Open": dataOpen,
  #     "High": dataHigh,
  #     "Low": dataLow,
  #     "Close": dataClose}
  # data = pandas.DataFrame(data=data, index=dataDates)
  # mplfinance.plot(data, type='line', mav=(10, 100))

  # _, (subplot1, subplot2, subplot3) = pyplot.subplots(nrows=3, sharex=True)

  # subplot1.plot(dailyProfit)
  # subplot1.set_title("Profit")
  # subplot1.set_ylabel("$")

  # subplot2.plot(dailyPercent)
  # subplot2.set_title("Percent")
  # subplot2.set_ylabel("%")

  # subplot3.plot(dailyMovement)
  # subplot3.set_title("Daily Movement")
  # subplot3.set_ylabel("$")

  # pyplot.xlabel("Time")
  # pyplot.show()


if __name__ == "__main__":
  main()
