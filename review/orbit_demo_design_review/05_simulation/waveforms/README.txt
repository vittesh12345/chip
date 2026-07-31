orbit_demo review waveforms (written for the review package, not part of the repo)

Revision: rtl/*.v at repo HEAD 0495cfa6 (unchanged since 26566f0); md5 in run_info.txt.
Simulator: Icarus Verilog 14.0 (devel) (s20260301-500-g2e81fcccb-dirty), iverilog -g2005 -Wall.
Clock 10 ns (HALF = 5 ns). This is an RTL zero-delay simulation: there is no process,
voltage or temperature corner, and no timing. "temp_c" is a digital sensor input,
not a die temperature.

Files
  tb_orbit_wave.v           testbench wrapper. Its DUT instance is a copy of tb/tb_orbit_demo.v
                            lines 66-85: instance name dut, named ports, no parameter overrides.
  run_waves.sh              builds and runs the 5 scenarios (+scen=1..5), writes the VCDs and logs
  run_negctl.sh             negative control: each scenario must FAIL on a scratch RTL copy
                            that carries the bug it targets (rtl/ is only read)
  plot_waves.py             timing diagrams and per-cycle CSVs, read directly from the VCDs
  wave_<name>.vcd           raw waveforms ($dumpvars(0, tb_orbit_wave); includes dut internals)
  run_scen<n>.log           sim log with the self-check verdict line WAVE_<name> PASS|FAIL
  wave_<name>.png / .csv    rendered diagram; CSV = values sampled 1 ns before each rising edge
  orbit_demo_waveforms.pdf  all diagrams (6 pages)
  negctl_summary.txt        negative-control result

Scenarios (all self-checking)
  1 a_mac3           reset, then a 3-beat MAC on all 4 lanes, in_first..in_last
                     lanes: (-128*-128)x3 = 49152; (127*-128)x3 = -48768;
                     -128*127 + -128*-128 + 127*127 = 16257; -1*-1 + 100*-3 + 0*-128 = -299
  2 b_backpressure   out_ready low for 6 cycles with the buffer full; a non-last beat is blocked;
                     the drain and the refill happen in the same cycle; then 4 more held cycles
  3 c_fault          g_lane[1].u_lane.u_acc_b.q[3] is flipped at a falling edge (SPEC section 7).
                     mismatch rises in the same cycle and forces out_valid and in_ready to 0;
                     fault rises at the next edge; R is never transferred; clear_fault zeroes
                     both copies; the recovery beat then transfers correctly
  4 d_thermal        temp_c, one reading per cycle: 60 -> 85 -> 97 -> 65 with temp_valid = 1.
                     Sequence NORMAL -> THROTTLE -> STOP -> NORMAL. in_ready is high on alternate
                     cycles in THROTTLE. u_thermal.u_copy1.q[0] is upset once in THROTTLE and
                     therm_repair is high for exactly that cycle
  5 c2_fault_sticky  as 3, plus a second, test-only flip that restores the bit. mismatch drops,
                     but fault stays high until clear_fault (SPEC section 5, sticky)

Regenerate
  ./run_waves.sh /home/user/chip
  ./run_negctl.sh /home/user/chip
  <python with matplotlib> -I plot_waves.py .
