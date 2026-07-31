#!/usr/bin/env bash
# Re-run of mk/pd.mk target pd-corners (lines 249-266) against the copy-separated
# sky130hd run. Same script (pd/sta_corners.tcl), same docker wrapper
# (scripts/run_pd.sh --shell), same env vars and openroad options; only the
# PD_ODB/PD_SDC/PD_SPEF paths point at build/pd_sep and the logs go to scratch.
set -euo pipefail
REPO=/home/user/chip
OUT=/tmp/claude-0/-home-user-chip/6bdc94fa-7275-51e9-a492-50b01aa47cf0/scratchpad/review_work/corners_sep
WORK=$OUT/work          # run_pd.sh --work (mounted rw; nothing is written there by STA)
RES=$REPO/build/pd_sep/results/sky130hd/orbit_demo/sep
PLAT=$REPO/build/pd/platform/sky130hd
ORFS_FLOW=/OpenROAD-flow-scripts/flow
cd "$REPO"
test -f $RES/6_final.spef
for c in tt ss_100C_1v60 ff_n40C_1v95; do
    if [ $c = tt ]; then lib=$ORFS_FLOW/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
    else lib=$PLAT/corners/sky130_fd_sc_hd__$c.lib; fi
    echo "corner $c lib $lib"
    scripts/run_pd.sh --work $WORK --platform sky130hd --cores 2 --timeout 3600 --image openroad/orfs:latest \
        --shell "PD_CORNER=$c PD_LIB=$lib PD_ODB=$RES/6_final.odb \
        PD_SDC=$RES/6_final.sdc PD_SPEF=$RES/6_final.spef \
        openroad -no_init -threads 1 -exit $REPO/pd/sta_corners.tcl" > $OUT/sta_$c.log 2>&1
    echo "  exit $?"
done
