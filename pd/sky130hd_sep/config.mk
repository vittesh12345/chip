# ORFS design configuration: orbit_demo on SkyWater sky130hd with the
# redundant copies physically separated by placement fences.
#
# Identical to pd/sky130hd/config.mk (the unconstrained baseline) except for
# the "Copy separation" section at the end. Run it through
# scripts/run_pd_sep.sh (make pd-sep), which passes PD_VERILOG_FILES and
# PD_SDC_FILE exactly as scripts/run_pd.sh does for the baseline.

export DESIGN_NAME     = orbit_demo
export DESIGN_NICKNAME = orbit_demo
export PLATFORM        = sky130hd

ifeq ($(strip $(PD_VERILOG_FILES)),)
  $(error PD_VERILOG_FILES is empty: run the flow through scripts/run_pd_sep.sh)
endif
export VERILOG_FILES = $(PD_VERILOG_FILES)

ifeq ($(strip $(PD_SDC_FILE)),)
  export SDC_FILE = $(dir $(DESIGN_CONFIG))constraint.sdc
else
  export SDC_FILE = $(PD_SDC_FILE)
endif

# ---------------------------------------------------------------------------
# Redundant storage must survive synthesis as distinct flip-flops (same as the
# baseline): every orbit_keep_reg copy stays its own kept instance, so the
# copies cannot be merged, and their cell names keep the hierarchical path
# (g_lane[i].u_lane.u_acc_a/q[k]...) that the fences below select on.
# ---------------------------------------------------------------------------
export SYNTH_KEEP_MODULES = *orbit_keep_reg*

# ---------------------------------------------------------------------------
# Floorplan / placement (same as the baseline: same die, same utilisation).
# ---------------------------------------------------------------------------
export CORE_UTILIZATION       = 40
export CORE_ASPECT_RATIO      = 1
export CORE_MARGIN            = 2
export PLACE_DENSITY_LB_ADDON = 0.20

export PLACE_PINS_ARGS = -min_distance 2 -min_distance_in_tracks

export TNS_END_PERCENT = 100

# ---------------------------------------------------------------------------
# Copy separation.
#
# regions.tcl runs at the end of the floorplan step and creates one fenced
# placement region (odb dbRegion + dbGroup) per copy: copy A of every
# accumulator/result pair, copy B, and each of the three thermal copies.
# Global placement, detailed placement and every later re-legalisation (CTS,
# repair) keep the members inside; non-members are kept from being placed in
# a fence (a few straddle a fence edge; measured in the report).
#
# PDSEP_FLOORPLAN selects the region arrangement defined in regions.tcl.
# ENABLE_DPO=0: improve_placement does not keep the placement legal with the
# fences (measured in scripts/pdsep_mechanism_test.tcl: check_placement fails
# after it), so it is switched off; detailed placement itself is unchanged.
#
# SLEW_MARGIN/CAP_MARGIN (percent): repair_design over-fixes max slew and
# capacitance by this margin. The fences stretch the A/B comparator and
# mismatch OR-tree nets across the core; without a margin the first edges run
# at 7.0 ns ended with 6 max-slew and 3 max-cap violations on those nets after
# detailed routing (the baseline, without margins, had none).
# ---------------------------------------------------------------------------
export POST_FLOORPLAN_TCL = $(dir $(DESIGN_CONFIG))regions.tcl
export PDSEP_FLOORPLAN   ?= edges
export PDSEP_REGION_TYPE ?= EXCLUSIVE
export ENABLE_DPO         = 0
export SLEW_MARGIN        = 20
export CAP_MARGIN         = 20
