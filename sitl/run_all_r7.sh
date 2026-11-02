#!/bin/sh
# Round 7: the three added result sets of the gateway emulation, as jobs of at most 20 missions, in two lanes (two
# vehicle instances at once). Round 6 files are not touched; every job writes to sitl/raw_r7/<set>/.
# Usage: sh sitl/run_all_r7.sh <folder with the round 6 five run RTL snapshot (proto_sessions.csv and
# proto_primitives.csv)> [budget_s]
# The script is resumable: a job whose _run.json exists is skipped, and a lane starts no new job once budget_s seconds
# (default 4800) have passed, so the script can be started again until every job is done. A job of the larger set is
# missions 20 j to 20 j + 19 of one configuration (output tag <profile>_<config>_from<first>); its seeds are those of
# those missions in every configuration, so splitting changes no seed.
# As in round 6, design K (kem_auth) takes its delays from the 15 run files in rtlsim/results/ and every other
# configuration from the five run snapshot; the Falcon-512 configurations add rtlsim/results/proto_falcon.csv.
# SITL_PYTHON names the interpreter with pymavlink and cryptography 50.0.1, SITL_ARDUPILOT the flight stack folder,
# SITL_PQLIB the library folder (sitl/pqlib/build.sh). Start the runs only when no other heavy job runs on the host.
# Author: Huda Mueen.
RTL=$1
BUDGET=${2:-4800}
PY=${SITL_PYTHON:-python3}
AP=${SITL_ARDUPILOT:-../third_party/wp2_ardupilot}
WD=$(dirname "$AP")/wp2_sitl_runs
T0=$(date +%s)
BURST="none classical hybrid_published hybrid_cache hybrid_strict hybrid_strict_inband kem_auth pqsig_real pqsig_falcon"

job_list() {  # one line per job: set config first count
  echo "falcon20 pqsig_falcon 0 20"
  echo "falcon20 pqsig_falcon_counter 0 20"
  for k in $BURST; do echo "burst20 $k 0 20"; done
  for f in 0 20 40 60 80; do for k in $BURST; do echo "large100 $k $f 20"; done; done
}

lane() {  # lane number (0 or 1): runs every second job
  i=0
  job_list | while read -r set k first n; do
    i=$((i + 1))
    [ $((i % 2)) -eq "$1" ] || continue
    tag=sik_$k
    [ "$first" -gt 0 ] && tag=${tag}_from$first
    mkdir -p sitl/raw_r7/$set
    [ -f sitl/raw_r7/$set/${tag}_run.json ] && continue
    [ $(($(date +%s) - T0)) -lt "$BUDGET" ] || { echo "lane $1: budget reached"; break; }
    rtl=$RTL
    [ "$k" = kem_auth ] && rtl=rtlsim/results
    echo "lane $1: $set $k missions $first to $((first + n - 1)) start $(date -u +%H:%M:%S)"
    $PY -m sitl.run_missions_r6 --set "$set" --config "$k" --profile sik --instance "$1" --first "$first" \
      --missions "$n" --rtl "$rtl" --workdir "$WD/r7_lane$1" >> sitl/raw_r7/$set/lane$1.log 2>&1 \
      || echo "lane $1: $set $k $first failed"
  done
}

lane 0 &
lane 1 &
wait
echo "jobs left: $(job_list | while read -r set k first n; do t=sik_$k; [ "$first" -gt 0 ] && t=${t}_from$first; [ -f sitl/raw_r7/$set/${t}_run.json ] || echo x; done | wc -l)"
