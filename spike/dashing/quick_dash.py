import time
from dashing import QuickDash

def main():
    d = QuickDash()
    d.status = "Running..."
    d.logs.append("Started")
    for progress in range(100):
      d.gauges['progess'] = progress
      if progress % 10 == 0:
        d.logs.append("Started")
      time.sleep(0.05)

    d.status = "Done!"
    time.sleep(1)