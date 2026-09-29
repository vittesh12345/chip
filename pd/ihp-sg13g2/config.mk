# ORFS design configuration: ORBIT-AI demonstrator on IHP SG13G2 (open 130 nm
# BiCMOS PDK), typical 1.20 V 25 C liberty as selected by the ORFS platform.
# A second open-PDK data point for the same RTL; see pd/sky130hd/config.mk for
# the reasoning behind each setting, which is the same here.

export DESIGN_NAME     = orbit_demo
export DESIGN_NICKNAME = orbit_demo
export PLATFORM        = ihp-sg13g2

ifeq ($(strip $(PD_VERILOG_FILES)),)
  $(error PD_VERILOG_FILES is empty: run the flow through scripts/run_pd.sh)
endif
export VERILOG_FILES = $(PD_VERILOG_FILES)

ifeq ($(strip $(PD_SDC_FILE)),)
  export SDC_FILE = $(dir $(DESIGN_CONFIG))constraint.sdc
else
  export SDC_FILE = $(PD_SDC_FILE)
endif

# Keep every orbit_keep_reg copy as its own instance through flat synthesis
# (the RTL also carries (* keep_hierarchy *)).
export SYNTH_KEEP_MODULES = *orbit_keep_reg*

export CORE_UTILIZATION       = 40
export CORE_ASPECT_RATIO      = 1
export PLACE_DENSITY_LB_ADDON = 0.20
export PLACE_PINS_ARGS        = -min_distance 2 -min_distance_in_tracks
export TNS_END_PERCENT        = 100

# As in the ORFS ihp-sg13g2 example designs: metal density fill (the
# sg13g2_minimal.lydrc deck checks global metal density, which an unfilled
# block fails) and the CTS buffer distance used by riscv32i/ibex.
export USE_FILL         = 1
export CTS_BUF_DISTANCE = 60
