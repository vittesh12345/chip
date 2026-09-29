# ORBIT-AI demonstrator timing constraints for the ORFS sky130hd flow.
#
# One clock, clk. All other inputs and all outputs are constrained against it
# with a fixed fraction of the period for the (unknown) outside world, as the
# ORFS example designs do. The documented combinational path
# out_ready -> in_ready (SPEC section 4) is timed as an in-to-out path.
#
# scripts/run_pd.sh rewrites the "set clk_period" line (and nothing else) to
# sweep the period; the value below is the committed default. Keep the line in
# this exact form: ORFS also scrapes it for the ABC delay target.
#
# 7.0 ns (142.9 MHz) is the shortest period of the sweep in
# reports/pd/period_sweep_sky130hd.md that closes setup and hold at the ORFS
# sky130hd corner (TT 25C 1.80V); 6.0 ns fails.

set clk_period 7
set clk_io_pct 0.2

set clk_port [get_ports clk]
create_clock -name clk -period $clk_period $clk_port

set non_clock_inputs [all_inputs -no_clocks]
set_input_delay  [expr {$clk_period * $clk_io_pct}] -clock clk $non_clock_inputs
set_output_delay [expr {$clk_period * $clk_io_pct}] -clock clk [all_outputs]
