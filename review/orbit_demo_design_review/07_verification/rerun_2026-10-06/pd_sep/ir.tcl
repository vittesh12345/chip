set R /home/user/chip/build/pd_sep/results/sky130hd/orbit_demo/sep
read_liberty /OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
read_db $R/6_final.odb
read_sdc $R/6_final.sdc
source /OpenROAD-flow-scripts/flow/platforms/sky130hd/setRC.tcl
read_spef $R/6_final.spef
set_pdnsim_net_voltage -net VDD -voltage 1.8
set_pdnsim_net_voltage -net VSS -voltage 0.0
analyze_power_grid -net VDD -enable_em -em_outfile /tmp/claude-0/-home-user-chip/6bdc94fa-7275-51e9-a492-50b01aa47cf0/scratchpad/review_work/pd_sep/sta/em_vdd.rpt
analyze_power_grid -net VSS -enable_em -em_outfile /tmp/claude-0/-home-user-chip/6bdc94fa-7275-51e9-a492-50b01aa47cf0/scratchpad/review_work/pd_sep/sta/em_vss.rpt
