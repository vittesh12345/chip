# Copy-separated physical design (area: pdsep): the sky130hd ORFS flow of
# orbit_demo with placement fences that keep the redundant copies apart
# (copy A / copy B of every accumulator and result pair, the three thermal
# copies). Configuration in pd/sky130hd_sep/ (config.mk, constraint.sdc,
# regions.tcl); runner scripts/run_pd_sep.sh; outputs under $(BUILD)/pd_sep/.
#
#   make pd-sep          full ORFS run (synthesis .. GDS, KLayout DRC and LVS)
#                        with the fences, then pd-sep-gls and pd-sep-report.
#                        Exits non-zero if a check or a separation target fails.
#   make pd-sep-report   re-extract the reports of an existing run: separation
#                        measurement against the baseline (scripts/pdsep_separation.py,
#                        plus pd/copy_separation.py run read-only), regions.json
#                        for the 3D viewer, timing/DRC/LVS/antenna/storage audit
#                        (pd/collect_pd.py run read-only), KLayout render with the
#                        fences outlined, gzipped GDS, summary.md; publishes into
#                        reports/pdsep/ for the production RTL.
#   make pd-sep-gls      post-route gate-level simulation of the separated
#                        netlist with the pd area's harness (pd/gls/, read-only).
#
# Not in TEST_TARGETS: one ORFS run takes 15-25 minutes with PDSEP_CORES=2.

PDSEP_IMAGE        ?= openroad/orfs:latest
PDSEP_CORES        ?= 2
PDSEP_TIMEOUT      ?= 5400
# Empty: the period committed in pd/sky130hd_sep/constraint.sdc.
PDSEP_PERIOD       ?=
PDSEP_VARIANT      ?= sep
# Empty: the region arrangement selected in pd/sky130hd_sep/config.mk.
PDSEP_FP           ?=
PDSEP_FLOW_TARGETS ?= all drc lvs
PDSEP_REQUIRE      ?= drc,lvs
PDSEP_GLS_CYCLES   ?= 30000
PDSEP_GLS_SEED     ?= 1
# The unconstrained baseline (pd area) used for the before/after comparison.
PDSEP_BASE_DEF     ?= $(BUILD)/pd/results/sky130hd/$(TOP)/base/6_final.def
PDSEP_BASE_CHECKS  ?= reports/pd/sky130hd/checks.json

PDSEP_WORK     := $(BUILD)/pd_sep
PDSEP_RESULTS   = $(PDSEP_WORK)/results/sky130hd/$(TOP)/$(PDSEP_VARIANT)
PDSEP_OUT       = $(PDSEP_WORK)/report/$(PDSEP_VARIANT)
PDSEP_PLAT     := $(PDSEP_WORK)/platform
PDSEP_VENV     := $(PDSEP_WORK)/venv
PDSEP_GLS_DIR   = $(PDSEP_WORK)/gls/$(PDSEP_VARIANT)
PDSEP_PUBLISH  ?= $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),reports/pdsep)
PDSEP_ORFS     := /OpenROAD-flow-scripts/flow

PDSEP_RUN = scripts/run_pd_sep.sh --work $(PDSEP_WORK) --cores $(PDSEP_CORES) \
            --timeout $(PDSEP_TIMEOUT) --image $(PDSEP_IMAGE)

.PHONY: pd-sep pd-sep-flow pd-sep-report pd-sep-gls pd-sep-clean

pd-sep: pd-sep-flow
	$(MAKE) --no-print-directory pd-sep-gls
	$(MAKE) --no-print-directory pd-sep-report
	@echo "pd-sep: all checks passed (variant $(PDSEP_VARIANT))"

pd-sep-flow:
	$(PDSEP_RUN) --rtl "$(RTL)" --variant $(PDSEP_VARIANT) $(if $(PDSEP_PERIOD),--period $(PDSEP_PERIOD)) \
	    $(if $(PDSEP_FP),--floorplan $(PDSEP_FP)) -- $(PDSEP_FLOW_TARGETS)

# Platform files copied out of the image once (liberty, merged cell LEF, layer colours).
$(PDSEP_PLAT)/cells.lib:
	@mkdir -p $(dir $@)
	$(PDSEP_RUN) --shell 'cp $(PDSEP_ORFS)/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib $(abspath $@).tmp' && mv $@.tmp $@

$(PDSEP_PLAT)/cells.lef:
	@mkdir -p $(dir $@)
	$(PDSEP_RUN) --shell 'cp $(PDSEP_ORFS)/platforms/sky130hd/lef/sky130_fd_sc_hd_merged.lef $(abspath $@).tmp' && mv $@.tmp $@

$(PDSEP_PLAT)/sky130hd.lyp:
	@mkdir -p $(dir $@)
	$(PDSEP_RUN) --shell 'cp $(PDSEP_ORFS)/platforms/sky130hd/sky130hd.lyp $(abspath $@).tmp' && mv $@.tmp $@

# Standalone KLayout + Pillow for the annotated render (no container needed).
$(PDSEP_VENV)/bin/python:
	python3 -m venv $(PDSEP_VENV)
	$(PDSEP_VENV)/bin/pip install -q klayout==0.30.12 pillow

pd-sep-report: $(PDSEP_PLAT)/cells.lib $(PDSEP_PLAT)/cells.lef $(PDSEP_PLAT)/sky130hd.lyp $(PDSEP_VENV)/bin/python
	@test -f $(PDSEP_WORK)/logs/sky130hd/$(TOP)/$(PDSEP_VARIANT)/6_report.json || \
	    { echo "pd-sep-report: no finished run for variant $(PDSEP_VARIANT) in $(PDSEP_WORK); run make pd-sep"; exit 1; }
	@mkdir -p $(PDSEP_OUT)
	@rc=0; \
	python3 scripts/pdsep_separation.py \
	    $(if $(wildcard $(PDSEP_BASE_DEF)),--def baseline=$(PDSEP_BASE_DEF)) \
	    --def separated=$(PDSEP_RESULTS)/6_final.def --lef $(PDSEP_PLAT)/cells.lef \
	    --md $(PDSEP_OUT)/separation.md --json $(PDSEP_OUT)/separation.json \
	    --regions-json $(PDSEP_OUT)/regions.json --check separated || rc=1; \
	python3 pd/copy_separation.py --def $(PDSEP_RESULTS)/6_final.def --lef $(PDSEP_PLAT)/cells.lef \
	    --out $(PDSEP_OUT)/copy_separation_pd_script.txt > /dev/null || rc=1; \
	python3 pd/collect_pd.py --work $(PDSEP_WORK) --platform sky130hd --variant $(PDSEP_VARIANT) \
	    --design $(TOP) --liberty $(PDSEP_PLAT)/cells.lib --out $(PDSEP_OUT) --require "$(PDSEP_REQUIRE)" \
	    > $(PDSEP_OUT)/collect_pd.log 2>&1 || rc=1; \
	tail -3 $(PDSEP_OUT)/collect_pd.log; \
	$(PDSEP_VENV)/bin/python scripts/pdsep_render.py --gds $(PDSEP_RESULTS)/6_final.gds \
	    --lyp $(PDSEP_PLAT)/sky130hd.lyp --regions $(PDSEP_OUT)/regions.json \
	    --out $(PDSEP_OUT)/$(TOP)_sky130hd_sep.png || rc=1; \
	gzip -9 -n -c $(PDSEP_RESULTS)/6_final.gds > $(PDSEP_OUT)/$(TOP)_sky130hd_sep.gds.gz; \
	python3 scripts/pdsep_summary.py --work $(PDSEP_WORK) --variant $(PDSEP_VARIANT) --out-dir $(PDSEP_OUT) \
	    --base-checks $(PDSEP_BASE_CHECKS) --gls $(PDSEP_GLS_DIR)/gls.log || rc=1; \
	if [ -n "$(PDSEP_PUBLISH)" ]; then \
	    mkdir -p $(PDSEP_PUBLISH); \
	    for f in summary.md regions.json separation.md separation.json checks.json results.md \
	             storage_audit.txt worst_setup_path.txt worst_hold_path.txt power_default_activity.txt \
	             6_finish.rpt 6_drc_count.rpt copy_separation_pd_script.txt period_exploration.md \
	             $(TOP)_sky130hd_sep.png; do \
	        if [ -f $(PDSEP_OUT)/$$f ]; then cp $(PDSEP_OUT)/$$f $(PDSEP_PUBLISH)/; fi; \
	    done; \
	    cp $(PDSEP_WORK)/reports/sky130hd/$(TOP)/$(PDSEP_VARIANT)/pdsep_regions.txt $(PDSEP_PUBLISH)/ 2>/dev/null || true; \
	    gz=$(PDSEP_OUT)/$(TOP)_sky130hd_sep.gds.gz; \
	    if [ $$(stat -c %s $$gz) -lt 5000000 ]; then cp $$gz $(PDSEP_PUBLISH)/; \
	    else echo "pd-sep-report: $$gz is over 5 MB, not published"; fi; \
	    echo "pd-sep-report: published to $(PDSEP_PUBLISH)/"; \
	else echo "pd-sep-report: PDSEP_PUBLISH is empty (RTL_DIR=$(RTL_DIR)); nothing copied to reports/"; fi; \
	exit $$rc

# Post-route GLS: routed netlist vs RTL in lockstep with a flip injected into
# every redundant bit (the pd area's harness, used read-only).
pd-sep-gls: $(PDSEP_PLAT)/cells.lib
	@test -f $(PDSEP_RESULTS)/6_final.v || { echo "pd-sep-gls: no $(PDSEP_RESULTS)/6_final.v; run make pd-sep"; exit 1; }
	python3 pd/gls/gen_gls.py --netlist $(PDSEP_RESULTS)/6_final.v --out-dir $(PDSEP_GLS_DIR) --state IQ
	yosys -q -p "read_liberty -ignore_miss_func -ignore_miss_dir -ignore_miss_data_latch $(PDSEP_PLAT)/cells.lib; \
	    write_verilog -noattr $(PDSEP_GLS_DIR)/cells.v"
	iverilog -g2005 -o $(PDSEP_GLS_DIR)/tb_gls.vvp -I $(PDSEP_GLS_DIR) pd/gls/tb_gls.v $(RTL) \
	    $(PDSEP_GLS_DIR)/orbit_demo_gl.v $(PDSEP_GLS_DIR)/cells.v
	set -o pipefail; vvp -n $(PDSEP_GLS_DIR)/tb_gls.vvp +cycles=$(PDSEP_GLS_CYCLES) +seed=$(PDSEP_GLS_SEED) \
	    | tee $(PDSEP_GLS_DIR)/gls.log
	@if [ -n "$(PDSEP_PUBLISH)" ]; then mkdir -p $(PDSEP_PUBLISH) && cp $(PDSEP_GLS_DIR)/gls.log $(PDSEP_PUBLISH)/gls.log; fi
	@grep -q "^GLS PASS" $(PDSEP_GLS_DIR)/gls.log

pd-sep-clean:
	rm -rf $(PDSEP_WORK)/results $(PDSEP_WORK)/logs $(PDSEP_WORK)/objects $(PDSEP_WORK)/reports \
	       $(PDSEP_WORK)/report $(PDSEP_WORK)/gls $(PDSEP_WORK)/sdc
