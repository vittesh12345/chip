# Supplementary queries (scratch, not a repo script). Same setup lines as
# pd/sta_corners.tcl: liberty, odb, sdc, propagated clock, SPEF.
read_liberty $::env(PD_LIB)
read_db $::env(PD_ODB)
read_sdc $::env(PD_SDC)
set_propagated_clock [all_clocks]
read_spef $::env(PD_SPEF)
puts "CORNER $::env(PD_CORNER) liberty [file tail $::env(PD_LIB)]"
foreach {name from to} {reg2reg all_registers all_registers in2reg all_inputs all_registers reg2out all_registers all_outputs in2out all_inputs all_outputs} {
  foreach dly {max min} {
    puts "=== $name $dly ==="
    report_checks -path_delay $dly -from [$from] -to [$to] -format end -digits 3
  }
}
puts "=== drv ==="
report_check_types -max_slew -max_capacitance -max_fanout -violators -digits 3
puts "=== setup violating endpoints ==="
report_checks -path_delay max -slack_max 0 -group_path_count 1000000 -endpoint_path_count 1 -format end -digits 3
puts "=== hold violating endpoints ==="
report_checks -path_delay min -slack_max 0 -group_path_count 1000000 -endpoint_path_count 1 -format end -digits 3
puts "=== end ==="
