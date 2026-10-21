#!/bin/sh
# Run every configuration on the given link profiles in two lanes (two vehicle instances at once).
# Usage: sh sitl/run_all.sh [profiles]   (default: sik ieee802154). Needs sitl/fetch.sh first.
# SITL_ARDUPILOT names the flight stack folder; SITL_PYTHON the interpreter with pymavlink.
PY=${SITL_PYTHON:-python3}
for p in ${*:-sik ieee802154}; do
  ( nice -n 5 $PY -m sitl.run_missions --config none --profile $p --instance 0 &&
    nice -n 5 $PY -m sitl.run_missions --config hybrid --profile $p --instance 0 ) > sitl/raw/lane0_$p.log 2>&1 &
  ( nice -n 5 $PY -m sitl.run_missions --config signing --profile $p --instance 1 &&
    nice -n 5 $PY -m sitl.run_missions --config pqsig --profile $p --instance 1 ) > sitl/raw/lane1_$p.log 2>&1 &
  wait
done
