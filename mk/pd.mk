# Physical design (area: pd): RTL-to-GDSII of orbit_demo with
# OpenROAD-flow-scripts (ORFS) on the SkyWater sky130hd open PDK.
#
#   make pd          full ORFS run of $(RTL) (synthesis .. detailed route,
#                    final report, GDS, KLayout DRC and LVS) at the committed
#                    clock period (pd/<platform>/constraint.sdc), then pd-report.
#                    Fails if any check fails (timing, DRC, LVS, LEC, antenna,
#                    storage audit of the routed netlist).
#   make pd-report   re-extract and re-check the reports of an existing run.
#   make pd-sweep    clock-period sweep, one full ORFS run per period in
#                    PD_SWEEP_PERIODS (informational, not a pass/fail target).
#   make pd-ihp      the same flow on IHP SG13G2 (second open-PDK data point).
#
# The flow runs in the openroad/orfs Docker image through scripts/run_pd.sh.
# ORFS outputs: $(BUILD)/pd/{logs,objects,reports,results}/<platform>/orbit_demo/<variant>/,
# sweep runs under $(BUILD)/pd/sweep/, extracted reports under
# $(BUILD)/pd/report/<platform>/. The extracted reports are copied into the
# committed reports/pd/ only for runs of the production RTL (RTL_DIR=rtl), so a
# run against a modified RTL copy never overwrites the evidence.
#
# Not in TEST_TARGETS: one run takes about 6 minutes with PD_CORES=2.

PD_IMAGE         ?= openroad/orfs:latest
PD_PLATFORM      ?= sky130hd
PD_CORES         ?= 2
PD_TIMEOUT       ?= 3600
# Empty: use the period committed in pd/$(PD_PLATFORM)/constraint.sdc.
PD_PERIOD        ?=
PD_VARIANT       ?= base
PD_FLOW_TARGETS  ?= all drc lvs
# NOT_RUN counts as a failure for these checks in `make pd`.
PD_REQUIRE       ?= drc,lvs
PD_SWEEP_PERIODS ?= 20 10 8 7 6

PD_WORK       := $(BUILD)/pd
PD_SWEEP_WORK := $(PD_WORK)/sweep
PD_OUT         = $(PD_WORK)/report/$(PD_PLATFORM)
PD_PLAT_DIR    = $(PD_WORK)/platform/$(PD_PLATFORM)
PD_PUBLISH    ?= $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),reports/pd)

# Files inside the image, per platform: liberty used for timing (and by the
# storage audit to recognise flip-flops), KLayout layer properties, corner.
PD_ORFS_FLOW          := /OpenROAD-flow-scripts/flow
PD_LIB_sky130hd       := platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
PD_LYP_sky130hd       := platforms/sky130hd/sky130hd.lyp
PD_CORNER_sky130hd    := sky130_fd_sc_hd__tt_025C_1v80.lib (TT, 25 C, 1.80 V), the only liberty ORFS uses for sky130hd
PD_LIB_ihp-sg13g2     := platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib
PD_LYP_ihp-sg13g2     := platforms/ihp-sg13g2/sg13g2.lyp
PD_CORNER_ihp-sg13g2  := sg13g2_stdcell_typ_1p20V_25C.lib (typical, 25 C, 1.20 V), the ORFS default for ihp-sg13g2

PD_RUN = scripts/run_pd.sh --work $(PD_WORK) --platform $(PD_PLATFORM) \
         --cores $(PD_CORES) --timeout $(PD_TIMEOUT) --image $(PD_IMAGE)

.PHONY: pd pd-flow pd-report pd-sweep pd-ihp pd-clean

pd: pd-flow
	$(MAKE) --no-print-directory pd-report

# The ORFS run itself (make re-runs only the stages whose inputs changed).
pd-flow:
	$(PD_RUN) --rtl "$(RTL)" --variant $(PD_VARIANT) $(if $(PD_PERIOD),--period $(PD_PERIOD)) \
	    -- $(PD_FLOW_TARGETS)

# Extract, check and (for the production RTL) publish the results of a run.
# The images are rendered from the final GDS by KLayout in batch mode.
pd-report:
	@test -f $(PD_WORK)/logs/$(PD_PLATFORM)/$(TOP)/$(PD_VARIANT)/6_report.json || \
	    { echo "pd-report: no finished ORFS run in $(PD_WORK) for $(PD_PLATFORM)/$(PD_VARIANT); run make pd"; exit 1; }
	@mkdir -p $(PD_OUT) $(PD_PLAT_DIR)
	set -o pipefail; $(PD_RUN) --shell 'cp $(PD_ORFS_FLOW)/$(PD_LIB_$(PD_PLATFORM)) $(abspath $(PD_PLAT_DIR))/cells.lib && \
	    klayout -zz -r $(CURDIR)/pd/render_layout.py \
	      -rd gds=$(abspath $(PD_WORK))/results/$(PD_PLATFORM)/$(TOP)/$(PD_VARIANT)/6_final.gds \
	      -rd lyp=$(PD_ORFS_FLOW)/$(PD_LYP_$(PD_PLATFORM)) \
	      -rd out=$(abspath $(PD_OUT))/$(TOP)_$(PD_PLATFORM).png \
	      -rd detail_out=$(abspath $(PD_OUT))/$(TOP)_$(PD_PLATFORM)_detail.png -rd detail_frac=0.10' \
	    | tee $(PD_OUT)/render.log
	gzip -9 -n -c $(PD_WORK)/results/$(PD_PLATFORM)/$(TOP)/$(PD_VARIANT)/6_final.gds > $(PD_OUT)/$(TOP)_$(PD_PLATFORM).gds.gz
	@rc=0; python3 pd/collect_pd.py --work $(PD_WORK) --platform $(PD_PLATFORM) --variant $(PD_VARIANT) \
	    --design $(TOP) --liberty $(PD_PLAT_DIR)/cells.lib --out $(PD_OUT) --require "$(PD_REQUIRE)" || rc=$$?; \
	if [ -n "$(PD_PUBLISH)" ]; then \
	    mkdir -p $(PD_PUBLISH)/$(PD_PLATFORM); \
	    for f in results.md checks.json storage_audit.txt worst_setup_path.txt worst_hold_path.txt \
	             power_default_activity.txt cell_usage.txt synth_stat.txt 6_finish.rpt 6_drc_count.rpt render.log; do \
	        if [ -f $(PD_OUT)/$$f ]; then cp $(PD_OUT)/$$f $(PD_PUBLISH)/$(PD_PLATFORM)/; fi; \
	    done; \
	    cp $(PD_OUT)/$(TOP)_$(PD_PLATFORM).png $(PD_OUT)/$(TOP)_$(PD_PLATFORM)_detail.png $(PD_PUBLISH)/; \
	    gz=$(PD_OUT)/$(TOP)_$(PD_PLATFORM).gds.gz; \
	    if [ $$(stat -c %s $$gz) -lt 5000000 ]; then cp $$gz $(PD_PUBLISH)/; \
	    else echo "pd-report: $$gz is over 5 MB, not published"; fi; \
	    echo "pd-report: published to $(PD_PUBLISH)/"; \
	else echo "pd-report: RTL_DIR=$(RTL_DIR) is not the production RTL; nothing published"; fi; \
	exit $$rc

# Clock-period sweep: every point is a complete run up to the final report
# (no GDS), in its own variant p<period>ns under $(PD_SWEEP_WORK).
pd-sweep:
	@set -e; for p in $(PD_SWEEP_PERIODS); do \
	    scripts/run_pd.sh --work $(PD_SWEEP_WORK) --platform $(PD_PLATFORM) --cores $(PD_CORES) \
	        --timeout $(PD_TIMEOUT) --image $(PD_IMAGE) --rtl "$(RTL)" --variant p$${p}ns --period $$p \
	        -- $(abspath $(PD_SWEEP_WORK))/logs/$(PD_PLATFORM)/$(TOP)/p$${p}ns/6_report.log; \
	done
	@mkdir -p $(PD_OUT)
	python3 pd/sweep_summary.py --work $(PD_SWEEP_WORK) --platform $(PD_PLATFORM) --design $(TOP) \
	    --periods "$(PD_SWEEP_PERIODS)" --corner "$(PD_CORNER_$(PD_PLATFORM))" --out $(PD_OUT)/period_sweep.md
	@if [ -n "$(PD_PUBLISH)" ]; then mkdir -p $(PD_PUBLISH) && \
	    cp $(PD_OUT)/period_sweep.md $(PD_PUBLISH)/period_sweep_$(PD_PLATFORM).md; fi

# Second open PDK. Same flow and checks; DRC/LVS are whatever ORFS provides.
pd-ihp:
	$(MAKE) --no-print-directory pd PD_PLATFORM=ihp-sg13g2

pd-clean:
	rm -rf $(PD_WORK)
