# 3D layout viewer for the routed orbit_demo die (area: viz).
#
#   make viz           GDS/DEF -> viz/layout.bin + viz/layout.json,
#                      reports/viz/orbit_demo_sky130hd_3d.glb and
#                      reports/viz/redundancy_placement.md
#   make viz-shots     re-render the page screenshots into reports/viz/
#   make viz-serve     serve the page locally (http://localhost:$(VIZ_PORT)/)
#   make viz-gcd       development data: stock ORFS sky130hd gcd run
#
# Inputs default to the newest routed orbit_demo under $(BUILD)/pd (written by
# the pd area, never by this file). Override with VIZ_GDS=... VIZ_DEF=...
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

# Newest final GDS/DEF of $(VIZ_DESIGN) under the pd area (lazy: only
# evaluated when a viz target runs).
viz_newest = $(shell find $(1) -path '*/$(VIZ_PLATFORM)/$(VIZ_DESIGN)/*' -name '$(2)' \
               -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)
VIZ_GDS ?= $(call viz_newest,$(VIZ_PD_DIR)/results,6_final.gds)
VIZ_DEF ?= $(patsubst %.gds,%.def,$(VIZ_GDS))

VIZ_PLATFORM_FILES := $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd.tlef \
                      $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd_merged.lef \
                      $(VIZ_PLATFORM_DIR)/sky130hd.lyt

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
	  --pd-summary reports/pd/summary.md \
	  --out-dir $(VIZ_OUT) \
	  --glb $(VIZ_REPORTS)/$(VIZ_DESIGN)_$(VIZ_PLATFORM)_3d.glb \
	  --redundancy-report $(VIZ_REPORTS)/redundancy_placement.md

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
