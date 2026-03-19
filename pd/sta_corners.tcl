# Static timing of the routed orbit_demo at one liberty corner (OpenROAD's
# OpenSTA). Run once per corner by `make pd-corners`.
#
# ORFS closes sky130hd timing at its single TT 25C 1.80V liberty. Re-timing
# the final routed database with other sky130_fd_sc_hd corner libraries shows
# how much margin (or deficit) the TT closure leaves. Information only: the
# design was not optimised for these corners.
#
# Parasitics: the ORFS OpenRCX SPEF (nominal extraction rules) is used for
# every corner; no RC corners are modelled.
#
# Environment: PD_CORNER (name), PD_LIB (liberty), PD_ODB, PD_SDC, PD_SPEF.

read_liberty $::env(PD_LIB)
read_db $::env(PD_ODB)
read_sdc $::env(PD_SDC)
set_propagated_clock [all_clocks]
read_spef $::env(PD_SPEF)

puts "CORNER $::env(PD_CORNER) liberty [file tail $::env(PD_LIB)]"
report_worst_slack -max -digits 3
report_tns -max -digits 3
report_worst_slack -min -digits 3
report_tns -min -digits 3
report_clock_min_period -include_port_paths
puts "=== worst setup path ==="
report_checks -path_delay max -format full_clock_expanded -digits 3
puts "=== worst hold path ==="
report_checks -path_delay min -format full_clock_expanded -digits 3
