"""Golden reference model of orbit_demo, written from docs/SPEC.md.

This model is deliberately independent of the RTL: it follows the SPEC text
(sections 2-6) with plain Python integers, and is cycle based.

    ref = OrbitRef()
    out = ref.outputs(inp)      # combinational outputs for the current inputs
    ev  = ref.step(inp)         # advance one rising edge; returns what happened

Fault-free operation only: the duplicated copies never disagree here, so
``mismatch`` is always 0 and ``fault`` can only be cleared, never set. (The
fault-injection area models upsets separately.)

Running this file directly executes a small self-test of the model against
hand-computed SPEC examples (no simulator needed).
"""

from dataclasses import dataclass

LANES = 4
T_THROTTLE = 80
T_STOP = 95
T_RECOVER = 70

NORMAL, THROTTLE, STOP = 0, 1, 2
STATE_NAMES = {0: "NORMAL", 1: "THROTTLE", 2: "STOP", 3: "UNUSED3"}

MASK32 = 0xFFFF_FFFF
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1


def s8(x):
    """Interpret the low 8 bits of x as a signed INT8."""
    x &= 0xFF
    return x - 0x100 if x & 0x80 else x


def s32(x):
    """Interpret the low 32 bits of x as a signed INT32."""
    x &= MASK32
    return x - (1 << 32) if x & 0x8000_0000 else x


def lane8(v, i):
    """Signed INT8 operand of lane i from a packed 8*LANES-bit bus."""
    return s8(v >> (8 * i))


def lane32(v, i):
    """Unsigned 32-bit field of lane i from a packed 32*LANES-bit bus."""
    return (v >> (32 * i)) & MASK32


def pack32(values):
    """Pack LANES 32-bit values (lane 0 in the low bits)."""
    word = 0
    for i, v in enumerate(values):
        word |= (v & MASK32) << (32 * i)
    return word


def pack8(values):
    """Pack LANES signed INT8 values (lane 0 in the low bits)."""
    word = 0
    for i, v in enumerate(values):
        word |= (v & 0xFF) << (8 * i)
    return word


def therm_next(state, temp_valid, temp_c):
    """SPEC section 6 next-state table (first match wins)."""
    t = s8(temp_c)
    if not temp_valid or t >= T_STOP:
        return STOP
    if state == NORMAL:
        return THROTTLE if t >= T_THROTTLE else NORMAL
    if state == THROTTLE:
        return NORMAL if t <= T_RECOVER else THROTTLE
    # STOP, or the unused code 3 which behaves as STOP
    return NORMAL if t <= T_RECOVER else STOP


@dataclass
class Inputs:
    """Values of the orbit_demo input ports during one clock cycle."""
    rst_n: int = 1
    in_valid: int = 0
    in_first: int = 0
    in_last: int = 0
    in_a: int = 0
    in_b: int = 0
    out_ready: int = 0
    temp_valid: int = 1
    temp_c: int = 25
    clear_fault: int = 0


@dataclass
class Outputs:
    in_ready: int
    out_valid: int
    out_data: int
    therm_state: int
    shutdown_req: int
    fault: int
    therm_repair: int


@dataclass
class Events:
    """What happened at one rising edge (used for scoreboarding and coverage)."""
    reset: bool = False
    in_fire: bool = False
    out_fire: bool = False
    result: int = None            # packed result loaded into the buffer, if any
    wrap_pos: int = 0             # lanes whose sum overflowed above INT32_MAX
    wrap_neg: int = 0             # lanes whose sum overflowed below INT32_MIN
    state_before: int = STOP
    state_after: int = STOP
    phase_before: int = 0
    out_valid_before: int = 0
    dropped: bool = False         # a presented result was discarded by clear_fault


class OrbitRef:
    """Cycle-accurate model of orbit_demo per docs/SPEC.md."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.acc = [0] * LANES          # unsigned 32-bit images
        self.res = [0] * LANES
        self.out_valid_q = 0
        self.fault_q = 0
        self.state = STOP               # reset value: STOP in all three copies
        self.phase = 0

    # ---- combinational view -------------------------------------------------
    def admit(self):
        if self.state == NORMAL:
            return 1
        if self.state == THROTTLE:
            return 1 - self.phase       # admit = ~phase
        return 0                        # STOP and unused code 3

    def outputs(self, inp):
        mismatch = 0                    # fault-free: copies always agree
        in_ready = (self.admit() and not self.fault_q and not mismatch and
                    not inp.clear_fault and (not self.out_valid_q or inp.out_ready))
        out_valid = self.out_valid_q and not self.fault_q and not mismatch
        return Outputs(
            in_ready=int(bool(in_ready)),
            out_valid=int(bool(out_valid)),
            out_data=pack32(self.res),
            therm_state=self.state,
            shutdown_req=(self.state >> 1) & 1,
            fault=self.fault_q,
            therm_repair=0,
        )

    # ---- clock edge -----------------------------------------------------------
    def step(self, inp):
        ev = Events(state_before=self.state, phase_before=self.phase,
                    out_valid_before=self.out_valid_q)
        if not inp.rst_n:
            self.reset()
            ev.reset = True
            ev.state_after = self.state
            return ev

        o = self.outputs(inp)
        in_fire = bool(inp.in_valid and o.in_ready)
        out_fire = bool(o.out_valid and inp.out_ready)
        ev.in_fire, ev.out_fire = in_fire, out_fire

        nstate = therm_next(self.state, inp.temp_valid, inp.temp_c)
        nphase = (1 - self.phase) if self.state == THROTTLE else 0

        if inp.clear_fault:
            # Zero both copies of every accumulator and result, empty the buffer.
            ev.dropped = bool(self.out_valid_q and not out_fire)
            self.acc = [0] * LANES
            self.res = [0] * LANES
            self.out_valid_q = 0
            self.fault_q = 0
        else:
            if in_fire:
                for i in range(LANES):
                    p = lane8(inp.in_a, i) * lane8(inp.in_b, i)     # exact 16-bit product
                    base = 0 if inp.in_first else s32(self.acc[i])
                    total = base + p                                  # mathematical sum
                    if total > INT32_MAX:
                        ev.wrap_pos += 1
                    elif total < INT32_MIN:
                        ev.wrap_neg += 1
                    self.acc[i] = total & MASK32                      # wraps mod 2^32
                if inp.in_last:
                    self.res = list(self.acc)
                    ev.result = pack32(self.res)
            if in_fire and inp.in_last:
                self.out_valid_q = 1
            elif out_fire:
                self.out_valid_q = 0

        self.state = nstate
        self.phase = nphase
        ev.state_after = nstate
        return ev


# ---- self-test ----------------------------------------------------------------
def _selftest():
    ok = 0

    def check(cond, what):
        nonlocal ok
        if not cond:
            raise AssertionError(what)
        ok += 1

    # Products (SPEC section 9 claim 1)
    for a, b, p in [(-128, -128, 16384), (127, -128, -16256), (-128, 127, -16256),
                    (127, 127, 16129), (-1, -1, 1), (0, -128, 0), (-1, 127, -127)]:
        check(s8(a & 0xFF) * s8(b & 0xFF) == p, f"product {a}*{b}")

    # Thermal table, including hysteresis, signed temperatures and invalid sensor
    table = [
        (NORMAL, 1, 79, NORMAL), (NORMAL, 1, 80, THROTTLE), (NORMAL, 1, 94, THROTTLE),
        (NORMAL, 1, 95, STOP), (NORMAL, 0, 20, STOP), (NORMAL, 1, -40, NORMAL),
        (THROTTLE, 1, 71, THROTTLE), (THROTTLE, 1, 70, NORMAL), (THROTTLE, 1, 95, STOP),
        (THROTTLE, 0, 60, STOP), (THROTTLE, 1, -1, NORMAL),
        (STOP, 1, 71, STOP), (STOP, 1, 80, STOP), (STOP, 1, 70, NORMAL),
        (STOP, 0, 20, STOP), (STOP, 1, -128, NORMAL), (3, 1, 70, NORMAL), (3, 1, 71, STOP),
    ]
    for st, v, t, want in table:
        check(therm_next(st, v, t & 0xFF) == want, f"therm_next({st},{v},{t})")

    # Reset: STOP, nothing admitted; recovery at 70 C; throttle alternates from admit
    m = OrbitRef()
    inp = Inputs(rst_n=1, in_valid=1, in_first=1, in_last=1, out_ready=1, temp_valid=1, temp_c=71)
    check(m.outputs(inp).in_ready == 0 and m.outputs(inp).shutdown_req == 1, "reset STOP")
    m.step(inp)
    check(m.state == STOP, "71 C keeps STOP")
    inp.temp_c = 70
    m.step(inp)
    check(m.state == NORMAL and m.outputs(inp).in_ready == 1, "70 C recovers")
    inp.temp_c = 80
    m.step(inp)                              # accepted in NORMAL; now THROTTLE
    adm = []
    for _ in range(6):
        adm.append(m.outputs(inp).in_ready)
        m.step(inp)
    check(adm == [1, 0, 1, 0, 1, 0], "alternate-cycle admission starting with admit")

    # Wraparound both directions, no saturation
    m = OrbitRef()
    m.state = NORMAL
    m.acc = [INT32_MAX & MASK32, INT32_MIN & MASK32, 0, 0]
    ev = m.step(Inputs(in_valid=1, in_first=0, in_last=1, out_ready=1,
                       in_a=pack8([1, 1, 0, 0]), in_b=pack8([1, -1, 0, 0])))
    check(m.res[0] == 0x8000_0000 and m.res[1] == 0x7FFF_FFFF, "wrap values")
    check(ev.wrap_pos == 1 and ev.wrap_neg == 1, "wrap events")

    # Backpressure: full buffer blocks every beat; drain + in_last replaces with no bubble
    m = OrbitRef()
    m.state = NORMAL
    inp = Inputs(in_valid=1, in_first=1, in_last=1, out_ready=0, in_a=pack8([2] * 4), in_b=pack8([3] * 4))
    m.step(inp)
    inp.in_last = 0
    check(m.outputs(inp).in_ready == 0 and m.outputs(inp).out_valid == 1, "full buffer blocks non-last beat")
    inp.out_ready = 1
    inp.in_last = 1
    check(m.outputs(inp).in_ready == 1, "out_ready opens in_ready")
    ev = m.step(inp)
    check(ev.in_fire and ev.out_fire and m.out_valid_q == 1, "no bubble")

    # clear_fault: in_ready low, sums zeroed, buffer emptied, thermal untouched
    inp = Inputs(in_valid=1, in_first=0, in_last=1, out_ready=0, clear_fault=1,
                 in_a=pack8([5] * 4), in_b=pack8([5] * 4))
    check(m.outputs(inp).in_ready == 0, "clear holds in_ready low")
    st = m.state
    ev = m.step(inp)
    check(ev.dropped and m.out_valid_q == 0 and m.acc == [0] * 4 and m.res == [0] * 4, "clear zeroes")
    check(m.state == st, "clear keeps thermal state")
    inp.clear_fault = 0
    m.step(inp)
    check(m.res == [25] * 4, "sum after clear starts from zero")
    return ok


if __name__ == "__main__":
    n = _selftest()
    print(f"orbit_ref self-test PASS ({n} checks)")
