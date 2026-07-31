#!/usr/bin/env bash
# Negative control for tb_orbit_wave.v: each scenario must FAIL on a scratch
# copy of the RTL carrying the bug that scenario is meant to show. rtl/ is only
# read. Copies and logs go to <out-dir> (default ../wave_negctl).
#   usage: run_negctl.sh [repo-dir] [out-dir]
set -uo pipefail
REPO=${1:-/home/user/chip}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${2:-$HERE/../wave_negctl}
export PATH=/opt/eda/oss-cad-suite/bin:$PATH
rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"

mk() {  # <mutant> <file> <sed expression>
    mkdir -p "$1"; cp "$REPO"/rtl/*.v "$1"/; sed -i "$3" "$1/$2"
    if cmp -s "$REPO/rtl/$2" "$1/$2"; then echo "$1: mutation did not apply"; exit 2; fi
}
mk zext_product         orbit_mac_lane.v    's/wire        \[31:0\] prod32 = {{16{prod\[15\]}}, prod};/wire        [31:0] prod32 = {16'"'"'d0, prod};/'
mk no_backpressure      orbit_demo.v        's/(~out_valid_q | out_ready);/1'"'"'b1;/'
mk out_valid_ungated    orbit_demo.v        's/assign out_valid = out_valid_q \& ~fault_q \& ~mismatch;/assign out_valid = out_valid_q \& ~fault_q;/'
mk fault_not_sticky     orbit_demo.v        's/fault_q <= 1'"'"'b1;/fault_q <= 1'"'"'b1; else fault_q <= 1'"'"'b0;/'
mk throttle_every_cycle orbit_thermal_tmr.v 's/((voted == S_THROTTLE) \& ~phase)/(voted == S_THROTTLE)/'
mk copy1_no_repair      orbit_thermal_tmr.v '/u_copy1 (/{n;s/\.d(nxt)/.d(c1)/}'

# mutant -> scenario that must catch it
declare -A TARGET=([zext_product]=1 [no_backpressure]=2 [out_valid_ungated]=3
                   [fault_not_sticky]=5 [throttle_every_cycle]=4 [copy1_no_repair]=4)
fail=0
for m in zext_product no_backpressure out_valid_ungated fault_not_sticky throttle_every_cycle copy1_no_repair; do
    diff "$REPO/rtl" "$m" > "$m/mutation.diff"
    ( cd "$m" && iverilog -g2005 -Wall -Wno-timescale -o w.vvp "$HERE/tb_orbit_wave.v" \
          orbit_keep_reg.v orbit_mac_lane.v orbit_thermal_tmr.v orbit_demo.v )
    for s in 1 2 3 4 5; do
        r=$(cd "$m" && vvp -n w.vvp +scen=$s 2>&1 | tee "scen$s.log" | grep -E '^WAVE_|watchdog')
        tag=""
        if [ "$s" = "${TARGET[$m]}" ]; then
            case "$r" in *" FAIL "*) tag="  <- target scenario: CAUGHT" ;; *) tag="  <- target scenario: MISSED"; fail=1 ;; esac
        fi
        echo "$m scen$s: $r$tag"
    done
    rm -f "$m/w.vvp" "$m"/*.vcd
done
exit $fail
