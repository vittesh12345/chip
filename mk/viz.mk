# 3D layout viewer for the routed orbit_demo die (area: viz).
#
#   make viz           GDS/DEF -> viz/layout.bin + viz/layout.json,
#                      reports/viz/orbit_demo_sky130hd_3d.glb and
#                      reports/viz/redundancy_placement.md
#   make viz-shots     re-render the page screenshots into reports/viz/
#   make viz-serve     serve the page locally (http://localhost:$(VIZ_PORT)/)
#   make viz-gcd       development data: stock ORFS sky130hd gcd run
#
# Inputs default to the pd area's production run of orbit_demo (variant base),
# else the newest routed variant under $(BUILD)/pd/results (written by the pd
# area, only read here). Override with VIZ_GDS=... VIZ_DEF=...
# VIZ_FLAGS passes extra options to scripts/viz_gds_to_3d.py (e.g. --glb-core).
# The platform LEF/layer files are copied once out of the ORFS image into
# $(VIZ_PLATFORM_DIR); the viewer never needs the container at view time.
# Not part of TEST_TARGETS.

VIZ_DESIGN       ?= orbit_demo
VIZ_PLATFORM     ?= sky130hd
VIZ_ORFS_IMAGE   ?= openroad/orfs:latest
VIZ_BUILD        ?= $(BUILD)/viz
VIZ_VENV         ?= $(VIZ_BUILD)/venv
VIZ_PY           ?= $(VIZ_VENV)/bin/python
VIZ_PLATFORM_DIR ?= $(VIZ_BUILD)/platform
VIZ_PD_DIR       ?= $(BUILD)/pd
VIZ_OUT          ?= viz
VIZ_REPORTS      ?= reports/viz
VIZ_PORT         ?= 8765
VIZ_THREADS      ?= 1
VIZ_FLAGS        ?=

# Final GDS/DEF of $(VIZ_DESIGN): the production pd variant ($(VIZ_PD_VARIANT),
# the pd area's PD_VARIANT default) if it exists, else the newest variant under
# $(VIZ_PD_DIR)/results (sweep and negative-control runs live elsewhere and are
# never picked). Recursive variables: only evaluated when a viz target runs.
VIZ_PD_VARIANT ?= base
viz_newest = $(shell find $(1) -path '*/$(VIZ_PLATFORM)/$(VIZ_DESIGN)/*' -name '$(2)' \
               -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)
viz_prod_gds = $(VIZ_PD_DIR)/results/$(VIZ_PLATFORM)/$(VIZ_DESIGN)/$(VIZ_PD_VARIANT)/6_final.gds
VIZ_GDS ?= $(or $(wildcard $(viz_prod_gds)),$(call viz_newest,$(VIZ_PD_DIR)/results,6_final.gds))
VIZ_DEF ?= $(patsubst %.gds,%.def,$(VIZ_GDS))
# Design stats: the first of these that exists (written by the pd area).
VIZ_PD_SUMMARY ?= reports/pd/summary.md,reports/pd/$(VIZ_PLATFORM)/results.md

# One target stands for the whole copied set (tlef, merged cell LEF, .lyt, .lyp).
VIZ_PLATFORM_FILES := $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd.tlef

.PHONY: viz viz-shots viz-serve viz-venv viz-platform viz-gcd viz-clean

$(VIZ_PY):
	python3 -m venv $(VIZ_VENV)
	$(VIZ_VENV)/bin/pip install -q -r viz/requirements.txt

viz-venv: $(VIZ_PY)

$(VIZ_PLATFORM_FILES):
	mkdir -p $(VIZ_PLATFORM_DIR)
	docker run --rm -v $(abspath $(VIZ_PLATFORM_DIR)):/out $(VIZ_ORFS_IMAGE) bash -c \
	  'p=/OpenROAD-flow-scripts/flow/platforms/$(VIZ_PLATFORM); \
	   cp $$p/lef/sky130_fd_sc_hd.tlef $$p/lef/sky130_fd_sc_hd_merged.lef \
	      $$p/sky130hd.lyt $$p/sky130hd.lyp /out/ && chmod a+r /out/*'

viz-platform: $(VIZ_PLATFORM_FILES)

viz: $(VIZ_PY) $(VIZ_PLATFORM_FILES)
	@if [ -z "$(VIZ_GDS)" ] || [ ! -f "$(VIZ_GDS)" ]; then \
	  echo "viz: no routed GDS found under $(VIZ_PD_DIR)/results (run 'make pd' first, or pass VIZ_GDS=... VIZ_DEF=...)"; exit 1; fi
	@if [ ! -f "$(VIZ_DEF)" ]; then echo "viz: DEF $(VIZ_DEF) not found (pass VIZ_DEF=...)"; exit 1; fi
	mkdir -p $(VIZ_OUT) $(VIZ_REPORTS)
	OMP_NUM_THREADS=$(VIZ_THREADS) $(VIZ_PY) scripts/viz_gds_to_3d.py \
	  --gds $(VIZ_GDS) --def $(VIZ_DEF) \
	  --tech-lef $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd.tlef \
	  --cell-lef $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd_merged.lef \
	  --lyt $(VIZ_PLATFORM_DIR)/sky130hd.lyt \
	  --pd-summary $(VIZ_PD_SUMMARY) --pd-config pd/$(VIZ_PLATFORM)/config.mk \
	  --out-dir $(VIZ_OUT) \
	  --glb $(VIZ_REPORTS)/$(VIZ_DESIGN)_$(VIZ_PLATFORM)_3d.glb \
	  --redundancy-report $(VIZ_REPORTS)/redundancy_placement.md $(VIZ_FLAGS)

viz-shots: $(VIZ_PY)
	$(VIZ_PY) scripts/viz_shots.py --page-dir $(VIZ_OUT) --out-dir $(VIZ_REPORTS) \
	  --site-dir $(VIZ_BUILD)/site

viz-serve: $(VIZ_PY)
	$(VIZ_PY) scripts/viz_shots.py --page-dir $(VIZ_OUT) --site-dir $(VIZ_BUILD)/site \
	  --serve --port $(VIZ_PORT)

# Development data only: the stock ORFS sky130hd gcd design, routed into
# $(VIZ_BUILD)/gcd_run (never into the pd area).
viz-gcd:
	mkdir -p $(VIZ_BUILD)/gcd_run
	docker run --rm -v $(abspath $(VIZ_BUILD))/gcd_run:/work $(VIZ_ORFS_IMAGE) bash -c \
	  'source /OpenROAD-flow-scripts/env.sh >/dev/null && cd /OpenROAD-flow-scripts/flow && \
	   make DESIGN_CONFIG=designs/sky130hd/gcd/config.mk WORK_HOME=/work NUM_CORES=$(VIZ_THREADS)'

viz-clean:
	rm -rf $(VIZ_BUILD)/site $(VIZ_BUILD)/gcd_run
