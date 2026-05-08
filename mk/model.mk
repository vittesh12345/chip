# Concept arithmetic model (area: model): model/concept_budget.py recomputes
# every number the ORBIT-AI v0.1 brief publishes from its stated assumptions;
# model/test_concept_budget.py asserts them at the brief's printed precision.
# Owner: model area (model/, mk/model.mk, reports/model/). Standard library only.
#
#   make model          run the unit tests, then regenerate the report
#                       $(BUILD)/model/concept_budget.txt; the report is copied to
#                       reports/model/ only when RTL_DIR is the production rtl/.
#                       Part of TEST_TARGETS.
#
# The RTL is read only for LANES and the thermal thresholds (cross-check).
# MODEL_PD_SUMMARY: if this file states a closed clock, the demonstrator peak is
# given at that clock; otherwise the clock stays a parameter (MODEL_DEMO_MHZ).

MODEL_PY         ?= python3
MODEL_OUT        := $(BUILD)/model
MODEL_PD_SUMMARY ?= reports/pd/summary.md
MODEL_DEMO_MHZ   ?= 50 100 200
MODEL_PUBLISH    := $(if $(filter rtl rtl/ ./rtl,$(RTL_DIR)),reports/model)

.PHONY: model model-test model-report

model: model-test model-report

model-test:
	@mkdir -p $(MODEL_OUT)
	set -o pipefail; MODEL_RTL_DIR=$(RTL_DIR) $(MODEL_PY) model/test_concept_budget.py -v 2>&1 \
	    | tee $(MODEL_OUT)/test.log

model-report: model-test
	@mkdir -p $(MODEL_OUT)
	$(MODEL_PY) model/concept_budget.py --rtl-dir $(RTL_DIR) --pd-summary $(MODEL_PD_SUMMARY) \
	    $(foreach f,$(MODEL_DEMO_MHZ),--demo-clock-mhz $(f)) > $(MODEL_OUT)/concept_budget.txt
	@if [ -n "$(MODEL_PUBLISH)" ]; then \
	    mkdir -p $(MODEL_PUBLISH) && cp $(MODEL_OUT)/concept_budget.txt $(MODEL_OUT)/test.log $(MODEL_PUBLISH)/ \
	    && echo "model: wrote $(MODEL_PUBLISH)/concept_budget.txt"; \
	else \
	    echo "model: RTL_DIR=$(RTL_DIR) is not the production rtl/; report left in $(MODEL_OUT)"; \
	fi

TEST_TARGETS += model
