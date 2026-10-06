#!/usr/bin/env bash
# Run one SymbiYosys task and compare its status with the expected one.
#
#   run_sby.sh <file.sby> <task> <PASS|FAIL> <timeout_s> <label>
#
# The work directory is <dir of file.sby>/<basename>_<task> (sby default),
# the full log <work>.log. Prints one line
#   <OK|BAD> <label> status=<sby status> expected=<PASS|FAIL> <seconds>s
# and exits 0 only if the status equals the expectation. A timeout or an
# sby error (status ERROR/UNKNOWN/TIMEOUT) never matches.
set -u
sby_file=$1; task=$2; expect=$3; limit=$4; label=$5

dir=$(dirname "$sby_file")
base=$(basename "$sby_file" .sby)
work="$dir/${base}_${task}"

start=$(date +%s)
timeout "$limit" sby -f "$sby_file" "$task" > "$work.log" 2>&1
rc=$?
secs=$(( $(date +%s) - start ))

if [ $rc -eq 124 ]; then
    status=TIMEOUT
elif [ -f "$work/status" ]; then
    status=$(awk '{print $1; exit}' "$work/status")
else
    status=ERROR
fi

if [ "$status" = "$expect" ]; then
    echo "OK  $label status=$status expected=$expect ${secs}s"
    exit 0
fi
echo "BAD $label status=$status expected=$expect ${secs}s (log: $work.log)"
grep -E "Assert failed|Cover|ERROR|Error" "$work.log" | grep -v "Copy" | head -5
exit 1
