#!/usr/bin/env bash
# Regenerate the 03_schematics views exactly as they were made for this package (2026-10-06).
# Run from the repository root (a checkout at the package commit) with Yosys 0.69+154
# (/opt/eda/oss-cad-suite/bin) and Graphviz dot on PATH. Gate-level views need the ORFS
# sep run outputs under build/pd_sep/ (gitignored; regenerate with make pd-sep).
set -euo pipefail
OUT=${1:-review/orbit_demo_design_review/03_schematics}
RTL="rtl/orbit_keep_reg.v rtl/orbit_mac_lane.v rtl/orbit_thermal_tmr.v rtl/orbit_demo.v"

# RTL level: one sheet per module, hierarchy kept (sub-instances drawn as boxes).
for M in orbit_keep_reg orbit_mac_lane orbit_thermal_tmr orbit_demo; do
  yosys -q -p "read_verilog -sv $RTL; hierarchy -top $M; proc; opt -purge; clean; \
    show -format dot -prefix $OUT/rtl_level/$M.rtl_schematic -width -signed -stretch -colors 1 $M; \
    write_json $OUT/rtl_level/$M.rtl.json"
  dot -Tpdf $OUT/rtl_level/$M.rtl_schematic.dot -o $OUT/rtl_level/$M.rtl_schematic.pdf
  dot -Tsvg $OUT/rtl_level/$M.rtl_schematic.dot -o $OUT/rtl_level/$M.rtl_schematic.svg
done

# Gate level: the two kept orbit_keep_reg parameterisations in the ORFS synthesized netlist
# (sky130_fd_sc_hd cells, before placement/resizing).
cat > /tmp/gl.ys <<YS
read_liberty -lib build/pd_sep/platform/cells.lib
read_verilog build/pd_sep/results/sky130hd/orbit_demo/sep/1_2_yosys.v
hierarchy -top orbit_demo
show -format dot -prefix $OUT/gate_level/orbit_keep_reg_W2_thermal_copy_gate_schematic -width -stretch *RESET_VAL=2'10
show -format dot -prefix $OUT/gate_level/orbit_keep_reg_W32_acc_res_copy_gate_schematic -width -stretch *W=s32'00000000000000000000000000100000
YS
yosys -q -s /tmp/gl.ys
for f in $OUT/gate_level/*.dot; do dot -Tpdf "$f" -o "${f%.dot}.pdf"; dot -Tsvg "$f" -o "${f%.dot}.svg"; done
