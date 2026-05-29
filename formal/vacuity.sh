#!/usr/bin/env bash
# Vacuity / sensitivity check for the formal proofs.
#
#   vacuity.sh <out-dir> <template.sby> <harness.sv> <timeout-s> <rtl.v>...
#
# For every mutant below: copy the RTL into <out-dir>/<mutant>/rtl/, apply one
# deliberate bug with sed, check that the copy really differs, generate the
# .sby for that copy and run the SymbiYosys task that should catch the bug.
# A mutant is "caught" only if sby ends with status FAIL (a real
# counterexample, not ERROR / UNKNOWN / timeout) and one of the failed
# assertions carries the expected property prefix. Exits non-zero if any
# mutant is not caught. Writes <out-dir>/vacuity.md and vacuity.tsv.

set -uo pipefail

if [ $# -lt 5 ]; then
    echo "usage: $0 <out-dir> <template.sby> <harness.sv> <timeout-s> <rtl.v>..." >&2
    exit 2
fi

here=$(cd "$(dirname "$0")" && pwd)
out=$1
tmpl=$2
tb=$3
limit=$4
shift 4
rtl=("$@")

rm -rf "$out"
mkdir -p "$out"
tsv="$out/vacuity.tsv"
printf 'mutant\tfile\ttask\texpect\tresult\tstatus\tfailed\tstep\tseconds\tdescription\n' > "$tsv"
missed=0

# mutant <name> <rtl file> <task> <expected property prefix> <sed script> <description>
mutant() {
    local name=$1 file=$2 task=$3 expect=$4 script=$5 desc=$6
    local dir="$out/$name" src="" copies=() f

    mkdir -p "$dir/rtl"
    for f in "${rtl[@]}"; do
        cp "$f" "$dir/rtl/"
        copies+=("$dir/rtl/$(basename "$f")")
        if [ "$(basename "$f")" = "$file" ]; then
            src=$f
        fi
    done
    if [ -z "$src" ]; then
        echo "[vacuity] $name: $file is not among the RTL files" >&2
        printf '%s\t%s\t%s\t%s\tNOT_APPLIED\t-\t-\t-\t0\t%s\n' "$name" "$file" "$task" "$expect" "$desc" >> "$tsv"
        missed=1
        return
    fi
    sed -i -e "$script" "$dir/rtl/$file"
    if cmp -s "$src" "$dir/rtl/$file"; then
        echo "[vacuity] $name: the mutation did not change $file" >&2
        printf '%s\t%s\t%s\t%s\tNOT_APPLIED\t-\t-\t-\t0\t%s\n' "$name" "$file" "$task" "$expect" "$desc" >> "$tsv"
        missed=1
        return
    fi
    diff -u "$src" "$dir/rtl/$file" > "$dir/mutation.diff"

    "$here/gen_sby.sh" "$tmpl" "$dir/orbit_demo.sby" "$tb" "${copies[@]}"

    local start secs status failed step result log
    start=$(date +%s)
    "$here/run_task.sh" "$dir/orbit_demo.sby" "$dir/run" "$task" FAIL "$limit" > "$dir/result.txt"
    secs=$(( $(date +%s) - start ))
    log="$dir/run/orbit_demo_$task/logfile.txt"
    status=$(awk 'NR == 1 { print $1 }' "$dir/run/orbit_demo_$task/status" 2>/dev/null || echo ERROR)
    # Failed assertions of counterexamples from the initial (reset) state:
    # base-case engine lines, and sby summary lines outside the induction
    # section. Induction-step failures are not counterexamples and are ignored.
    local pairs
    pairs=$(awk '
        /Checking assertions in step [0-9]+/ && !/\.induction:/ {
            s = $0; sub(/.*Checking assertions in step /, "", s); sub(/[^0-9].*/, "", s); step = s }
        /Assert failed in orbit_demo_fv: / && !/\.induction:/ {
            n = $0; sub(/.*Assert failed in orbit_demo_fv: /, "", n); print n, step }
        /counterexample trace/ { ind = ($0 ~ /\[induction\]/) }
        /failed assertion orbit_demo_fv\./ && !ind {
            n = $0; sub(/.*failed assertion orbit_demo_fv\./, "", n)
            st = "-"; if (n ~ / step [0-9]+$/) { st = n; sub(/.* step /, "", st) }
            sub(/ .*/, "", n); print n, st }
    ' "$log" 2>/dev/null)
    failed=$(printf '%s\n' "$pairs" | awk 'NF { print $1 }' | sort -u | tr '\n' ' ' | sed 's/ $//')
    step=$(printf '%s\n' "$pairs" | awk '$2 ~ /^[0-9]+$/ { print $2 }' | sort -n | head -n 1)
    # Live mode (suprove) reports only the task status, no property names and
    # no trace. Attribute the failure only if the model has exactly one
    # liveness property.
    if [ "$status" = "FAIL" ] && [ -z "$failed" ]; then
        local lives
        lives=$(sed -n 's/^ *cell \$live \\\(.*\)$/\1/p' "$dir/run/orbit_demo_$task/model/design_prep.il" 2>/dev/null)
        if [ "$(printf '%s\n' $lives | grep -c .)" -eq 1 ]; then
            failed=$lives
        fi
    fi
    result="MISSED"
    if [ "$status" = "FAIL" ] && printf '%s\n' $failed | grep -qE "^($expect)"; then
        result="CAUGHT"
    else
        missed=1
    fi
    printf '[vacuity] %-26s %-14s %-6s %-6s step %-3s %4ss  %s\n' \
        "$name" "$task" "$status" "$result" "${step:--}" "$secs" "$failed"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$file" "$task" "$expect" "$result" \
        "$status" "${failed:--}" "${step:--}" "$secs" "$desc" >> "$tsv"
}

# --- The mutants ---------------------------------------------------------
# Datapath (P1, P8)
mutant zext_product orbit_mac_lane.v datapath P1_ \
    "s/{{16{prod\[15\]}}, prod}/{16'd0, prod}/" \
    "product zero-extended instead of sign-extended"
mutant first_ignored orbit_mac_lane.v datapath P1_ \
    "s/(first ? 32'd0 : acc_\([ab]\))/acc_\1/" \
    "in_first ignored: every beat continues the sum (both copies)"
mutant result_from_old_acc orbit_mac_lane.v datapath P1_ \
    "/u_res_[ab]/,/);/ s/acc_\([ab]\)_sum)/acc_\1)/" \
    "result registers load the pre-beat sum (both copies)"
mutant clear_keeps_acc orbit_mac_lane.v datapath P8_ \
    "s/wire acc_en = clr | mac_en;/wire acc_en = mac_en;/" \
    "clear_fault does not zero the accumulators (both copies)"
# Only visible from a state with a latched fault (task clear, arbitrary start).
mutant clear_keeps_fault orbit_demo.v clear P8_any_no_fault \
    "/else if (clear_fault) begin/,/fault_q/ s/fault_q     <= 1'b0;/fault_q     <= fault_q;/" \
    "clear_fault does not clear a latched fault"
# Handshake (P2, P3, P4)
mutant no_backpressure orbit_demo.v handshake P4_ \
    "s/(~out_valid_q | out_ready);/1'b1;/" \
    "in_ready ignores a full output buffer"
mutant out_valid_never_cleared orbit_demo.v handshake P2_ \
    "s/else if (out_fire)/else if (1'b0)/" \
    "out_valid_q not cleared by out_fire (duplicate delivery)"
mutant out_valid_never_set orbit_demo.v live P2_ \
    "s/out_valid_q <= 1'b1;/out_valid_q <= 1'b0;/" \
    "out_valid_q never set: accepted results are never presented"
# Thermal (P5, P6)
mutant stop_threshold_gt orbit_thermal_tmr.v thermal P5_ \
    "s/t >= T_STOP/t > T_STOP/" \
    "STOP at t > 95 instead of t >= 95"
mutant recover_threshold_lt orbit_thermal_tmr.v thermal P5_ \
    "s/S_THROTTLE: nxt = (t <= T_RECOVER)/S_THROTTLE: nxt = (t < T_RECOVER)/" \
    "THROTTLE recovers at t < 70 instead of t <= 70"
mutant throttle_every_cycle orbit_thermal_tmr.v thermal P6_ \
    "s/((voted == S_THROTTLE) \& ~phase)/(voted == S_THROTTLE)/" \
    "THROTTLE admits every cycle"
# BMC stops at the first failing step, which here is the combinational phase
# helper; the P6 assertions are clocked and report one step later. The pdr
# variant below shows that P6 alone catches it without helpers.
mutant phase_not_reset orbit_thermal_tmr.v thermal P5_h_phase \
    "s/? ~phase : 1'b0;/? ~phase : phase;/" \
    "phase keeps its value outside THROTTLE"
# Fault-free invariants (P7)
mutant acc_b_clear_value orbit_mac_lane.v dup P7_ \
    "/u_acc_b/,/);/ s/clr ? 32'd0/clr ? 32'd1/" \
    "clear_fault writes 1 into accumulator copy B"
mutant therm_copy2_frozen orbit_thermal_tmr.v dup P7_ \
    "/\.q(c2)/ s/\.en(1'b1)/.en(1'b0)/" \
    "thermal copy 2 is never rewritten after reset"
# The same bugs against the helper-free abc pdr proofs. These tasks have no
# helper invariants, so every assertion in them is a real property. pdr reports
# the first falsified output it meets, which can vary between runs, so the
# expectation lists every property the bug necessarily breaks.
mutant zext_product_pdr orbit_mac_lane.v datapath_pdr "P1_|P8_fresh" \
    "s/{{16{prod\[15\]}}, prod}/{16'd0, prod}/" \
    "product zero-extended (abc pdr, no helpers)"
mutant clear_keeps_acc_pdr orbit_mac_lane.v datapath_pdr "P8_|P1_" \
    "s/wire acc_en = clr | mac_en;/wire acc_en = mac_en;/" \
    "clear_fault does not zero the accumulators (abc pdr, no helpers)"
mutant throttle_every_cycle_pdr orbit_thermal_tmr.v thermal_pdr P6_ \
    "s/((voted == S_THROTTLE) \& ~phase)/(voted == S_THROTTLE)/" \
    "THROTTLE admits every cycle (abc pdr, no helpers)"
mutant no_backpressure_pdr orbit_demo.v handshake_pdr "P4_|P2_" \
    "s/(~out_valid_q | out_ready);/1'b1;/" \
    "in_ready ignores a full output buffer (abc pdr, no helpers)"
mutant phase_not_reset_pdr orbit_thermal_tmr.v thermal_pdr P6_ \
    "s/? ~phase : 1'b0;/? ~phase : phase;/" \
    "phase keeps its value outside THROTTLE (abc pdr, no helpers)"

# --- Report ----------------------------------------------------------------
{
    echo "# Formal vacuity check: proofs against deliberately broken RTL"
    echo
    echo "Each mutant is one sed edit of a generated copy of the RTL (never rtl/"
    echo "itself). CAUGHT = the named SymbiYosys task ended with status FAIL and a"
    echo "counterexample from the initial state (reset asserted in step 0) violated a"
    echo "property with the expected prefix. Step 0 failures are properties that are"
    echo "asserted in every state, including the unconstrained first cycle (P4)."
    echo
    echo "| Mutant | File | Task | Expect | Result | sby status | Failed properties | First step | Time (s) | Bug |"
    echo "|---|---|---|---|---|---|---|---|---|---|"
    tail -n +2 "$tsv" | while IFS=$'\t' read -r n f t e r s fl st sec d; do
        echo "| $n | $f | $t | ${e//|/* or }* | $r | $s | $fl | $st | $sec | $d |"
    done
} > "$out/vacuity.md"

if [ "$missed" -ne 0 ]; then
    echo "[vacuity] FAILED: at least one mutant was not caught (see $out/vacuity.md)"
    exit 1
fi
echo "[vacuity] all mutants caught (see $out/vacuity.md)"
