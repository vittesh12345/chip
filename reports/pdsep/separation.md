# Copy separation measurement (scripts/pdsep_separation.py)

Distances between placed standard-cell boxes (DEF origin + LEF SIZE), in um. *Centre* is centre-to-centre; *gap* is edge-to-edge (0 = the cells touch or overlap). A sky130_fd_sc_hd row is 2.72 um tall; a dfxtp_1 flip-flop is 7.36 um wide.

- **baseline**: `build/pd/results/sky130hd/orbit_demo/base/6_final.def`
- **separated**: `build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.def`

## Per group

| Group | Copies | baseline: centroid | baseline: same-bit centre min / median / max | baseline: same-bit touching | baseline: min gap any FF / any cell | separated: centroid | separated: same-bit centre min / median / max | separated: same-bit touching | separated: min gap any FF / any cell |
|---|---|---|---|---|---|---|---|---|---|
| Accumulator lane 0 | A vs B | 17.3 | 3.56 / 24.67 / 82.12 | 1 of 32 | 0.00 / 0.00 | 291.0 | 262.67 / 291.55 / 330.00 | 0 of 32 | 243.80 / 234.00 |
| Accumulator lane 1 | A vs B | 26.9 | 2.76 / 30.69 / 91.87 | 3 of 32 | 0.00 / 0.00 | 289.0 | 254.85 / 289.10 / 327.97 | 0 of 32 | 243.40 / 236.50 |
| Accumulator lane 2 | A vs B | 46.2 | 2.87 / 55.16 / 116.97 | 1 of 32 | 0.00 / 0.00 | 292.9 | 252.55 / 293.58 / 323.19 | 0 of 32 | 244.26 / 241.74 |
| Accumulator lane 3 | A vs B | 29.5 | 6.10 / 30.83 / 111.28 | 1 of 32 | 0.00 / 0.00 | 288.3 | 253.37 / 288.54 / 327.34 | 0 of 32 | 243.34 / 225.81 |
| Result lane 0 | A vs B | 24.1 | 2.87 / 24.52 / 119.83 | 3 of 32 | 0.00 / 0.00 | 292.4 | 261.87 / 290.88 / 329.00 | 0 of 32 | 244.50 / 241.98 |
| Result lane 1 | A vs B | 32.3 | 7.43 / 27.86 / 130.04 | 0 of 32 | 0.00 / 0.00 | 290.0 | 251.17 / 295.42 / 324.59 | 0 of 32 | 243.40 / 241.96 |
| Result lane 2 | A vs B | 46.3 | 2.76 / 53.08 / 128.05 | 2 of 32 | 0.00 / 0.00 | 296.0 | 255.82 / 295.71 / 331.24 | 0 of 32 | 243.58 / 237.04 |
| Result lane 3 | A vs B | 33.4 | 4.58 / 30.72 / 185.06 | 1 of 32 | 0.00 / 0.00 | 293.4 | 251.17 / 293.70 / 332.22 | 0 of 32 | 242.94 / 242.88 |
| Thermal state (TMR) | 0 vs 1 | 8.8 | 5.52 / 9.26 / 13.00 | 0 of 2 | 2.72 / 0.00 | 100.7 | 97.92 / 100.82 / 103.73 | 0 of 2 | 92.54 / 89.76 |
| Thermal state (TMR) | 0 vs 2 | 5.5 | 5.74 / 5.83 / 5.91 | 1 of 2 | 0.00 / 0.00 | 206.7 | 206.72 / 206.72 / 206.72 | 0 of 2 | 201.31 / 198.56 |
| Thermal state (TMR) | 1 vs 2 | 11.0 | 10.97 / 11.48 / 12.00 | 0 of 2 | 8.16 / 2.72 | 106.1 | 103.62 / 106.21 / 108.80 | 0 of 2 | 97.92 / 92.48 |

## Overall

| Quantity | baseline | separated |
|---|---|---|
| redundant flip-flops found | 518 | 518 |
| acc/res same-bit centre distance, min (um) | 2.76 | 251.17 |
| acc/res same-bit centre distance, median of group medians (um) | 30.70 | 292.57 |
| acc/res min edge gap, any copy-A FF vs any copy-B FF of the same group (um) | 0.00 | 242.94 |
| all copy-A FFs vs all copy-B FFs (any lane), min edge gap (um) | 0.00 | 242.94 |
| acc/res centroid distance, min / max (um) | 17.3 / 46.3 | 288.3 / 296.0 |
| thermal same-bit centre distance, min / median (um) | 5.52 / 8.44 | 97.92 / 106.26 |
| thermal min edge gap between any two copies (um) | 0.00 | 92.54 |
| same-bit pairs in touching/overlapping cells | 13 of 262 | 0 of 262 |
| placement regions in the DEF | 0 | 5 |
| group members outside their region | n/a | 0 |
| non-member cells fully inside a fence / straddling a fence edge (excl. fill, tap) | n/a | 2 / 107 |

## Regions in separated

| Region | Type | Box (um) |
|---|---|---|
| pdsep_copyA | FENCE | (2.30, 2.72) - (52.44, 342.72) |
| pdsep_copyB | FENCE | (293.94, 2.72) - (344.08, 342.72) |
| pdsep_th0 | FENCE | (161.92, 272.00) - (184.92, 288.32) |
| pdsep_th1 | FENCE | (161.92, 165.92) - (184.92, 182.24) |
| pdsep_th2 | FENCE | (161.92, 57.12) - (184.92, 73.44) |

| Region pair | Edge gap (um) |
|---|---|
| pdsep_copyA / pdsep_copyB | 241.50 |
| pdsep_copyA / pdsep_th0 | 109.48 |
| pdsep_copyA / pdsep_th1 | 109.48 |
| pdsep_copyA / pdsep_th2 | 109.48 |
| pdsep_copyB / pdsep_th0 | 109.02 |
| pdsep_copyB / pdsep_th1 | 109.02 |
| pdsep_copyB / pdsep_th2 | 109.02 |
| pdsep_th0 / pdsep_th1 | 89.76 |
| pdsep_th0 / pdsep_th2 | 198.56 |
| pdsep_th1 / pdsep_th2 | 92.48 |

## Acceptance check (separated)

PASS: every target met.

Targets: no same-bit pair in touching/overlapping cells; every same-bit pair >= 20 um centre to centre; min edge gap between any flip-flops of different copies of a group >= 10 um; thermal regions pairwise >= 10 um apart; every group member inside its region.

Geometric distances only: no radiation transport or upset-rate model is implied.
