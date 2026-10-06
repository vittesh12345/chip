#!/usr/bin/env bash
# Run OpenROAD-flow-scripts (ORFS) on orbit_demo inside the openroad/orfs
# Docker image.
#
# Usage:
#   scripts/run_pd.sh --work DIR --rtl "a.v b.v ..." [options] [--] [ORFS targets]
#   scripts/run_pd.sh --work DIR --shell 'COMMAND' [options]
#
# Options:
#   --work DIR       ORFS WORK_HOME (logs/, objects/, reports/, results/ go here)
#   --rtl "FILES"    RTL files for synthesis (space separated)
#   --platform P     ORFS platform with a config in pd/<P>/ (default sky130hd)
#   --period NS      clock period in ns; default: the value in pd/<P>/constraint.sdc
#   --variant NAME   ORFS FLOW_VARIANT (default: base)
#   --cores N        NUM_CORES for OpenROAD and the container CPU limit (default 2)
#   --timeout SEC    kill the flow after SEC seconds (default 3600)
#   --image IMG      Docker image (default openroad/orfs:latest)
#   --var NAME=VAL   extra ORFS make variable (repeatable), e.g. to override a
#                    config.mk setting for an experiment
#   --shell CMD      instead of ORFS, run CMD with bash in the same container
#                    setup (used for KLayout rendering and copying platform files)
# ORFS targets default to "all" (synth .. finish, including the GDS).
#
# The repository is mounted read-only at its own path, the work directory
# read-write at its own path, so every path is the same inside and outside the
# container and nothing the container writes lands outside --work. The
# container runs as the calling user so the outputs are not root-owned.

set -euo pipefail

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PLATFORM=sky130hd
PERIOD=
VARIANT=base
CORES=2
TIMEOUT=3600
IMAGE=openroad/orfs:latest
WORK=
RTL=
SHELL_CMD=
declare -a EXTRA_VARS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --work)     WORK=$2; shift 2 ;;
        --rtl)      RTL=$2; shift 2 ;;
        --platform) PLATFORM=$2; shift 2 ;;
        --period)   PERIOD=$2; shift 2 ;;
        --variant)  VARIANT=$2; shift 2 ;;
        --cores)    CORES=$2; shift 2 ;;
        --timeout)  TIMEOUT=$2; shift 2 ;;
        --image)    IMAGE=$2; shift 2 ;;
        --shell)    SHELL_CMD=$2; shift 2 ;;
        --var)      EXTRA_VARS+=("$2"); shift 2 ;;
        -h|--help)  usage ;;
        --)         shift; break ;;
        -*)         echo "run_pd.sh: unknown option $1" >&2; usage ;;
        *)          break ;;
    esac
done
TARGETS=("$@")
[[ ${#TARGETS[@]} -gt 0 ]] || TARGETS=(all)

[[ -n "$WORK" ]] || { echo "run_pd.sh: --work is required" >&2; usage; }
[[ -n "$RTL" || -n "$SHELL_CMD" ]] || { echo "run_pd.sh: --rtl is required" >&2; usage; }

CONFIG_DIR=$REPO/pd/$PLATFORM
[[ -f $CONFIG_DIR/config.mk && -f $CONFIG_DIR/constraint.sdc ]] || {
    echo "run_pd.sh: no ORFS config for platform '$PLATFORM' in $CONFIG_DIR" >&2; exit 2; }

if ! docker info >/dev/null 2>&1; then
    echo "run_pd.sh: Docker daemon not reachable." >&2
    echo "  start it with: nohup dockerd >/tmp/dockerd.log 2>&1 &" >&2
    exit 2
fi

mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)

# Common container setup: repository read-only and the work area read-write,
# both at their host paths; run as the calling user.
DOCKER=(docker run --rm --init --cpus "$CORES" --user "$(id -u):$(id -g)" -e HOME=/tmp)

if [[ -n "$SHELL_CMD" ]]; then
    exec "${DOCKER[@]}" -v "$REPO:$REPO:ro" -v "$WORK:$WORK:rw" -w "$REPO" "$IMAGE" \
        bash -c 'source /OpenROAD-flow-scripts/env.sh >/dev/null && eval "$0"' "$SHELL_CMD"
fi

# Absolute RTL paths; every RTL directory outside the repo is mounted too.
declare -a RTL_ABS=() MOUNTS=()
for f in $RTL; do
    [[ -f $f ]] || { echo "run_pd.sh: RTL file not found: $f" >&2; exit 2; }
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
# Rewritten only when its content changes, so ORFS does not redo synthesis.
SDC_DIR=$WORK/sdc/$PLATFORM
mkdir -p "$SDC_DIR"
SDC=$SDC_DIR/$VARIANT.sdc
if [[ -n $PERIOD ]]; then
    grep -qE '^set clk_period [0-9.]+' "$CONFIG_DIR/constraint.sdc" || {
        echo "run_pd.sh: no 'set clk_period' line in constraint.sdc" >&2; exit 2; }
    sed -E "s/^set clk_period [0-9.]+/set clk_period $PERIOD/" "$CONFIG_DIR/constraint.sdc" > "$SDC.tmp"
else
    cp "$CONFIG_DIR/constraint.sdc" "$SDC.tmp"
fi
if cmp -s "$SDC.tmp" "$SDC"; then rm -f "$SDC.tmp"; else mv "$SDC.tmp" "$SDC"; fi

mkdir -p "$WORK/logs"
RUNLOG=$WORK/logs/run_pd_${PLATFORM}_${VARIANT}.log
NAME="orbit-pd-${PLATFORM}-${VARIANT//[^A-Za-z0-9_.-]/_}-$$"

echo "run_pd.sh: platform=$PLATFORM variant=$VARIANT period=${PERIOD:-default} cores=$CORES"
echo "run_pd.sh: work=$WORK targets=${TARGETS[*]}"
echo "run_pd.sh: log=$RUNLOG"

# ORFS make command, run from the flow directory of the image.
MAKE_CMD=(make -C /OpenROAD-flow-scripts/flow
    "DESIGN_CONFIG=$CONFIG_DIR/config.mk"
    "WORK_HOME=$WORK"
    "FLOW_VARIANT=$VARIANT"
    "NUM_CORES=$CORES"
    "PD_VERILOG_FILES=${RTL_ABS[*]}"
    "PD_SDC_FILE=$SDC"
    ${EXTRA_VARS[@]+"${EXTRA_VARS[@]}"}
    "${TARGETS[@]}")

set +e
"${DOCKER[@]}" --name "$NAME" \
    "${MOUNTS[@]}" \
    "$IMAGE" \
    bash -c 'source /OpenROAD-flow-scripts/env.sh >/dev/null && exec timeout --signal=TERM "$0" "$@"' \
    "$TIMEOUT" "${MAKE_CMD[@]}" 2>&1 | tee "$RUNLOG"
rc=${PIPESTATUS[0]}
set -e

if [[ $rc -ne 0 ]]; then
    echo "run_pd.sh: ORFS FAILED (exit $rc); see $RUNLOG" >&2
    [[ $rc -eq 124 ]] && echo "run_pd.sh: timed out after ${TIMEOUT}s" >&2
    exit "$rc"
fi
echo "run_pd.sh: ORFS finished OK"
