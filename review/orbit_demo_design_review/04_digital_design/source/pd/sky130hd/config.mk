# ORFS design configuration: ORBIT-AI 4-lane INT8 demonstrator on SkyWater
# sky130hd (open PDK, TT 25C 1.80V liberty as selected by the ORFS platform).
#
# Used by scripts/run_pd.sh inside the openroad/orfs container:
#   make -C /OpenROAD-flow-scripts/flow DESIGN_CONFIG=<this file> WORK_HOME=... \
#        PD_VERILOG_FILES="<abs RTL paths>" PD_SDC_FILE=<generated sdc> ...
# The RTL list and the SDC come from the caller (mk/pd.mk passes $(RTL)), so
# the same config can be run against a modified copy of the RTL.

export DESIGN_NAME     = orbit_demo
export DESIGN_NICKNAME = orbit_demo
export PLATFORM        = sky130hd

ifeq ($(strip $(PD_VERILOG_FILES)),)
  $(error PD_VERILOG_FILES is empty: run the flow through scripts/run_pd.sh)
endif
export VERILOG_FILES = $(PD_VERILOG_FILES)

# The runner writes a copy of constraint.sdc with the requested clock period
# into the work area; fall back to the committed file when run by hand.
ifeq ($(strip $(PD_SDC_FILE)),)
  export SDC_FILE = $(dir $(DESIGN_CONFIG))constraint.sdc
else
  export SDC_FILE = $(PD_SDC_FILE)
endif

# ---------------------------------------------------------------------------
# Redundant storage must survive synthesis as distinct flip-flops.
#
# ORFS synthesises flat (synth -flatten). Yosys' flatten pass leaves any
# module carrying the keep_hierarchy attribute as a separate instance, so each
# orbit_keep_reg copy keeps its own flip-flops and its own reset/enable logic,
# and opt_merge cannot merge the three thermal copies (whose D inputs are the
# same net) because they are never in one module.
#
# The RTL already puts (* keep_hierarchy *) on orbit_keep_reg. SYNTH_KEEP_MODULES
# re-applies it through the supported ORFS hook (synth.tcl: setattr -mod -set
# keep_hierarchy 1) so the property does not depend on the RTL attribute
# alone. The pattern is a glob because the builtin frontend names the
# parameterised copies "$paramod\orbit_keep_reg\W=...", which a bare module
# name does not match.
#
# OpenROAD then links the design flat (OPENROAD_HIERARCHICAL=0, the default);
# the instance names keep the full hierarchical path, which the storage audit
# (pd/audit_storage.py) uses to check the routed netlist.
# ---------------------------------------------------------------------------
export SYNTH_KEEP_MODULES = *orbit_keep_reg*

# ---------------------------------------------------------------------------
# Floorplan / placement. A small block: size the core from utilisation.
# ---------------------------------------------------------------------------
export CORE_UTILIZATION       = 40
export CORE_ASPECT_RATIO      = 1
export CORE_MARGIN            = 2
export PLACE_DENSITY_LB_ADDON = 0.20

# Pins: spread the 215 signal pins a little apart on the boundary.
export PLACE_PINS_ARGS = -min_distance 2 -min_distance_in_tracks

# Repair every violating endpoint, not only the worst few percent.
export TNS_END_PERCENT = 100
