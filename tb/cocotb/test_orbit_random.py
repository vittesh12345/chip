"""Constrained-random cocotb test of orbit_demo against orbit_ref.OrbitRef.

Every cycle the test drives random inputs, then compares in_ready, out_valid,
out_data, therm_state, shutdown_req, fault and therm_repair with the golden
model, and checks every result transfer against a scoreboard of results the
model loaded into the output buffer. Functional coverage of interesting events
is counted and required to be non-zero.

Tests (selected by the runner, run_random.py):
  random_workload  random in_valid / out_ready, random temperatures covering
                   every thermal transition and invalid readings, random
                   first/last patterns, occasional clear_fault and reset.
  wrap_soak        long accumulation biased towards extreme products so that
                   the INT32 sums wrap in both directions (needs > 131072 beats).

Environment (set by run_random.py):
  SIM_SEED            seed of this run's stimulus generator
  SIM_CYCLES          cycles for random_workload (default 20000)
  SIM_SOAK_MAX        cycle limit for wrap_soak (default 400000)
  SIM_COV_FILE        where to write the coverage / result JSON

Timing: inputs are written just after the rising edge, outputs are sampled at
the falling edge (all combinational paths settled), and the model advances
once per cycle.
"""

import collections
import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from orbit_ref import (LANES, NORMAL, STOP, STATE_NAMES, THROTTLE, Inputs,
                       OrbitRef, lane32, pack8, s8)

INPUT_PORTS = ("rst_n", "in_valid", "in_first", "in_last", "in_a", "in_b",
               "out_ready", "temp_valid", "temp_c", "clear_fault")
OUTPUT_PORTS = ("in_ready", "out_valid", "out_data", "therm_state",
                "shutdown_req", "fault", "therm_repair")

# Coverage points that must be hit (count > 0) by each test.
REQUIRED = {
    "random_workload": [
        "in_fire", "out_fire", "single_beat_sums", "multi_beat_sums",
        "continue_after_last", "first_restarts_sum",
        "throttle_entry", "stop_by_temp", "stop_by_invalid",
        "recover_from_throttle", "recover_from_stop",
        "throttle_hysteresis_hold", "stop_hysteresis_hold", "normal_at_71_79",
        "normal_hold_at_79", "throttle_at_80", "throttle_hold_at_94", "stop_at_95",
        "throttle_hold_at_71", "stop_hold_at_71", "recover_at_70_from_throttle",
        "recover_at_70_from_stop",
        "negative_temp_cycles", "throttle_admit", "throttle_phase_block",
        "stop_blocked", "drain_in_stop", "backpressure_cycles",
        "buffer_full_blocks_last", "buffer_full_blocks_nonlast", "back_to_back",
        "clear_fault_cycles", "clear_dropped_result", "prod_min_min", "prod_max_min",
    ],
    "wrap_soak": ["in_fire", "out_fire", "wrap_pos", "wrap_neg", "back_to_back"],
}

MAX_REPORTED = 10     # mismatches printed in detail
MAX_ERRORS = 25       # stop the run after this many errors


# ---------------------------------------------------------------------------
# Stimulus
# ---------------------------------------------------------------------------
EXTREMES = (-128, -127, -1, 0, 1, 126, 127)

# (name, weight, valid, generator of one reading); "ramp" (generator None) is
# a slow drift of 1 C every few cycles, turning at a random low point in 50..69
# and a random high point in 81..100, so it crosses every threshold exactly and
# in every state, like a real die temperature would.
TEMP_REGIMES = [
    ("ramp",          15, 1, None),
    ("cool",          45, 1, lambda r: r.randint(0, 70)),
    ("negative",       5, 1, lambda r: r.randint(-128, -1)),
    ("recover_edge",   6, 1, lambda r: r.choice((69, 70, 70, 71))),
    ("warm",           7, 1, lambda r: r.randint(71, 79)),
    ("throttle_edge",  6, 1, lambda r: r.choice((79, 80, 80, 81))),
    ("hot",           12, 1, lambda r: r.randint(80, 94)),
    ("stop_edge",      4, 1, lambda r: r.choice((94, 95, 95, 96))),
    ("critical",       3, 1, lambda r: r.randint(95, 127)),
    ("invalid",        4, 0, lambda r: r.randint(-128, 127)),
    ("wild",           3, 1, lambda r: r.randint(-128, 127)),
]


class RandomWorkload:
    """Per-cycle random inputs for random_workload.

    A beat that is offered and not accepted is normally held unchanged
    (valid/ready convention); with a small probability it is withdrawn or
    replaced, which the SPEC allows and the DUT must handle.
    """

    def __init__(self, rng):
        self.r = rng
        self.pending = None           # (first, last, a, b) currently offered
        self.sum_left = 0
        self.sum_first = True
        self.p_valid = 1.0
        self.p_ready = 1.0
        self.epoch_left = 0
        self.regime = TEMP_REGIMES[0]
        self.regime_left = 0
        self.ramp_t = 70
        self.ramp_dir = 1
        self.ramp_period = 1
        self.ramp_count = 0
        self.ramp_lo, self.ramp_hi = 55, 100
        self.clear_left = 0
        self.reset_left = 0

    def _operand(self):
        x = self.r.random()
        if x < 0.5:
            return self.r.randint(-128, 127)
        if x < 0.8:
            return self.r.choice(EXTREMES)
        return self.r.randint(-4, 4)

    def _new_beat(self):
        r = self.r
        if self.sum_left == 0:
            x = r.random()
            if x < 0.3:
                self.sum_left = 1
            elif x < 0.6:
                self.sum_left = r.randint(2, 4)
            elif x < 0.85:
                self.sum_left = r.randint(5, 20)
            else:
                self.sum_left = r.randint(21, 100)
            self.sum_first = r.random() < 0.85    # else continue the previous sum
            first = self.sum_first
        else:
            first = r.random() < 0.01             # occasional restart mid-sum
        self.sum_left -= 1
        last = self.sum_left == 0 or r.random() < 0.03   # occasional early result
        a = pack8([self._operand() for _ in range(LANES)])
        b = pack8([self._operand() for _ in range(LANES)])
        return (int(first), int(last), a, b)

    def _temperature(self):
        r = self.r
        if self.regime_left == 0:
            self.regime = r.choices(TEMP_REGIMES, weights=[g[1] for g in TEMP_REGIMES])[0]
            x = r.random()
            self.regime_left = (r.randint(1, 5) if x < 0.3 else
                                r.randint(5, 60) if x < 0.7 else r.randint(60, 400))
            if self.regime[3] is None:
                self.ramp_lo, self.ramp_hi = r.randint(50, 69), r.randint(81, 100)
                self.ramp_t = r.randint(self.ramp_lo, self.ramp_hi)
                self.ramp_dir = r.choice((-1, 1))
                self.ramp_period = r.randint(1, 4)
                self.regime_left = r.randint(100, 500)
        self.regime_left -= 1
        _name, _w, valid, gen = self.regime
        if gen is None:
            self.ramp_count += 1
            if self.ramp_count >= self.ramp_period:
                self.ramp_count = 0
                self.ramp_t += self.ramp_dir
                if not self.ramp_lo < self.ramp_t < self.ramp_hi:
                    self.ramp_dir = -self.ramp_dir
            gen = lambda _r: self.ramp_t                 # noqa: E731
        if valid and r.random() < 0.002:          # single-cycle sensor dropout
            return 0, gen(r) & 0xFF
        return valid, gen(r) & 0xFF

    def next(self, accepted):
        r = self.r
        inp = Inputs()
        if self.epoch_left == 0:
            self.epoch_left = r.randint(20, 500)
            self.p_valid = r.choice((0.2, 0.6, 0.9, 1.0, 1.0))
            self.p_ready = r.choice((1.0, 1.0, 0.9, 0.6, 0.3, 0.02))
        self.epoch_left -= 1

        if accepted:
            self.pending = None
        elif self.pending is not None and r.random() < 0.02:
            self.pending = None if r.random() < 0.5 else self._new_beat()
        if self.pending is None and r.random() < self.p_valid:
            self.pending = self._new_beat()
        if self.pending is not None:
            inp.in_valid = 1
            inp.in_first, inp.in_last, inp.in_a, inp.in_b = self.pending
        else:
            inp.in_valid = 0
            inp.in_first = r.getrandbits(1)       # don't-care values while idle
            inp.in_last = r.getrandbits(1)
            inp.in_a = r.getrandbits(8 * LANES)
            inp.in_b = r.getrandbits(8 * LANES)

        inp.out_ready = int(r.random() < self.p_ready)
        inp.temp_valid, inp.temp_c = self._temperature()

        if self.clear_left == 0 and r.random() < 0.003:
            self.clear_left = r.randint(1, 3)
        inp.clear_fault = int(self.clear_left > 0)
        self.clear_left = max(0, self.clear_left - 1)

        if self.reset_left == 0 and r.random() < 0.00005:
            self.reset_left = r.randint(1, 3)
        inp.rst_n = int(self.reset_left == 0)
        self.reset_left = max(0, self.reset_left - 1)
        return inp


class SoakWorkload:
    """Long accumulation for wrap_soak: in_first only on the first beat, no
    clear_fault, products biased so lane 0 and 2 drift up and lane 1 and 3
    drift down; temperature mostly cool with short throttle excursions."""

    def __init__(self, rng):
        self.r = rng
        self.pending = None
        self.first_sent = False
        self.hot_left = 0

    def _lane(self, direction):
        r = self.r
        if r.random() < 0.9:
            if direction > 0:
                return r.choice(((-128, -128), (127, 127), (-128, -127)))
            return r.choice(((-128, 127), (127, -128), (-127, 127)))
        return (r.randint(-128, 127), r.randint(-128, 127))

    def next(self, accepted):
        r = self.r
        inp = Inputs()
        if accepted:
            self.pending = None
        if self.pending is None:
            ops = [self._lane(+1), self._lane(-1), self._lane(+1), self._lane(-1)]
            first = 0 if self.first_sent else 1
            self.first_sent = True
            last = int(r.random() < 0.02)
            self.pending = (first, last, pack8([o[0] for o in ops]), pack8([o[1] for o in ops]))
        inp.in_valid = 1
        inp.in_first, inp.in_last, inp.in_a, inp.in_b = self.pending
        inp.out_ready = int(r.random() < 0.9)
        if self.hot_left == 0 and r.random() < 0.001:
            self.hot_left = r.randint(5, 40)
        if self.hot_left:
            self.hot_left -= 1
            inp.temp_valid, inp.temp_c = 1, r.randint(80, 90)
        else:
            inp.temp_valid, inp.temp_c = 1, r.randint(20, 70)
        return inp


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
class Harness:
    def __init__(self, dut, name):
        self.dut = dut
        self.name = name
        self.log = dut._log
        self.h_in = {p: getattr(dut, p) for p in INPUT_PORTS}
        self.h_out = {p: getattr(dut, p) for p in OUTPUT_PORTS}
        self.last_written = {}
        self.ref = OrbitRef()
        self.cov = collections.Counter()
        self.errors = 0
        self.reported = 0
        self.history = collections.deque(maxlen=6)
        self.expected = collections.deque()      # results loaded, not yet transferred
        self.prev_fire_last = False
        self.cycle = 0

    def drive(self, inp):
        for p in INPUT_PORTS:
            v = getattr(inp, p)
            if self.last_written.get(p) != v:
                self.h_in[p].value = v
                self.last_written[p] = v

    def sample(self):
        out = {}
        for p, h in self.h_out.items():
            try:
                out[p] = int(h.value)
            except ValueError:                     # X or Z
                out[p] = None
        return out

    def error(self, msg):
        self.errors += 1
        if self.reported < MAX_REPORTED:
            self.reported += 1
            self.log.error("cycle %d: %s", self.cycle, msg)
            for c, inp in self.history:
                self.log.error("    history cycle %d: %s", c, inp)

    def check_cycle(self, inp, got):
        want = self.ref.outputs(inp)
        for p in OUTPUT_PORTS:
            w = getattr(want, p)
            if got[p] != w:
                if p == "out_data" and got[p] is not None:
                    detail = " ".join(
                        f"lane{i}:{lane32(got[p], i):08x}/{lane32(w, i):08x}" for i in range(LANES))
                    self.error(f"{p} got/want {detail}")
                elif p == "therm_state":
                    self.error(f"therm_state got {got[p]} want {STATE_NAMES[w]}")
                else:
                    self.error(f"{p} got {got[p]} want {w}")
        return want

    def cover(self, inp, want, ev):
        c = self.cov
        c["cycles"] += 1
        if ev.reset:
            c["reset_cycles"] += 1
            self.prev_fire_last = False
            return
        sb, sa = ev.state_before, ev.state_after
        t = s8(inp.temp_c)
        if sb != sa:
            if sa == THROTTLE:
                c["throttle_entry"] += 1
            elif sa == STOP:
                c["stop_by_temp" if inp.temp_valid else "stop_by_invalid"] += 1
            elif sa == NORMAL:
                c["recover_from_throttle" if sb == THROTTLE else "recover_from_stop"] += 1
        if inp.temp_valid:
            if t < 0:
                c["negative_temp_cycles"] += 1
            if sb == THROTTLE and 71 <= t <= 79:
                c["throttle_hysteresis_hold"] += 1
            if sb == STOP and 71 <= t <= 94:
                c["stop_hysteresis_hold"] += 1
            if sb == NORMAL and 71 <= t <= 79:
                c["normal_at_71_79"] += 1
            # exact threshold values, in the state where they matter
            if sb == NORMAL and t == 79:
                c["normal_hold_at_79"] += 1
            if sb == NORMAL and t == 80:
                c["throttle_at_80"] += 1
            if sb == THROTTLE and t == 94:
                c["throttle_hold_at_94"] += 1
            if sb != STOP and t == 95:
                c["stop_at_95"] += 1
            if sb == THROTTLE and t == 71:
                c["throttle_hold_at_71"] += 1
            if sb == STOP and t == 71:
                c["stop_hold_at_71"] += 1
            if sb == THROTTLE and t == 70:
                c["recover_at_70_from_throttle"] += 1
            if sb == STOP and t == 70:
                c["recover_at_70_from_stop"] += 1
        else:
            c["invalid_sensor_cycles"] += 1
        if inp.in_valid:
            if sb == THROTTLE:
                if ev.in_fire:
                    c["throttle_admit"] += 1
                elif ev.phase_before:
                    c["throttle_phase_block"] += 1
            elif sb >= STOP:
                c["stop_blocked"] += 1
            admit = sb == NORMAL or (sb == THROTTLE and not ev.phase_before)
            if admit and ev.out_valid_before and not inp.out_ready and not inp.clear_fault:
                c["buffer_full_blocks_last" if inp.in_last else "buffer_full_blocks_nonlast"] += 1
        if want.out_valid and not inp.out_ready:
            c["backpressure_cycles"] += 1
        if ev.out_fire:
            c["out_fire"] += 1
            if sb >= STOP:
                c["drain_in_stop"] += 1
        if inp.clear_fault:
            c["clear_fault_cycles"] += 1
            if ev.dropped:
                c["clear_dropped_result"] += 1
            if ev.out_fire:
                c["clear_with_transfer"] += 1
        if ev.in_fire:
            c["in_fire"] += 1
            if inp.in_first and inp.in_last:
                c["single_beat_sums"] += 1
            elif inp.in_last:
                c["multi_beat_sums"] += 1
            if not inp.in_first and self.prev_fire_last:
                c["continue_after_last"] += 1
            if inp.in_first and not self.prev_fire_last:
                c["first_restarts_sum"] += 1
            if inp.in_last and ev.out_fire:
                c["back_to_back"] += 1
            for i in range(LANES):
                a, b = s8(inp.in_a >> (8 * i)), s8(inp.in_b >> (8 * i))
                if a == -128 and b == -128:
                    c["prod_min_min"] += 1
                elif (a, b) in ((127, -128), (-128, 127)):
                    c["prod_max_min"] += 1
            self.prev_fire_last = bool(inp.in_last)
        c["wrap_pos"] += ev.wrap_pos
        c["wrap_neg"] += ev.wrap_neg

    def scoreboard(self, inp, got, ev):
        dut_out_fire = got["out_valid"] == 1 and inp.out_ready == 1
        if dut_out_fire:
            if not self.expected:
                self.error("result transferred but none expected")
            else:
                want = self.expected.popleft()
                if got["out_data"] != want:
                    g = "X" if got["out_data"] is None else f"{got['out_data']:#034x}"
                    self.error(f"transferred result {g} differs from scoreboard {want:#034x}")
                self.cov["results_checked"] += 1
        if ev.reset or inp.clear_fault:
            self.expected.clear()
        if ev.result is not None:
            self.expected.append(ev.result)
        if len(self.expected) > 1:
            self.error("more than one result waiting in a one-result buffer")

    async def run(self, workload, cycles, stop_when=None):
        dut = self.dut
        # Reset for three edges; the model starts at the first reset edge.
        inp = Inputs(rst_n=0, temp_valid=1, temp_c=25, out_ready=1)
        self.drive(inp)
        await RisingEdge(dut.clk)
        self.ref.reset()
        accepted = False
        extra = None
        for cyc in range(cycles):
            self.cycle = cyc
            inp = workload.next(accepted) if cyc >= 2 else Inputs(rst_n=0, temp_valid=1, temp_c=25)
            self.drive(inp)
            await FallingEdge(dut.clk)
            got = self.sample()
            want = self.check_cycle(inp, got)
            ev = self.ref.step(inp)
            self.scoreboard(inp, got, ev)
            self.cover(inp, want, ev)
            self.history.append((cyc, inp))
            accepted = ev.in_fire
            if self.errors >= MAX_ERRORS:
                self.log.error("stopping after %d errors", self.errors)
                break
            if stop_when is not None and extra is None and stop_when(self.cov):
                extra = 500                          # a little more after the goal
            if extra is not None:
                extra -= 1
                if extra == 0:
                    break
            await RisingEdge(dut.clk)
        return self.cycle + 1


def write_report(name, seed, harness, cycles):
    missing = [k for k in REQUIRED[name] if harness.cov.get(k, 0) == 0]
    report = {
        "test": name,
        "seed": seed,
        "cycles": cycles,
        "errors": harness.errors,
        "coverage": dict(sorted(harness.cov.items())),
        "required": REQUIRED[name],
        "missing_coverage": missing,
    }
    path = os.environ.get("SIM_COV_FILE")
    if path:
        with open(path, "w") as f:
            json.dump(report, f, indent=1, sort_keys=True)
    return missing


async def _run(dut, name, workload_cls, cycles, stop_when=None):
    seed = int(os.environ.get("SIM_SEED", cocotb.RANDOM_SEED))
    rng = random.Random(seed)
    Clock(dut.clk, 10, unit="ns").start(start_high=False)
    h = Harness(dut, name)
    done = await h.run(workload_cls(rng), cycles, stop_when)
    missing = write_report(name, seed, h, done)
    dut._log.info("%s seed %d: %d cycles, %d errors, coverage %s",
                  name, seed, done, h.errors, dict(sorted(h.cov.items())))
    assert h.errors == 0, f"{h.errors} mismatches against the reference model"
    assert not missing, f"coverage points never hit: {missing}"


@cocotb.test()
async def random_workload(dut):
    """Random traffic, thermal and control stimulus, checked every cycle."""
    await _run(dut, "random_workload", RandomWorkload, int(os.environ.get("SIM_CYCLES", "20000")))


@cocotb.test()
async def wrap_soak(dut):
    """Accumulate long enough for INT32 wraparound in both directions."""
    await _run(dut, "wrap_soak", SoakWorkload, int(os.environ.get("SIM_SOAK_MAX", "400000")),
               stop_when=lambda cov: cov["wrap_pos"] > 0 and cov["wrap_neg"] > 0)
