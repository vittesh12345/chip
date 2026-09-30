# Mutation testing (area: mutation): tests the tests. Owner: mutation area
# (scripts/mutation_test.py, mk/mutation.mk, reports/mutation/).
#
#   make mutation          generate the single-point mutants of $(RTL) listed in
#                          scripts/mutation_test.py under $(BUILD)/mutation/m<NN>/rtl,
#                          check that the unmodified copy passes every target, run
#                          MUTATION_TARGETS on every mutant (MUTATION_JOBS mutants in
#                          parallel), run MUTATION_EXTRA_TARGETS on the survivors, and
#                          write $(BUILD)/mutation/summary.md (kill matrix, score,
#                          analysis of every survivor). Slow (about 65 minutes); NOT in
#                          TEST_TARGETS. For the production RTL the summary and
#                          results.json are copied to reports/mutation/.
#                          Fails if a mutant pattern is stale, the baseline fails, or a
#                          survivor has no written analysis. Surviving mutants are an
#                          expected result (reported), not a failure.
#                          The evidence bench MUTATION_GAP_BENCH (checks the suite lacks)
#                          is then run on $(RTL) (must PASS) and on every survivor.
#   make mutation-gaps     the same with --resume: reuses finished runs, so after a
#                          complete `make mutation` it only reruns the evidence bench
#                          and rewrites the summary
#   make mutation-list     list the mutants
#   make mutation-report   rewrite the summary from an existing results.json
#
# Resume an interrupted run with MUTATION_FLAGS=--resume; run a subset with
# MUTATION_FLAGS=--only=name1,name2.

MUTATION_OUT        := $(BUILD)/mutation
MUTATION_PY         ?= python3
MUTATION_TARGETS    ?= lint sim formal-quick fault-quick synth
MUTATION_EXTRA_TARGETS ?= formal
MUTATION_JOBS       ?= 2
MUTATION_TIMEOUT    ?= 3600
MUTATION_FLAGS      ?=
MUTATION_GAP_BENCH  ?= reports/mutation/tb_mutation_gaps.v
MUTATION_REPORT_DIR ?= reports/mutation
MUTATION_PUBLISH    ?= $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),$(MUTATION_REPORT_DIR))

MUTATION_RUN = $(MUTATION_PY) scripts/mutation_test.py --rtl-dir $(RTL_DIR) --out $(MUTATION_OUT) \
               --targets "$(MUTATION_TARGETS)" --extra-targets "$(MUTATION_EXTRA_TARGETS)" \
               --jobs $(MUTATION_JOBS) --timeout $(MUTATION_TIMEOUT) \
               --gap-bench $(MUTATION_GAP_BENCH)

# $(call MUTATION_COPY_OUT): publish summary and results for the production RTL.
define MUTATION_COPY_OUT
	@if [ -n "$(MUTATION_PUBLISH)" ]; then \
	    mkdir -p $(MUTATION_PUBLISH) && \
	    cp $(MUTATION_OUT)/summary.md $(MUTATION_PUBLISH)/summary.md && \
	    cp $(MUTATION_OUT)/results.json $(MUTATION_PUBLISH)/results.json && \
	    echo "[mutation] copied summary.md and results.json to $(MUTATION_PUBLISH)/"; \
	fi
endef

.PHONY: mutation mutation-gaps mutation-list mutation-report

mutation:
	@mkdir -p $(MUTATION_OUT)
	set -o pipefail; $(MUTATION_RUN) $(MUTATION_FLAGS) 2>&1 | tee $(MUTATION_OUT)/run.log
	$(MUTATION_COPY_OUT)

mutation-gaps:
	@mkdir -p $(MUTATION_OUT)
	set -o pipefail; $(MUTATION_RUN) --resume $(MUTATION_FLAGS) 2>&1 | tee $(MUTATION_OUT)/run_gaps.log
	$(MUTATION_COPY_OUT)

mutation-list:
	@$(MUTATION_PY) scripts/mutation_test.py --list

mutation-report:
	$(MUTATION_RUN) --report-only
	$(MUTATION_COPY_OUT)
