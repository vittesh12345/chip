# Empirical test of the placement-fence mechanism used by pd/sky130hd_sep.
#
# Run with OpenROAD inside the ORFS image (see mk/pdsep.mk, pd-sep-mechanism):
#   PDSEP_IN_ODB=<baseline 3_2_place_iop.odb> PDSEP_IN_SDC=<2_floorplan.sdc>
#   REPORTS_DIR=<dir> openroad -no_init -threads 2 -exit scripts/pdsep_mechanism_test.tcl
#
# Starts from the UNCONSTRAINED baseline database after pin placement, adds
# the fences with pd/sky130hd_sep/regions.tcl, then runs the placement steps
# of the ORFS flow and measures after each step whether every group member
# is inside its fence and every non-member outside:
#   1. global_placement (same arguments as the ORFS place step),
#   2. detailed_placement,
#   3. improve_placement (ORFS ENABLE_DPO), on a copy of the legal result,
#   4. a forced violation: one copy-A flip-flop is moved into the copy-B fence
#      and detailed_placement is run again.
# Every result line starts with MECH.

set plat /OpenROAD-flow-scripts/flow/platforms/sky130hd
set repo [file normalize [file join [file dirname [info script]] ..]]
read_liberty $plat/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
read_db $::env(PDSEP_IN_ODB)
read_sdc $::env(PDSEP_IN_SDC)
source $plat/setRC.tcl

source $repo/pd/sky130hd_sep/regions.tcl

proc mech_measure {tag} {
  set block [ord::get_db_block]
  set in 0; set out 0; set full 0; set strad 0
  foreach inst [$block getInsts] {
    set g [$inst getGroup]
    set bb [$inst getBBox]
    if {$g ne "NULL" && $g ne ""} {
      set ok 0
      foreach b [[$g getRegion] getBoundaries] {
        if {[$bb xMin] >= [$b xMin] && [$bb xMax] <= [$b xMax] && [$bb yMin] >= [$b yMin] && [$bb yMax] <= [$b yMax]} { set ok 1 }
      }
      if {$ok} { incr in } else { incr out }
    } else {
      if {[[$inst getMaster] getType] ne "CORE" || [$inst isFixed]} continue
      foreach r [$block getRegions] {
        foreach b [$r getBoundaries] {
          if {[$bb xMin] < [$b xMax] && [$bb xMax] > [$b xMin] && [$bb yMin] < [$b yMax] && [$bb yMax] > [$b yMin]} {
            if {[$bb xMin] >= [$b xMin] && [$bb xMax] <= [$b xMax] && [$bb yMin] >= [$b yMin] && [$bb yMax] <= [$b yMax]} {
              incr full
            } else {
              incr strad
            }
          }
        }
      }
    }
  }
  puts [format "MECH %-38s members inside their fence %4d, outside %3d; non-members fully inside a fence %3d, straddling a fence edge %3d" $tag $in $out $full $strad]
  return $out
}

proc mech_check_placement {tag} {
  if {[catch {check_placement -verbose} msg]} {
    puts "MECH $tag: check_placement FAILED ([string trim [lindex [split $msg \n] 0]])"
  } else {
    puts "MECH $tag: check_placement passed"
  }
}

set block [ord::get_db_block]
puts "MECH regions: [llength [$block getRegions]] ([join [lmap r [$block getRegions] {$r getName}] {, }])"

remove_buffers
buffer_ports
global_placement -density 0.578 -pad_left 0 -pad_right 0 -routability_driven -timing_driven \
  -force_center_initial_place -min_phi_coef 0.95 -max_phi_coef 1.05
mech_measure "after global_placement"
set_placement_padding -global -left 0 -right 0
detailed_placement
mech_measure "after detailed_placement"
mech_check_placement "after detailed_placement"
# remember the legal placement so the DPO result can be undone afterwards
set saved {}
foreach inst [$block getInsts] {
  if {![$inst isFixed]} { lappend saved [list $inst [$inst getLocation] [$inst getOrient]] }
}

improve_placement -max_displacement "5 1"
mech_measure "after improve_placement (DPO)"
mech_check_placement "after improve_placement (DPO)"

# Back to the legal placement; force one copy-A flip-flop into the copy-B fence.
foreach s $saved {
  lassign $s inst loc orient
  $inst setOrient $orient
  $inst setLocation {*}$loc
}
mech_measure "after restoring the legal placement"
set victim ""
foreach inst [$block getInsts] {
  if {[string match "*u_acc_a/q*" [$inst getName]] && [string match "*df*" [[$inst getMaster] getName]]} { set victim $inst; break }
}
set rb ""
foreach r [$block getRegions] { if {[$r getName] eq "pdsep_copyB"} { set rb [lindex [$r getBoundaries] 0] } }
$victim setLocation [expr {([$rb xMin] + [$rb xMax]) / 2 / 460 * 460}] [expr {([$rb yMin] + [$rb yMax]) / 2 / 2720 * 2720}]
puts "MECH forced [string map {\\ {}} [$victim getName]] to [$victim getLocation] (inside the copy-B fence)"
mech_measure "after the forced move"
detailed_placement
mech_measure "after re-legalisation"
set bb [$victim getBBox]
puts "MECH moved flip-flop now at ([expr {[$bb xMin]/1000.0}], [expr {[$bb yMin]/1000.0}]) um"
mech_check_placement "after re-legalisation"
