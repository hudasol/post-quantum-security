#!/bin/sh
# Fetch and build the flight stack used by the software in the loop study, outside the repository.
# ArduPilot Copter 4.7.2 (tag Copter-4.7.2, commit fb773567896014da007bca58358704d4a0d8516f), licence GPL-3.0.
# Nothing fetched here is committed. Usage: sh sitl/fetch.sh [third party folder]
set -e
TP=${1:-../third_party}
AP=$TP/wp2_ardupilot
COMMIT=fb773567896014da007bca58358704d4a0d8516f
if [ ! -d "$AP" ]; then
  git clone --depth 1 --branch Copter-4.7.2 https://github.com/ArduPilot/ardupilot.git "$AP"
  git -C "$AP" submodule update --init --recursive --depth 1
fi
test "$(git -C "$AP" rev-parse HEAD)" = "$COMMIT" || { echo "unexpected ArduPilot commit"; exit 1; }
python3 -m venv "$TP/venv_wp2"
"$TP/venv_wp2/bin/pip" install pymavlink==2.4.50 empy==3.3.4 pexpect future lxml numpy pandas matplotlib
cd "$AP"
PATH="$TP/venv_wp2/bin:$PATH" nice -n 10 python3 ./waf configure --board sitl
PATH="$TP/venv_wp2/bin:$PATH" nice -n 10 python3 ./waf copter -j2
ls -l build/sitl/bin/arducopter
