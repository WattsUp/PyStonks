#!/usr/bin/env python
## Test an algorithm against maximum history
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

from . import alpaca
from . import strategy as st
import datetime

## Main function
def main():
  api = alpaca.Alpaca(datetime.date.today(), live=True)
  api.runLive(st.Strategy())


if __name__ == "__main__":
  main()
