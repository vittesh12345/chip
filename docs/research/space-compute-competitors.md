# Space compute: competitor comparison for ORBIT-AI

Compiled 2026-09-30 for the ORBIT-AI scroll page (`site/chip-space/`). Every competitor
figure below is the vendor's or a cited third party's published number, in that source's
own unit. The figures are **not like-for-like**: MIPS/DMIPS are instruction rates on a
general-purpose CPU, GFLOPS are floating-point operations, TOPS are INT8 operations
(dense unless marked sparse). They are shown side by side for scale only.

Method note: direct page fetches were blocked by the network proxy in this session, so
figures were taken from web-search extracts of the listed pages. Anything not found is
marked "not found" rather than estimated. Re-check against the primary datasheets before
using any figure outside this page.

## Table

| Chip | Vendor | Process | Peak compute (vendor unit) | Power | Radiation (published) | Status |
|---|---|---|---|---|---|---|
| RAD750 | BAE Systems | 250 nm / 150 nm | ~400 MIPS at 200 MHz (266 MIPS or more across clock grades) | 5 W (CPU) | 200 krad to 1 Mrad TID | Flight heritage: Curiosity, Perseverance, JWST (118 MHz) |
| RAD5545 | BAE Systems | 45 nm SOI (IBM Trusted Foundry) | 5.6 GOPS / 3.7 GFLOPS (SBC brief); 5,200 MIPS, >3,700 MFLOPS | ~20 W chip, all peripherals on; 35 W SpaceVPX board at 95 °C | 100 krad TID | Rad-hard quad-core SoC; SpaceVPX board product |
| GR740 | Frontgrade Gaisler | 65 nm (STM C65SPACE) | 1,700 DMIPS at 250 MHz (4 × LEON4FT) | < 3 W core, typical | 300 krad(Si) TID; SEL immune to 125 MeV·cm²/mg | QML-V qualified (DLA 5962-21204, May 2022) |
| PIC64-HPSC | Microchip (NASA HPSC) | 12 nm FinFET (GlobalFoundries 12LP+) | up to 2 TOPS INT8 / 1 TFLOPS BF16 (vector units, 8 × X280 cores) | not found | RH: 100 krad TID (tested to 200 krad), SEL 78 MeV·cm²/mg. RT: 50 krad TID, SEL 42 MeV·cm²/mg | Announced 2024; in NASA JPL testing (2026) |
| XQR Versal AI Core XQRVC1902 | AMD | 7 nm (TSMC) | 133 TOPS INT8 (AI Engine peak, 400 AI Engines; VC1902 product-guide figure) | not found (design-dependent) | Passed 120 krad(Si) TID; no SEL to LET 80 MeV·cm²/mg | Class B qualified (2022); shipping since 2023 |
| Jetson Orin NX 16GB | NVIDIA | 8 nm (Samsung) | up to 100 TOPS INT8 (sparse) | 10 to 25 W configurable | Not rad-hard. TID test: survived past 36.2 krad(Si). Heavy-ion test: no destructive latch-up at tested energies | COTS; a shielded Orin NX flew Aug 2024 (Transporter-11, Aethero) |
| Myriad 2 (MA2450) | Intel Movidius | 28 nm | ~1,000 GFLOPS FP16 | ~1 W nominal | No rating published; beam-tested at CERN (2018), passed unmodified | COTS; flew on ESA Φ-sat-1 (launched Sep 2020) |
| ORBIT-AI demonstrator (built) | Vantage | 130 nm (SkyWater sky130 open PDK) | 1.1 GOPS INT8 peak (4 MACs × 2 ops × 139 MHz) | not measured | None claimed; sky130 is not radiation-characterised | Routed layout: DRC 0, LVS clean; 936 / 936 injected flips stopped or repaired |
| ORBIT-AI 16-tile full-size design | Vantage | not specified | 6.55 to 26.21 TOPS INT8 dense at 200 to 800 MHz (design figure, on paper) | 40 W sizing allocation, not an estimate | None claimed | Design only; not built |

## Sources

- RAD750: https://en.wikipedia.org/wiki/RAD750 ; https://satsearch.co/products/bae-systems-rad750-radiation-hardened-powerpc-microprocessor ; https://www.spaceflightnow.com/mars/msl/120810computer/
- RAD5545: https://satsearch.co/products/bae-systems-rad5545-space-vpx-single-board-computer ; https://en.wikipedia.org/wiki/RAD5500
- GR740: https://download.gaisler.com/products/gr740/doc/GR740-OVERVIEW.pdf ; https://www.gaisler.com/products/gr740 ; http://microelectronics.esa.int/gr740/DASIA2015-GR740-Hjorth.pdf ; https://www.gaisler.com/news-events/qml-v-and-qml-q-space-grade-qualification-of-the-gr740-quad-core-leon4ft-microprocessor
- PIC64-HPSC: https://www.microchip.com/en-us/about/news-releases/products/microchip-unveils-industrys-highest-performance-64-bit-hpsc-mpu ; https://www.mouser.lt/pdfDocs/PIC64-HPSC-Series-00005391.pdf ; https://riscv.org/blog/eight-core-risc-v-processor-and-tsn-switch-for-ai-space-designs/ ; https://glitchwire.com/news/nasas-hpsc-processor-tests-500x-faster-than-current-spaceflight-computers-openin/
- XQRVC1902: https://www.amd.com/en/products/adaptive-socs-and-fpgas/versal/space-grade.html ; https://docs.amd.com/v/u/en-US/versal-ai-core-product-selection-guide ; https://indico.esa.int/event/531/contributions/10592/attachments/6538/11610/AMD%20XQR%20Versal%20Adaptive%20SoCs%20Enable%20Next-Generation%20Signal%20Processing%20and%20AI%20in%20Space%20-%20SEFUW%20Non-NDA%202025-03-25%20FINAL.pdf ; https://www.amd.com/en/newsroom/press-releases/2022-11-15-amd-announces-completion-of-class-b-qualification-.html
- Jetson Orin NX: https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/ ; https://www.researchgate.net/publication/387116286_Total_Ionizing_Dose_Radiation_Testing_of_NVIDIA_Jetson_Orin_NX_System_on_Module ; https://hubble.com/community/guides/nvidia-jetson-orin-on-satellites-what-on-orbit-edge-ai-looks-like-today/
- Myriad 2: https://www.intel.com/content/dam/support/us/en/documents/boardsandkits/neural-compute-sticks/Myriad2VPU-ProductBrief.pdf ; https://www.esa.int/Enabling_Support/Space_Engineering_Technology/ESA_team_blasts_Intel_s_new_AI_chip_with_radiation_at_CERN ; https://www.eoportal.org/satellite-missions/phisat-1
- ORBIT-AI: reports/pdsep/summary.md ; reports/model/concept_budget.txt ; docs/orbit-ai-design-brief.pdf

## Uncertain or not verified

- XQRVC1902 133 TOPS is the Versal AI Core VC1902 product-guide peak; the space-grade part's rated clock, and so its peak, may differ. No per-device power figure was found.
- PIC64-HPSC power was not found in a source.
- RAD5545 chip power (~20 W) comes from Wikipedia; the 35 W figure is the SpaceVPX board.
- Myriad 2 ~1,000 GFLOPS FP16 is a vendor-derived figure (Intel brief: "teraflops ... within a nominal 1 W"). No TID/SEL rating was published for Φ-sat-1.
- Jetson Orin NX: the 36.2 krad figure is one TID test of the module (ResearchGate paper), not a rating. The Aug 2024 flight is from a third-party guide (hubble.com).
- GR740 flight on GOMX-5 was reported in one search extract and is not used on the page.
