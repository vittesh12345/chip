#!/usr/bin/env bash
# Build tb_orbit_wave.v against the production RTL and write one VCD and one
# log per scenario into this directory.
#   usage: run_waves.sh [repo-dir]      (default /home/user/chip)
set -euo pipefail
REPO=${1:-/home/user/chip}
HERE=$(cd "$(dirname "$0")" && pwd)
export PATH=/opt/eda/oss-cad-suite/bin:$PATH
cd "$HERE"
R=$REPO/rtl
{
  echo "date_utc   $(date -u +%FT%TZ)"
  echo "repo_head  $(git -C "$REPO" rev-parse HEAD)"
  echo "iverilog   $(iverilog -V 2>&1 | head -1)"
  md5sum "$R/orbit_keep_reg.v" "$R/orbit_mac_lane.v" "$R/orbit_thermal_tmr.v" "$R/orbit_demo.v"
} > run_info.txt
iverilog -g2005 -Wall -Wno-timescale -o tb_orbit_wave.vvp tb_orbit_wave.v \
    "$R/orbit_keep_reg.v" "$R/orbit_mac_lane.v" "$R/orbit_thermal_tmr.v" "$R/orbit_demo.v" \
    > compile.log 2>&1
fail=0
for s in 1 2 3 4 5; do
    vvp -n tb_orbit_wave.vvp +scen=$s > run_scen$s.log 2>&1 || fail=1
    line=$(grep -E '^WAVE_' run_scen$s.log || echo "WAVE scen$s: no result line")
    echo "$line"
    case "$line" in *" PASS "*) ;; *) fail=1 ;; esac
done
rm -f tb_orbit_wave.vvp
exit $fail
