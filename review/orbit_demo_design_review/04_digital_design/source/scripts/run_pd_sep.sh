#!/usr/bin/env bash
# Run OpenROAD-flow-scripts (ORFS) on orbit_demo with the copy-separation
# fences (pd/sky130hd_sep/) inside the openroad/orfs Docker image.
#
# Usage:
#   scripts/run_pd_sep.sh --rtl "a.v b.v ..." [options] [--] [ORFS targets]
#   scripts/run_pd_sep.sh --shell 'COMMAND' [options]
#
# Options:
#   --work DIR       ORFS WORK_HOME (default build/pd_sep)
#   --rtl "FILES"    RTL files for synthesis (space separated)
#   --period NS      clock period in ns; default: pd/sky130hd_sep/constraint.sdc
#   --variant NAME   ORFS FLOW_VARIANT (default: sep)
#   --floorplan FP   region arrangement from pd/sky130hd_sep/regions.tcl
#                    (PDSEP_FLOORPLAN; default: the value in config.mk)
#   --cores N        NUM_CORES for OpenROAD and the container CPU limit (default 2)
#   --timeout SEC    kill the flow after SEC seconds (default 5400)
#   --image IMG      Docker image (default openroad/orfs:latest)
#   --var NAME=VAL   extra ORFS make variable (repeatable)
#   --shell CMD      run CMD with bash in the same container setup instead of ORFS
# ORFS targets default to "all" (synth .. finish, including the GDS).
#
# Same container conventions as scripts/run_pd.sh (the baseline runner, which
# this script copies rather than modifies): the repository is mounted
# read-only at its own path and the work directory read-write at its own path,
# and the container runs as the calling user. The ORFS platform is sky130hd;
# only the design configuration directory differs (pd/sky130hd_sep).

set -euo pipefail

usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG_DIR=$REPO/pd/sky130hd_sep
PLATFORM=sky130hd
PERIOD=
VARIANT=sep
FLOORPLAN=
CORES=2
TIMEOUT=5400
IMAGE=openroad/orfs:latest
WORK=$REPO/build/pd_sep
RTL=
SHELL_CMD=
declare -a EXTRA_VARS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --work)      WORK=$2; shift 2 ;;
        --rtl)       RTL=$2; shift 2 ;;
        --period)    PERIOD=$2; shift 2 ;;
        --variant)   VARIANT=$2; shift 2 ;;
        --floorplan) FLOORPLAN=$2; shift 2 ;;
        --cores)     CORES=$2; shift 2 ;;
        --timeout)   TIMEOUT=$2; shift 2 ;;
        --image)     IMAGE=$2; shift 2 ;;
        --shell)     SHELL_CMD=$2; shift 2 ;;
        --var)       EXTRA_VARS+=("$2"); shift 2 ;;
        -h|--help)   usage ;;
        --)          shift; break ;;
        -*)          echo "run_pd_sep.sh: unknown option $1" >&2; usage ;;
        *)           break ;;
    esac
done
TARGETS=("$@")
[[ ${#TARGETS[@]} -gt 0 ]] || TARGETS=(all)

[[ -n "$RTL" || -n "$SHELL_CMD" ]] || { echo "run_pd_sep.sh: --rtl is required" >&2; usage; }
[[ -f $CONFIG_DIR/config.mk && -f $CONFIG_DIR/constraint.sdc && -f $CONFIG_DIR/regions.tcl ]] || {
    echo "run_pd_sep.sh: incomplete ORFS config in $CONFIG_DIR" >&2; exit 2; }

if ! docker info >/dev/null 2>&1; then
    echo "run_pd_sep.sh: Docker daemon not reachable." >&2
    echo "  start it with: nohup dockerd >/tmp/dockerd.log 2>&1 &" >&2
    exit 2
fi

mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)

DOCKER=(docker run --rm --init --cpus "$CORES" --user "$(id -u):$(id -g)" -e HOME=/tmp)

if [[ -n "$SHELL_CMD" ]]; then
    exec "${DOCKER[@]}" -v "$REPO:$REPO:ro" -v "$WORK:$WORK:rw" -w "$REPO" "$IMAGE" \
        bash -c 'source /OpenROAD-flow-scripts/env.sh >/dev/null && eval "$0"' "$SHELL_CMD"
fi

declare -a RTL_ABS=() MOUNTS=()
for f in $RTL; do
    [[ -f $f ]] || { echo "run_pd_sep.sh: RTL file not found: $f" >&2; exit 2; }
    RTL_ABS+=("$(cd "$(dirname "$f")" && pwd)/$(basename "$f")")
done
MOUNTS+=(-v "$REPO:$REPO:ro" -v "$WORK:$WORK:rw")
declare -A seen=()
for f in "${RTL_ABS[@]}"; do
    d=$(dirname "$f")
    case "$d/" in "$REPO"/*|"$WORK"/*) continue ;; esac
    [[ -n ${seen[$d]:-} ]] && continue
    seen[$d]=1
    MOUNTS+=(-v "$d:$d:ro")
done

# Per-run SDC: the committed constraint with only the period line replaced.
SDC_DIR=$WORK/sdc/$PLATFORM
mkdir -p "$SDC_DIR"
SDC=$SDC_DIR/$VARIANT.sdc
if [[ -n $PERIOD ]]; then
    grep -qE '^set clk_period [0-9.]+' "$CONFIG_DIR/constraint.sdc" || {
        echo "run_pd_sep.sh: no 'set clk_period' line in constraint.sdc" >&2; exit 2; }
    sed -E "s/^set clk_period [0-9.]+/set clk_period $PERIOD/" "$CONFIG_DIR/constraint.sdc" > "$SDC.tmp"
else
    cp "$CONFIG_DIR/constraint.sdc" "$SDC.tmp"
fi
if cmp -s "$SDC.tmp" "$SDC"; then rm -f "$SDC.tmp"; else mv "$SDC.tmp" "$SDC"; fi

mkdir -p "$WORK/logs"
RUNLOG=$WORK/logs/run_pd_sep_${VARIANT}.log
NAME="orbit-pdsep-${VARIANT//[^A-Za-z0-9_.-]/_}-$$"

echo "run_pd_sep.sh: variant=$VARIANT floorplan=${FLOORPLAN:-config default} period=${PERIOD:-default} cores=$CORES"
echo "run_pd_sep.sh: work=$WORK targets=${TARGETS[*]}"
echo "run_pd_sep.sh: log=$RUNLOG"

MAKE_CMD=(make -C /OpenROAD-flow-scripts/flow
    "DESIGN_CONFIG=$CONFIG_DIR/config.mk"
    "WORK_HOME=$WORK"
    "FLOW_VARIANT=$VARIANT"
    "NUM_CORES=$CORES"
    "PD_VERILOG_FILES=${RTL_ABS[*]}"
    "PD_SDC_FILE=$SDC")
[[ -n $FLOORPLAN ]] && MAKE_CMD+=("PDSEP_FLOORPLAN=$FLOORPLAN")
MAKE_CMD+=(${EXTRA_VARS[@]+"${EXTRA_VARS[@]}"} "${TARGETS[@]}")

set +e
"${DOCKER[@]}" --name "$NAME" \
    "${MOUNTS[@]}" \
    "$IMAGE" \
    bash -c 'source /OpenROAD-flow-scripts/env.sh >/dev/null && exec timeout --signal=TERM "$0" "$@"' \
    "$TIMEOUT" "${MAKE_CMD[@]}" 2>&1 | tee "$RUNLOG"
rc=${PIPESTATUS[0]}
set -e

if [[ $rc -ne 0 ]]; then
    echo "run_pd_sep.sh: ORFS FAILED (exit $rc); see $RUNLOG" >&2
    [[ $rc -eq 124 ]] && echo "run_pd_sep.sh: timed out after ${TIMEOUT}s" >&2
    exit "$rc"
fi
echo "run_pd_sep.sh: ORFS finished OK"
