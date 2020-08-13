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
  def __init__(self, symbol):
    self.symbol = symbol
    self.lifetimeBuyPrices = []
    self.lifetimeSellPrices = []
    self.lifetimeShares = []
    self.buyShares = 0
    self.sellShares = 0
    self.buyPrice = 0
    self.sellPrice = 0
    self.dayTrade = True
    self.position = None

def colorProfitPercent(profitPercent):
  if profitPercent > 0.05:
    return colorama.Fore.CYAN
  if profitPercent > 0:
    return colorama.Fore.GREEN
  if profitPercent == 0:
    return colorama.Fore.WHITE
  if profitPercent > -0.005:
    return colorama.Fore.YELLOW
  return colorama.Fore.RED

def colorProfit(profit):
  if profit > 0:
    return colorama.Fore.GREEN
  if profit == 0:
    return colorama.Fore.WHITE
  return colorama.Fore.RED

def colorAccuracy(accuracy):
  if accuracy > 0.80:
    return colorama.Fore.CYAN
  if accuracy > 0.65:
    return colorama.Fore.GREEN
  if accuracy > 0.5:
    return colorama.Fore.YELLOW
  return colorama.Fore.RED

def overallReport(restAPI, dateStart, dateEnd, orders):
  history = restAPI.get_portfolio_history(
      date_start=(dateStart - datetime.timedelta(days=10)),
      date_end=dateEnd,
      timeframe="1D")

  print(f"╔════════════╤═══════════════╤═════════════════════╤═════════════╤════════╗")
  print(f"║ Date       │ Ending Equity │ Daily Change (P/L)  │ Wins/Losses │ Risk   ║")
  dailyReturns = []
  wins = []
  losses = []
  orderIndex = 0
  securities = {}
  initialEquity = None
  deposits = 0
  for i in range(len(history.timestamp)):
    timestamp = est.localize(
        datetime.datetime.fromtimestamp(
            history.timestamp[i]))
    if timestamp.date() < dateStart:
      continue
    prevEquity = history.equity[i - 1]
    if initialEquity is None:
      initialEquity = prevEquity
    endingEquity = history.equity[i]

    profit = endingEquity - prevEquity
    profitPercent = (profit / prevEquity)
    dailyReturns.append(profitPercent)

    dailyWins = []
    dailyLosses = []
    while orderIndex < len(
      orders) and orders[orderIndex].filled_at.date() <= timestamp.date():
      order = orders[orderIndex]
      if order.symbol not in securities:
        securities[order.symbol] = Security(order.symbol)
      security = securities[order.symbol]
      filledQty = float(order.filled_qty)
      filledPrice = float(order.filled_avg_price) * filledQty
      if order.side == "buy":
        security.buyShares += filledQty
        security.buyPrice += filledPrice
      else:
        security.sellShares += filledQty
        security.sellPrice += filledPrice

      if security.sellShares == security.buyShares:
        # Exiting position
        if order.filled_at.date() == timestamp.date():
          orderProfit = security.sellPrice - security.buyPrice
          security.lifetimeBuyPrices.append(security.buyPrice)
          security.lifetimeSellPrices.append(security.sellPrice)
          security.lifetimeShares.append(security.buyShares)
          if orderProfit > 0:
            wins.append(orderProfit)
            dailyWins.append(orderProfit)
          else:
            losses.append(orderProfit)
            dailyLosses.append(orderProfit)

        # Reset for next position entry
        security.sellPrice = 0
        security.sellShares = 0
        security.buyPrice = 0
        security.buyShares = 0
      orderIndex += 1

    countWins = len(dailyWins)
    countLosses = len(dailyLosses)
    if (countWins + countLosses) == 0:
      accuracy = 0
    else:
      accuracy = countWins / (countWins + countLosses)

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

    print(f"║ {timestamp.date().isoformat()} │ "
          f"${endingEquity:12,.2f} │ "
          f"${colorProfit(profit)}{profit:10,.2f} {colorProfitPercent(profitPercent)}{profitPercent * 100:6.2f}%{colorama.Fore.WHITE} │ "
          f"{countWins:3}:{countLosses:<3}{colorAccuracy(accuracy)}{accuracy * 100:3.0f}%{colorama.Fore.WHITE} │ "
          f"{riskToReward:6} ║")
    # print("Overnight positions")
    # for symbol, security in securities.items():
    #   if security.buyShares != 0:
    #     print(f"{symbol:5} {security.buyShares - security.sellShares}")

  print(f"╠════════════╧═══════════════╧═══════╤═════════════╧═════════════╧════════╣")
  profit = history.equity[-1] - (initialEquity + deposits)

  print(f"║ Total profit:      ${colorProfit(profit)}{profit:12,.2f}{colorama.Fore.WHITE}   │ "
        f"Beginning equity:   ${initialEquity:12,.2f}  ║")

  profitPercent = profit / initialEquity
  print(f"║ Simple return:             {colorProfitPercent(profitPercent)}{profitPercent * 100:6.3f}%{colorama.Fore.WHITE} │ "
        f"Deposits:           ${deposits:12,.2f}  ║")

  averageReturns = np.mean(dailyReturns)

  stddev = np.std(dailyReturns)
  if stddev == 0:
    sharpeRatio = float('inf')
  else:
    sharpeRatio = averageReturns / stddev * np.sqrt(252)
  if sharpeRatio < 1:
    colorRatio = colorama.Fore.RED
  elif sharpeRatio > 3:
    colorRatio = colorama.Fore.GREEN
  else:
    colorRatio = colorama.Fore.YELLOW
  print(f"║ Average daily return:      {colorProfitPercent(averageReturns)}{averageReturns * 100:6.3f}%{colorama.Fore.WHITE} │ "
        f"Sharpe ratio:              {colorRatio}{sharpeRatio:6.3f}{colorama.Fore.WHITE}  ║")

  twr = np.product(np.array(dailyReturns) + 1) - 1

  negativeReturns = np.array([a for a in dailyReturns if a < 0])
  downsideVariance = np.sum(negativeReturns**2) / len(dailyReturns)
  if downsideVariance == 0:
    sortinoRatio = float('inf')
  else:
    sortinoRatio = averageReturns / np.sqrt(downsideVariance) * np.sqrt(252)
  if sortinoRatio < 2:
    colorRatio = colorama.Fore.RED
  elif sortinoRatio > 6:
    colorRatio = colorama.Fore.GREEN
  else:
    colorRatio = colorama.Fore.YELLOW
  print(f"║ Time weighted return:      {colorProfitPercent(twr)}{twr * 100:6.3f}%{colorama.Fore.WHITE} │ "
        f"Sortino ratio:             {colorRatio}{sortinoRatio:6.3f}{colorama.Fore.WHITE}  ║")

  countWins = len(wins)
  countLosses = len(losses)
  averageWin = np.average(wins) if countWins != 0 else 0
  averageLoss = np.average(losses) if countLosses != 0 else 0
  print(f"║ Winning trades:        {countWins:6}      │ "
        f"Average win:         ${averageWin:10,.2f}   ║")
  print(f"║ Losing trades:         {countLosses:6}      │ "
        f"Average loss:        ${averageLoss:10,.2f}   ║")
  if (countWins + countLosses) == 0:
    accuracy = 0
  else:
    accuracy = countWins / (countWins + countLosses)

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
  print(f"║ Trade accuracy:            {colorAccuracy(accuracy)}{accuracy * 100:6.3f}%{colorama.Fore.WHITE} │ "
        f"Risk-to-reward ratio:   {riskToReward:11}║")

  sortedSecurities = sorted(
      securities.items(),
      key=lambda security: np.sum(security[1].lifetimeBuyPrices) -
      np.sum(security[1].lifetimeSellPrices))
  print(f"╠════════╤════════════════╤══════════╪═══════════════════╤════════════════╣")
  print(f"║ Symbol │ Total Profit   │ Shares   │ Profit/Share      │ Wins/Losses    ║")
  for symbol, security in sortedSecurities:
    if np.sum(security.lifetimeShares) == 0:
      continue
    profit = np.sum(security.lifetimeSellPrices) - \
        np.sum(security.lifetimeBuyPrices)
    profitPercent = profit / np.sum(security.lifetimeBuyPrices)

    profitEach = profit / np.sum(security.lifetimeShares)
    countWins = 0
    countLosses = 0
    exitProfits = []
    for i in range(len(security.lifetimeBuyPrices)):
      exitProfit = security.lifetimeSellPrices[i] - \
        security.lifetimeBuyPrices[i]
      exitProfits.append(exitProfit / security.lifetimeBuyPrices[i])
      if exitProfit >= 0:
        countWins += 1
      else:
        countLosses += 1
    accuracy = countWins / (countWins + countLosses)

    print(f"║ {symbol:<6} │ "
          f"${colorProfit(profit)}{profit:13,.2f}{colorama.Fore.WHITE} │ "
          f"{np.sum(security.lifetimeShares):8,.0f} │ "
          f"${profitEach:8,.2f} {colorProfitPercent(profitPercent)}{profitPercent*100:6.2f}%{colorama.Fore.WHITE} │ "
          f"{countWins:4}:{countLosses:<4}{colorAccuracy(accuracy)} {accuracy * 100:3.0f}%{colorama.Fore.WHITE} ║")
  print(f"╚════════╧════════════════╧══════════╧═══════════════════╧════════════════╝")

def ordersReport(restAPI, dateStart, dateEnd, orders):
  history = restAPI.get_portfolio_history(
      date_start=(dateStart - datetime.timedelta(days=10)),
      date_end=dateEnd,
      timeframe="1D")

  print(f"╔═══════╤═══════╤════════════╤═════════════╤════════╤═════════════════════╗")
  print(f"║ Time  │ Asset │ Position   │ Enter Price │ Shares │ Profit              ║")
  orderIndex = 0
  securities = {}
  for i in range(len(history.timestamp)):
    timestamp = est.localize(
        datetime.datetime.fromtimestamp(
            history.timestamp[i]))
    if timestamp.date() < dateStart:
      continue
    print(f"╠═{timestamp.date().isoformat()}════╪════════════╪═════════════╪════════╪═════════════════════╣")
    lines = []
    while orderIndex < len(
      orders) and orders[orderIndex].filled_at.date() <= timestamp.date():
      order = orders[orderIndex]
      if order.symbol not in securities:
        securities[order.symbol] = Security(order.symbol)
      security = securities[order.symbol]
      if security.sellShares == 0 and security.buyShares == 0:
        if order.side == "buy":
          security.position = "long"
        else:
          security.position = "short"

      filledQty = float(order.filled_qty)
      filledPrice = float(order.filled_avg_price) * filledQty
      if order.side == "buy":
        security.buyShares += filledQty
        security.buyPrice += filledPrice
      else:
        security.sellShares += filledQty
        security.sellPrice += filledPrice

      if security.sellShares == security.buyShares:
        # Exiting position
        if order.filled_at.date() == timestamp.date():
          profit = security.sellPrice - security.buyPrice
          if security.dayTrade:
            position = "Day   " + security.position
            for line in lines:
              if line[1] == order.symbol and line[2].startswith("Enter"):
                lines.remove(line)
          else:
            position = "Exit  " + security.position
          if order.side == "sell":
            enterPrice = security.buyPrice
            shares = security.buyShares
          else:
            enterPrice = security.sellPrice
            shares = -security.sellShares

          profitPercent = profit / enterPrice
          time = order.filled_at.astimezone(est)

          lines.append([time, order.symbol, position, enterPrice,
                        shares, profit, profitPercent])

        # Reset for next position entry
        security.sellPrice = 0
        security.sellShares = 0
        security.buyPrice = 0
        security.buyShares = 0
        security.dayTrade = True
      elif (security.position == "long" and order.side == "buy") or (security.position == "short" and order.side == "sell"):
        # Entering / increasing position
        if order.filled_at.date() == timestamp.date():
          position = "Enter " + security.position
          if order.side == "sell":
            enterPrice = security.buyPrice
            shares = -filledQty
          else:
            enterPrice = security.sellPrice
            shares = filledQty

          time = order.filled_at.astimezone(est)
          contribution = False
          for line in lines:
            if line[1] == order.symbol and (
              line[2].startswith("Enter") or line[2].startswith("Incr")):
              line[0] = time
              if not security.dayTrade:
                line[2] = "Incr. " + security.position
              line[3] += filledPrice
              line[4] += shares
              contribution = True

          if not contribution:
            lines.append([time, order.symbol, position, filledPrice,
                          shares, 0, 0])
      else:
        # Decreasing position
        pass

      orderIndex += 1

    for symbol, security in securities.items():
      if security.buyShares != 0 or security.sellShares != 0:
        security.dayTrade = False
    lines.sort(key=lambda line: line[0])
    for line in lines:
      if line[2].startswith("Enter") or line[2].startswith("Incr"):
        print(f"║ {line[0]:%H:%M} │ "
              f"{line[1]:5} │ "
              f"{line[2]:<10} │ "
              f"${line[3]:10,.2f} │ "
              f"{line[4]:6,.0f} │ "
              f"                    ║")
      else:
        print(f"║ {line[0]:%H:%M} │ "
              f"{line[1]:5} │ "
              f"{line[2]:<10} │ "
              f"${line[3]:10,.2f} │ "
              f"{line[4]:6,.0f} │ "
              f"${colorProfit(line[5])}{line[5]:10,.2f} {colorProfitPercent(line[6])}{line[6] * 100:6.2f}%{colorama.Fore.WHITE} ║")
      # print(line)
    #     # print(f"{symbol:5} {security.buyShares - security.sellShares}")
  print(f"╚═══════╧═══════╧════════════╧═════════════╧════════╧═════════════════════╝")


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

  overallReport(restAPI, dateStart, dateEnd, orders)
  if options.orders:
    ordersReport(restAPI, dateStart, dateEnd, orders)

  # print(restAPI.list_orders(status="closed"))


if __name__ == '__main__':
  main()
