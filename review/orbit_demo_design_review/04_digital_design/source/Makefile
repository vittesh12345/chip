# ORBIT-AI 4-lane INT8 demonstrator: top-level build.
#
# Each area adds its own targets in mk/<area>.mk and appends fast, self-checking
# targets to TEST_TARGETS. `make test` runs all of them.
#
# RTL_DIR can point at a modified copy of rtl/ (fault or mutation experiments);
# production runs use rtl/.

SHELL := /bin/bash
.DEFAULT_GOAL := help

OSS_CAD ?= /opt/eda/oss-cad-suite
export PATH := $(OSS_CAD)/bin:$(PATH)

RTL_DIR ?= rtl
RTL     := $(RTL_DIR)/orbit_keep_reg.v $(RTL_DIR)/orbit_mac_lane.v \
           $(RTL_DIR)/orbit_thermal_tmr.v $(RTL_DIR)/orbit_demo.v
TOP     := orbit_demo
BUILD   ?= build

TEST_TARGETS :=

.PHONY: help lint test clean

help:
	@echo "make lint     Verilator -Wall lint of the RTL"
	@echo "make test     every fast self-checking target: $(TEST_TARGETS)"
	@echo "make clean    remove $(BUILD)/"
	@echo "See README.md for the area targets (sim, formal, fault, synth, pd, model, ecc)."

lint:
	verilator --lint-only -Wall --top-module $(TOP) $(RTL)

include $(sort $(wildcard mk/*.mk))

test: lint $(TEST_TARGETS)
	@echo "ALL TEST TARGETS PASSED: lint $(TEST_TARGETS)"

clean:
	rm -rf $(BUILD)
