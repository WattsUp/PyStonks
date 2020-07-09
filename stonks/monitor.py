#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

import alpaca_trade_api
from colorama import Fore, Style, init as ColoramaInit
import datetime
import os
import schedule
import time

ColoramaInit(autoreset=True)

## Fetch account information from alpaca and print the current value and
#  change from last trading day at close
#  @param api alpaca_trade_api REST object
def update(api):
  account = api.get_account()
  timestamp = datetime.datetime.now().replace(microsecond=0)
  equity = float(account.equity)
  dailyProfit = equity - float(account.last_equity)
  dailyProfitPercent = dailyProfit / equity * 100
  color = Fore.WHITE
  if dailyProfit > 0:
    color = Fore.GREEN
  elif dailyProfit < 0:
    color = Fore.RED
  print(f"{timestamp} "
        f"${equity:10.2f} "
        f"{color}${dailyProfit:8.2f} {dailyProfitPercent:8.3f}%")

## Main function
def main():
  paper = True
  ALPACA_API_KEY = os.getenv("ALPACA_API_KEY_PAPER")
  ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_PAPER")
  base_url = "https://paper-api.alpaca.markets"

  if not paper:
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
    base_url = "https://api.alpaca.markets"
  api = alpaca_trade_api.REST(ALPACA_API_KEY,
                              ALPACA_SECRET_KEY,
                              base_url,
                              api_version="v2")
  update(api)
  schedule.every().minute.at(":05").do(update, api)
  while True:
    schedule.run_pending()
    time.sleep(1)


if __name__ == "__main__":
  main()
