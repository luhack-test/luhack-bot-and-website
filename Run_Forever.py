# Created by DethMetalDuck, stolen from https://www.alexkras.com/how-to-restart-python-script-after-exception-and-run-it-forever/
# Run_Forever is quick and dirty, infinitely restarts the given python filename if it crashes

from subprocess import Popen
import sys

args = sys.argv[1:]

while True:
    print("Starting python " + " ".join(args))
    p = Popen(["python", *args])
    p.wait()
