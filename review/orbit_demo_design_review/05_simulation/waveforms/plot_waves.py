#!/usr/bin/env python3
"""Render timing diagrams and per-cycle CSV tables from the VCDs written by
tb_orbit_wave.v. Every plotted value is read from the VCD; nothing is drawn
from expectations. Markers are placed at value changes found in the VCD.

usage: plot_waves.py [wave-dir]        (default: this script's directory)
outputs: wave_<name>.png, wave_<name>.csv, orbit_demo_waveforms.pdf
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

INK = "#0b0b0b"        # traces and values
INK2 = "#52514e"       # labels, axis text
GRID = "#d9d8d4"       # cycle grid
ACCENT = "#2a78d6"     # event markers (always with a text label)
SURFACE = "#ffffff"

PERIOD_PS = 10000      # 10 ns clock (tb_orbit_wave.v HALF = 5)
SKEW_PS = 1000         # outputs sampled 1 ns before the rising edge


# ---------------------------------------------------------------- VCD parsing
class Vcd:
    def __init__(self, path):
        self.path = path
        self.timescale = None
        self.vars = {}      # full name -> (id, width)
        self.changes = {}   # id -> [(t, value-string)]
        self.end = 0
        self._parse()

    def _parse(self):
        scope = []
        t = 0
        with open(self.path) as f:
            toks = f.read().split()
        i = 0
        n = len(toks)
        while i < n:
            tok = toks[i]
            if tok == "$timescale":
                j = toks.index("$end", i)
                self.timescale = "".join(toks[i + 1:j])
                i = j + 1
            elif tok == "$scope":
                scope.append(toks[i + 2])
                i = toks.index("$end", i) + 1
            elif tok == "$upscope":
                scope.pop()
                i = toks.index("$end", i) + 1
            elif tok == "$var":
                j = toks.index("$end", i)
                width, ident, name = int(toks[i + 2]), toks[i + 3], toks[i + 4]
                full = ".".join(scope + [name])
                self.vars[full] = (ident, width)
                self.changes.setdefault(ident, [])
                i = j + 1
            elif tok in ("$date", "$version", "$comment"):
                i = toks.index("$end", i) + 1
            elif tok in ("$dumpvars", "$dumpall", "$dumpon", "$dumpoff", "$end", "$enddefinitions"):
                i += 1
            elif tok[0] == "#":
                t = int(tok[1:])
                self.end = max(self.end, t)
                i += 1
            elif tok[0] in "bBrR":
                val, ident = tok[1:], toks[i + 1]
                self._add(ident, t, val)
                i += 2
            elif tok[0] in "01xXzZ":
                self._add(tok[1:], t, tok[0])
                i += 1
            else:
                i += 1

    def _add(self, ident, t, val):
        lst = self.changes.setdefault(ident, [])
        if lst and lst[-1][0] == t:
            lst[-1] = (t, val)          # last value in a time step wins
        else:
            lst.append((t, val))

    def series(self, name):
        if name not in self.vars:
            raise KeyError(f"{name} not in {self.path}")
        ident, width = self.vars[name]
        out = []
        for t, v in self.changes[ident]:
            v = v.lower()
            if any(c in v for c in "xz"):
                out.append((t, None))
            else:
                out.append((t, int(v, 2)))
        # drop repeats
        ded = []
        for t, v in out:
            if not ded or ded[-1][1] != v:
                ded.append((t, v))
        return ded, width

    def value_at(self, name, t):
        s, _ = self.series(name)
        v = None
        for tt, vv in s:
            if tt <= t:
                v = vv
            else:
                break
        return v

    def rises(self, name):
        s, _ = self.series(name)
        return [t for (t, v), (_, pv) in zip(s[1:], s[:-1]) if v == 1 and pv == 0]

    def changes_of(self, name):
        s, _ = self.series(name)
        return [t for t, _ in s[1:]]


# ---------------------------------------------------------------- formatting
def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def s8(v):
    return v - 256 if v & 0x80 else v


def fmt_i32(v):
    return f"{s32(v)}"


def fmt_i32hex(v):
    return f"{s32(v)} (0x{v:08X})"


def fmt_i8x4(v):
    lanes = [s8((v >> (8 * k)) & 0xFF) for k in range(4)]
    return ",".join(str(x) for x in lanes)


def fmt_bin(width):
    return lambda v: format(v, f"0{width}b")


def fmt_therm(v):
    return {0: "NORMAL", 1: "THROTTLE", 2: "STOP", 3: "3 (unused)"}.get(v, str(v))


def fmt_dec(v):
    return str(v)


def fmt_temp(v):
    return str(s8(v))


T = "tb_orbit_wave."
D = T + "dut."


# ---------------------------------------------------------------- drawing
MONO_W = 0.60          # DejaVu Sans Mono advance width / font size


def _fit_label(txt, width_in, sizes=(6.3, 5.6, 5.0)):
    """Return (text, fontsize) that fits width_in inches, trying a two-line
    split at the middle comma; None if nothing fits."""
    for fs in sizes:
        if len(txt) * MONO_W * fs / 72 <= width_in * 0.92:
            return txt, fs
    if "," in txt:
        cut = [i for i, c in enumerate(txt) if c == ","]
        mid = min(cut, key=lambda i: abs(i - len(txt) / 2))
        two = txt[:mid + 1] + "\n" + txt[mid + 1:]
        longest = max(len(x) for x in two.split("\n"))
        for fs in sizes:
            if longest * MONO_W * fs / 72 <= width_in * 0.92:
                return two, fs
    return None, None


def draw(ax, vcd, rows, t0, t1, title, markers=(), grid_every=1):
    """rows: (label, signal, kind, formatter[, height]); kind in bit|bus|analog.
    Every drawn value comes from vcd. grid_every: draw every n-th rising edge."""
    ax.set_facecolor(SURFACE)
    fig = ax.figure
    ax_w_in = ax.get_position().width * fig.get_figwidth()
    span_ns = (t1 - t0) / 1000
    heights = [(r[4] if len(r) > 4 else 1.0) for r in rows]
    ytop = sum(heights)
    e = PERIOD_PS // 2
    k = 0
    while e <= t1:
        if e >= t0 and k % grid_every == 0:
            ax.axvline(e / 1000, color=GRID, lw=0.6, zorder=0)
        e += PERIOD_PS
        k += 1
    ycur = ytop
    for r, row in enumerate(rows):
        label, sig, kind, fmt = row[:4]
        h = heights[r]
        ycur -= h
        base = ycur + 0.2
        hi = ycur + h - 0.2
        mid = (base + hi) / 2
        ax.text(t0 / 1000 - span_ns * 0.008, mid, label, ha="right", va="center",
                fontsize=7, color=INK2, family="monospace")
        s, width = vcd.series(sig)
        pts = []
        cur = None
        for t, v in s:
            if t <= t0:
                cur = v
            elif t < t1:
                if not pts:
                    pts.append((t0, cur))
                pts.append((t, v))
        if not pts:
            pts.append((t0, cur))
        pts.append((t1, pts[-1][1]))
        segs = [(ta, va, tb) for (ta, va), (tb, _) in zip(pts[:-1], pts[1:]) if tb > ta]
        if kind == "bit":
            xs, ys = [], []
            for ta, va, tb in segs:
                if va is None:
                    ax.fill([ta / 1000, tb / 1000, tb / 1000, ta / 1000], [base, base, hi, hi],
                            color=GRID, lw=0)
                    y = mid
                else:
                    y = hi if va else base
                xs += [ta / 1000, tb / 1000]
                ys += [y, y]
            ax.plot(xs, ys, color=INK, lw=1.1, solid_joinstyle="miter")
        elif kind == "bus":
            for ta, va, tb in segs:
                xa, xb = ta / 1000, tb / 1000
                sl = min(span_ns * 0.002, (xb - xa) / 4)
                xs = [xa, xa + sl, xb - sl, xb, xb - sl, xa + sl, xa]
                ys = [mid, hi, hi, mid, base, base, mid]
                ax.plot(xs, ys, color=INK, lw=0.9)
                if va is None:
                    ax.fill(xs, ys, color=GRID, lw=0)
                    txt = "x"
                else:
                    txt = fmt(va)
                w_in = (xb - xa) / span_ns * ax_w_in
                lab, fs = _fit_label(txt, w_in)
                if lab is not None:
                    ax.text((xa + xb) / 2, mid, lab, ha="center", va="center", fontsize=fs,
                            color=INK, family="monospace", linespacing=1.0)
        elif kind == "analog":
            lo_v, hi_v, refs = fmt
            def y_of(v):
                return base + (v - lo_v) / (hi_v - lo_v) * (hi - base)
            for rv, rl in refs:
                yr = y_of(rv)
                ax.plot([t0 / 1000, t1 / 1000], [yr, yr], color=INK2, lw=0.6, ls=(0, (2, 2)))
                ax.text(t1 / 1000 + span_ns * 0.004, yr, rl, fontsize=6, color=INK2,
                        va="center", ha="left")
            xs, ys = [], []
            for ta, va, tb in segs:
                xs += [ta / 1000, tb / 1000]
                ys += [y_of(s8(va)), y_of(s8(va))]
            ax.plot(xs, ys, color=INK, lw=1.1)
            for yv in (lo_v, hi_v):
                ax.text(t0 / 1000 + span_ns * 0.002, y_of(yv), f"{yv}", fontsize=5.5, color=INK2,
                        va="center", ha="left")
    # markers; stagger labels that would collide
    last_x, level = None, 0
    for (tm, lab) in sorted(markers):
        x = tm / 1000
        if last_x is not None and (x - last_x) < span_ns * 0.18:
            level = 1 - level
        else:
            level = 0
        last_x = x
        ax.axvline(x, color=ACCENT, lw=1.0, ls=(0, (4, 2)), zorder=3)
        ax.text(x, ytop + 0.08 + 0.42 * level, lab, color=INK, fontsize=6.5, ha="center",
                va="bottom", bbox=dict(boxstyle="square,pad=0.15", fc=SURFACE, ec=ACCENT, lw=0.6))
    ax.set_xlim(t0 / 1000, t1 / 1000)
    ax.set_ylim(-0.1, ytop + 1.0)
    ax.set_yticks([])
    for sp in ("left", "right", "top"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(INK2)
    ax.tick_params(axis="x", colors=INK2, labelsize=7)
    g = "every rising edge" if grid_every == 1 else f"every {grid_every}th rising edge"
    ax.set_xlabel(f"time (ns); grid = {g} of clk (10 ns period)", fontsize=7, color=INK2)
    ax.set_title(title, fontsize=9, color=INK, loc="left")


def export_csv(vcd, rows, path, t0, t1):
    """One row per clock cycle: values sampled 1 ns before each rising edge,
    the same instant tb_orbit_wave.v samples them."""
    edges = []
    e = PERIOD_PS // 2
    while e <= t1:
        if e - SKEW_PS >= t0:
            edges.append(e)
        e += PERIOD_PS
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        rows = [r for r in rows if r[0] != "clk"]
        w.writerow(["cycle", "sample_time_ns"] + [r[0].strip() for r in rows])
        for k, e in enumerate(edges):
            ts = e - SKEW_PS
            vals = []
            for row in rows:
                label, sig, kind, fmt = row[:4]
                v = vcd.value_at(sig, ts)
                if v is None:
                    vals.append("x")
                elif kind == "analog":
                    vals.append(str(s8(v)))
                elif kind == "bit":
                    vals.append(str(v))
                else:
                    vals.append(fmt(v))
            w.writerow([k, ts / 1000] + vals)


# ---------------------------------------------------------------- scenarios
def scen_a(vcd):
    rows = [
        ("clk", T + "clk", "bit", None),
        ("rst_n", T + "rst_n", "bit", None),
        ("therm_state", T + "therm_state", "bus", fmt_therm),
        ("in_valid", T + "in_valid", "bit", None),
        ("in_ready", T + "in_ready", "bit", None),
        ("in_first", T + "in_first", "bit", None),
        ("in_last", T + "in_last", "bit", None),
        ("in_a [l0..l3]", T + "in_a", "bus", fmt_i8x4),
        ("in_b [l0..l3]", T + "in_b", "bus", fmt_i8x4),
        ("lane0 u_acc_a.q", T + "p_acc_a0", "bus", fmt_i32),
        ("lane1 u_acc_a.q", T + "p_acc_a1", "bus", fmt_i32),
        ("lane2 u_acc_a.q", T + "p_acc_a2", "bus", fmt_i32),
        ("lane3 u_acc_a.q", T + "p_acc_a3", "bus", fmt_i32),
        ("out_valid", T + "out_valid", "bit", None),
        ("out_ready", T + "out_ready", "bit", None),
        ("out_data lane0", T + "out_lane0", "bus", fmt_i32hex),
        ("out_data lane1", T + "out_lane1", "bus", fmt_i32hex),
        ("out_data lane2", T + "out_lane2", "bus", fmt_i32hex),
        ("out_data lane3", T + "out_lane3", "bus", fmt_i32hex),
        ("fault", T + "fault", "bit", None),
    ]
    rise_ov = vcd.rises(T + "out_valid")
    mk = []
    if rise_ov:
        mk.append((rise_ov[0], "edge accepting in_last; out_valid = 1"))
    return rows, mk, "(a) reset, then a 3-beat MAC on all 4 lanes (in_first .. in_last), signed edge cases"


def scen_b(vcd):
    rows = [
        ("clk", T + "clk", "bit", None),
        ("therm_state", T + "therm_state", "bus", fmt_therm),
        ("in_valid", T + "in_valid", "bit", None),
        ("in_first", T + "in_first", "bit", None),
        ("in_last", T + "in_last", "bit", None),
        ("in_ready", T + "in_ready", "bit", None),
        ("in_fire", T + "in_fire", "bit", None),
        ("in_a [l0..l3]", T + "in_a", "bus", fmt_i8x4),
        ("in_b [l0..l3]", T + "in_b", "bus", fmt_i8x4),
        ("out_valid_q", T + "p_out_valid_q", "bit", None),
        ("out_valid", T + "out_valid", "bit", None),
        ("out_ready", T + "out_ready", "bit", None),
        ("out_fire", T + "out_fire", "bit", None),
        ("out_data lane0", T + "out_lane0", "bus", fmt_i32),
        ("out_data lane1", T + "out_lane1", "bus", fmt_i32),
        ("out_data lane2", T + "out_lane2", "bus", fmt_i32),
        ("out_data lane3", T + "out_lane3", "bus", fmt_i32),
    ]
    mk = []
    fr = vcd.rises(T + "out_ready")
    fo = vcd.rises(T + "out_fire")
    if fo:
        mk.append((fo[0], "out_fire and in_fire in one cycle (X out, Y1 in)"))
    return rows, mk, "(b) output backpressure: out_ready low with a full buffer, then drain and refill"


def scen_c(vcd, sticky=False):
    rows = [
        ("clk", T + "clk", "bit", None),
        ("in_valid", T + "in_valid", "bit", None),
        ("in_ready", T + "in_ready", "bit", None),
        ("in_fire", T + "in_fire", "bit", None),
        ("lane1 u_acc_a.q", T + "p_acc_a1", "bus", fmt_i32),
        ("lane1 u_acc_b.q", T + "p_acc_b1", "bus", fmt_i32),
        ("lane1 u_res_a.q", T + "p_res_a1", "bus", fmt_i32),
        ("lane1 u_res_b.q", T + "p_res_b1", "bus", fmt_i32),
        ("lane_mismatch", T + "p_lane_mismatch", "bus", fmt_bin(4)),
        ("mismatch", T + "p_mismatch", "bit", None),
        ("fault (fault_q)", T + "fault", "bit", None),
        ("out_valid_q", T + "p_out_valid_q", "bit", None),
        ("out_valid", T + "out_valid", "bit", None),
        ("out_ready", T + "out_ready", "bit", None),
        ("out_fire", T + "out_fire", "bit", None),
        ("out_data lane1", T + "out_lane1", "bus", fmt_i32),
        ("clear_fault", T + "clear_fault", "bit", None),
    ]
    ch = vcd.changes_of(T + "p_acc_b1")
    mk = []
    mm = vcd.rises(T + "p_mismatch")
    if mm:
        mk.append((mm[0], "acc_b[3] flip (negedge)"))
    if sticky:
        s, _ = vcd.series(T + "p_mismatch")
        falls = [t for (t, v), (_, pv) in zip(s[1:], s[:-1]) if v == 0 and pv == 1]
        if falls:
            mk.append((falls[0], "2nd flip: copies agree"))
    cf = vcd.rises(T + "clear_fault")
    if cf:
        mk.append((cf[0], "clear_fault"))
    title = ("(c2) fault is sticky: a second test-only flip restores agreement, fault stays until clear_fault"
             if sticky else
             "(c) single-bit upset in g_lane[1].u_lane.u_acc_b.q, fault-stop, clear_fault recovery")
    return rows, mk, title


def scen_d_rows():
    return [
        ("temp_c (C)", T + "temp_c", "analog",
         (55, 100, [(70, "70 T_RECOVER"), (80, "80 T_THROTTLE"), (95, "95 T_STOP")]), 3.0),
        ("temp_valid", T + "temp_valid", "bit", None),
        ("therm_state", T + "therm_state", "bus", fmt_therm),
        ("shutdown_req", T + "shutdown_req", "bit", None),
        ("u_thermal.phase", T + "p_phase", "bit", None),
        ("in_valid", T + "in_valid", "bit", None),
        ("in_ready", T + "in_ready", "bit", None),
        ("u_copy0.q", T + "p_copy0", "bus", fmt_bin(2)),
        ("u_copy1.q", T + "p_copy1", "bus", fmt_bin(2)),
        ("u_copy2.q", T + "p_copy2", "bus", fmt_bin(2)),
        ("therm_repair", T + "therm_repair", "bit", None),
    ]


def scen_d(vcd):
    rows = scen_d_rows()
    mk = []
    rp = vcd.rises(T + "therm_repair")
    if rp:
        mk.append((rp[0], "u_copy1.q[0] upset"))
    return rows, mk, "(d) thermal ramp 60 -> 85 -> 97 -> 65 C, one reading per cycle, temp_valid = 1"


def main():
    wdir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42})
    specs = [
        ("a_mac3", scen_a, {}),
        ("b_backpressure", scen_b, {}),
        ("c_fault", scen_c, {}),
        ("c2_fault_sticky", lambda v: scen_c(v, sticky=True), {}),
        ("d_thermal", scen_d, {}),
    ]
    pdf_path = os.path.join(wdir, "orbit_demo_waveforms.pdf")
    with PdfPages(pdf_path) as pdf:
        for name, fn, _ in specs:
            vcd = Vcd(os.path.join(wdir, f"wave_{name}.vcd"))
            assert vcd.timescale == "1ps", vcd.timescale
            rows, mk, title = fn(vcd)
            t0, t1 = 0, vcd.end
            fig_h = 1.3 + 0.36 * sum((r[4] if len(r) > 4 else 1.0) for r in rows)
            fig, ax = plt.subplots(figsize=(11.69, max(4.0, fig_h)))
            fig.subplots_adjust(left=0.13, right=0.93, top=0.90, bottom=0.10)
            ncyc = vcd.end // PERIOD_PS
            draw(ax, vcd, rows, t0, t1, title, mk, grid_every=(10 if ncyc > 40 else 1))
            fig.text(0.13, 0.015, f"source: {os.path.basename(vcd.path)} (Icarus Verilog, tb_orbit_wave.v +scen); "
                     "values read from the VCD; signed decimal unless noted", fontsize=6.5, color=INK2)
            fig.savefig(os.path.join(wdir, f"wave_{name}.png"), dpi=200, facecolor=SURFACE)
            pdf.savefig(fig, facecolor=SURFACE)
            plt.close(fig)
            export_csv(vcd, rows, os.path.join(wdir, f"wave_{name}.csv"), t0, t1)
            if name == "d_thermal":
                # zoom: THROTTLE entry and the copy1 upset
                rp = vcd.rises(T + "therm_repair")[0]
                z0, z1 = rp - 14 * PERIOD_PS, rp + 6 * PERIOD_PS
                rows_z = [("clk", T + "clk", "bit", None)] + scen_d_rows()[1:]
                rows_z.insert(1, ("temp_c (C)", T + "temp_c", "bus", fmt_temp))
                fig, ax = plt.subplots(figsize=(11.69, 1.3 + 0.36 * len(rows_z)))
                fig.subplots_adjust(left=0.13, right=0.93, top=0.88, bottom=0.12)
                draw(ax, vcd, rows_z, z0, z1,
                     "(d, zoom) THROTTLE: in_ready on alternate cycles; u_copy1.q upset outvoted, "
                     "therm_repair for one cycle", mk)
                fig.text(0.13, 0.015, f"source: {os.path.basename(vcd.path)}, window "
                         f"{z0 / 1000:.0f}-{z1 / 1000:.0f} ns", fontsize=6.5, color=INK2)
                fig.savefig(os.path.join(wdir, "wave_d_thermal_zoom.png"), dpi=200, facecolor=SURFACE)
                pdf.savefig(fig, facecolor=SURFACE)
                plt.close(fig)
        d = pdf.infodict()
        d["Title"] = "orbit_demo review waveforms (tb_orbit_wave.v)"
    print("wrote", pdf_path)


if __name__ == "__main__":
    main()
