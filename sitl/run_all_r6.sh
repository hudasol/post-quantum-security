#!/bin/sh
# Round 6: run the ten configurations with executed cryptography; the first seven in two lanes (two vehicle
# instances at once), then kem_auth alone, then hybrid_strict_inband and pqsig_counter alone, one after the other.
# Usage: sh sitl/run_all_r6.sh <folder with proto_sessions.csv and proto_primitives.csv> [profiles]
# (default profile: sik). Needs sitl/fetch.sh and sitl/pqlib/build.sh first. SITL_PYTHON names the interpreter
# with pymavlink and cryptography 50.0.1, SITL_ARDUPILOT the flight stack folder, SITL_PQLIB the library folder.
# The runs are timed: start them only when no other heavy job runs on the host, and without nice.
RTL=$1
shift
PY=${SITL_PYTHON:-python3}
mkdir -p sitl/raw_r6
for p in ${*:-sik}; do
  ( $PY -m sitl.run_missions_r6 --config none --profile $p --instance 0 --rtl "$RTL" &&
    $PY -m sitl.run_missions_r6 --config classical --profile $p --instance 0 --rtl "$RTL" &&
    $PY -m sitl.run_missions_r6 --config hybrid_strict --profile $p --instance 0 --rtl "$RTL" &&
    $PY -m sitl.run_missions_r6 --config pqsig_real --profile $p --instance 0 --rtl "$RTL" ) > sitl/raw_r6/lane0_$p.log 2>&1 &
  ( $PY -m sitl.run_missions_r6 --config signing --profile $p --instance 1 --rtl "$RTL" &&
    $PY -m sitl.run_missions_r6 --config hybrid_published --profile $p --instance 1 --rtl "$RTL" &&
    $PY -m sitl.run_missions_r6 --config hybrid_cache --profile $p --instance 1 --rtl "$RTL" ) > sitl/raw_r6/lane1_$p.log 2>&1 &
  wait
  # Design K (kem_auth) was added after the first seven and runs alone, one lane, after them. Its vehicle side
  # delays come from the 15 run RTL files in rtlsim/results/ (the snapshot folder has no design K rows).
  $PY -m sitl.run_missions_r6 --config kem_auth --profile $p --instance 0 --rtl rtlsim/results > sitl/raw_r6/lane0_kem_auth_$p.log 2>&1
  # In band resynchronisation and ML-DSA-44 per command with a counter were added after kem_auth; each runs alone,
  # one lane, with the vehicle side delays of the first seven (the five run snapshot folder given as RTL).
  $PY -m sitl.run_missions_r6 --config hybrid_strict_inband --profile $p --instance 0 --rtl "$RTL" > sitl/raw_r6/lane0_hybrid_strict_inband_$p.log 2>&1
  $PY -m sitl.run_missions_r6 --config pqsig_counter --profile $p --instance 0 --rtl "$RTL" > sitl/raw_r6/lane0_pqsig_counter_$p.log 2>&1
done
