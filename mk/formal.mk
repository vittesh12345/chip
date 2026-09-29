# Formal verification of the fault-free orbit_demo with SymbiYosys.
# Owner: formal area (formal/, mk/formal.mk, reports/formal/).
#
#   make formal          every proof, liveness and cover task (about a minute);
#                        writes $(BUILD)/formal/summary.md
#   make formal-quick    k-induction proofs, product lemma and covers (< 1 minute);
#                        separate work directory, writes $(BUILD)/formal/summary_quick.md
#   make formal-vacuity  the proofs must FAIL on deliberately broken copies of the RTL
#   make formal-extra    slow exploratory job datapath_pdr (P1/P8 by abc pdr without
#                        helper invariants); not part of `formal`
#   make formal-report   formal-vacuity + formal, then refresh $(FORMAL_REPORT_DIR)/
#                        (includes the formal-extra result if it exists)
#   make formal-<task>   one task, e.g. formal-datapath (task list: formal/orbit_demo.sby)
#
# Everything runs against $(RTL), so `make RTL_DIR=<copy> BUILD=<dir> formal`
# checks a modified copy. Tasks run one after another; each uses at most two
# solver processes (k-induction runs base case and induction step in parallel).

FORMAL_SRC         := formal
FORMAL_OUT         := $(BUILD)/formal
FORMAL_SBY_TMPL    := $(FORMAL_SRC)/orbit_demo.sby
FORMAL_TB          := $(FORMAL_SRC)/orbit_demo_fv.sv
FORMAL_TIMEOUT     ?= 1800
FORMAL_VAC_TIMEOUT ?= 900
FORMAL_REPORT_DIR  ?= reports/formal

# Work directories: `formal`, `formal-extra` and formal-<task> share one,
# `formal-quick` has its own so that both can run in one `make -j test`.
FORMAL_FULL_DIR    := $(FORMAL_OUT)/full
FORMAL_QUICK_DIR   := $(FORMAL_OUT)/quick

FORMAL_PROVE_TASKS := thermal dup handshake datapath product
FORMAL_PDR_TASKS   := thermal_pdr dup_pdr handshake_pdr
FORMAL_LIVE_TASKS  := live
FORMAL_COVER_TASKS := cover wrap
FORMAL_TASKS       := $(FORMAL_PROVE_TASKS) $(FORMAL_PDR_TASKS) $(FORMAL_LIVE_TASKS) $(FORMAL_COVER_TASKS)
FORMAL_QUICK_TASKS := $(FORMAL_PROVE_TASKS) $(FORMAL_COVER_TASKS)
FORMAL_EXTRA_TASKS := datapath_pdr

# $(call FORMAL_GEN,<dir>): write <dir>/orbit_demo.sby for $(RTL). Regenerated
# in every recipe so that a different RTL_DIR never reuses a stale file.
FORMAL_GEN       = bash $(FORMAL_SRC)/gen_sby.sh $(FORMAL_SBY_TMPL) $(1)/orbit_demo.sby $(FORMAL_TB) $(RTL)
# $(call FORMAL_RUN_TASK,<dir>,<task>,<PASS|FAIL>)
FORMAL_RUN_TASK  = bash $(FORMAL_SRC)/run_task.sh $(abspath $(1))/orbit_demo.sby $(abspath $(1))/run \
                   $(2) $(3) $(FORMAL_TIMEOUT)
# $(call FORMAL_SUMMARIZE,<dir>)
FORMAL_SUMMARIZE = python3 $(FORMAL_SRC)/summarize.py --run $(1)/run --rtl-dir $(RTL_DIR) \
                   --optional-tasks "$(FORMAL_EXTRA_TASKS)"
# Logs copied into the report directory drop solver progress lines and the
# per-bit "undriven input treated as $anyseq" notes (the harness inputs are
# free on purpose; sby's one-line total is kept), and shorten the work path.
FORMAL_LOG_NOISE = engine_0: +[0-9]+ :|Checking (assumptions|assertions) in step|Frame +Clauses|Starting new anytime pass|\] Copy '|Treating undriven bit
FORMAL_LOG_TRIM  = grep -v -E "$(FORMAL_LOG_NOISE)" | sed -E 's|\[[^]]*/orbit_demo_([a-z_]+)\]|[\1]|'

# $(call FORMAL_RUN_SET,<tasks>,<dir>,<summary.md>): run the tasks in sequence,
# summarize, and fail unless every task ended with PASS.
define FORMAL_RUN_SET
	@$(call FORMAL_GEN,$(2))
	@fail=0; \
	for t in $(1); do $(call FORMAL_RUN_TASK,$(2),$$t,PASS) || fail=1; done; \
	$(call FORMAL_SUMMARIZE,$(2)) --tasks "$(1)" -o $(3); \
	if [ $$fail -ne 0 ]; then echo "[formal] FAILED: see $(3)"; exit 1; fi; \
	echo "[formal] all $(words $(1)) tasks passed: see $(3)"
endef

.PHONY: formal formal-quick formal-extra formal-vacuity formal-report \
        $(addprefix formal-,$(FORMAL_TASKS) $(FORMAL_EXTRA_TASKS))

formal:
	$(call FORMAL_RUN_SET,$(FORMAL_TASKS),$(FORMAL_FULL_DIR),$(FORMAL_OUT)/summary.md)

formal-quick:
	$(call FORMAL_RUN_SET,$(FORMAL_QUICK_TASKS),$(FORMAL_QUICK_DIR),$(FORMAL_OUT)/summary_quick.md)

formal-extra:
	$(call FORMAL_RUN_SET,$(FORMAL_EXTRA_TASKS),$(FORMAL_FULL_DIR),$(FORMAL_OUT)/summary_extra.md)

$(addprefix formal-,$(FORMAL_TASKS) $(FORMAL_EXTRA_TASKS)): formal-%:
	@$(call FORMAL_GEN,$(FORMAL_FULL_DIR))
	@$(call FORMAL_RUN_TASK,$(FORMAL_FULL_DIR),$*,PASS)

formal-vacuity:
	@bash $(FORMAL_SRC)/vacuity.sh $(FORMAL_OUT)/vacuity $(FORMAL_SBY_TMPL) $(FORMAL_TB) \
	    $(FORMAL_VAC_TIMEOUT) $(RTL)

formal-report:
	@$(MAKE) --no-print-directory formal-vacuity
	@$(MAKE) --no-print-directory formal
	@rm -rf $(FORMAL_REPORT_DIR)/logs && mkdir -p $(FORMAL_REPORT_DIR)/logs
	@$(call FORMAL_SUMMARIZE,$(FORMAL_FULL_DIR)) --tasks "$(FORMAL_TASKS)" \
	    --vacuity $(FORMAL_OUT)/vacuity/vacuity.tsv -o $(FORMAL_REPORT_DIR)/summary.md
	@cp $(FORMAL_OUT)/vacuity/vacuity.md $(FORMAL_REPORT_DIR)/vacuity.md
	@for t in $(FORMAL_TASKS) $(FORMAL_EXTRA_TASKS); do \
	    f=$(FORMAL_FULL_DIR)/run/orbit_demo_$$t/logfile.txt; \
	    if [ -f $$f ]; then cat $$f | $(FORMAL_LOG_TRIM) > $(FORMAL_REPORT_DIR)/logs/$$t.log; fi; \
	done
	@for d in $(FORMAL_OUT)/vacuity/*/; do \
	    m=$$(basename $$d); \
	    { cat $$d/mutation.diff; echo; cat $$d/result.txt; echo; \
	      cat $$d/run/orbit_demo_*/logfile.txt | $(FORMAL_LOG_TRIM); } \
	        > $(FORMAL_REPORT_DIR)/logs/vacuity_$$m.log 2>/dev/null || true; \
	done
	@echo "[formal] report written to $(FORMAL_REPORT_DIR)/"

TEST_TARGETS += formal-quick formal
