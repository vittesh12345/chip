# Synthesis (area: synth): generic Yosys synthesis of orbit_demo, structural
# checks, the storage audit of the nine redundant groups (brief page 4), a
# negative control, netlist-vs-RTL equivalence and gate-level simulation.
# Owner: synth area (synth/, scripts/storage_audit.py, mk/synth.mk, reports/synth/).
#
#   make synth            synth-generic, synth-audit, synth-audit-selftest,
#                         synth-nokeep, synth-equiv and synth-gls (about 2 minutes);
#                         part of TEST_TARGETS
#   make synth-generic    Yosys generic synthesis of $(RTL) (synth/synth_generic.ys):
#                         check -assert, no latches, generic cells only, no Yosys
#                         warnings; netlists, stat and logic depth in $(BUILD)/synth/
#   make synth-audit      scripts/storage_audit.py on the netlist as synthesized and on
#                         its flat view: 9 groups, 521 flip-flop bits, 3 unprotected
#   make synth-audit-selftest
#                         the audit must detect every defect class injected into a copy
#                         of the flat netlist (synth/audit_selftest.py)
#   make synth-nokeep     negative control (synth/negative_control.py): without
#                         keep_hierarchy the thermal copies must merge and the audit
#                         must FAIL; (* keep *) on the register alone is reported
#   make synth-equiv      netlist == RTL by register-cut combinational equivalence
#                         (synth/equiv_cut.ys + synth/equiv.sby, SymbiYosys/bitwuzla),
#                         plus two mutated RTL copies that must be found different
#   make synth-gls        tb/tb_orbit_demo.v on the netlist with Yosys simcells.v and
#                         simlib.v (Icarus); must PASS with the summary of the RTL run
#   make synth-yowasp     the same synthesis with YoWASP Yosys 0.69 (the brief's tool),
#                         installed from PyPI into $(BUILD)/synth/yowasp-venv; flip-flop
#                         counts must match native Yosys and its netlist must pass the
#                         audit; cell counts are compared. Needs network; not in `synth`.
#   make synth-report     synth and synth-yowasp (keep going on failure), then write
#                         $(SYNTH_REPORT_DIR)/ (only when RTL_DIR is the production rtl/)
#
# Everything runs against $(RTL) and writes to $(BUILD)/synth/, so
# `make RTL_DIR=<copy> BUILD=<dir> synth` checks a modified copy of the RTL.

SYNTH_OUT         := $(BUILD)/synth
SYNTH_PY          ?= python3
SYNTH_YOSYS       ?= yosys
SYNTH_YOSYS_CONFIG ?= yosys-config
SYNTH_SBY         ?= sby
SYNTH_JOBS        ?= 2
SYNTH_YS          := synth/synth_generic.ys
SYNTH_RTL_ABS      = $(abspath $(RTL))
SYNTH_JSON         = $(SYNTH_OUT)/orbit_demo_synth.json
SYNTH_FLAT_JSON    = $(SYNTH_OUT)/orbit_demo_synth_flat.json
SYNTH_NETLIST      = $(SYNTH_OUT)/orbit_demo_synth.v
SYNTH_GLS_TB      := tb/tb_orbit_demo.v
SYNTH_GLS_SEED    ?= 1
SYNTH_IVERILOG    ?= iverilog -g2005 -Wall -Wno-timescale
SYNTH_GLS_DIR      = $(SYNTH_OUT)/gls
SYNTH_YOWASP_PKG  ?= yowasp-yosys==0.69.0.0.post1233
SYNTH_YOWASP_VENV  = $(SYNTH_OUT)/yowasp-venv
SYNTH_YOWASP_DIR   = $(SYNTH_OUT)/yowasp
SYNTH_REPORT_DIR  ?= reports/synth
SYNTH_PUBLISH     ?= $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),$(SYNTH_REPORT_DIR))
SYNTH_TB_SUMMARY   = sed -n '/^tb_orbit_demo summary/,/^TB_ORBIT_DEMO/p' $(1)

.PHONY: synth synth-generic synth-audit synth-audit-selftest synth-nokeep synth-equiv \
        synth-gls synth-yowasp synth-report

synth: synth-generic synth-audit synth-audit-selftest synth-nokeep synth-equiv synth-gls
	@echo "SYNTH PASS: generic synthesis + checks, storage audit (+ self-test), keep_hierarchy negative control, equivalence to RTL, gate-level simulation"

# One Yosys run writes every netlist view; it is repeated on each invocation
# (about 2 s) so the results can never be stale with respect to $(RTL).
synth-generic:
	@mkdir -p $(SYNTH_OUT)
	@rm -f $(SYNTH_OUT)/synth_counts.txt $(SYNTH_JSON) $(SYNTH_FLAT_JSON) $(SYNTH_NETLIST)
	@echo "yosys -s $(SYNTH_YS) $(RTL)  (log: $(SYNTH_OUT)/synth.log)"
	@cd $(SYNTH_OUT) && $(SYNTH_YOSYS) -q -l synth.log -s $(abspath $(SYNTH_YS)) $(SYNTH_RTL_ABS) \
	    || { grep -A3 ERROR $(SYNTH_OUT)/synth.log | head -20; echo "synth-generic: FAIL"; exit 1; }
	@if grep -n '^Warning:' $(SYNTH_OUT)/synth.log; then echo "synth-generic: FAIL (Yosys warnings above)"; exit 1; fi
	@$(SYNTH_PY) synth/synth_report.py counts $(SYNTH_OUT)/synth_stat.json $(SYNTH_OUT)/synth_ltp.txt \
	    > $(SYNTH_OUT)/synth_counts.tmp
	@echo "SYNTH_GENERIC PASS: check -assert, no latches, generic cells only, no warnings" >> $(SYNTH_OUT)/synth_counts.tmp
	@mv $(SYNTH_OUT)/synth_counts.tmp $(SYNTH_OUT)/synth_counts.txt
	@cat $(SYNTH_OUT)/synth_counts.txt

synth-audit: synth-generic
	@rm -f $(SYNTH_OUT)/storage_audit.txt $(SYNTH_OUT)/storage_audit_flat.txt
	$(SYNTH_PY) scripts/storage_audit.py $(SYNTH_JSON) --report $(SYNTH_OUT)/storage_audit.txt
	@$(SYNTH_PY) scripts/storage_audit.py $(SYNTH_FLAT_JSON) --report $(SYNTH_OUT)/storage_audit_flat.txt > /dev/null \
	    || { cat $(SYNTH_OUT)/storage_audit_flat.txt; exit 1; }
	@echo "synth-audit: flat view: $$(tail -1 $(SYNTH_OUT)/storage_audit_flat.txt)"

synth-audit-selftest: synth-generic
	@rm -f $(SYNTH_OUT)/audit_selftest.log
	set -o pipefail; $(SYNTH_PY) synth/audit_selftest.py $(SYNTH_FLAT_JSON) $(SYNTH_OUT)/audit_selftest \
	    | tee $(SYNTH_OUT)/audit_selftest.tmp
	@mv $(SYNTH_OUT)/audit_selftest.tmp $(SYNTH_OUT)/audit_selftest.log

synth-nokeep: synth-generic
	@rm -rf $(SYNTH_OUT)/negative_control.txt $(SYNTH_OUT)/nokeep $(SYNTH_OUT)/regkeep
	$(SYNTH_PY) synth/negative_control.py --out $(SYNTH_OUT) --script $(SYNTH_YS) \
	    --baseline $(SYNTH_OUT)/synth_stat.json --yosys $(SYNTH_YOSYS) $(RTL)

synth-equiv: synth-generic
	@rm -f $(SYNTH_OUT)/equiv_result.txt
	$(SYNTH_PY) synth/run_equiv.py --netlist $(SYNTH_NETLIST) --out $(SYNTH_OUT) --jobs $(SYNTH_JOBS) \
	    --yosys $(SYNTH_YOSYS) --sby $(SYNTH_SBY) $(RTL)

# The directed bench is run on the RTL (reference) and on the -noexpr netlist,
# whose every cell is an instance of a Yosys simulation model.
synth-gls: synth-generic
	@rm -rf $(SYNTH_GLS_DIR) && mkdir -p $(SYNTH_GLS_DIR)
	$(SYNTH_IVERILOG) -o $(SYNTH_GLS_DIR)/rtl.vvp $(SYNTH_GLS_TB) $(RTL)
	vvp -n $(SYNTH_GLS_DIR)/rtl.vvp +seed=$(SYNTH_GLS_SEED) > $(SYNTH_GLS_DIR)/rtl.log 2>&1 \
	    || { tail -20 $(SYNTH_GLS_DIR)/rtl.log; echo "synth-gls: RTL reference run FAILED"; exit 1; }
	@grep -q '^TB_ORBIT_DEMO PASS' $(SYNTH_GLS_DIR)/rtl.log
	datdir=$$($(SYNTH_YOSYS_CONFIG) --datdir) && \
	    $(SYNTH_IVERILOG) -o $(SYNTH_GLS_DIR)/gls.vvp $(SYNTH_GLS_TB) $(SYNTH_NETLIST) \
	    $$datdir/simcells.v $$datdir/simlib.v > $(SYNTH_GLS_DIR)/compile.log 2>&1 \
	    || { cat $(SYNTH_GLS_DIR)/compile.log; exit 1; }
	@if [ -s $(SYNTH_GLS_DIR)/compile.log ]; then cat $(SYNTH_GLS_DIR)/compile.log; echo "synth-gls: FAIL (compiler warnings)"; exit 1; fi
	@echo "vvp gls.vvp +seed=$(SYNTH_GLS_SEED)  (gate-level, about a minute; log: $(SYNTH_GLS_DIR)/gls.log)"
	@vvp -n $(SYNTH_GLS_DIR)/gls.vvp +seed=$(SYNTH_GLS_SEED) > $(SYNTH_GLS_DIR)/gls.log 2>&1 \
	    || { tail -30 $(SYNTH_GLS_DIR)/gls.log; echo "SYNTH_GLS FAIL" > $(SYNTH_GLS_DIR)/result.txt; exit 1; }
	@$(call SYNTH_TB_SUMMARY,$(SYNTH_GLS_DIR)/gls.log) | tee $(SYNTH_GLS_DIR)/result.tmp
	@grep -q '^TB_ORBIT_DEMO PASS' $(SYNTH_GLS_DIR)/gls.log \
	    || { echo "SYNTH_GLS FAIL: bench did not pass on the netlist" | tee -a $(SYNTH_GLS_DIR)/result.tmp; \
	         mv $(SYNTH_GLS_DIR)/result.tmp $(SYNTH_GLS_DIR)/result.txt; exit 1; }
	@if diff <($(call SYNTH_TB_SUMMARY,$(SYNTH_GLS_DIR)/rtl.log)) <($(call SYNTH_TB_SUMMARY,$(SYNTH_GLS_DIR)/gls.log)); then \
	    echo "SYNTH_GLS PASS: TB_ORBIT_DEMO PASS on the netlist, summary identical to the RTL run" | tee -a $(SYNTH_GLS_DIR)/result.tmp; \
	    mv $(SYNTH_GLS_DIR)/result.tmp $(SYNTH_GLS_DIR)/result.txt; \
	else \
	    echo "SYNTH_GLS FAIL: summary differs from the RTL run" | tee -a $(SYNTH_GLS_DIR)/result.tmp; \
	    mv $(SYNTH_GLS_DIR)/result.tmp $(SYNTH_GLS_DIR)/result.txt; exit 1; \
	fi

# YoWASP runs Yosys as WebAssembly with only some host paths visible; paths
# under /tmp are not, so keep BUILD outside /tmp for this target.
$(SYNTH_YOWASP_VENV)/bin/yowasp-yosys:
	@mkdir -p $(SYNTH_OUT)
	python3 -m venv $(SYNTH_YOWASP_VENV)
	$(SYNTH_YOWASP_VENV)/bin/pip install -q "$(SYNTH_YOWASP_PKG)"

synth-yowasp: synth-generic $(SYNTH_YOWASP_VENV)/bin/yowasp-yosys
	@rm -rf $(SYNTH_YOWASP_DIR) && mkdir -p $(SYNTH_YOWASP_DIR)
	@echo "yowasp-yosys -s $(SYNTH_YS) $(RTL)  (first run compiles the WebAssembly module, about a minute)"
	@cd $(SYNTH_YOWASP_DIR) && $(abspath $(SYNTH_YOWASP_VENV))/bin/yowasp-yosys -V > version.txt && \
	    $(abspath $(SYNTH_YOWASP_VENV))/bin/yowasp-yosys -q -l synth.log -s $(abspath $(SYNTH_YS)) $(SYNTH_RTL_ABS) \
	    || { tail -20 $(SYNTH_YOWASP_DIR)/synth.log; echo "synth-yowasp: FAIL"; exit 1; }
	$(SYNTH_PY) scripts/storage_audit.py $(SYNTH_YOWASP_DIR)/orbit_demo_synth.json \
	    --report $(SYNTH_YOWASP_DIR)/storage_audit.txt > /dev/null \
	    || { cat $(SYNTH_YOWASP_DIR)/storage_audit.txt; exit 1; }
	@echo "synth-yowasp: audit of the YoWASP netlist: $$(tail -1 $(SYNTH_YOWASP_DIR)/storage_audit.txt)"
	set -o pipefail; $(SYNTH_PY) synth/synth_report.py yowasp-compare $(SYNTH_OUT) $(SYNTH_YOWASP_DIR) \
	    | tee $(SYNTH_YOWASP_DIR)/compare.txt

synth-report:
	-@$(MAKE) --no-print-directory -k synth synth-yowasp
	@if [ -z "$(SYNTH_PUBLISH)" ]; then \
	    echo "synth-report: RTL_DIR=$(RTL_DIR) is not the production rtl/; nothing copied to reports/"; \
	else \
	    mkdir -p $(SYNTH_PUBLISH) && \
	    for f in synth_stat.txt synth_counts.txt synth_ltp.txt storage_audit.txt storage_audit_flat.txt \
	             audit_selftest.log negative_control.txt equiv_result.txt; do \
	        if [ -f $(SYNTH_OUT)/$$f ]; then cp $(SYNTH_OUT)/$$f $(SYNTH_PUBLISH)/$$f; else rm -f $(SYNTH_PUBLISH)/$$f; fi; \
	    done; \
	    for v in nokeep regkeep; do \
	        cp $(SYNTH_OUT)/$$v/storage_audit.txt $(SYNTH_PUBLISH)/storage_audit_$$v.txt 2>/dev/null || rm -f $(SYNTH_PUBLISH)/storage_audit_$$v.txt; \
	    done; \
	    cp $(SYNTH_GLS_DIR)/result.txt $(SYNTH_PUBLISH)/gls_result.txt 2>/dev/null || rm -f $(SYNTH_PUBLISH)/gls_result.txt; \
	    cp $(SYNTH_YOWASP_DIR)/compare.txt $(SYNTH_PUBLISH)/yowasp_compare.txt 2>/dev/null || rm -f $(SYNTH_PUBLISH)/yowasp_compare.txt; \
	    cp $(SYNTH_YOWASP_DIR)/storage_audit.txt $(SYNTH_PUBLISH)/storage_audit_yowasp.txt 2>/dev/null || rm -f $(SYNTH_PUBLISH)/storage_audit_yowasp.txt; \
	    $(SYNTH_PY) synth/synth_report.py trim-log $(SYNTH_OUT)/synth.log > $(SYNTH_PUBLISH)/synth_log_trimmed.txt; \
	    $(SYNTH_PY) synth/synth_report.py summary --build $(SYNTH_OUT) --out $(SYNTH_PUBLISH)/summary.md \
	        --rtl "$(RTL)"; \
	fi

TEST_TARGETS += synth
