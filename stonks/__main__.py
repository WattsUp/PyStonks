#!/usr/bin/env python
## Trading bot programs
import sys
if sys.version_info[0] != 3 or sys.version_info[1] < 6:
  print("This script requires Python version >=3.6")
  sys.exit(1)

# import live

if __name__ == "__main__":
  if len(sys.argv) < 2:
    mode = None
  else:
    mode = sys.argv[1].lower()

  if mode == "test":
    print("Testing")
    import test
    test.main()
  elif mode == "add":
    import alpaca
    api = alpaca.Alpaca()
    api.addSymbols(sys.argv[2:])
  # elif mode == "live":
  #   print("Live Trading")
  #   live.main()
  else:
    print("Perform or test a stock trading algorithm")
    print("Follow with mode to execute algorithm")
    print("\"test\": test an algorithm over longest history period as possible")
    # print("\"live\": run an algorithm with live trading")
