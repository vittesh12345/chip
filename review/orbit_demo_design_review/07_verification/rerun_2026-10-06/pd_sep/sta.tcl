set R /home/user/chip/build/pd_sep/results/sky130hd/orbit_demo/sep
read_liberty /OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
read_db $R/6_final.odb
read_sdc $R/6_final.sdc
source /OpenROAD-flow-scripts/flow/platforms/sky130hd/setRC.tcl
read_spef $R/6_final.spef
puts "STA_NOW setup_wns [sta::worst_slack -max] hold_wns [sta::worst_slack -min]"
report_tns
report_wns
report_worst_slack -max
report_worst_slack -min
report_clock_min_period
report_clock_min_period -include_port_paths
report_check_types -max_slew -max_capacitance -max_fanout -violators
report_power
