# Write the gate-level netlist of an OpenROAD database as flat Verilog.
# Used by `make pd-negctl` on the synthesis database (1_synth.odb), so the
# storage audit reads the same kind of flat netlist on every platform (the
# ORFS 1_synth_lec.v can have standard cells stripped for LEC on some
# platforms). Environment: PD_ODB (input), PD_NETLIST (output).
read_db $::env(PD_ODB)
write_verilog $::env(PD_NETLIST)
