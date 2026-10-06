# ORBIT-AI 4-lane INT8 demonstrator: behavioral specification

This is the contract for the RTL in `rtl/` and for every testbench, formal
property, fault-injection campaign and implementation script in this
repository. The design is the "BUILT / DIGITAL DEMONSTRATOR" box of the
ORBIT-AI v0.1 concept brief (`docs/orbit-ai-design-brief.pdf`), not the full
16-tile chip.

Nothing here is radiation-qualified, timing-signed-off for flight or
thermally validated. Thresholds are illustrative.

## 1. Files

| File | Module | Role |
|---|---|---|
| `rtl/orbit_demo.v` | `orbit_demo` | Top level: handshake, output buffer, fault latch |
| `rtl/orbit_mac_lane.v` | `orbit_mac_lane` | One INT8 MAC lane with duplicated storage |
| `rtl/orbit_thermal_tmr.v` | `orbit_thermal_tmr` | Three-copy thermal state machine with repair |
| `rtl/orbit_keep_reg.v` | `orbit_keep_reg` | One copy of a redundant register (`keep_hierarchy`) |

Verilog-2005, synthesizable, single clock `clk`, synchronous active-low reset
`rst_n`. Parameters: `LANES = 4`, `T_THROTTLE = 80`, `T_STOP = 95`,
`T_RECOVER = 70` (signed 8-bit degrees C).

## 2. Ports of `orbit_demo`

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Synchronous reset, active low |
| `in_valid` | in | 1 | Input beat valid |
| `in_ready` | out | 1 | Input beat accepted this cycle if `in_valid` is also high |
| `in_first` | in | 1 | This beat starts a new sum (`acc = a*b`) |
| `in_last` | in | 1 | After this beat, copy every lane's sum to the output buffer |
| `in_a`, `in_b` | in | `8*LANES` | Signed INT8 operands; lane `i` at `[8*i +: 8]` |
| `out_valid` | out | 1 | Output buffer holds a presentable result |
| `out_ready` | in | 1 | Consumer takes the result this cycle if `out_valid` is high |
| `out_data` | out | `32*LANES` | Result; lane `i` at `[32*i +: 32]`, signed INT32 |
| `temp_valid` | in | 1 | Thermal reading is valid |
| `temp_c` | in | 8 | Signed whole degrees Celsius |
| `clear_fault` | in | 1 | Synchronous: clear fault, zero all lane storage, empty output buffer |
| `fault` | out | 1 | Sticky: a duplicated copy disagreed (registered, 1-cycle latency) |
| `therm_state` | out | 2 | Voted thermal state: 0 NORMAL, 1 THROTTLE, 2 STOP, 3 unused (behaves as STOP) |
| `therm_repair` | out | 1 | The three thermal copies do not all agree this cycle |
| `shutdown_req` | out | 1 | `therm_state[1]`: STOP (or the unused code 3) |

Handshakes: a beat transfers on a rising edge where `in_valid && in_ready`
(`in_fire`); a result transfers where `out_valid && out_ready` (`out_fire`).

## 3. Arithmetic

On `in_fire`, for every lane `i`:

```
p_i   = sext32( signed8(in_a[i]) * signed8(in_b[i]) )   // exact 16-bit product
acc_i = (in_first ? 0 : acc_i) + p_i   (mod 2^32)       // wraps, no saturation, no overflow flag
```

If `in_last` is also high, the updated `acc_i` of every lane is loaded into
the output buffer and `out_valid` rises on the next cycle (latency 1).
`in_first && in_last` in one beat is legal (single-term sum). Beats without
`in_first` continue the current sum, including across a previous `in_last`.

The four lanes are independent; lanes are not summed together.

## 4. Handshake and output buffer

```
out_valid = out_valid_q & ~fault_q & ~mismatch
in_ready  = admit & ~fault_q & ~mismatch & ~clear_fault & (~out_valid_q | out_ready)
```

* The buffer holds one result. While it is full and not drained this cycle,
  every beat (not only `in_last` beats) is blocked.
* `in_last` accepted in the same cycle as `out_fire` replaces the result with
  no bubble.
* While `out_valid && !out_ready`, `out_data` is stable (no fault case).
* `out_ready` combinationally affects `in_ready` (documented path).

## 5. Duplicated storage and fault-stop

Each lane stores two copies of the accumulator (`u_acc_a`, `u_acc_b`) and of
the result (`u_res_a`, `u_res_b`). Both copies are updated from their own
stored values with a shared product. `out_data` comes from copy A.

```
mismatch = OR over lanes of (acc_a != acc_b) | (res_a != res_b)   // combinational, always compared
fault_q  <= fault_q | mismatch                                    // sticky
```

* A mismatch immediately (same cycle) forces `out_valid = 0` and
  `in_ready = 0`; from the next cycle `fault` is high and stays high.
* Consequence: an upset in any one copy of accumulator or result storage can
  never cause a wrong `out_data` to be transferred. It causes a stop.
* `clear_fault` (or reset) clears `fault_q` and `out_valid_q` and writes 0
  into both copies of every accumulator and result register. It does not touch
  the thermal state. `in_ready` is low while `clear_fault` is high.
* There is no automatic replay/retry; the host must re-send the work.

## 6. Thermal state machine (TMR)

Three 2-bit copies (`u_thermal.u_copy0/1/2`), bitwise majority vote, the next
state is computed from the voted state and written into all three copies
every cycle (feedback repair). Reset value: STOP in all copies.

Next state (`t` = signed `temp_c`):

| Condition (first match wins) | Next |
|---|---|
| `!temp_valid` or `t >= 95` | STOP |
| voted NORMAL and `t >= 80` | THROTTLE |
| voted NORMAL | NORMAL |
| voted THROTTLE and `t <= 70` | NORMAL |
| voted THROTTLE | THROTTLE |
| voted STOP or 3, `t <= 70` | NORMAL |
| voted STOP or 3 | STOP |

Admission (`admit`):

* NORMAL: every cycle.
* THROTTLE: alternate cycles. A single `phase` flip-flop resets to 0, and is
  forced to 0 whenever the voted state is not THROTTLE; in THROTTLE it
  toggles every cycle. `admit = ~phase`. The first THROTTLE cycle admits.
* STOP / 3: never. The output buffer can still drain while stopped.

`therm_repair = (c0 != c1) | (c1 != c2)`. A single upset copy is outvoted
immediately and rewritten at the next edge.

## 7. Storage map (for audits and fault injection)

Hierarchical names below are the iverilog/Verilator paths from a testbench
instance named `dut`.

| Group | Instances | Bits | Protection |
|---|---|---|---|
| Accumulator pair, lane i (x4) | `dut.g_lane[i].u_lane.u_acc_a.q`, `...u_acc_b.q` | 2x32 each | duplicate + compare |
| Result pair, lane i (x4) | `dut.g_lane[i].u_lane.u_res_a.q`, `...u_res_b.q` | 2x32 each | duplicate + compare |
| Thermal state | `dut.u_thermal.u_copy0/1/2.q` | 3x2 | TMR + repair |
| Throttle phase | `dut.u_thermal.phase` | 1 | none |
| Output valid | `dut.out_valid_q` | 1 | none |
| Fault latch | `dut.fault_q` | 1 | none |

Total: 256 + 256 + 6 + 3 = **521 flip-flop bits**, of which 518 are in the
nine audited redundant groups (4 accumulator pairs, 4 result pairs, 1 thermal
triple).

Fault injection in simulation must flip a stored bit away from the active
clock edge (e.g. at the falling edge); an assignment in the same time step as
the rising edge races the register update.

## 8. Known unprotected elements (expected fault-injection escapes)

These are deliberate limitations of the brief's demonstrator. Campaigns
should measure and report them, not hide them.

* `out_valid_q`: a 1->0 upset drops a result; 0->1 re-presents a stale result.
* `fault_q`: a 1->0 upset re-enables a stopped design (copies may still
  disagree, in which case `mismatch` keeps it stopped combinationally).
* `phase`: shifts or doubles one throttled admission.
* The shared multiplier, the comparators, the voter, clock, reset, sensor
  inputs and handshake inputs.
* A common-mode fault that corrupts both copies identically.

## 9. Claims from the brief that this repository must check

1. Four signed INT8 MAC lanes with INT32 accumulation; signed edge cases
   (-128 x -128, 127 x -128, ...).
2. One-result output buffer with backpressure.
3. Duplicate accumulator / result storage with mismatch fault-stop.
4. Three-copy thermal state with feedback repair; throttle from 80 C
   (alternate-cycle admission), stop at 95 C or invalid sensor, recovery at
   70 C.
5. INT32 wraparound; no saturation or overflow alarm.
6. Synthesis keeps every redundant copy in distinct flip-flops (nine groups).
7. Faults are injected only into generated test copies or from the testbench;
   the production RTL has no fault ports.
