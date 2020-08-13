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
    self.lifetimeEntryPrices = []
    self.lifetimeProfits = []
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

def getActivityTimestamp(activity):
  if activity.activity_type == "FILL":
    return activity.transaction_time.astimezone(est)
  if activity.activity_type == "CSR":
    return est.localize(datetime.datetime.fromisoformat(
      activity.date + "T20:01:00"))
  print(activity)
  sys.exit(0)

def overallReport(restAPI, dateStart, dateEnd, activities):
  history = restAPI.get_portfolio_history(
      date_start=(dateStart - datetime.timedelta(days=10)),
      date_end=dateEnd,
      timeframe="1D")
  if datetime.datetime.fromtimestamp(history.timestamp[-1]).date() < dateStart:
    print("Selected date(s) have no account history")
    sys.exit(0)

  print(f"╔════════════╤═══════════════╤═══════════════════════╤══════════════╤═════════╗")
  print(f"║ Date       │ Ending Equity │ Daily Change (P/L)    │ Wins/Losses  │ Risk    ║")
  dailyReturns = []
  wins = []
  losses = []
  initialEquity = None
  endingEquity = 0
  deposits = 0
  securities = {}
  for i in range(len(history.timestamp)):
    timestamp = est.localize(
        datetime.datetime.fromtimestamp(
            history.timestamp[i]))
    if timestamp.date() < dateStart:
      continue

    dailyWins = []
    dailyLosses = []
    dailyDeposits = 0
    if timestamp.date() in activities:
      for activity in activities[timestamp.date()]:
        if activity["type"] == "order":
          if "profit" in activity:
            if activity["profit"] > 0:
              wins.append(activity["profit"])
              dailyWins.append(activity["profit"])
            else:
              losses.append(activity["profit"])
              dailyLosses.append(activity["profit"])

            if activity["symbol"] not in securities:
              securities[activity["symbol"]] = Security(activity["symbol"])
            security = securities[activity["symbol"]]

            security.lifetimeEntryPrices.append(activity["enterPrice"])
            security.lifetimeProfits.append(activity["profit"])
            security.lifetimeShares.append(activity["shares"])
          else:
            # Entering
            pass

        elif activity["type"] == "deposit":
          dailyDeposits += activity["amount"]
        else:
          print(activity)
          sys.exit()

    prevEquity = history.equity[i - 1]
    if initialEquity is None:
      initialEquity = prevEquity
    if i != len(history.timestamp) - 1:
      # Don't count deposits added on the last day
      deposits += dailyDeposits
    # Deposits go in after close but are counted in closing equity
    endingEquity = history.equity[i] - dailyDeposits

    profit = endingEquity - prevEquity
    profitPercent = (profit / prevEquity)
    dailyReturns.append(profitPercent)

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
        riskToReward = f"{colorama.Fore.GREEN}{1:3.0f}:{1/rrRatio:<3.0f}{colorama.Fore.WHITE}"
      elif rrRatio > 1:
        riskToReward = f"{colorama.Fore.RED}{rrRatio:3.0f}:{1:<3.0f}{colorama.Fore.WHITE}"
      else:
        riskToReward = f"  1:1  "

    print(f"║ {timestamp.date().isoformat()} │ "
          f"${endingEquity:12,.2f} │ "
          f"${colorProfit(profit)}{profit:12,.2f} {colorProfitPercent(profitPercent)}{profitPercent * 100:6.2f}%{colorama.Fore.WHITE} │ "
          f"{countWins:3}:{countLosses:<3}{colorAccuracy(accuracy)} {accuracy * 100:3.0f}%{colorama.Fore.WHITE} │ "
          f"{riskToReward:7} ║")

  print(f"╠════════════╧═══════════════╧═════════╤═════════════╧══════════════╧═════════╣")
  profit = endingEquity - (initialEquity + deposits)

  print(f"║ Total profit:        ${colorProfit(profit)}{profit:12,.2f}{colorama.Fore.WHITE}   │ "
        f"Beginning equity:     ${initialEquity:12,.2f}  ║")

  profitPercent = profit / (initialEquity + deposits)
  print(f"║ Simple return:             {colorProfitPercent(profitPercent)}{profitPercent * 100:8.3f}%{colorama.Fore.WHITE} │ "
        f"Deposits:             ${deposits:12,.2f}  ║")

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
  print(f"║ Average daily return:      {colorProfitPercent(averageReturns)}{averageReturns * 100:8.3f}%{colorama.Fore.WHITE} │ "
        f"Sharpe ratio:                {colorRatio}{sharpeRatio:6.3f}{colorama.Fore.WHITE}  ║")

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
  print(f"║ Time weighted return:      {colorProfitPercent(twr)}{twr * 100:8.3f}%{colorama.Fore.WHITE} │ "
        f"Sortino ratio:               {colorRatio}{sortinoRatio:6.3f}{colorama.Fore.WHITE}  ║")

  countWins = len(wins)
  countLosses = len(losses)
  averageWin = np.average(wins) if countWins != 0 else 0
  averageLoss = np.average(losses) if countLosses != 0 else 0
  print(f"║ Winning trades:          {countWins:6}      │ "
        f"Average win:           ${averageWin:10,.2f}   ║")
  print(f"║ Losing trades:           {countLosses:6}      │ "
        f"Average loss:          ${averageLoss:10,.2f}   ║")
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
      riskToReward = f"{1:5}:{1:<5}"
  print(f"║ Trade accuracy:            {colorAccuracy(accuracy)}{accuracy * 100:8.3f}%{colorama.Fore.WHITE} │ "
        f"Risk-to-reward ratio:     {riskToReward:11}║")

  sortedSecurities = sorted(
      securities.items(),
      key=lambda security: -np.sum(security[1].lifetimeProfits))
  print(f"╠════════╤════════════════╤═══════════╤╧═══════════════════╤══════════════════╣")
  print(f"║ Symbol │ Total Profit   │ Shares    │ Profit/Share       │ Wins/Losses      ║")
  for symbol, security in sortedSecurities:
    if np.sum(security.lifetimeShares) == 0:
      continue
    profit = np.sum(security.lifetimeProfits)
    profitPercent = profit / np.sum(security.lifetimeEntryPrices)

    profitEach = profit / np.sum(security.lifetimeShares)
    countWins = 0
    countLosses = 0
    exitProfits = []
    for i in range(len(security.lifetimeProfits)):
      exitProfit = security.lifetimeProfits[i]
      exitProfits.append(exitProfit / security.lifetimeEntryPrices[i])
      if exitProfit >= 0:
        countWins += 1
      else:
        countLosses += 1
    accuracy = countWins / (countWins + countLosses)

    print(f"║ {symbol:<6} │ "
          f"${colorProfit(profit)}{profit:13,.2f}{colorama.Fore.WHITE} │ "
          f"{np.sum(security.lifetimeShares):9,.0f} │ "
          f"${profitEach:9,.2f} {colorProfitPercent(profitPercent)}{profitPercent*100:6.2f}%{colorama.Fore.WHITE} │ "
          f"{countWins:4}:{countLosses:<4}{colorAccuracy(accuracy)} {accuracy * 100:5.1f}%{colorama.Fore.WHITE} ║")
  print(f"╚════════╧════════════════╧═══════════╧════════════════════╧══════════════════╝")

def ordersReport(restAPI, dateStart, dateEnd, activities):
  history = restAPI.get_portfolio_history(
      date_start=(dateStart - datetime.timedelta(days=10)),
      date_end=dateEnd,
      timeframe="1D")

  print(f"╔═══════╤════════╤═════════════╤═════════════╤═════════╤══════════════════════╗")
  print(f"║ Time  │ Symbol │ Position    │ Enter Price │ Shares  │ Profit               ║")
  for i in range(len(history.timestamp)):
    timestamp = est.localize(
        datetime.datetime.fromtimestamp(
            history.timestamp[i]))
    if timestamp.date() < dateStart:
      continue
    print(f"╠═{timestamp.date().isoformat()}═════╪═════════════╪═════════════╪═════════╪══════════════════════╣")
    if timestamp.date() in activities:
      for activity in activities[timestamp.date()]:
        if activity["type"] == "order":
          timestamp = activity["timestamp"]
          symbol = activity["symbol"]
          position = activity["position"]
          enterPrice = activity["enterPrice"]
          shares = activity["shares"]
          profit = ""
          if "profit" in activity:
            profit = activity["profit"]
            profitPercent = activity["profitPercent"]
            profit = f"${colorProfit(profit)}{profit:10,.2f} {colorProfitPercent(profitPercent)}{profitPercent * 100:7.2f}%{colorama.Fore.WHITE}"
          print(f"║ {timestamp:%H:%M} │ "
                f"{symbol:6} │ "
                f"{position:<10} │ "
                f"${enterPrice:10,.2f} │ "
                f"{shares:7,.0f} │ "
                f"{profit:20} ║")

        else:
          # print(activity)
          pass
  print(f"╚═══════╧════════╧═════════════╧═════════════╧═════════╧══════════════════════╝")

def aggregateActivities(activities, includeEnterDay=False):
  days = {}
  prevTimestamp = getActivityTimestamp(activities[0])
  day = []
  securities = {}
  for activity in activities:
    timestamp = getActivityTimestamp(activity)
    if timestamp.date() != prevTimestamp.date():
      for security in securities.values():
        if security.buyShares != 0 or security.sellShares != 0:
          security.dayTrade = False
      day.sort(key=lambda data: data["timestamp"])
      days[prevTimestamp.date()] = day
      prevTimestamp = timestamp
      day = []

    if activity.activity_type == "FILL":
      if activity.symbol not in securities:
        securities[activity.symbol] = Security(activity.symbol)
      security = securities[activity.symbol]
      if security.sellShares == 0 and security.buyShares == 0:
        if activity.side == "buy":
          security.position = "long"
        else:
          security.position = "short"

      qty = float(activity.qty)
      price = float(activity.price) * qty
      if activity.side == "buy":
        security.buyShares += qty
        security.buyPrice += price
      else:
        security.sellShares += qty
        security.sellPrice += price

      if security.sellShares == security.buyShares:
        # Exiting position
        if security.dayTrade:
          position = f"Day   {security.position:5}"
          for data in day:
            if data["type"] != "order" or data["symbol"] != activity.symbol:
              continue
            data["complete"] = True
            if not includeEnterDay and data["position"].startswith("Enter"):
              day.remove(data)
        else:
          position = f"Exit  {security.position:5}"
        if activity.side == "sell":
          enterPrice = security.buyPrice
          shares = security.buyShares
        else:
          enterPrice = security.sellPrice
          shares = -security.sellShares

        profit = security.sellPrice - security.buyPrice
        data = {
          "type": "order",
          "symbol": activity.symbol,
          "timestamp": timestamp,
          "position": position,
          "enterPrice": enterPrice,
          "shares": shares,
          "profit": profit,
          "profitPercent": profit / enterPrice,
          "complete": True,
        }
        day.append(data)

        # Reset for next position entry
        security.sellPrice = 0
        security.sellShares = 0
        security.buyPrice = 0
        security.buyShares = 0
        security.dayTrade = True
      elif (security.position == "long" and activity.side == "buy") or (security.position == "short" and activity.side == "sell"):
        # Entering / increasing position
        position = f"Enter {security.position:5}"
        if activity.side == "buy":
          shares = qty
        else:
          shares = -qty

        contribution = False
        for data in day:
          if data["type"] != "order" or data["symbol"] != activity.symbol:
            continue
          if data["complete"]:
            continue
          if data["position"].startswith(
            "Enter") or data["position"].startswith("Incr"):
            data["timestamp"] = timestamp
            if not security.dayTrade:
              data["position"] = f"Incr. {security.position:5}"
            data["enterPrice"] += price
            data["shares"] += shares
            contribution = True

        if not contribution:
          data = {
            "type": "order",
            "symbol": activity.symbol,
            "timestamp": timestamp,
            "position": position,
            "enterPrice": price,
            "shares": shares,
            "complete": False,
          }
          day.append(data)
      else:
        # Decreasing position
        pass
    elif activity.activity_type == "CSR":
      # Cash receipt
      data = {
        "type": "deposit",
        "timestamp": timestamp,
        "amount": float(activity.net_amount)
      }
      day.append(data)

    else:
      print(activity)
      sys.exit(0)

  # Add last day
  day.sort(key=lambda data: data["timestamp"])
  days[prevTimestamp.date()] = day
  return days

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      "--live",
      help="Run on live, not paper, account",
      action="store_true")
  parser.add_argument(
    "--start",
    help=("Day to start report, format: " +
          datetime.date.today().isoformat()),
  )
  parser.add_argument(
    "--date",
    help=("Generate report for single day, format: " +
          datetime.date.today().isoformat()),
  )
  parser.add_argument(
    "--end",
    help=("Day to end report, format: " +
          datetime.date.today().isoformat()),
    default=datetime.date.today().isoformat()
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
  parser.add_argument(
      "--enter-day",
      help="Include enter day position in list of orders (requires --orders)",
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
  accountCreatedAt = account.created_at.date()
  if options.live:
    firstTrade = restAPI.get_activities(
        activity_types="FILL", direction="asc", page_size=1)[0]
    accountCreatedAt = getActivityTimestamp(firstTrade).date()

  dateEnd = datetime.date.fromisoformat(options.end)
  if options.date:
    dateStart = datetime.date.fromisoformat(options.date)
    dateEnd = dateStart
  elif options.start:
    dateStart = datetime.date.fromisoformat(options.start)
  else:
    dateStart = dateEnd - datetime.timedelta(days=options.period)
  dateStart = max(dateStart, accountCreatedAt)

  activities = restAPI.get_activities(direction="asc")
  done = False
  while not done:
    activityList = restAPI.get_activities(
      direction="asc", page_token=activities[-1].id)
    if len(activityList) > 0:
      activities.extend(activityList)
    else:
      done = True

  activities.sort(key=lambda activity: getActivityTimestamp(activity))

  activities = aggregateActivities(activities, options.enter_day)
  # for date, dailyActivities in activities.items():
  #   print(date, len(dailyActivities))

  overallReport(restAPI, dateStart, dateEnd, activities)
  if options.orders:
    ordersReport(restAPI, dateStart, dateEnd, activities)


if __name__ == '__main__':
  main()
