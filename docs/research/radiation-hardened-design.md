# Radiation-aware design practice for the ORBIT-AI demonstrator (design v2)

Research note, 29 September 2026, for the 4-lane INT8 demonstrator (`rtl/`, [SPEC](../SPEC.md), brief page 3). **It makes no radiation-hardness claim**: we found no published single-event data for sky130, and nothing here was beam tested. Most papers were read as abstracts or search extracts (ECSS, NTRS, arXiv and MDPI PDFs were blocked by the proxy); check figures against the full text before quoting.

## 1. What matters for this demonstrator

**Redundancy only helps if the copies fail independently.** Copies that share one voter or next-state cone ("local TMR") all receive the same wrong value when a transient hits that logic ([NASA LTMR vs DTMR](https://ntrs.nasa.gov/api/citations/20180000010/downloads/20180000010.pdf)). The same holds for shared clock, reset and enable nets ([Berg 2016](https://ntrs.nasa.gov/api/citations/20160009479/downloads/20160009479.pdf)). Closely packed copies also share charge ([He & Chen 2014](https://link.springer.com/article/10.1007/s11432-014-5100-1)). The usual practice is a voter in every redundant feedback path, so each copy is rewritten from the majority every clock ([XAPP197](https://docs.amd.com/api/khub/documents/RagbuUllwwnBwlW_UtEcKw/content), [Johnson & Wirthlin 2010](https://dl.acm.org/doi/10.1145/1723112.1723154)).

**Distance is the main layout lever.**

- **130 nm:** charge sharing between transistors reaches about 1-2 µm ([Amusan 2006](https://ieeexplore.ieee.org/document/4033184/), summary).
- **90 nm:** 5 µm was the minimum separation for redundant nodes ([Double-DICE](https://ieeexplore.ieee.org/document/5236054/)), and separating nodes did more than guard rings ([Amusan 2009](https://ieeexplore.ieee.org/document/4812109/)).
- **65 nm:** multi-cell upsets (MCU) fell exponentially with distance, and fell further with well contacts between the copies ([Furuta 2014](https://ieeexplore.ieee.org/document/6832610/); [Yamamoto 2011](https://ieeexplore.ieee.org/document/6093866/), 110 → 1 MCUs).
- **Published projects** space TMR copies 10-15 µm apart:
  - a 130 nm ASIC, 15 µm ([arXiv 2112.05720](https://arxiv.org/abs/2112.05720));
  - Fermilab ([Miryala 2017](https://indico.cern.ch/event/608587/contributions/2614129/attachments/1521485/2377027/SEE_Tolerant_Standard_Cell_Based_Design_While_Guaranteeing_Specific_Distance_Between_Memory_Elements.pdf));
  - TriglaV, at least 10 µm (JINST 21 C03023);
  - CERN TMRG ([docs](https://github.com/rlf-arlut/tmrg/blob/master/doc/source/implementation.rst)).
- **sky130 reference:** the open [sky130RHBDlib](https://github.com/stineje/sky130RHBDlib) TMR cell uses about 21.5 µm between copies. It has not been tested.
- **Well direction:** upsets spread furthest along a shared well (Tipton 2006, TNS 53(6); [Yoshimoto 2012](https://ieeexplore.ieee.org/document/6241847/)). sky130hd wells run along the 2.72 µm rows, so vertical separation crosses more well junctions.

**Where the design stands.** In v1, same-bit copies were as close as 2.76 µm, and 13 of 262 pairs touched. The fenced run `e7` (`build/pd_sep/report/e7/summary.md`) meets its targets: copy A to copy B at least 251 µm, thermal copies at least 97.9 µm, no touching pairs. But `e7` fails setup (WNS −0.140 ns at 7.0 ns), has 6 slew and 3 capacitance violations, and has not run KLayout DRC/LVS.

Reading `e7/6_final.v` for this note turned up three shared drivers:
- one clock leaf buffer (`clkbuf_leaf_22_clk`) drives thermal copies 0 **and** 1;
- `u_thermal.nxt[0]` reaches all three thermal copies through one `buf_4`;
- one `rst_n` input buffer feeds every copy's reset gates, and one of its leaves feeds lane-1 copy A and thermal copies 1 and 2.

**Detection is not correction.** Duplicate-with-compare (DWC) detects errors; recovery needs re-execution or a way to tell which copy is right ([Johnson/LANL](https://www.osti.gov/servlets/purl/1268220), [Lima 2003](https://www.inf.ufrgs.br/~fglima/lima_dac03.pdf)). Equivalence checking cannot confirm that redundancy survived ([Berg & LaBel 2016](https://ntrs.nasa.gov/api/citations/20160003521/downloads/20160003521.pdf)), and synthesis can remove it ([SYNFI](https://github.com/lowRISC/synfi)).

**What cannot be concluded without beam testing:**
- any sky130 upset rate, cross-section or LET threshold;
- whether 20 µm is enough in sky130 (all the distances above come from other processes);
- sky130 transient pulse widths;
- latch-up, total-dose and displacement-damage behaviour;
- whether fault-injection percentages predict behaviour in orbit.

Geometry and fault injection show the mitigation was *built as intended*, not that it *works*.

## 2. Design v2 recommendations

MUST: closes a documented single point at low cost. SHOULD: worth doing in v2. COULD: optional, or needs a SPEC change.

### (a) RTL / architecture

| ID | Pri. | Change | Expected fault-injection effect | Verification |
|---|---|---|---|---|
| R1 | MUST | Triplicate `out_valid_q`, `fault_q` and `phase` as `orbit_keep_reg` copies with voted feedback, `q_k <= next(vote_k(q0,q1,q2))`. Cost: +6 flops (521 → 527), 9 `maj3` cells. | `neg_out_valid_q` (result lost or duplicated) becomes masked and repaired. A 1→0 upset in `fault_q` no longer restarts a stopped design. | Upset scenario per copy; "copies agree 1 cycle after the upset"; storage audit grows to 12 groups. |
| R2 | MUST | Give each thermal copy its own voter and next-state cone: `c_k <= nxt(vote_k(c0,c1,c2))`. | Today, in STOP at 71-94 °C, one transient on the voter or `nxt` writes NORMAL into all three copies. At 71-79 °C the design then stays NORMAL and admits work, bypassing hysteresis. With R2, only one copy is hit and it is outvoted. | Transient scenarios on `vote_k` and `nxt_k`: expect masked. |
| R3 | MUST | Decode lane control (`in_fire`, accumulator/result enables, `clr`) separately in domain A and domain B. Each domain votes the TMR control state (`admit`, `fault`, `out_valid`) locally. Ports are driven from A. | A transient on the shared `in_fire` or `clr` corrupts both copies identically: silent wrong data (SDC). With R3 it corrupts one copy, causing a mismatch and a fault-stop. | Transients on `in_fire_a/b` and `clr_a/b`: expect detected. |
| R4 | SHOULD | Give copy B its own 8×8 multiplier. Alternatives: skew copy B by one cycle ([VDCLS](https://www.mdpi.com/2079-9292/12/2/464)), or add a mod-3 residue check ([NASA 1979](https://ntrs.nasa.gov/citations/19790022776)). The residue check needs signed and 2^32-wrap corrections and misses errors that are multiples of 3. | `neg_product` goes from undetected to fault-stop. The `in_a`/`in_b` pins stay a shared point. | `neg_product` becomes a detection proof; measure the area. |
| R5 | SHOULD | Duplicate the comparator: `mismatch_A` in domain A, `mismatch_B` in domain B. | A comparator stuck at "no mismatch" is a hidden (latent) fault ([ISO 26262 LFM](https://www.synopsys.com/content/dam/synopsys/events/gomactech-2022-snps-fusa.pdf)). With R5 it no longer hides a later storage upset. | Mutate the mismatch net to constant 0 (`const0`), then inject a storage upset. |
| R6 | SHOULD | Leave STOP or THROTTLE only after two consecutive valid readings ≤ 70 °C; entering STOP stays immediate. Our own inference, not from a source. One TMR bit; changes SPEC §6. | Today, in STOP at 90 °C, one glitched `temp_c` sample leads to NORMAL, then THROTTLE, which admits work until 95 °C. With R6 a single glitch is ignored. | Transient on `temp_c`; update P5/P6. |
| R7 | SHOULD | TMR fault-cause register (8 bits: accumulator or result, per lane) and a saturating correction counter, as in LEON3FT ICNT ([manual](https://www.frontgrade.com/sites/default/files/documents/functional-manual-ut699e-ut700-leon.pdf)). New ports. | Each injected event becomes observable. No rate is implied. | Counter increments exactly once per masked upset. |

**COULD (R8-R11):**
- SEC-DED (39,32) on the result registers in place of duplication, which corrects instead of stopping; the encoder must be checked against copy B.
- A per-lane output check field (mod-3 residue or parity of `res_b`) that the host can verify.
- `rst_n`/`clear_fault` qualified over 2 edges or filtered with `maj3` plus `dlygate4sd3_1`. The delay would be a parameter: the 400-700 ps widths in [Narasimham 2007](https://ieeexplore.ieee.org/document/4395066/) come from another 130 nm process.
- A TMR sum-sequence counter, turning the "host re-sends" rule in SPEC §5 into a retry protocol.

Keep DWC with fault-stop on the 32-bit datapath (full TMR: +256 flops, +256 voters, multiplier still shared). The SPEC should say DWC detects but does not mask.

### (b) Physical design

- **P1 MUST: fence whole domains.** Put each domain's voter, next-state, enable, clear and comparator cells in that domain's fence, so that only flop outputs cross between fences. Thermal copy *k* and control copies *k* share fence *k*: unrelated logic of one domain may share a region ([Appels & Prinzie 2020](https://www.mdpi.com/2079-9292/9/11/1936)). `regions.tcl` needs `keep_hierarchy` wrappers to find these cells by name. Keep EXCLUSIVE regions and `ENABLE_DPO=0`.
- **P2 MUST: keep the spacing targets.** At least 20 µm same-bit centre-to-centre and at least 10 µm edge gap, for every group including the new ones. This is based on published 10-15 µm practice and the ~21.5 µm sky130RHBDlib pitch; it is geometry, not a rating. Report the minimum, the 1st percentile, and the number of pairs under 10, 15 and 20 µm.
- **P3 MUST: close timing and sign off.** Fix setup, slew and capacitance, and run KLayout DRC/LVS. The `e7` worst path is `in_a[31]` → `g_lane[3].u_acc_a`.
- **P4 SHOULD: add a `lanes` floorplan.** Stack horizontal bands per lane: A*i* / lane *i* logic / B*i*. A band from one lane may sit next to a band from another lane (A*i* beside B*j*). A vertical gap of 8 rows (21.8 µm) meets the same-bit target at any x and crosses wells. Compare timing, wirelength (160 → 244 mm in `e7`) and power against `edges`.
- **P5 SHOULD: add well taps between copies.**
  - ORFS runs `tapcell -distance 14`: a 27.6 µm pitch per row, offset 13.8 µm between rows (1524 taps in `e7`).
  - Add a tap column in each fence gap, or use `-distance 7` (about +1,900 µm², ~3 % of cell area).
  - Run magic's `full` DRC style so the latch-up rules LU.2/LU.3 (15 µm) are checked ([sky130.tech](https://github.com/RTimothyEdwards/open_pdks/blob/master/sky130/magic/sky130.tech)).
  - Confirm no deep n-well under redundant storage (triple well raised MCU in Yamamoto 2011). hd cells have no guard rings: document "tap grid only".
- **P6 SHOULD: clock tree.** Keep one root; redundant clock trees add skew risk ([Berg RADECS 2016](https://ntrs.nasa.gov/citations/20160013226)). No leaf buffer may drive two copies of one group. Set `CTS_CLUSTER_DIAMETER` below the fence gap and audit the result.
- **P7 SHOULD: reset and clear.** Give each domain its own reset/clear leaf buffer inside its fence ([RTG4 AC463](https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ApplicationNotes/ApplicationNotes/Microchip_RTG4_Radiation_Mitigated_Clock_and_Reset_Network_Usage_Application_Note_AC463_V2.pdf), [TOFHIR2](https://arxiv.org/abs/2404.01208)). Mechanism-test it first, as for the fences. The pin and root buffer stay a documented single point.
- **P8 COULD: pin placement.** Use `IO_CONSTRAINTS` to put `in_a`/`in_b` next to the lane logic and `out_data` next to copy A.

### (c) Verification additions

- **V1 MUST:** Add upset scenarios for every new TMR copy, with a one-cycle repair assertion. The negative scenarios become positive ones.
- **V2 MUST:** Add one-cycle transient scenarios, each with a stated expected outcome, on `vote_k`, `nxt_k`, `in_fire_a/b`, `clr_a/b`, `mismatch_*`, the reset leaves and `prod`. Add "same bit flipped in A and B in one cycle" as a known escape ([Bagbaba 2021](https://arxiv.org/abs/2103.05106)).
- **V3 MUST: structural audit of the synthesized and routed netlists.** Each TMR flop's input cone must contain its own voter that reads all three copies. The A and B cones must share only the documented inputs. Re-run after every step that edits the netlist.
- **V4 MUST: make `pdsep_separation.py --check` the signoff gate.** Extend it to the new groups, the fence of each voter and enable cell, and "no clock or reset leaf drives two copies of one group" (the §1 findings would fail today).
- **V5 SHOULD: report outcomes by element class:** masked, corrected, detected and stopped, silent data corruption (SDC), or hang. Detection coverage = detected / (detected + SDC) ([Mukherjee 2003](https://www.researchgate.net/publication/3215342_Measuring_architectural_vulnerability_factors)). Also report how often fault-stop fires.
- **V6 SHOULD:** Re-run the fault proofs on the sky130 netlist (liberty read without `-lib`, [Yosys](https://github.com/YosysHQ/yosys/blob/main/frontends/liberty/liberty.cc)).
- **V7 SHOULD:** Run [MCY](https://github.com/nakengelhardt/faultinjection_mcy) mutation on the comparators, voters and fault path, and list every UNCOVERED mutant.
- **V8 COULD:** Inject an upset into every flop of the routed netlist, as [Trikarenos](https://arxiv.org/abs/2407.05938) did. Also run sampled transients of 100 ps to 1 ns, and report sample size and confidence ([Leveugle 2009](https://www.researchgate.net/publication/221341698_Statistical_Fault_Injection_Quantified_Error_and_Confidence)).

**Out of reach in an open flow:**
- sky130 upset and latch-up rates, which need a beam test;
- calibrated charge-collection (TCAD) models;
- characterized guard-ringed cells (sky130RHBDlib is untested and not in ORFS);
- pairwise spacing constraints like Innovus `create_inst_space_group` (fences plus a script check substitute);
- a triplicated clock tree with skew signoff;
- section-level ECSS citations until someone reads the PDF.

## 3. Sources

1. ECSS-E-HB-20-40A (2023), not retrieved: <https://ecss.nl/home/ecss-e-hb-20-40a-engineering-techniques-for-radiation-effects-mitigation-in-asics-and-fpgas-handbook/>
2. Amusan et al., IEEE TNS 53(6) 2006: <https://ieeexplore.ieee.org/document/4033184/>
3. Amusan et al., IEEE TDMR 9(2) 2009: <https://ieeexplore.ieee.org/document/4812109/>
4. 90 nm Double-DICE, 2009: <https://ieeexplore.ieee.org/document/5236054/>
5. Furuta et al., IEEE TNS 2014: <https://ieeexplore.ieee.org/document/6832610/>
6. Yamamoto et al., IEEE TNS 58(6) 2011: <https://ieeexplore.ieee.org/document/6093866/>
7. He & Chen, Sci. China Inf. Sci. 2014: <https://link.springer.com/article/10.1007/s11432-014-5100-1>
8. Yoshimoto et al., IRPS 2012: <https://ieeexplore.ieee.org/document/6241847/> (Tipton et al., IEEE TNS 53(6) 2006, no link checked)
9. 130 nm ASIC, 15 µm TMR spacing: <https://arxiv.org/abs/2112.05720>
10. Miryala, TWEPP 2017: <https://indico.cern.ch/event/608587/contributions/2614129/attachments/1521485/2377027/SEE_Tolerant_Standard_Cell_Based_Design_While_Guaranteeing_Specific_Distance_Between_Memory_Elements.pdf>
11. TMRG docs; Kulis, JINST 12 C01082: <https://github.com/rlf-arlut/tmrg/blob/master/doc/source/implementation.rst>
12. Appels & Prinzie, Electronics 2020: <https://www.mdpi.com/2079-9292/9/11/1936>
13. sky130RHBDlib: <https://github.com/stineje/sky130RHBDlib>
14. open_pdks sky130 magic tech: <https://github.com/RTimothyEdwards/open_pdks/blob/master/sky130/magic/sky130.tech>
15. OpenROAD tapcell: <https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/tap/src/tapcell.cpp>
16. NASA LTMR vs DTMR: <https://ntrs.nasa.gov/api/citations/20180000010/downloads/20180000010.pdf>
17. Berg, NEPP 2016: <https://ntrs.nasa.gov/api/citations/20160009479/downloads/20160009479.pdf>
18. Berg et al., RADECS 2016: <https://ntrs.nasa.gov/citations/20160013226>
19. Berg & LaBel, TMR verification: <https://ntrs.nasa.gov/api/citations/20160003521/downloads/20160003521.pdf>
20. Xilinx XAPP197: <https://docs.amd.com/api/khub/documents/RagbuUllwwnBwlW_UtEcKw/content>
21. Johnson & Wirthlin, FPGA 2010: <https://dl.acm.org/doi/10.1145/1723112.1723154>
22. Johnson et al., DWC: <https://www.osti.gov/servlets/purl/1268220>
23. Lima et al., DAC 2003: <https://www.inf.ufrgs.br/~fglima/lima_dac03.pdf>
24. VDCLS, Electronics 2023: <https://www.mdpi.com/2079-9292/12/2/464>
25. NASA residue codes, 1979: <https://ntrs.nasa.gov/citations/19790022776>
26. UT699E/UT700 LEON3FT manual: <https://www.frontgrade.com/sites/default/files/documents/functional-manual-ut699e-ut700-leon.pdf>
27. Microchip AC463: <https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ApplicationNotes/ApplicationNotes/Microchip_RTG4_Radiation_Mitigated_Clock_and_Reset_Network_Usage_Application_Note_AC463_V2.pdf>
28. TOFHIR2: <https://arxiv.org/abs/2404.01208>
29. Narasimham et al., IEEE TNS 2007: <https://ieeexplore.ieee.org/document/4395066/>
30. SYNFI: <https://github.com/lowRISC/synfi>
31. Yosys read_liberty: <https://github.com/YosysHQ/yosys/blob/main/frontends/liberty/liberty.cc>
32. MCY fault-injection demo: <https://github.com/nakengelhardt/faultinjection_mcy>
33. Bagbaba et al.: <https://arxiv.org/abs/2103.05106>
34. Trikarenos: <https://arxiv.org/abs/2407.05938>
35. Leveugle et al., DATE 2009: <https://www.researchgate.net/publication/221341698_Statistical_Fault_Injection_Quantified_Error_and_Confidence>
36. Mukherjee et al., IEEE Micro 2003: <https://www.researchgate.net/publication/3215342_Measuring_architectural_vulnerability_factors>
37. Synopsys FuSa, GOMACTech 2022: <https://www.synopsys.com/content/dam/synopsys/events/gomactech-2022-snps-fusa.pdf>
