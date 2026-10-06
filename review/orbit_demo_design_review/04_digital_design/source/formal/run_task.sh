#!/usr/bin/env bash
# Run one SymbiYosys task and compare its status with the expected one.
#
#   run_task.sh <file.sby> <run-dir> <task> <PASS|FAIL> [timeout-seconds]
#
# The work directory is <run-dir>/orbit_demo_<task>. Prints one result line
# and exits 0 only if sby finished with the expected status (so an ERROR or a
# timeout never counts as the FAIL that a vacuity check expects).

set -uo pipefail

if [ $# -lt 4 ]; then
    echo "usage: $0 <file.sby> <run-dir> <task> <PASS|FAIL> [timeout]" >&2
    exit 2
fi

sby_file=$1
run_dir=$2
task=$3
expect=$4
limit=${5:-1800}

mkdir -p "$run_dir"
work="$run_dir/orbit_demo_$task"

start=$(date +%s)
timeout "$limit" sby -f --prefix "$run_dir/orbit_demo" "$sby_file" "$task" \
    > "$run_dir/orbit_demo_$task.console.log" 2>&1
rc=$?
secs=$(( $(date +%s) - start ))

status="ERROR"
if [ "$rc" -eq 124 ]; then
    status="TIMEOUT"
    echo "TIMEOUT after ${limit}s" > "$work/status" 2>/dev/null || true
elif [ -f "$work/status" ]; then
    status=$(awk 'NR == 1 { print $1 }' "$work/status")
fi

if [ "$status" = "$expect" ]; then
    printf '[formal] %-14s %-7s (expected %s, %ss)\n' "$task" "$status" "$expect" "$secs"
    exit 0
fi
printf '[formal] %-14s %-7s (expected %s, %ss)  see %s/logfile.txt\n' \
    "$task" "$status" "$expect" "$secs" "$work"
exit 1
