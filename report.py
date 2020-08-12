#!/usr/bin/env python

import alpaca_trade_api
import argparse
import colorama
import datetime
import numpy as np
import os
import pytz
import sys

est = pytz.timezone("America/New_York")
colorama.init(autoreset=True)

class Security:
  def __init__(self):
    self.lifetimeProfit = 0
    self.shares = 0
    self.price = 0

def overallReport(restAPI, dateStart, dateEnd, orders):
  history = restAPI.get_portfolio_history(
      date_start=(dateStart - datetime.timedelta(days=10)),
      date_end=dateEnd,
      timeframe="1D")

  print(f"X-------------------------------------------------------------------------X")
  print(f"| Date       | Ending Equity | Daily Change (P/L)  | Wins/Losses | Risk   |")
  dailyReturns = []
  wins = []
  losses = []
  orderIndex = 0
  securities = {}
  for i in range(len(history.timestamp)):
    timestamp = est.localize(
        datetime.datetime.fromtimestamp(
            history.timestamp[i]))
    if timestamp.date() < dateStart:
      continue
    prevEquity = history.equity[i - 1]
    endingEquity = history.equity[i]

    profit = endingEquity - prevEquity
    profitPercent = (profit / prevEquity)
    if profit < 0:
      color = colorama.Fore.RED
    elif profit > 0:
      color = colorama.Fore.GREEN
    else:
      color = colorama.Fore.WHITE
    dailyReturns.append(profitPercent)

    dailyWins = []
    dailyLosses = []
    while orderIndex < len(
      orders) and orders[orderIndex].filled_at.date() <= timestamp.date():
      order = orders[orderIndex]
      if order.symbol not in securities:
        securities[order.symbol] = Security()
      security = securities[order.symbol]
      filledQty = float(order.filled_qty)
      filledPrice = float(order.filled_avg_price) * filledQty
      if order.side == "buy":
        security.shares += filledQty
        security.price += filledPrice
      else:
        if security.shares == 0:
          print(f"Sold shares before buying {order.symbol}")
          sys.exit(0)
        entryPrice = security.price * filledQty / security.shares
        security.shares -= filledQty
        security.price -= entryPrice
        if order.filled_at.date() == timestamp.date():
          orderProfit = filledPrice - entryPrice
          if orderProfit > 0:
            wins.append(orderProfit)
            dailyWins.append(orderProfit)
          else:
            losses.append(orderProfit)
            dailyLosses.append(orderProfit)
      orderIndex += 1

    countWins = len(dailyWins)
    countLosses = len(dailyLosses)
    if (countWins + countLosses) == 0:
      color2 = colorama.Fore.BLACK
      accuracy = 0
    else:
      accuracy = countWins / (countWins + countLosses)
      if accuracy < 0.5:
        color2 = colorama.Fore.RED
      elif accuracy > 0.65:
        color2 = colorama.Fore.GREEN
      else:
        color2 = colorama.Fore.YELLOW

    if countWins == 0 or countLosses == 0:
      riskToReward = ""
    else:
      averageWin = np.average(dailyWins)
      averageLoss = np.abs(np.average(dailyLosses))
      rrRatio = averageLoss / averageWin
      if rrRatio < 1:
        riskToReward = f"{colorama.Fore.GREEN}{1:2.0f}:{1/rrRatio:<3.0f}{colorama.Fore.WHITE}"
      elif rrRatio > 1:
        riskToReward = f"{colorama.Fore.RED}{rrRatio:2.0f}:{1:<3.0f}{colorama.Fore.WHITE}"
      else:
        riskToReward = f" 1:1  "

    print(f"| {timestamp.date().isoformat()} | "
          f"${endingEquity:12,.2f} | "
          f"${color}{profit:10,.2f} {profitPercent * 100:6.2f}%{colorama.Fore.WHITE} | "
          f"{countWins:3}:{countLosses:<3}{color2}{accuracy * 100:3.0f}%{colorama.Fore.WHITE} | "
          f"{riskToReward:6} | ")

  print(f"X-------------------------------------------------------------------------X")
  averageReturns = np.mean(dailyReturns)
  if averageReturns < 0:
    color1 = colorama.Fore.RED
  elif averageReturns > 0:
    color1 = colorama.Fore.GREEN
  else:
    color1 = colorama.Fore.WHITE

  twr = np.product(np.array(dailyReturns) + 1) - 1
  if twr < 0:
    color2 = colorama.Fore.RED
  elif twr > 0:
    color2 = colorama.Fore.GREEN
  else:
    color2 = colorama.Fore.WHITE
  print(f"| Average daily return:      {color1}{averageReturns * 100:6.3f}%{colorama.Fore.WHITE} | "
        f"Time weighted return:      {color2}{twr * 100:6.3f}%{colorama.Fore.WHITE} |")

  stddev = np.std(dailyReturns)
  if stddev == 0:
    sharpeRatio = float('inf')
  else:
    sharpeRatio = averageReturns / stddev * np.sqrt(252)
  if sharpeRatio < 1:
    color1 = colorama.Fore.RED
  elif sharpeRatio > 3:
    color1 = colorama.Fore.GREEN
  else:
    color1 = colorama.Fore.YELLOW

  negativeReturns = np.array([a for a in dailyReturns if a < 0])
  downsideVariance = np.sum(negativeReturns**2) / len(dailyReturns)
  if downsideVariance == 0:
    sortinoRatio = float('inf')
  else:
    sortinoRatio = averageReturns / np.sqrt(downsideVariance) * np.sqrt(252)
  if sortinoRatio < 2:
    color2 = colorama.Fore.RED
  elif sortinoRatio > 6:
    color2 = colorama.Fore.GREEN
  else:
    color2 = colorama.Fore.YELLOW
  print(f"| Sharpe ratio:              {color1}{sharpeRatio:6.3f}{colorama.Fore.WHITE}  | "
        f"Sortino ratio:             {color2}{sortinoRatio:6.3f}{colorama.Fore.WHITE}  |")

  countWins = len(wins)
  countLosses = len(losses)
  averageWin = np.average(wins) if countWins != 0 else 0
  averageLoss = np.average(losses) if countLosses != 0 else 0
  print(f"| Winning trades:        {countWins:6}      | "
        f"Average win:         ${averageWin:10.2f}   |")
  print(f"| Losing trades:         {countLosses:6}      | "
        f"Average loss:        ${averageLoss:10.2f}   |")
  if (countWins + countLosses) == 0:
    color1 = colorama.Fore.BLACK
    accuracy = 0
  else:
    accuracy = countWins / (countWins + countLosses)
    if accuracy < 0.5:
      color1 = colorama.Fore.RED
    elif accuracy > 0.65:
      color1 = colorama.Fore.GREEN
    else:
      color1 = colorama.Fore.YELLOW

  if countWins == 0 or countLosses == 0:
    riskToReward = ""
  else:
    rrRatio = np.abs(averageLoss / averageWin)
    if rrRatio < 1:
      riskToReward = f"{colorama.Fore.GREEN}{1:5}:{1/rrRatio:<5.1f}{colorama.Fore.WHITE}"
    elif rrRatio > 1:
      riskToReward = f"{colorama.Fore.RED}{rrRatio:5.1f}:{1:<5}{colorama.Fore.WHITE}"
    else:
      riskToReward = f"  1:1  "
  print(f"| Trade accuracy:            {color1}{accuracy * 100:6.3f}%{colorama.Fore.WHITE} | "
        f"Risk-to-reward ratio:   {riskToReward:11}|")
  print(f"X-------------------------------------------------------------------------X")

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      "--live",
      help="Run on live, not paper, account",
      action="store_true")
  parser.add_argument(
    "--end",
    help=("Day to end report, format: " +
          datetime.date.today().isoformat()),
    default=datetime.date.today().isoformat()
  )
  parser.add_argument(
    "--start",
    help=("Day to start report, format: " +
          datetime.date.today().isoformat()),
  )
  parser.add_argument(
    "--period",
    help="Number of days to return report over, default 5",
    default=5
  )
  parser.add_argument(
      "--orders",
      help="List orders for each day",
      action="store_true")
  options = parser.parse_args()
  options.period = int(options.period)
  if options.period < 1:
    print("Period must be at least 1")

  ALPACA_API_KEY = os.getenv("ALPACA_API_KEY_PAPER")
  ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_PAPER")
  base_url = "https://paper-api.alpaca.markets"
  if options.live:
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
    base_url = "https://api.alpaca.markets"

  restAPI = alpaca_trade_api.REST(ALPACA_API_KEY,
                                  ALPACA_SECRET_KEY,
                                  base_url,
                                  api_version="v2")

  account = restAPI.get_account()

  dateEnd = datetime.date.fromisoformat(options.end)
  if options.start:
    dateStart = datetime.date.fromisoformat(options.start)
  else:
    dateStart = dateEnd - datetime.timedelta(days=options.period)
  dateStart = max(dateStart, account.created_at.date())

  orders = []
  after = account.created_at
  while after.date() < dateEnd:
    orderList = restAPI.list_orders(
        status="closed",
        limit=500,
        after=after.isoformat(),
        direction="asc")
    for order in orderList:
      if order.status == "filled":
        orders.append(order)
    if len(orderList) == 0:
      break
    else:
      after = orderList[-1].created_at
  orders.sort(key=lambda order: order.filled_at)

  if options.orders:
    # orderReport()
    pass
  else:
    overallReport(restAPI, dateStart, dateEnd, orders)

  # print(restAPI.list_orders(status="closed"))


if __name__ == '__main__':
  main()
