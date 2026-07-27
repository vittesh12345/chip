# 3D layout viewer for the routed orbit_demo die (area: viz).
#
#   make viz           GDS/DEF -> viz/layout.json + viz/layout.b64.txt (the
#                      publishable page data), the GLBs in reports/viz/
#                      (portable metals + parts, and the detailed all-layer
#                      Draco GLB) and reports/viz/redundancy_placement.md
#   make viz-shots     re-render the page screenshots and GLB previews into reports/viz/
#   make viz-serve     serve the page locally (http://localhost:$(VIZ_PORT)/)
#   make viz-gcd       development data: stock ORFS sky130hd gcd run
#
# Inputs default to the copy-separated run of the pdsep area
# ($(BUILD)/pd_sep/results/sky130hd/orbit_demo/sep/6_final.{gds,def}); if it
# does not exist, the pd area's baseline run ($(BUILD)/pd/results/.../base/).
# The baseline DEF is also read for the before/after copy distances.
# Override with VIZ_GDS=... VIZ_DEF=... ; VIZ_FLAGS passes extra options to
# scripts/viz_gds_to_3d.py (e.g. --write-bin for a raw layout.bin, --glb-core).
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
VIZ_NODE_DIR     ?= $(VIZ_BUILD)/node
VIZ_GLTF_TRANSFORM ?= $(VIZ_NODE_DIR)/node_modules/.bin/gltf-transform
VIZ_OUT          ?= viz
VIZ_REPORTS      ?= reports/viz
VIZ_PORT         ?= 8765
VIZ_THREADS      ?= 1
VIZ_FLAGS        ?=

# Separated (fenced) run first, baseline as the fallback. Recursive
# variables: only evaluated when a viz target runs.
VIZ_SEP_DIR      ?= $(BUILD)/pd_sep/results/$(VIZ_PLATFORM)/$(VIZ_DESIGN)/sep
VIZ_BASE_DIR     ?= $(BUILD)/pd/results/$(VIZ_PLATFORM)/$(VIZ_DESIGN)/base
VIZ_GDS ?= $(or $(wildcard $(VIZ_SEP_DIR)/6_final.gds),$(wildcard $(VIZ_BASE_DIR)/6_final.gds))
VIZ_DEF ?= $(patsubst %.gds,%.def,$(VIZ_GDS))
VIZ_BASELINE_DEF ?= $(wildcard $(VIZ_BASE_DIR)/6_final.def)
VIZ_PD_CONFIG ?= $(if $(findstring pd_sep,$(VIZ_GDS)),pd/$(VIZ_PLATFORM)_sep/config.mk,pd/$(VIZ_PLATFORM)/config.mk)
VIZ_REGIONS_JSON ?= $(wildcard reports/pdsep/regions.json)
# Design stats: the first of these that exists.
VIZ_PD_SUMMARY ?= $(if $(findstring pd_sep,$(VIZ_GDS)),reports/pdsep/summary.md,reports/pd/summary.md,reports/pd/$(VIZ_PLATFORM)/results.md)

VIZ_PLATFORM_FILES := $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd.tlef

.PHONY: viz viz-shots viz-serve viz-venv viz-platform viz-node viz-gcd viz-clean

$(VIZ_PY):
	python3 -m venv $(VIZ_VENV)
	$(VIZ_VENV)/bin/pip install -q -r viz/requirements.txt

viz-venv: $(VIZ_PY)

# @gltf-transform/cli (Draco compression of the detailed GLB), from npm.
$(VIZ_GLTF_TRANSFORM):
	mkdir -p $(VIZ_NODE_DIR)
	cd $(VIZ_NODE_DIR) && npm install --no-audit --no-fund --silent @gltf-transform/cli@4.5.1

viz-node: $(VIZ_GLTF_TRANSFORM)

$(VIZ_PLATFORM_FILES):
	mkdir -p $(VIZ_PLATFORM_DIR)
	docker run --rm -v $(abspath $(VIZ_PLATFORM_DIR)):/out $(VIZ_ORFS_IMAGE) bash -c \
	  'p=/OpenROAD-flow-scripts/flow/platforms/$(VIZ_PLATFORM); \
	   cp $$p/lef/sky130_fd_sc_hd.tlef $$p/lef/sky130_fd_sc_hd_merged.lef \
	      $$p/sky130hd.lyt $$p/sky130hd.lyp /out/ && chmod a+r /out/*'

viz-platform: $(VIZ_PLATFORM_FILES)

viz: $(VIZ_PY) $(VIZ_PLATFORM_FILES) $(VIZ_GLTF_TRANSFORM)
	@if [ -z "$(VIZ_GDS)" ] || [ ! -f "$(VIZ_GDS)" ]; then \
	  echo "viz: no routed GDS found ($(VIZ_SEP_DIR) or $(VIZ_BASE_DIR)); run the pd flow first or pass VIZ_GDS=... VIZ_DEF=..."; exit 1; fi
	@if [ ! -f "$(VIZ_DEF)" ]; then echo "viz: DEF $(VIZ_DEF) not found (pass VIZ_DEF=...)"; exit 1; fi
	@case "$(VIZ_GDS)" in *pd_sep*) ;; *) echo "viz: NOTE: the separated run was not found; using $(VIZ_GDS)";; esac
	mkdir -p $(VIZ_OUT) $(VIZ_REPORTS)
	OMP_NUM_THREADS=$(VIZ_THREADS) $(VIZ_PY) scripts/viz_gds_to_3d.py \
	  --gds $(VIZ_GDS) --def $(VIZ_DEF) \
	  --tech-lef $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd.tlef \
	  --cell-lef $(VIZ_PLATFORM_DIR)/sky130_fd_sc_hd_merged.lef \
	  --lyt $(VIZ_PLATFORM_DIR)/sky130hd.lyt \
	  --pd-summary $(VIZ_PD_SUMMARY) --pd-config $(VIZ_PD_CONFIG) \
	  $(if $(VIZ_REGIONS_JSON),--regions-json $(VIZ_REGIONS_JSON)) \
	  $(if $(and $(VIZ_BASELINE_DEF),$(filter-out $(VIZ_BASELINE_DEF),$(VIZ_DEF))),--baseline-def $(VIZ_BASELINE_DEF)) \
	  --out-dir $(VIZ_OUT) \
	  --glb $(VIZ_REPORTS)/$(VIZ_DESIGN)_$(VIZ_PLATFORM)_3d.glb \
	  --glb-full $(VIZ_REPORTS)/$(VIZ_DESIGN)_$(VIZ_PLATFORM)_3d_full.glb \
	  --gltf-transform $(VIZ_GLTF_TRANSFORM) \
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
