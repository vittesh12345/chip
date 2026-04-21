# Physical design (area: pd): RTL-to-GDSII of orbit_demo with
# OpenROAD-flow-scripts (ORFS) on the SkyWater sky130hd open PDK.
#
#   make pd          full ORFS run of $(RTL) at the committed clock period
#                    (pd/<platform>/constraint.sdc): synthesis .. detailed route,
#                    final report, GDS, KLayout DRC and LVS; then pd-report,
#                    pd-gls and pd-negctl. Exits non-zero if any check fails.
#   make pd-report   re-extract and re-check the reports of an existing run
#                    (timing, DRC, LVS, LEC, antenna, storage audit of the
#                    routed netlist, layout images, compressed GDS, and the
#                    measured physical separation of the redundant copies).
#   make pd-gls      post-route gate-level simulation: routed netlist vs RTL in
#                    lockstep, with a flip injected into every redundant bit.
#   make pd-negctl   controls: without the RTL attribute, SYNTH_KEEP_MODULES
#                    alone must keep every copy (audit PASS); without both the
#                    thermal copies merge and the storage audit must FAIL.
#   make pd-sweep    clock-period sweep, one full ORFS run per period in
#                    PD_SWEEP_PERIODS (informational).
#   make pd-corners  re-time the routed design at other sky130 corners
#                    (informational; downloads the SS/FF liberty files).
#   make pd-ihp      the same flow on IHP SG13G2 (second open-PDK data point).
#
# The flow runs in the openroad/orfs Docker image through scripts/run_pd.sh.
# ORFS outputs: $(BUILD)/pd/{logs,objects,reports,results}/<platform>/orbit_demo/<variant>/;
# sweep runs under $(BUILD)/pd/sweep/, the negative control under
# $(BUILD)/pd/negctl/, extracted reports under $(BUILD)/pd/report/<platform>/.
# Extracted reports are copied into the committed reports/pd/ only for runs of
# the production RTL (RTL_DIR=rtl), so a run against a modified RTL copy never
# overwrites the evidence.
#
# Not in TEST_TARGETS: one ORFS run takes 7-13 minutes with PD_CORES=2 (more
# with DRC/LVS), and `make pd` needs Docker.

PD_IMAGE         ?= openroad/orfs:latest
PD_PLATFORM      ?= sky130hd
PD_CORES         ?= 2
PD_TIMEOUT       ?= 3600
# Empty: use the period committed in pd/$(PD_PLATFORM)/constraint.sdc.
PD_PERIOD        ?=
PD_VARIANT       ?= base
PD_FLOW_TARGETS  ?= all drc lvs
# A NOT_RUN result counts as a failure for these checks in pd-report.
PD_REQUIRE       ?= drc,lvs
PD_SWEEP_PERIODS ?= 20 10 8 7 6.5 6
PD_GLS_CYCLES    ?= 30000
PD_GLS_SEED      ?= 1

PD_WORK       := $(BUILD)/pd
PD_SWEEP_WORK := $(PD_WORK)/sweep
PD_NEG_WORK   := $(PD_WORK)/negctl
PD_OUT         = $(PD_WORK)/report/$(PD_PLATFORM)
PD_PLAT_DIR    = $(PD_WORK)/platform/$(PD_PLATFORM)
PD_RESULTS     = $(PD_WORK)/results/$(PD_PLATFORM)/$(TOP)/$(PD_VARIANT)
PD_GLS_DIR     = $(PD_WORK)/gls/$(PD_PLATFORM)
PD_PUBLISH    ?= $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),reports/pd)
PD_PUB_DIR     = $(PD_PUBLISH)/$(PD_PLATFORM)

# Per platform, inside the image: liberty used for timing (also the source of
# the flip-flop list for the audit and of the GLS cell models), KLayout layer
# properties, the flip-flop state variable in the Yosys-generated cell models,
# and a description of the timing corner.
PD_ORFS_FLOW          := /OpenROAD-flow-scripts/flow
PD_LIB_sky130hd       := platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
PD_LYP_sky130hd       := platforms/sky130hd/sky130hd.lyp
PD_LEF_sky130hd       := platforms/sky130hd/lef/sky130_fd_sc_hd_merged.lef
PD_STATE_sky130hd     := IQ
PD_CORNER_sky130hd    := sky130_fd_sc_hd__tt_025C_1v80.lib (TT, 25 C, 1.80 V), the only liberty ORFS uses for sky130hd
PD_IMGW_sky130hd      := 1200
PD_PUBGDS_sky130hd    := yes
PD_LIB_ihp-sg13g2     := platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib
PD_LYP_ihp-sg13g2     := platforms/ihp-sg13g2/sg13g2.lyp
PD_LEF_ihp-sg13g2     := platforms/ihp-sg13g2/lef/sg13g2_stdcell.lef
PD_STATE_ihp-sg13g2   := IQ
PD_CORNER_ihp-sg13g2  := sg13g2_stdcell_typ_1p20V_25C.lib (typical, 25 C, 1.20 V), the ORFS default for ihp-sg13g2
# The IHP run is a secondary data point: smaller images, GDS not committed.
PD_IMGW_ihp-sg13g2    := 800
PD_PUBGDS_ihp-sg13g2  := no

# Extra sky130_fd_sc_hd corners for pd-corners (not shipped in the ORFS image).
PD_CORNER_URL  ?= https://raw.githubusercontent.com/efabless/skywater-pdk-libs-sky130_fd_sc_hd/master/timing
PD_XCORNERS    ?= ss_100C_1v60 ff_n40C_1v95

PD_RUN = scripts/run_pd.sh --work $(PD_WORK) --platform $(PD_PLATFORM) \
         --cores $(PD_CORES) --timeout $(PD_TIMEOUT) --image $(PD_IMAGE)

.PHONY: pd pd-flow pd-report pd-gls pd-negctl pd-sweep pd-corners pd-ihp pd-clean

pd: pd-flow
	$(MAKE) --no-print-directory pd-report
	$(MAKE) --no-print-directory pd-gls
	$(MAKE) --no-print-directory pd-negctl
	@echo "pd: all checks passed ($(PD_PLATFORM), $(PD_VARIANT))"

# The ORFS run itself (ORFS re-runs only the stages whose inputs changed).
pd-flow:
	$(PD_RUN) --rtl "$(RTL)" --variant $(PD_VARIANT) $(if $(PD_PERIOD),--period $(PD_PERIOD)) \
	    -- $(PD_FLOW_TARGETS)

# Liberty and cell LEF of the platform, copied out of the image once.
$(PD_PLAT_DIR)/cells.lib:
	@mkdir -p $(dir $@)
	$(PD_RUN) --shell 'cp $(PD_ORFS_FLOW)/$(PD_LIB_$(PD_PLATFORM)) $(abspath $@).tmp' && mv $@.tmp $@

$(PD_PLAT_DIR)/cells.lef:
	@mkdir -p $(dir $@)
	$(PD_RUN) --shell 'cp $(PD_ORFS_FLOW)/$(PD_LEF_$(PD_PLATFORM)) $(abspath $@).tmp' && mv $@.tmp $@

# Extract, check and (for the production RTL) publish the results of a run.
# The images are rendered from the final GDS by KLayout in batch mode; the six
# thermal-copy flip-flops are outlined in green and the detail view is
# centred on them.
pd-report: $(PD_PLAT_DIR)/cells.lib $(PD_PLAT_DIR)/cells.lef
	@test -f $(PD_WORK)/logs/$(PD_PLATFORM)/$(TOP)/$(PD_VARIANT)/6_report.json || \
	    { echo "pd-report: no finished ORFS run in $(PD_WORK) for $(PD_PLATFORM)/$(PD_VARIANT); run make pd"; exit 1; }
	@mkdir -p $(PD_OUT)
	python3 pd/copy_separation.py --def $(PD_RESULTS)/6_final.def --lef $(PD_PLAT_DIR)/cells.lef \
	    --out $(PD_OUT)/copy_separation.txt --boxes $(PD_OUT)/thermal_cells.json
	set -o pipefail; $(PD_RUN) --shell 'klayout -zz -r $(CURDIR)/pd/render_layout.py \
	      -rd gds=$(abspath $(PD_RESULTS))/6_final.gds \
	      -rd lyp=$(PD_ORFS_FLOW)/$(PD_LYP_$(PD_PLATFORM)) \
	      -rd highlight=$(abspath $(PD_OUT))/thermal_cells.json \
	      -rd out=$(abspath $(PD_OUT))/$(TOP)_$(PD_PLATFORM).png \
	      -rd detail_out=$(abspath $(PD_OUT))/$(TOP)_$(PD_PLATFORM)_detail.png -rd detail_frac=0.12 -rd width=$(PD_IMGW_$(PD_PLATFORM))' \
	    | tee $(PD_OUT)/render.log
	gzip -9 -n -c $(PD_RESULTS)/6_final.gds > $(PD_OUT)/$(TOP)_$(PD_PLATFORM).gds.gz
	@rc=0; python3 pd/collect_pd.py --work $(PD_WORK) --platform $(PD_PLATFORM) --variant $(PD_VARIANT) \
	    --design $(TOP) --liberty $(PD_PLAT_DIR)/cells.lib --out $(PD_OUT) --require "$(PD_REQUIRE)" || rc=$$?; \
	if [ -n "$(PD_PUBLISH)" ]; then \
	    mkdir -p $(PD_PUB_DIR); \
	    for f in results.md checks.json storage_audit.txt worst_setup_path.txt worst_hold_path.txt \
	             power_default_activity.txt cell_usage.txt synth_stat.txt 6_finish.rpt 6_drc_count.rpt \
	             copy_separation.txt render.log; do \
	        if [ -f $(PD_OUT)/$$f ]; then cp $(PD_OUT)/$$f $(PD_PUB_DIR)/; fi; \
	    done; \
	    cp $(PD_OUT)/$(TOP)_$(PD_PLATFORM).png $(PD_OUT)/$(TOP)_$(PD_PLATFORM)_detail.png $(PD_PUBLISH)/; \
	    gz=$(PD_OUT)/$(TOP)_$(PD_PLATFORM).gds.gz; \
	    if [ "$(PD_PUBGDS_$(PD_PLATFORM))" != yes ]; then echo "pd-report: GDS not published for $(PD_PLATFORM)"; \
	    elif [ $$(stat -c %s $$gz) -lt 5000000 ]; then cp $$gz $(PD_PUBLISH)/; \
	    else echo "pd-report: $$gz is over 5 MB, not published"; fi; \
	    echo "pd-report: published to $(PD_PUBLISH)/"; \
	else echo "pd-report: PD_PUBLISH is empty (RTL_DIR=$(RTL_DIR)); nothing copied to reports/"; fi; \
	exit $$rc

# Post-route gate-level simulation (zero delay) of the routed netlist against
# the RTL, with cell models generated by Yosys from the timing liberty.
pd-gls: $(PD_PLAT_DIR)/cells.lib
	@test -f $(PD_RESULTS)/6_final.v || { echo "pd-gls: no $(PD_RESULTS)/6_final.v; run make pd"; exit 1; }
	python3 pd/gls/gen_gls.py --netlist $(PD_RESULTS)/6_final.v --out-dir $(PD_GLS_DIR) \
	    --state $(PD_STATE_$(PD_PLATFORM)) --liberty $(PD_PLAT_DIR)/cells.lib
	yosys -q -p "read_liberty -ignore_miss_func -ignore_miss_dir -ignore_miss_data_latch $(PD_PLAT_DIR)/cells.lib; \
	    write_verilog -noattr $(PD_GLS_DIR)/cells.v"
	iverilog -g2005 -o $(PD_GLS_DIR)/tb_gls.vvp -I $(PD_GLS_DIR) pd/gls/tb_gls.v $(RTL) \
	    $(PD_GLS_DIR)/orbit_demo_gl.v $(PD_GLS_DIR)/cells.v
	set -o pipefail; vvp -n $(PD_GLS_DIR)/tb_gls.vvp +cycles=$(PD_GLS_CYCLES) +seed=$(PD_GLS_SEED) \
	    | tee $(PD_GLS_DIR)/gls.log
	@if [ -n "$(PD_PUBLISH)" ]; then mkdir -p $(PD_PUB_DIR) && cp $(PD_GLS_DIR)/gls.log $(PD_PUB_DIR)/gls.log; fi
	@grep -q "^GLS PASS" $(PD_GLS_DIR)/gls.log

# Controls for the keep mechanism and the storage audit. The RTL is copied
# with the keep_hierarchy attribute line removed and ORFS synthesis is run
# twice on the copy:
#   cfgkeep : SYNTH_KEEP_MODULES from config.mk still applies -> the audit must
#             PASS (the ORFS setting alone keeps every copy);
#   nokeep  : SYNTH_KEEP_MODULES cleared as well -> Yosys merges the three
#             thermal copies (identical D inputs) and the audit must FAIL on
#             the thermal group, which shows the audit is not vacuous.
PD_NEG_RTL = $(addprefix $(PD_NEG_WORK)/rtl/,$(notdir $(RTL)))
PD_NEG_RUN = scripts/run_pd.sh --work $(PD_NEG_WORK) --platform $(PD_PLATFORM) --cores $(PD_CORES) \
             --timeout $(PD_TIMEOUT) --image $(PD_IMAGE) --rtl "$(PD_NEG_RTL)"
PD_NEG_NET = $(PD_NEG_WORK)/results/$(PD_PLATFORM)/$(TOP)
pd-negctl: $(PD_PLAT_DIR)/cells.lib
	@mkdir -p $(PD_NEG_WORK)/rtl $(PD_OUT)
	@for f in $(RTL); do sed '/^(\* keep_hierarchy \*)$$/d' $$f > $(PD_NEG_WORK)/rtl/$$(basename $$f); done
	@echo "pd-negctl: keep_hierarchy attribute lines: original $$(cat $(RTL) | grep -c '^(\* keep_hierarchy \*)$$'), copy $$(cat $(PD_NEG_RTL) | grep -c '^(\* keep_hierarchy \*)$$')"
	$(PD_NEG_RUN) --variant cfgkeep -- synth > $(PD_NEG_WORK)/run_cfgkeep.log 2>&1 || { tail -20 $(PD_NEG_WORK)/run_cfgkeep.log; exit 1; }
	$(PD_NEG_RUN) --variant nokeep --var SYNTH_KEEP_MODULES= -- synth > $(PD_NEG_WORK)/run_nokeep.log 2>&1 || { tail -20 $(PD_NEG_WORK)/run_nokeep.log; exit 1; }
	for v in cfgkeep nokeep; do \
	    scripts/run_pd.sh --work $(PD_NEG_WORK) --platform $(PD_PLATFORM) --image $(PD_IMAGE) \
	        --shell "PD_ODB=$(abspath $(PD_NEG_NET))/$$v/1_synth.odb PD_NETLIST=$(abspath $(PD_NEG_NET))/$$v/1_synth_flat.v \
	            openroad -no_init -threads 1 -exit $(CURDIR)/pd/write_netlist.tcl" > /dev/null || exit 1; \
	done
	@rc1=0; rc2=0; \
	python3 pd/audit_storage.py --netlist $(PD_NEG_NET)/cfgkeep/1_synth_flat.v --liberty $(PD_PLAT_DIR)/cells.lib \
	    --report $(PD_OUT)/negctl_cfgkeep_audit.txt > /dev/null || rc1=$$?; \
	python3 pd/audit_storage.py --netlist $(PD_NEG_NET)/nokeep/1_synth_flat.v --liberty $(PD_PLAT_DIR)/cells.lib \
	    --report $(PD_OUT)/negctl_nokeep_audit.txt > /dev/null || rc2=$$?; \
	echo "cfgkeep (no RTL attribute, SYNTH_KEEP_MODULES set):"; grep -E "flip-flop count|RESULT" $(PD_OUT)/negctl_cfgkeep_audit.txt; \
	echo "nokeep (no RTL attribute, SYNTH_KEEP_MODULES cleared):"; grep -E "group thermal|flip-flop count|RESULT" $(PD_OUT)/negctl_nokeep_audit.txt; \
	if [ -n "$(PD_PUBLISH)" ]; then mkdir -p $(PD_PUB_DIR) && \
	    cp $(PD_OUT)/negctl_cfgkeep_audit.txt $(PD_OUT)/negctl_nokeep_audit.txt $(PD_PUB_DIR)/; fi; \
	if [ $$rc1 -eq 0 ] && [ $$rc2 -ne 0 ] && grep -q "FAIL  group thermal" $(PD_OUT)/negctl_nokeep_audit.txt; then \
	    echo "pd-negctl: PASS (SYNTH_KEEP_MODULES alone keeps all copies; without any keep the thermal copies merge and the audit detects it)"; \
	else echo "pd-negctl: FAIL (cfgkeep audit rc=$$rc1, expected 0; nokeep audit rc=$$rc2, expected a thermal-group failure)"; exit 1; fi

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

# Multi-corner STA of the routed design (sky130hd only).
$(PD_PLAT_DIR)/corners/sky130_fd_sc_hd__%.lib:
	@mkdir -p $(dir $@)
	curl -fsSL -o $@.tmp $(PD_CORNER_URL)/sky130_fd_sc_hd__$*.lib && mv $@.tmp $@

pd-corners: $(PD_PLAT_DIR)/cells.lib $(foreach c,$(PD_XCORNERS),$(PD_PLAT_DIR)/corners/sky130_fd_sc_hd__$(c).lib)
	@test -f $(PD_RESULTS)/6_final.spef || { echo "pd-corners: no routed run; run make pd"; exit 1; }
	@mkdir -p $(PD_OUT)
	@set -e; for c in tt $(PD_XCORNERS); do \
	    if [ $$c = tt ]; then lib=$(PD_ORFS_FLOW)/$(PD_LIB_$(PD_PLATFORM)); \
	    else lib=$(abspath $(PD_PLAT_DIR))/corners/sky130_fd_sc_hd__$$c.lib; fi; \
	    $(PD_RUN) --shell "PD_CORNER=$$c PD_LIB=$$lib PD_ODB=$(abspath $(PD_RESULTS))/6_final.odb \
	        PD_SDC=$(abspath $(PD_RESULTS))/6_final.sdc PD_SPEF=$(abspath $(PD_RESULTS))/6_final.spef \
	        openroad -no_init -threads 1 -exit $(CURDIR)/pd/sta_corners.tcl" > $(PD_OUT)/sta_$$c.log 2>&1; \
	done
	python3 pd/corners_summary.py --out $(PD_OUT)/sta_corners.txt \
	    --period "$$(sed -nE 's/^create_clock .*-period ([0-9.]+).*/\1/p' $(PD_RESULTS)/6_final.sdc | head -1)" \
	    --note "Liberty: tt = the ORFS platform file; the others from $(PD_CORNER_URL)" \
	    --note "sha256: $$(cd $(PD_PLAT_DIR)/corners && sha256sum *.lib | awk '{printf "%s %s; ", $$2, substr($$1,1,16)}')" \
	    $(foreach c,tt $(PD_XCORNERS),$(PD_OUT)/sta_$(c).log)
	@if [ -n "$(PD_PUBLISH)" ]; then mkdir -p $(PD_PUB_DIR) && cp $(PD_OUT)/sta_corners.txt $(PD_PUB_DIR)/; fi

# Second open PDK. Same flow and checks. ORFS provides a KLayout DRC deck
# (sg13g2_minimal.lydrc) but no KLayout LVS setup for ihp-sg13g2, so LVS is
# reported NOT_RUN there and only DRC is required.
pd-ihp:
	$(MAKE) --no-print-directory pd PD_PLATFORM=ihp-sg13g2 PD_REQUIRE=drc

pd-clean:
	rm -rf $(PD_WORK)
