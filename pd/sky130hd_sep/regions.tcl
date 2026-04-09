# Placement fences that keep the redundant copies of orbit_demo apart.
#
# Sourced by ORFS as POST_FLOORPLAN_TCL (end of floorplan.tcl, after the core
# rows exist and before tap cells, PDN and any placement), so every later
# placement step sees the constraint:
#
#   global_placement -skip_io, global_placement (timing/routability driven):
#       gpl builds one Nesterov region per dbGroup and places the group's
#       instances inside its dbRegion box; the region areas are blocked for
#       the top-level cells with dummy instances.
#   detailed_placement (place, CTS, CTS repair, global-route repair):
#       dpl legalises every group member inside its region and keeps every
#       non-member out (the region acts as a fence), and check_placement
#       fails on any cell in the wrong region.
#   improve_placement (DPO) does NOT honour regions (measured: it moved 47 of
#       1560 members out); config.mk therefore sets ENABLE_DPO=0.
#
# The mechanism was checked empirically before use (see reports/pdsep/summary.md)
# and the result is re-measured from the routed DEF by scripts/pdsep_separation.py.
#
# Groups (instance paths are the flat-link names that keep the orbit_keep_reg
# hierarchy, e.g. g_lane[2].u_lane.u_res_b/q[7]$_SDFFE_PN0P_). Each group holds
# the complete kept copy: its flip-flops plus the per-copy enable/reset gates
# (mux2i/nor2b) that orbit_keep_reg synthesises to, so a copy's D-path gates
# sit with its flip-flops:
#   copyA : u_acc_a and u_res_a of all 4 lanes (256 flip-flops)
#   copyB : u_acc_b and u_res_b of all 4 lanes (256 flip-flops)
#   th0/1/2 : u_thermal.u_copy0/1/2 (2 flip-flops each)
# Everything else (multipliers, adders, comparators, voter, next-state logic,
# control, clock tree, port buffers) is unconstrained and may go anywhere
# outside the fences.
#
# Floorplan variants (PDSEP_FLOORPLAN, default in config.mk). Boxes are in um
# relative to the lower-left corner of the core; "W"/"H" are the core width and
# height, and every box edge is snapped to the site grid / row boundaries.

set ::pdsep_variant [expr {[info exists ::env(PDSEP_FLOORPLAN)] && $::env(PDSEP_FLOORPLAN) ne "" ? $::env(PDSEP_FLOORPLAN) : "edges"}]
set ::pdsep_rtype [expr {[info exists ::env(PDSEP_REGION_TYPE)] && $::env(PDSEP_REGION_TYPE) ne "" ? $::env(PDSEP_REGION_TYPE) : "EXCLUSIVE"}]

# name  {x0 y0 x1 y1} as Tcl expressions of W and H
set ::pdsep_floorplans {
  edges {
    copyA {0            0          50           H}
    copyB {W-50         0          W            H}
    th0   {W/2-11.5     H/2+100    W/2+11.5     H/2+116.32}
    th1   {W/2-11.5     H/2-8.16   W/2+11.5     H/2+8.16}
    th2   {W/2-11.5     H/2-116.32 W/2+11.5     H/2-100}
  }
  mid {
    copyA {55           0          105          H}
    copyB {W-105        0          W-55         H}
    th0   {W/2-11.5     H/2+100    W/2+11.5     H/2+116.32}
    th1   {W/2-11.5     H/2-8.16   W/2+11.5     H/2+8.16}
    th2   {W/2-11.5     H/2-116.32 W/2+11.5     H/2-100}
  }
}

# group -> instance-name pattern (backslash escapes removed before matching)
set ::pdsep_members {
  copyA {^g_lane\[[0-9]+\]\.u_lane\.u_(acc|res)_a/}
  copyB {^g_lane\[[0-9]+\]\.u_lane\.u_(acc|res)_b/}
  th0   {^u_thermal\.u_copy0/}
  th1   {^u_thermal\.u_copy1/}
  th2   {^u_thermal\.u_copy2/}
}
# flip-flops expected per group (docs/SPEC.md section 7)
set ::pdsep_expect_ff {copyA 256 copyB 256 th0 2 th1 2 th2 2}

proc pdsep_apply_regions {} {
  global pdsep_variant pdsep_rtype pdsep_floorplans pdsep_members pdsep_expect_ff
  if {![dict exists $pdsep_floorplans $pdsep_variant]} {
    utl::error FLW 9001 "pdsep: unknown PDSEP_FLOORPLAN '$pdsep_variant' (known: [dict keys $pdsep_floorplans])"
  }
  set block [ord::get_db_block]
  set dbu [$block getDbUnitsPerMicron]
  set core [$block getCoreArea]
  set cx0 [$core xMin]; set cy0 [$core yMin]; set cx1 [$core xMax]; set cy1 [$core yMax]
  set W [expr {($cx1 - $cx0) / double($dbu)}]
  set H [expr {($cy1 - $cy0) / double($dbu)}]
  set row [lindex [$block getRows] 0]
  set site [$row getSite]
  set sw [$site getWidth]; set sh [$site getHeight]

  if {[$block getRegions] ne ""} {
    utl::error FLW 9002 "pdsep: the block already has regions; refusing to add a second set"
  }

  set boxes {}
  dict for {name expr4} [dict get $pdsep_floorplans $pdsep_variant] {
    set b {}
    foreach e $expr4 {
      lappend b [expr [string map [list W $W H $H] $e]]
    }
    lassign $b x0 y0 x1 y1
    # snap to the site grid (x) and row boundaries (y), clamp to the core
    set X0 [expr {$cx0 + int(round($x0 * $dbu / double($sw))) * $sw}]
    set X1 [expr {$cx0 + int(round($x1 * $dbu / double($sw))) * $sw}]
    set Y0 [expr {$cy0 + int(round($y0 * $dbu / double($sh))) * $sh}]
    set Y1 [expr {$cy0 + int(round($y1 * $dbu / double($sh))) * $sh}]
    set X0 [expr {max($X0, $cx0)}]; set Y0 [expr {max($Y0, $cy0)}]
    set X1 [expr {min($X1, $cx1)}]; set Y1 [expr {min($Y1, $cy1)}]
    if {$X1 <= $X0 || $Y1 <= $Y0} { utl::error FLW 9003 "pdsep: empty region $name" }
    dict set boxes $name [list $X0 $Y0 $X1 $Y1]
  }

  # the boxes must be pairwise disjoint
  set names [dict keys $boxes]
  for {set i 0} {$i < [llength $names]} {incr i} {
    for {set j [expr {$i + 1}]} {$j < [llength $names]} {incr j} {
      lassign [dict get $boxes [lindex $names $i]] a0 b0 a1 b1
      lassign [dict get $boxes [lindex $names $j]] c0 d0 c1 d1
      if {$a0 < $c1 && $c0 < $a1 && $b0 < $d1 && $d0 < $b1} {
        utl::error FLW 9004 "pdsep: regions [lindex $names $i] and [lindex $names $j] overlap"
      }
    }
  }

  set grp {}
  dict for {name box} $boxes {
    set reg [odb::dbRegion_create $block "pdsep_$name"]
    lassign $box X0 Y0 X1 Y1
    odb::dbBox_create $reg $X0 $Y0 $X1 $Y1
    $reg setRegionType $pdsep_rtype
    dict set grp $name [odb::dbGroup_create $reg "pdsep_grp_$name"]
  }

  set count {}; set ffs {}
  foreach name $names { dict set count $name 0; dict set ffs $name 0 }
  foreach inst [$block getInsts] {
    set nm [string map {"\\" ""} [$inst getName]]
    foreach name $names {
      if {[regexp [dict get $pdsep_members $name] $nm]} {
        [dict get $grp $name] addInst $inst
        dict incr count $name
        if {[string match "*__df*" [[$inst getMaster] getName]]} { dict incr ffs $name }
        break
      }
    }
  }

  set rpt [open $::env(REPORTS_DIR)/pdsep_regions.txt w]
  puts $rpt "pdsep floorplan variant $pdsep_variant, region type $pdsep_rtype"
  puts $rpt [format "core (um): %.3f %.3f %.3f %.3f" [expr {$cx0/double($dbu)}] [expr {$cy0/double($dbu)}] [expr {$cx1/double($dbu)}] [expr {$cy1/double($dbu)}]]
  set bad 0
  dict for {name box} $boxes {
    lassign $box X0 Y0 X1 Y1
    set line [format "region pdsep_%-6s box_um %9.3f %9.3f %9.3f %9.3f  members %4d  flip-flops %4d (expected %d)" \
      $name [expr {$X0/double($dbu)}] [expr {$Y0/double($dbu)}] [expr {$X1/double($dbu)}] [expr {$Y1/double($dbu)}] \
      [dict get $count $name] [dict get $ffs $name] [dict get $pdsep_expect_ff $name]]
    puts $rpt $line
    utl::report "pdsep: $line"
    if {[dict get $ffs $name] != [dict get $pdsep_expect_ff $name]} { set bad 1 }
  }
  close $rpt
  if {$bad} {
    utl::error FLW 9005 "pdsep: flip-flop count of a group differs from docs/SPEC.md section 7"
  }
}

pdsep_apply_regions
