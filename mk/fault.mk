# Fault injection (area: fault): what the duplicated lane storage and the
# triplicated thermal state catch, and what escapes from the unprotected
# flip-flops. Owner: fault area (fault/, mk/fault.mk, reports/fault/).
#
#   make fault           fault-formal, fault-campaign and fault-negctl, then
#                        $(BUILD)/fault/summary.md (about 3 minutes); for the
#                        production RTL the summary and the evidence are copied
#                        to reports/fault/
#   make fault-formal    SymbiYosys on generated copies of $(RTL) with one
#                        injectable upset each (fault/gen_fault_copies.py,
#                        harness fault/fi_harness.sv): k-induction proofs and
#                        covers for accumulator A/B, result A/B and thermal
#                        copies 0/1/2; the negative scenarios (out_valid_q,
#                        shared product) must FAIL
#   make fault-campaign  Icarus Verilog SEU campaign (fault/tb_seu_campaign.v):
#                        every one of the 521 stored bits, FAULT_TPB trials per
#                        bit (FAULT_TPB_UNPROT for the 3 unprotected flip-flops),
#                        classified and checked by fault/campaign_report.py
#   make fault-negctl    negative controls on an RTL copy without the copy
#                        comparator: the lane proofs and the campaign's
#                        no-escape checks must fail there
#   make fault-quick     a subset of the above (about 1 minute); in TEST_TARGETS
#
# Everything reads $(RTL) and writes under $(BUILD)/fault/, so
# `make RTL_DIR=<copy> BUILD=<dir> fault` checks a modified copy of the RTL.
# Sequential jobs; a k-induction task uses two solver processes.

FAULT_SRC           := fault
FAULT_OUT           := $(BUILD)/fault
FAULT_PY            ?= python3
FAULT_IVERILOG      ?= iverilog -g2005 -Wall -Wno-timescale
FAULT_TIMEOUT       ?= 1800
FAULT_PROVE_DEPTH   ?= 4
FAULT_SEED          ?= 1
FAULT_TPB           ?= 12
FAULT_TPB_UNPROT    ?= 200
FAULT_CONTROLS      ?= 20
FAULT_MIN_TPB       ?= 10
FAULT_MIN_TOTAL     ?= 5001
FAULT_SCENARIOS     ?= all
FAULT_QUICK_SCENARIOS ?= acc_a,res_b,therm_c1,neg_out_valid_q,neg_product
FAULT_QUICK_CAMPAIGN  ?= +tpb=2 +tpb_unprot=20 +controls=5
FAULT_QUICK_CHECK     ?= --min-tpb 2 --min-total 1000
FAULT_NEG_SCENARIOS   ?= acc_a,res_a
FAULT_NEG_CAMPAIGN    ?= +tpb=1 +tpb_unprot=4 +controls=5
FAULT_NEG_ESCAPE      ?= acc,res
FAULT_REPORT_DIR    ?= reports/fault
FAULT_PUBLISH       ?= $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),$(FAULT_REPORT_DIR))

FAULT_NEG_RTL        = $(addprefix $(FAULT_OUT)/negctl/rtl/,$(notdir $(RTL)))
FAULT_GEN            = $(FAULT_PY) $(FAULT_SRC)/gen_fault_copies.py --prove-depth $(FAULT_PROVE_DEPTH) \
                       --harness $(FAULT_SRC)/fi_harness.sv

# $(call FAULT_FORMAL_RUN,<rtl files>,<dir>,<scenarios>,<extra generator flags>)
# Regenerates the copies from scratch, then runs every task of every scenario.
define FAULT_FORMAL_RUN
	@rm -rf $(2)
	$(FAULT_GEN) --rtl $(1) --out $(2) --scenarios $(3) $(4)
	$(FAULT_PY) $(FAULT_SRC)/run_formal.py --dir $(2) --timeout $(FAULT_TIMEOUT) --out $(2)/results
endef

# $(call FAULT_CAMPAIGN_RUN,<rtl files>,<dir>,<plusargs>,<report flags>)
define FAULT_CAMPAIGN_RUN
	@mkdir -p $(2)
	$(FAULT_IVERILOG) -o $(2)/tb_seu_campaign.vvp $(FAULT_SRC)/tb_seu_campaign.v $(1)
	vvp -n $(2)/tb_seu_campaign.vvp +seed=$(FAULT_SEED) $(3) +out=$(2)/trials.tsv > $(2)/vvp.log 2>&1 || \
	    { tail -n 20 $(2)/vvp.log; exit 1; }
	@grep "^SEU_CAMPAIGN" $(2)/vvp.log || { tail -n 20 $(2)/vvp.log; exit 1; }
	$(FAULT_PY) $(FAULT_SRC)/campaign_report.py $(2)/trials.tsv --out $(2)/report $(4)
endef

.PHONY: fault fault-formal fault-campaign fault-negctl fault-quick

fault:
	@rc=0; \
	$(MAKE) --no-print-directory fault-formal || rc=1; \
	$(MAKE) --no-print-directory fault-campaign || rc=1; \
	$(MAKE) --no-print-directory fault-negctl || rc=1; \
	$(FAULT_PY) $(FAULT_SRC)/write_summary.py --build $(FAULT_OUT) --rtl $(RTL) --status $$rc \
	    --out $(FAULT_OUT)/summary.md $(if $(FAULT_PUBLISH),--publish $(FAULT_PUBLISH)) || rc=1; \
	if [ $$rc -ne 0 ]; then echo "[fault] FAILED: see $(FAULT_OUT)/summary.md"; exit 1; fi; \
	echo "[fault] all checks passed: see $(FAULT_OUT)/summary.md"

fault-formal:
	$(call FAULT_FORMAL_RUN,$(RTL),$(FAULT_OUT)/formal,$(FAULT_SCENARIOS),)

fault-campaign:
	$(call FAULT_CAMPAIGN_RUN,$(RTL),$(FAULT_OUT)/campaign,+tpb=$(FAULT_TPB) +tpb_unprot=$(FAULT_TPB_UNPROT) +controls=$(FAULT_CONTROLS),--min-tpb $(FAULT_MIN_TPB) --min-total $(FAULT_MIN_TOTAL))

fault-negctl:
	$(FAULT_GEN) --rtl $(RTL) --out $(FAULT_OUT)/negctl/rtl --write-mutant no_compare
	$(call FAULT_FORMAL_RUN,$(FAULT_NEG_RTL),$(FAULT_OUT)/negctl/formal,$(FAULT_NEG_SCENARIOS),--negctl)
	$(call FAULT_CAMPAIGN_RUN,$(FAULT_NEG_RTL),$(FAULT_OUT)/negctl/campaign,$(FAULT_NEG_CAMPAIGN),--min-tpb 1 --min-total 500 --expect-escape $(FAULT_NEG_ESCAPE))

# Separate work directories, so that fault-quick and fault can run in one `make -j`.
fault-quick:
	$(call FAULT_FORMAL_RUN,$(RTL),$(FAULT_OUT)/quick/formal,$(FAULT_QUICK_SCENARIOS),)
	$(call FAULT_CAMPAIGN_RUN,$(RTL),$(FAULT_OUT)/quick/campaign,$(FAULT_QUICK_CAMPAIGN),$(FAULT_QUICK_CHECK))
	@echo "[fault] fault-quick passed"

TEST_TARGETS += fault-quick
