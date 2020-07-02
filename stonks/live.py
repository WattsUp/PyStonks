#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

from . import alpaca
from . import strategy as st
import schedule
import time
import datetime

api = alpaca.Alpaca()
strategy = st.strategy

## Periodic function to be run every minute
def periodic():
  if api.isOpen():
    print("Market open", datetime.datetime.now())
    # Fetch latest bars
    # Update orders
    # Run strategy
  else:
    print("Market closed", datetime.datetime.now())


## Main function
def main():
  # Every minute, 5 seconds after
  schedule.every().minute.at(":05").do(periodic)
  while(True):
    schedule.run_pending()
    time.sleep(1)


if __name__ == "__main__":
  main()
