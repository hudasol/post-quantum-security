#!/bin/sh
# Fetch pqm4 benchmarks.csv at the commit read for stream S13 (round 5) into the shared third party folder.
# Usage: sh scripts/fetch_s13_pqm4.sh [target dir]   (default: third_party/pqm4_wp6 next to the repository)
set -e
COMMIT=e1146b1bc180c66689682f6ce63bd8f126a51ace
DIR=${1:-$(dirname "$0")/../../third_party/pqm4_wp6}
mkdir -p "$DIR"
curl -sSfL "https://raw.githubusercontent.com/mupq/pqm4/$COMMIT/benchmarks.csv" -o "$DIR/benchmarks.csv"
echo "pqm4 benchmarks.csv at $COMMIT in $DIR"
