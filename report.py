#!/usr/bin/env python

import alpaca_trade_api
import argparse
import colorama
import datetime
import numpy as np
import os
import pickle
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

## Get the appropriate color for a percent
#  Cyan for large positive, green for positive, white for zero, yellow for negative, red for large negative
#  @param profitPercent [-1, inf)
#  @return colorama.Fore color
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

## Get the appropriate color for a profit
#  Green for positive, white for zero, red for negative
#  @param profit (-inf, inf)
#  @return colorama.Fore color
def colorProfit(profit):
  if profit > 0:
    return colorama.Fore.GREEN
  if profit == 0:
    return colorama.Fore.WHITE
  return colorama.Fore.RED

## Get the appropriate color for an accuracy
#  Cyan for highly accurate, green for accurate, yellow for questionable, red for inaccurate
#  @param profitPercent [0, 1]
#  @return colorama.Fore color
def colorAccuracy(accuracy):
  if accuracy > 0.80:
    return colorama.Fore.CYAN
  if accuracy > 0.65:
    return colorama.Fore.GREEN
  if accuracy > 0.5:
    return colorama.Fore.YELLOW
  return colorama.Fore.RED

## Get the timestamp of an activity
#  @param activity Alpaca Entity
#  @return datetime
def getActivityTimestamp(activity):
  if activity.activity_type == "FILL":
    return activity.transaction_time.astimezone(est)
  if activity.activity_type == "CSR":
    return est.localize(datetime.datetime.fromisoformat(
      activity.date + "T20:01:00"))
  print("Unknown activity type", activity)
  sys.exit(0)

## Generate and print an overall report over the date window
#  Daily information includes ending equity, daily change, wins/losses, and risk to reward
#  Summary information includes profit, various return percentages, various ratios, risk to reward
#  Security information includes total profit, total shares, profit a share, and wins/losses
#  @param portfolio history Alpaca object
#  @param dateStart to begin report
#  @param dateEnd to end report
#  @param activities dict {date: [list of activities]}
#  @param dayTradesOnly will only show trade statistics for day trades
def overallReport(history, dateStart, dateEnd, activities, dayTradesOnly):
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
          if dayTradesOnly and not activity["position"].startswith("day"):
            continue
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

            security.lifetimeEntryPrices.append(activity["price"])
            security.lifetimeProfits.append(activity["profit"])
            security.lifetimeShares.append(activity["shares"])
          else:
            # Entering
            pass

        elif activity["type"] == "deposit":
          dailyDeposits += activity["amount"]
        else:
          print("Unknown activity type", activity)
          sys.exit()

    prevEquity = history.equity[i - 1]
    if initialEquity is None:
      initialEquity = prevEquity

    # Don't count deposits added on the last day
    if i != len(history.timestamp) - 1:
      deposits += dailyDeposits

    # Deposits go in after close but are counted in closing equity
    endingEquity = history.equity[i] - dailyDeposits

    profit = endingEquity - prevEquity
    profitPercent = (profit / prevEquity)
    dailyReturns.append(profitPercent)

    countWins = len(dailyWins)
    countLosses = len(dailyLosses)
    if (countWins + countLosses) == 0:
      accuracy = ""
    else:
      accuracy = countWins / (countWins + countLosses)
      accuracy = f"{colorAccuracy(accuracy)}{accuracy * 100:3.0f}%{colorama.Fore.WHITE}"

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
          f"{countWins:3}:{countLosses:<3} {accuracy:4} │ "
          f"{riskToReward:7} ║")

  print(f"╠════════════╧═══════════════╧═════════╤═════════════╧══════════════╧═════════╣")
  profit = endingEquity - (initialEquity + deposits)

  print(f"║ Total profit:        ${colorProfit(profit)}{profit:12,.2f}{colorama.Fore.WHITE}   │ "
        f"Beginning equity:    ${initialEquity:12,.2f}   ║")

  profitPercent = profit / (initialEquity + deposits)
  print(f"║ Simple return:             {colorProfitPercent(profitPercent)}{profitPercent * 100:8.3f}%{colorama.Fore.WHITE} │ "
        f"Deposits:            ${deposits:12,.2f}   ║")

  averageReturns = np.mean(dailyReturns)

  # Sharpe ratio is average daily return / stddev(daily returns) * sqrt(252
  # number of trading days in a year)
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

  # Time weighted return is the product of the returns
  # Throw in 1 and subtract 1 to make a profit percent into a close/open
  # percent and vise versa
  twr = np.product(np.array(dailyReturns) + 1) - 1

  # Sortino ratio is average daily return / stddev(negative only daily
  # returns) * sqrt(252 number of trading days in a year)
  negativeReturns = np.array([min(0, a) for a in dailyReturns])
  stddev = np.std(negativeReturns)
  if stddev == 0:
    sortinoRatio = float('inf')
  else:
    sortinoRatio = averageReturns / stddev * np.sqrt(252)
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
  if dayTradesOnly:
    print(f"║ Winning day trades:      {countWins:6}      │ "
          f"Average day trade win:  ${averageWin:9,.2f}   ║")
    print(f"║ Losing day trades:       {countLosses:6}      │ "
          f"Average day trade loss: ${averageLoss:9,.2f}   ║")
  else:
    print(f"║ Winning trades:          {countWins:6}      │ "
          f"Average trade win:      ${averageWin:9,.2f}   ║")
    print(f"║ Losing trades:           {countLosses:6}      │ "
          f"Average trade loss:     ${averageLoss:9,.2f}   ║")

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

## Get a bar sized by the number of characters, with 1/8 resolution
#  @param number of characters, rounded down to nearest 1/8
#  @return string
def getBar(characters, reverse=False):
  temp = "█" * int(np.floor(characters))
  characters = int(np.floor((characters % 1) * 8))
  if characters > 0:
    temp += chr(ord("▏") - characters + 1)
  return temp

## Generate and print a report over the date window for daily orders
#  Daily order information includes position (short/long, day/overnight), order price, shares, and profit
#  Summary information includes profit by day of week and time of day
#  @param portfolio history Alpaca object
#  @param dateStart to begin report
#  @param dateEnd to end report
#  @param activities dict {date: [list of activities]}
#  @param hideDayEnters will not print enter orders for day positions
#  @param dayTradesOnly will only show trade statistics for day trades
def ordersReport(history, dateStart, dateEnd, activities, hideDayEnters, dayTradesOnly):
  print(f"╔═══════╤════════╤═════════════╤═════════════╤═════════╤══════════════════════╗")
  print(f"║ Time  │ Symbol │ Position    │ Order Price │ Shares  │ Profit               ║")

  weekdays = {}
  timeOfDays = {}
  timeWindow = 15

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
          if dayTradesOnly and not activity["position"].startswith("day"):
            continue

          timestamp = activity["timestamp"]
          symbol = activity["symbol"]
          entranceExit = activity["entranceExit"]
          position = activity["position"]
          price = activity["price"]
          shares = activity["shares"]
          profit = ""
          if entranceExit == "Exit":
            profit = activity["profit"]

            weekday = timestamp.isoweekday()
            if weekday in weekdays:
              weekdays[weekday].append(profit)
            else:
              weekdays[weekday] = [profit]

            time = timestamp.time()
            timeOfDay = time.replace(hour=time.hour, minute=(
              timeWindow * (time.minute // timeWindow)), second=0, microsecond=0, tzinfo=None)
            if timeOfDay in timeOfDays:
              timeOfDays[timeOfDay].append(profit)
            else:
              timeOfDays[timeOfDay] = [profit]

            profitPercent = activity["profitPercent"]
            profit = f"${colorProfit(profit)}{profit:10,.2f} {colorProfitPercent(profitPercent)}{profitPercent * 100:7.2f}%{colorama.Fore.WHITE}"
          elif hideDayEnters and position.startswith("day"):
            continue
          print(f"║ {timestamp:%H:%M} │ "
                f"{symbol:6} │ "
                f"{entranceExit:<5} {position:5} │ "
                f"${price:10,.2f} │ "
                f"{shares:7,.0f} │ "
                f"{profit:20} ║")

        else:
          # print(activity)
          pass

  print(f"╠═══════╪════════╧═════════════╧═══════════╤═╧═════════╧══════════════════════╣")
  print(f"║ Day   │ Profits                          │ Losses                           ║")
  days = []
  maxMovement = 0
  for i in range(1, 6):
    profit = 0
    loss = 0
    if i in weekdays:
      for order in weekdays[i]:
        if order > 0:
          profit += order
        else:
          loss += order
      maxMovement = max(maxMovement, profit, -loss)

    # 1-Jan-0001 is a Monday
    day = {
      "date": datetime.date(1, 1, i),
      "profit": profit,
      "loss": loss
    }
    days.append(day)
  for day in days:
    date = day["date"]
    profit = day["profit"]
    loss = day["loss"]
    profitBars = getBar(profit / maxMovement * 20)
    lossBars = getBar(-loss / maxMovement * 20)
    print(f"║ {date:%a}   │ "
          f"${profit:10,.2f} {profitBars:20} │"
          f" ${loss:10,.2f} {lossBars:20} ║ ")

  print(f"╠═══════╪══════════════════════════════════╪══════════════════════════════════╣")
  print(f"║ Time  │ Profits                          │ Losses                           ║")
  timeSlices = []
  maxMovement = 0
  time = datetime.time(9, 30)
  while time < datetime.time(16, 0):
    profit = 0
    loss = 0
    if time in timeOfDays:
      for order in timeOfDays[time]:
        if order > 0:
          profit += order
        else:
          loss += order
      maxMovement = max(maxMovement, profit, -loss)

    timeSlice = {
      "time": time,
      "profit": profit,
      "loss": loss
    }
    timeSlices.append(timeSlice)

    time = (
        datetime.datetime.combine(
            date.today(),
            time) +
        datetime.timedelta(
            minutes=timeWindow)).time()

  for timeSlice in timeSlices:
    time = timeSlice["time"]
    profit = timeSlice["profit"]
    loss = timeSlice["loss"]
    profitBars = getBar(profit / maxMovement * 20)
    lossBars = getBar(-loss / maxMovement * 20)
    print(f"║ {time:%H:%M} │ "
          f"${profit:10,.2f} {profitBars:20} │"
          f" ${loss:10,.2f} {lossBars:20} ║ ")

  # for weekday, profit in weekdays.items():
  #   print(weekday, profit)
  # for timeOfDay, profit in timeOfDays.items():
  #   print(timeOfDay, profit)
  print(f"╚═══════╧══════════════════════════════════╧══════════════════════════════════╝")

## Get an aggregated list of activities (orders, deposits, etc.)
#  Aggregated means combining orders for the same position (for partial fills)
#  @param restAPI Alpaca object
#  @return dict {date: [list of activities]}
def getAggregateActivities(restAPI, live):
  # Load existing data from cache
  filename = f"datacache/__activities__.{restAPI.get_account().id}.pkl"
  pageToken = None
  if os.path.exists(filename):
    with open(filename, "rb") as file:
      pickleObj = pickle.load(file)

      days = pickleObj["days"]
      prevDate = pickleObj["prevDate"]
      day = pickleObj["day"]
      securities = pickleObj["securities"]
      pageToken = pickleObj["pageToken"]
  else:
    days = {}
    prevDate = None
    day = []
    securities = {}

  # Fetch any new activities
  activities = restAPI.get_activities(direction="asc", page_token=pageToken)
  done = len(activities) == 0
  while not done:
    pageToken = activities[-1].id
    activityList = restAPI.get_activities(
      direction="asc", page_token=pageToken)
    if len(activityList) > 0:
      activities.extend(activityList)
    else:
      done = True
  activities.sort(key=lambda activity: getActivityTimestamp(activity))

  # If no new activities, return existing data
  if len(activities) == 0:
    # print("No new activities")
    return days

  if prevDate is None:
    prevDate = getActivityTimestamp(activities[0]).date()

  # For new each activity
  for activity in activities:
    # If activity timestamp is a new day, save previous day and start a new one
    timestamp = getActivityTimestamp(activity)
    if timestamp.date() != prevDate:
      # Any held securities are not day trades
      for security in securities.values():
        if security.buyShares != 0 or security.sellShares != 0:
          security.dayTrade = False
      day.sort(key=lambda data: data["timestamp"])
      days[prevDate] = day
      prevDate = timestamp.date()
      day = []

    # If activity is a filled security order
    if activity.activity_type == "FILL":
      # Get security object from symbol, create one if non-existant
      if activity.symbol not in securities:
        securities[activity.symbol] = Security(activity.symbol)
      security = securities[activity.symbol]

      # If entering a position, note if long or short
      if security.sellShares == 0 and security.buyShares == 0:
        if activity.side == "buy":
          security.position = "long"
        elif activity.side == "sell_short":
          security.position = "short"
        else:
          print("Entering position is neither buy nor sell_short", activity)

      qty = float(activity.qty)
      price = float(activity.price) * qty
      if activity.side == "buy":
        security.buyShares += qty
        security.buyPrice += price
      elif activity.side == "sell" or activity.side == "sell_short":
        security.sellShares += qty
        security.sellPrice += price
      else:
        print("Activity is neither buy, sell, nor sell_short", activity)

      # Exiting position, sold same as bought
      if security.sellShares == security.buyShares:
        if security.dayTrade:
          if security.position == "long":
            security.position = "day L"
          else:
            security.position = "day S"
          for data in day:
            if data["type"] != "order" or data["symbol"] != activity.symbol:
              continue
            if data["complete"]:
              continue
            data["complete"] = True
            data["position"] = security.position

        if activity.side == "sell":
          price = security.sellPrice
          enterPrice = security.buyPrice
          shares = security.buyShares
        elif activity.side == "buy":
          price = security.buyPrice
          enterPrice = security.sellPrice
          shares = -security.sellShares
        else:
          print("Exiting position is neither buy nor sell", activity)

        profit = security.sellPrice - security.buyPrice
        data = {
          "type": "order",
          "symbol": activity.symbol,
          "timestamp": timestamp,
          "entranceExit": "Exit",
          "position": security.position,
          "price": price,
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
      elif (security.position == "long" and activity.side == "buy") or (security.position == "short" and activity.side == "sell_short"):
        # Entering / increasing position
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
          if data["entranceExit"] == "Enter" or data["entranceExit"] == "Incr.":
            data["timestamp"] = timestamp
            if not security.dayTrade:
              data["entranceExit"] = "Incr."
            data["price"] += price
            data["shares"] += shares
            contribution = True

        if not contribution:
          data = {
            "type": "order",
            "symbol": activity.symbol,
            "timestamp": timestamp,
            "entranceExit": "Enter",
            "position": security.position,
            "price": price,
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
      print("Unknown activity type", activity)
      sys.exit(0)

  # Add last day
  day.sort(key=lambda data: data["timestamp"])
  days[prevDate] = day

  # Save information required to resume adding activities
  if not os.path.exists("datacache"):
    os.mkdir("datacache")
  with open(filename, "wb") as file:
    pickleObj = {
      "days": days,
      "prevDate": prevDate,
      "day": day,
      "securities": securities,
      "pageToken": pageToken,
    }
    pickle.dump(pickleObj, file, protocol=pickle.HIGHEST_PROTOCOL)
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
      "--hide-day-enters",
      help="Hide enter day position in list of orders (requires --orders)",
      action="store_true")
  parser.add_argument(
      "--day-trades-only",
      help="Only show trade statistics on day trades",
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
    # If live, skip to first day with trades
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

  history = restAPI.get_portfolio_history(
      date_start=(dateStart - datetime.timedelta(days=10)),
      date_end=dateEnd,
      timeframe="1D")
  if datetime.datetime.fromtimestamp(history.timestamp[-1]).date() < dateStart:
    print("Selected date(s) have no account history")
    sys.exit(0)

  activitiesAgg = getAggregateActivities(restAPI, options.live)

  overallReport(
      history,
      dateStart,
      dateEnd,
      activitiesAgg,
      options.day_trades_only)
  if options.orders:
    ordersReport(
        history,
        dateStart,
        dateEnd,
        activitiesAgg,
        options.hide_day_enters,
         options.day_trades_only)


if __name__ == '__main__':
  main()
