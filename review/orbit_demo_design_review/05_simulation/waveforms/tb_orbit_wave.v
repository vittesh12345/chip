// Waveform scenarios for the orbit_demo design review package.
//
// Not part of the repository test suite. Written for the review package only;
// tb/ is not modified. The DUT instance is a copy of the one in
// tb/tb_orbit_demo.v (same instance name `dut`, same named port connections,
// no parameter overrides), so the hierarchical paths are the docs/SPEC.md
// section 7 paths (dut.g_lane[i].u_lane.u_acc_b.q, dut.u_thermal.u_copy1.q).
//
// One scenario per run, selected with +scen=<n>; each run writes its own VCD:
//   +scen=1  wave_a_mac3.vcd          reset, then a 3-beat MAC on all 4 lanes
//                                     (in_first .. in_last) incl. -128*-128, 127*-128
//   +scen=2  wave_b_backpressure.vcd  out_ready low for several cycles with a full
//                                     buffer; drain and refill in the same cycle
//   +scen=3  wave_c_fault.vcd         single-bit flip of g_lane[1].u_lane.u_acc_b.q at
//                                     a falling edge: mismatch, out_valid forced low,
//                                     fault rising, then clear_fault recovery
//   +scen=4  wave_d_thermal.vcd       temp_c ramp 60 -> 85 -> 97 -> 65 (temp_valid = 1):
//                                     NORMAL -> THROTTLE -> STOP -> NORMAL, plus one
//                                     upset in u_thermal.u_copy1.q (therm_repair)
//   +scen=5  wave_c2_fault_sticky.vcd as +scen=3, plus a second, test-only flip of the
//                                     same bit while the fault is latched, so the two
//                                     copies agree again: fault must stay high (sticky,
//                                     SPEC section 5) and out_valid low until clear_fault
//
// Timing (as tb/tb_orbit_demo.v): 10 ns clock (HALF = 5), inputs and upsets
// change at the falling edge, outputs are sampled SAMPLE_SKEW = 1 ns before the
// rising edge. Every scenario self-checks and ends with
// "WAVE_<name> PASS (<n> checks)" or "WAVE_<name> FAIL (<e> of <n> checks failed)".
//
// Build and run (Icarus Verilog):
//   iverilog -g2005 -Wall -Wno-timescale -o tb_orbit_wave.vvp tb_orbit_wave.v \
//       <repo>/rtl/orbit_keep_reg.v <repo>/rtl/orbit_mac_lane.v \
//       <repo>/rtl/orbit_thermal_tmr.v <repo>/rtl/orbit_demo.v
//   vvp -n tb_orbit_wave.vvp +scen=1      (2, 3, 4)

`timescale 1ns/1ps
`default_nettype none

module tb_orbit_wave;

    parameter integer HALF        = 5;
    parameter integer SAMPLE_SKEW = 1;

    localparam integer LANES = 4;
    localparam integer W     = 32 * LANES;

    localparam [1:0] NORMAL   = 2'd0;
    localparam [1:0] THROTTLE = 2'd1;
    localparam [1:0] STOP     = 2'd2;

    // ------------------------------------------------------------------
    // DUT (identical to tb/tb_orbit_demo.v lines 52-85)
    // ------------------------------------------------------------------
    reg              clk = 1'b0;
    reg              rst_n;
    reg              in_valid, in_first, in_last;
    reg  [8*LANES-1:0] in_a, in_b;
    reg              out_ready;
    reg              temp_valid;
    reg  [7:0]       temp_c;
    reg              clear_fault;
    wire             in_ready, out_valid, fault, therm_repair, shutdown_req;
    wire [W-1:0]     out_data;
    wire [1:0]       therm_state;

    always #HALF clk = ~clk;

    orbit_demo dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .in_valid     (in_valid),
        .in_ready     (in_ready),
        .in_first     (in_first),
        .in_last      (in_last),
        .in_a         (in_a),
        .in_b         (in_b),
        .out_valid    (out_valid),
        .out_ready    (out_ready),
        .out_data     (out_data),
        .temp_valid   (temp_valid),
        .temp_c       (temp_c),
        .clear_fault  (clear_fault),
        .fault        (fault),
        .therm_state  (therm_state),
        .therm_repair (therm_repair),
        .shutdown_req (shutdown_req)
    );

    // ------------------------------------------------------------------
    // Probes (for the VCD and the checks; SPEC section 7 paths)
    // ------------------------------------------------------------------
    wire [31:0] p_acc_a0 = dut.g_lane[0].u_lane.u_acc_a.q;
    wire [31:0] p_acc_b0 = dut.g_lane[0].u_lane.u_acc_b.q;
    wire [31:0] p_acc_a1 = dut.g_lane[1].u_lane.u_acc_a.q;
    wire [31:0] p_acc_b1 = dut.g_lane[1].u_lane.u_acc_b.q;
    wire [31:0] p_acc_a2 = dut.g_lane[2].u_lane.u_acc_a.q;
    wire [31:0] p_acc_b2 = dut.g_lane[2].u_lane.u_acc_b.q;
    wire [31:0] p_acc_a3 = dut.g_lane[3].u_lane.u_acc_a.q;
    wire [31:0] p_acc_b3 = dut.g_lane[3].u_lane.u_acc_b.q;
    wire [31:0] p_res_a1 = dut.g_lane[1].u_lane.u_res_a.q;
    wire [31:0] p_res_b1 = dut.g_lane[1].u_lane.u_res_b.q;
    wire [3:0]  p_lane_mismatch = dut.lane_mismatch;
    wire        p_mismatch      = dut.mismatch;
    wire        p_out_valid_q   = dut.out_valid_q;
    wire        p_fault_q       = dut.fault_q;
    wire [1:0]  p_copy0 = dut.u_thermal.u_copy0.q;
    wire [1:0]  p_copy1 = dut.u_thermal.u_copy1.q;
    wire [1:0]  p_copy2 = dut.u_thermal.u_copy2.q;
    wire        p_phase = dut.u_thermal.phase;
    wire        p_admit = dut.u_thermal.admit;
    wire        in_fire  = in_valid & in_ready;
    wire        out_fire = out_valid & out_ready;
    wire [31:0] out_lane0 = out_data[31:0];
    wire [31:0] out_lane1 = out_data[63:32];
    wire [31:0] out_lane2 = out_data[95:64];
    wire [31:0] out_lane3 = out_data[127:96];

    // ------------------------------------------------------------------
    // Checking
    // ------------------------------------------------------------------
    integer n_checks, n_fail, n_cyc, n_in_fire, n_out_fire;
    reg [8*16-1:0] sname;

    task chk(input cond, input [8*100-1:0] msg);
        begin
            n_checks = n_checks + 1;
            if (cond !== 1'b1) begin
                n_fail = n_fail + 1;
                $display("  FAIL t=%0t cyc=%0d: %0s", $time, n_cyc, msg);
            end
        end
    endtask

    task note(input [8*100-1:0] msg);
        $display("  t=%0t cyc=%0d: %0s", $time, n_cyc, msg);
    endtask

    // Sampled outputs of the current cycle (SAMPLE_SKEW before the rising edge).
    reg          s_in_ready, s_out_valid, s_fault, s_repair, s_shutdown, s_in_fire, s_out_fire;
    reg [1:0]    s_state;
    reg [W-1:0]  s_out_data;

    // One cycle: from a falling edge, sample, rising edge, next falling edge.
    task tick;
        begin
            #(HALF - SAMPLE_SKEW);
            s_in_ready  = in_ready;
            s_out_valid = out_valid;
            s_out_data  = out_data;
            s_fault     = fault;
            s_repair    = therm_repair;
            s_state     = therm_state;
            s_shutdown  = shutdown_req;
            s_in_fire   = in_valid & in_ready;
            s_out_fire  = out_valid & out_ready;
            if (s_in_fire === 1'b1)  n_in_fire  = n_in_fire + 1;
            if (s_out_fire === 1'b1) n_out_fire = n_out_fire + 1;
            chk(s_shutdown === s_state[1], "shutdown_req == therm_state[1]");
            @(posedge clk);
            n_cyc = n_cyc + 1;
            @(negedge clk);
        end
    endtask

    function [8*LANES-1:0] pk8(input integer v0, input integer v1, input integer v2, input integer v3);
        pk8 = {v3[7:0], v2[7:0], v1[7:0], v0[7:0]};
    endfunction

    function [W-1:0] pk32(input [31:0] v0, input [31:0] v1, input [31:0] v2, input [31:0] v3);
        pk32 = {v3, v2, v1, v0};
    endfunction

    function [1:0] therm_next(input [1:0] st, input tv, input [7:0] tc);   // SPEC section 6 table
        integer t;
        begin
            t = {{24{tc[7]}}, tc};
            if (!tv || t >= 95)       therm_next = STOP;
            else if (st == NORMAL)    therm_next = (t >= 80) ? THROTTLE : NORMAL;
            else if (st == THROTTLE)  therm_next = (t <= 70) ? NORMAL : THROTTLE;
            else                      therm_next = (t <= 70) ? NORMAL : STOP;
        end
    endfunction

    task idle_inputs;
        begin
            in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        end
    endtask

    // Reset for 3 cycles with a cool valid reading, release, and wait for the
    // first NORMAL cycle (SPEC 6: reset gives STOP; STOP -> NORMAL at <= 70 C).
    task reset_to_normal(input integer t_reset);
        begin
            rst_n = 1'b0; idle_inputs; in_a = 0; in_b = 0;
            out_ready = 1'b1; temp_valid = 1'b1; temp_c = t_reset[7:0]; clear_fault = 1'b0;
            @(negedge clk);
            repeat (3) begin
                tick;
                chk(s_state === STOP && s_in_ready === 1'b0 && s_out_valid === 1'b0 && s_fault === 1'b0,
                    "in reset: STOP, in_ready=0, out_valid=0, fault=0");
            end
            rst_n = 1'b1;
            tick;      // first edge after reset: reading <= 70 C registered, state still STOP here
            chk(s_state === STOP && s_in_ready === 1'b0, "first cycle after reset release: STOP");
            chk(therm_state === NORMAL && in_ready === 1'b1, "next cycle: NORMAL, in_ready=1");
            note("reset released, therm_state NORMAL");
        end
    endtask

    integer scen, k, adm, nthr;
    reg [1:0] m_state;
    reg       m_phase, exp_ready, exp_repair, seen_stop, bad;
    reg [W-1:0] held;
    integer temps [0:127];
    integer nt, inj_at, first_thr, first_stop, first_norm2;

    initial begin
        $timeformat(-9, 1, " ns", 10);
        n_checks = 0; n_fail = 0; n_cyc = 0; n_in_fire = 0; n_out_fire = 0;
        rst_n = 1'b0; idle_inputs; in_a = 0; in_b = 0; out_ready = 1'b1;
        temp_valid = 1'b1; temp_c = 8'd60; clear_fault = 1'b0;
        if (!$value$plusargs("scen=%d", scen)) scen = 1;
        case (scen)
            1: begin sname = "a_mac3";         $dumpfile("wave_a_mac3.vcd"); end
            2: begin sname = "b_backpressure"; $dumpfile("wave_b_backpressure.vcd"); end
            3: begin sname = "c_fault";        $dumpfile("wave_c_fault.vcd"); end
            4: begin sname = "d_thermal";      $dumpfile("wave_d_thermal.vcd"); end
            5: begin sname = "c2_fault_sticky"; $dumpfile("wave_c2_fault_sticky.vcd"); end
            default: begin $display("unknown +scen=%0d", scen); $finish; end
        endcase
        $dumpvars(0, tb_orbit_wave);
        $display("WAVE scenario %0d: %0s (clk period %0d ns)", scen, sname, 2 * HALF);

        case (scen)
        // --------------------------------------------------------------
        // (a) reset, then a 3-beat MAC on all four lanes
        //   lane 0: (-128)*(-128) x3          16384, 32768, 49152 = 0x0000C000
        //   lane 1: 127*(-128) x3             -16256, -32512, -48768 = 0xFFFF4180
        //   lane 2: -128*127, -128*-128, 127*127  -16256, 128, 16257 = 0x00003F81
        //   lane 3: -1*-1, 100*-3, 0*-128     1, -299, -299 = 0xFFFFFED5
        // --------------------------------------------------------------
        1: begin
            reset_to_normal(60);
            out_ready = 1'b1;
            in_valid = 1'b1; in_first = 1'b1; in_last = 1'b0;
            in_a = pk8(-128, 127, -128, -1); in_b = pk8(-128, -128, 127, -1);
            tick;
            chk(s_in_fire === 1'b1 && s_out_valid === 1'b0, "beat 1 (in_first) accepted, out_valid=0");
            chk({p_acc_a3, p_acc_a2, p_acc_a1, p_acc_a0} === pk32(32'h0000_4000, 32'hFFFF_C080, 32'hFFFF_C080, 32'h0000_0001),
                "after beat 1: acc_a = 0x00004000 0xFFFFC080 0xFFFFC080 0x00000001");
            chk({p_acc_b3, p_acc_b2, p_acc_b1, p_acc_b0} === {p_acc_a3, p_acc_a2, p_acc_a1, p_acc_a0}, "after beat 1: acc_b == acc_a");
            in_first = 1'b0; in_last = 1'b0;
            in_a = pk8(-128, 127, -128, 100); in_b = pk8(-128, -128, -128, -3);
            tick;
            chk(s_in_fire === 1'b1 && s_out_valid === 1'b0, "beat 2 accepted, out_valid=0");
            chk({p_acc_a3, p_acc_a2, p_acc_a1, p_acc_a0} === pk32(32'h0000_8000, 32'hFFFF_8100, 32'h0000_0080, 32'hFFFF_FED5),
                "after beat 2: acc_a = 0x00008000 0xFFFF8100 0x00000080 0xFFFFFED5");
            chk({p_acc_b3, p_acc_b2, p_acc_b1, p_acc_b0} === {p_acc_a3, p_acc_a2, p_acc_a1, p_acc_a0}, "after beat 2: acc_b == acc_a");
            in_first = 1'b0; in_last = 1'b1;
            in_a = pk8(-128, 127, 127, 0); in_b = pk8(-128, -128, 127, -128);
            tick;
            chk(s_in_fire === 1'b1 && s_out_valid === 1'b0, "beat 3 (in_last) accepted, out_valid still 0 in that cycle");
            idle_inputs;
            chk(out_valid === 1'b1, "out_valid high in the cycle after in_last (latency 1)");
            tick;
            chk(s_out_valid === 1'b1 && s_out_fire === 1'b1, "result presented and transferred (out_ready=1)");
            chk(s_out_data === pk32(32'h0000_C000, 32'hFFFF_4180, 32'h0000_3F81, 32'hFFFF_FED5),
                "out_data = 0x0000C000 0xFFFF4180 0x00003F81 0xFFFFFED5 (lane 0..3)");
            note("3-beat result transferred");
            tick;
            chk(s_out_valid === 1'b0, "buffer empty after the transfer");
            chk(s_fault === 1'b0 && s_repair === 1'b0 && p_mismatch === 1'b0, "fault=0, therm_repair=0, mismatch=0");
            chk(n_in_fire == 3 && n_out_fire == 1, "3 beats accepted, 1 result transferred");
            repeat (2) tick;
        end

        // --------------------------------------------------------------
        // (b) output backpressure
        //   X  = single beat 2*3, 3*4, 4*5, 5*6           = 6, 12, 20, 30
        //   Y1 = -128*-128, 127*-128, -1*9, 10*-10        (first, offered while X is held)
        //   Y2 = 1*1, 1*2, 1*3, 1*4                       (last)
        //   Y  = 16385, -16254, -6, -96 = 0x4001 0xFFFFC082 0xFFFFFFFA 0xFFFFFFA0
        // --------------------------------------------------------------
        2: begin
            reset_to_normal(60);
            out_ready = 1'b0;
            in_valid = 1'b1; in_first = 1'b1; in_last = 1'b1;
            in_a = pk8(2, 3, 4, 5); in_b = pk8(3, 4, 5, 6);
            tick;
            chk(s_in_fire === 1'b1, "X accepted with out_ready=0 (buffer was empty)");
            in_first = 1'b1; in_last = 1'b0;               // Y1, a NON-last beat, offered throughout
            in_a = pk8(-128, 127, -1, 10); in_b = pk8(-128, -128, 9, -10);
            bad = 1'b0;
            for (k = 0; k < 6; k = k + 1) begin
                tick;
                if (!(s_out_valid === 1'b1 && s_out_data === pk32(32'd6, 32'd12, 32'd20, 32'd30) &&
                      s_in_ready === 1'b0 && s_in_fire === 1'b0 && s_out_fire === 1'b0)) bad = 1'b1;
            end
            chk(bad === 1'b0, "6 cycles out_ready=0: out_valid=1, out_data = X stable, in_ready=0, Y1 blocked");
            note("6 backpressure cycles done, raising out_ready");
            out_ready = 1'b1;
            tick;
            chk(s_out_fire === 1'b1 && s_in_fire === 1'b1, "X transferred and Y1 accepted in the same cycle");
            in_first = 1'b0; in_last = 1'b1;               // Y2
            in_a = pk8(1, 1, 1, 1); in_b = pk8(1, 2, 3, 4);
            out_ready = 1'b0;
            tick;
            chk(s_in_fire === 1'b1 && s_out_valid === 1'b0, "Y2 (in_last) accepted into the empty buffer");
            idle_inputs;
            bad = 1'b0;
            for (k = 0; k < 4; k = k + 1) begin
                tick;
                if (!(s_out_valid === 1'b1 && s_out_fire === 1'b0 &&
                      s_out_data === pk32(32'h0000_4001, 32'hFFFF_C082, 32'hFFFF_FFFA, 32'hFFFF_FFA0))) bad = 1'b1;
            end
            chk(bad === 1'b0, "4 cycles out_ready=0: Y = 0x4001 0xFFFFC082 0xFFFFFFFA 0xFFFFFFA0 held");
            out_ready = 1'b1;
            tick;
            chk(s_out_fire === 1'b1 && s_out_data === pk32(32'h0000_4001, 32'hFFFF_C082, 32'hFFFF_FFFA, 32'hFFFF_FFA0),
                "Y transferred");
            tick;
            chk(s_out_valid === 1'b0, "buffer empty");
            chk(n_out_fire == 2 && n_in_fire == 3, "3 beats accepted, exactly 2 results (X, Y) transferred");
            chk(s_fault === 1'b0, "fault=0");
            repeat (2) tick;
        end

        // --------------------------------------------------------------
        // (c) single-bit upset in g_lane[1].u_lane.u_acc_b.q, clear_fault recovery
        //   sum 10*1 + 1*2, 20*1 + 2*2, 30*1 + 3*2, 40*1 + 4*2 = 12, 24, 36, 48 (result R, held)
        //   upset: acc_b lane 1 bit 3 flipped at a falling edge (24 -> 16)
        //   recovery beat: -128*-128, 127*-128, 5*5, -6*6 = 0x4000 0xFFFFC080 0x19 0xFFFFFFDC
        // --------------------------------------------------------------
        3, 5: begin
            reset_to_normal(60);
            out_ready = 1'b0;
            in_valid = 1'b1; in_first = 1'b1; in_last = 1'b0;
            in_a = pk8(10, 20, 30, 40); in_b = pk8(1, 1, 1, 1);
            tick;
            in_first = 1'b0; in_last = 1'b1;
            in_a = pk8(1, 2, 3, 4); in_b = pk8(2, 2, 2, 2);
            tick;
            chk(s_in_fire === 1'b1, "2-beat sum R accepted");
            idle_inputs;
            tick;
            chk(s_out_valid === 1'b1 && s_out_data === pk32(32'd12, 32'd24, 32'd36, 32'd48) && s_out_fire === 1'b0,
                "R = 12 24 36 48 presented, held (out_ready=0)");
            chk(p_acc_a1 === 32'd24 && p_acc_b1 === 32'd24, "lane 1 acc_a = acc_b = 24 before the upset");
            // Falling edge: inject, and from now on the consumer is ready and a beat is offered.
            dut.g_lane[1].u_lane.u_acc_b.q[3] = ~dut.g_lane[1].u_lane.u_acc_b.q[3];
            out_ready = 1'b1;
            in_valid = 1'b1; in_first = 1'b1; in_last = 1'b1;
            in_a = pk8(-128, 127, 5, -6); in_b = pk8(-128, -128, 5, 6);
            note("upset: g_lane[1].u_lane.u_acc_b.q[3] flipped at the falling edge");
            #1;
            chk(p_acc_b1 === 32'd16 && p_acc_a1 === 32'd24, "after the flip: lane 1 acc_b = 16, acc_a = 24");
            chk(p_lane_mismatch === 4'b0010 && p_mismatch === 1'b1, "lane_mismatch = 4'b0010, mismatch = 1 (same cycle)");
            chk(out_valid === 1'b0 && in_ready === 1'b0, "same cycle: out_valid forced 0 (R not presented), in_ready 0");
            chk(fault === 1'b0, "same cycle: fault still 0 (registered)");
            #(HALF - SAMPLE_SKEW - 1);
            // finish this cycle with the normal sampling
            s_out_fire = out_valid & out_ready; s_in_fire = in_valid & in_ready;
            chk(s_out_fire === 1'b0 && s_in_fire === 1'b0, "no out_fire, no in_fire in the upset cycle");
            @(posedge clk); n_cyc = n_cyc + 1; @(negedge clk);
            chk(fault === 1'b1, "fault high after the next rising edge");
            note("fault latched");
            bad = 1'b0;
            for (k = 0; k < 5; k = k + 1) begin
                tick;
                if (!(s_fault === 1'b1 && s_out_valid === 1'b0 && s_in_ready === 1'b0 &&
                      s_out_fire === 1'b0 && s_in_fire === 1'b0 && p_mismatch === 1'b1)) bad = 1'b1;
            end
            chk(bad === 1'b0, "5 cycles: fault=1 sticky, out_valid=0 with out_ready=1, in_ready=0");
            chk(p_out_valid_q === 1'b1, "out_valid_q still 1 internally: the result is withheld, not lost silently");
            chk(n_out_fire == 0, "the corrupted-storage result R was never transferred");
            if (scen == 5) begin
                // Second, test-only flip of the same bit: copies agree again.
                dut.g_lane[1].u_lane.u_acc_b.q[3] = ~dut.g_lane[1].u_lane.u_acc_b.q[3];
                note("second flip: g_lane[1].u_lane.u_acc_b.q[3] restored, copies agree again");
                #1;
                chk(p_acc_b1 === 32'd24 && p_acc_a1 === 32'd24 && p_mismatch === 1'b0,
                    "after the second flip: acc_a = acc_b = 24, mismatch = 0");
                #(HALF - SAMPLE_SKEW - 1);
                chk(fault === 1'b1 && out_valid === 1'b0 && in_ready === 1'b0,
                    "mismatch gone: fault still 1, out_valid 0, in_ready 0 (sticky)");
                @(posedge clk); n_cyc = n_cyc + 1; @(negedge clk);
                bad = 1'b0;
                for (k = 0; k < 4; k = k + 1) begin
                    tick;
                    if (!(s_fault === 1'b1 && s_out_valid === 1'b0 && s_in_ready === 1'b0 &&
                          s_out_fire === 1'b0 && s_in_fire === 1'b0 && p_mismatch === 1'b0)) bad = 1'b1;
                end
                chk(bad === 1'b0, "4 more cycles with copies equal: fault stays 1, nothing transferred or accepted");
                chk(n_out_fire == 0, "R still not transferred");
            end
            clear_fault = 1'b1;
            tick;
            chk(s_in_ready === 1'b0 && s_in_fire === 1'b0, "in_ready=0 while clear_fault=1");
            clear_fault = 1'b0;
            chk(fault === 1'b0 && p_mismatch === 1'b0 && out_valid === 1'b0, "after clear_fault: fault=0, mismatch=0, out_valid=0");
            chk({p_acc_a3, p_acc_a2, p_acc_a1, p_acc_a0, p_acc_b3, p_acc_b2, p_acc_b1, p_acc_b0} === 256'd0 &&
                p_res_a1 === 32'd0 && p_res_b1 === 32'd0, "after clear_fault: both copies of the storage are 0");
            note("clear_fault done");
            tick;
            chk(s_in_fire === 1'b1, "recovery beat accepted after clear_fault");
            idle_inputs;
            tick;
            chk(s_out_fire === 1'b1 && s_out_data === pk32(32'h0000_4000, 32'hFFFF_C080, 32'h0000_0019, 32'hFFFF_FFDC),
                "recovery result 0x00004000 0xFFFFC080 0x00000019 0xFFFFFFDC transferred");
            tick;
            chk(s_out_valid === 1'b0 && s_fault === 1'b0, "buffer empty, fault=0");
            chk(n_out_fire == 1, "exactly one result transferred in the whole scenario (the recovery result)");
            repeat (2) tick;
        end

        // --------------------------------------------------------------
        // (d) thermal ramp 60 -> 85 -> 97 -> 65 C, one reading per cycle,
        //     temp_valid = 1; single-beat sums offered every cycle, out_ready = 1
        //     (so in_ready == admit). Upset of u_thermal.u_copy1.q[0] during the
        //     85 C hold (THROTTLE = 2'b01 -> 2'b00).
        // --------------------------------------------------------------
        4: begin
            nt = 0;
            for (k = 0; k < 4;  k = k + 1) begin temps[nt] = 60;     nt = nt + 1; end
            for (k = 61; k <= 85; k = k + 1) begin temps[nt] = k;  nt = nt + 1; end
            for (k = 0; k < 8;  k = k + 1) begin temps[nt] = 85;     nt = nt + 1; end
            for (k = 86; k <= 97; k = k + 1) begin temps[nt] = k;  nt = nt + 1; end
            for (k = 0; k < 4;  k = k + 1) begin temps[nt] = 97;     nt = nt + 1; end
            for (k = 96; k >= 65; k = k - 1) begin temps[nt] = k;  nt = nt + 1; end
            for (k = 0; k < 6;  k = k + 1) begin temps[nt] = 65;     nt = nt + 1; end
            inj_at = 4 + 25 + 4;                            // 5th cycle of the 85 C hold
            reset_to_normal(60);
            m_state = NORMAL; m_phase = 1'b0;
            out_ready = 1'b1;
            in_valid = 1'b1; in_first = 1'b1; in_last = 1'b1;
            in_a = pk8(1, 2, 3, 4); in_b = pk8(1, 1, 1, 1);
            first_thr = -1; first_stop = -1; first_norm2 = -1; seen_stop = 1'b0;
            adm = 0; nthr = 0;
            $display("  k = ramp step; temp_c = reading applied in step k (registered at the rising edge ending it);");
            $display("  other columns sampled 1 ns before that edge. therm_state 0 NORMAL, 1 THROTTLE, 2 STOP.");
            $display("    k temp_c therm_state in_ready phase copy0 copy1 copy2 therm_repair");
            for (k = 0; k < nt; k = k + 1) begin
                temp_valid = 1'b1; temp_c = temps[k];
                exp_repair = 1'b0;
                if (k == inj_at) begin
                    dut.u_thermal.u_copy1.q[0] = ~dut.u_thermal.u_copy1.q[0];
                    exp_repair = 1'b1;
                    #1;
                    chk(therm_repair === 1'b1 && p_copy1 === 2'b00 && p_copy0 === 2'b01 && p_copy2 === 2'b01,
                        "upset: copy1 = 2'b00, copy0 = copy2 = 2'b01, therm_repair = 1");
                    chk(therm_state === THROTTLE, "upset: voted therm_state still THROTTLE");
                    note("upset: u_thermal.u_copy1.q[0] flipped at the falling edge");
                end
                exp_ready = (m_state == NORMAL) | ((m_state == THROTTLE) & ~m_phase);
                if (k == inj_at) #(HALF - SAMPLE_SKEW - 1); else #(HALF - SAMPLE_SKEW);
                s_in_ready = in_ready; s_state = therm_state; s_repair = therm_repair;
                s_shutdown = shutdown_req; s_fault = fault;
                if (in_valid & in_ready) n_in_fire = n_in_fire + 1;
                if (out_valid & out_ready) n_out_fire = n_out_fire + 1;
                $display("  %3d %6d %11d %8b %5b %5b %5b %5b %12b", k, temps[k], s_state, s_in_ready,
                         p_phase, p_copy0, p_copy1, p_copy2, s_repair);
                chk(s_state === m_state, "therm_state matches the SPEC section 6 table");
                chk(s_in_ready === exp_ready, "in_ready matches admission rule (out_ready=1, no fault)");
                chk(s_repair === exp_repair, "therm_repair only in the upset cycle");
                chk(s_shutdown === s_state[1] && s_fault === 1'b0, "shutdown_req = therm_state[1], fault = 0");
                if (s_state === THROTTLE) begin
                    nthr = nthr + 1;
                    if (s_in_ready === 1'b1) adm = adm + 1;
                    if (first_thr < 0) first_thr = k;
                    if (seen_stop) chk(1'b0, "no STOP -> THROTTLE transition on the way down");
                end
                if (s_state === STOP && first_stop < 0) begin first_stop = k; seen_stop = 1'b1; end
                if (s_state === NORMAL && seen_stop && first_norm2 < 0) first_norm2 = k;
                @(posedge clk);
                n_cyc = n_cyc + 1;
                m_phase = (m_state == THROTTLE) ? ~m_phase : 1'b0;
                m_state = therm_next(m_state, 1'b1, temps[k][7:0]);
                @(negedge clk);
                if (k == inj_at)
                    chk(therm_repair === 1'b0 && p_copy1 === p_copy0 && p_copy1 === p_copy2,
                        "next edge: copy1 rewritten from the voted next state, therm_repair = 0");
            end
            idle_inputs;
            tick; tick;
            // Literal transition points (one reading per cycle; the reading is registered at the edge).
            chk(first_thr >= 0 && temps[first_thr - 1] == 80, "NORMAL -> THROTTLE in the cycle after the 80 C reading");
            chk(first_stop >= 0 && temps[first_stop - 1] == 95, "THROTTLE -> STOP in the cycle after the 95 C reading");
            chk(first_norm2 >= 0 && temps[first_norm2 - 1] == 70, "STOP -> NORMAL in the cycle after the 70 C reading");
            chk(adm == (nthr + 1) / 2, "THROTTLE admits on alternate cycles, first THROTTLE cycle admits");
            chk(n_out_fire == n_in_fire, "every accepted single-beat sum was transferred");
            $display("  THROTTLE cycles %0d, admitted %0d; first THROTTLE cyc %0d, first STOP cyc %0d, NORMAL again cyc %0d",
                     nthr, adm, first_thr, first_stop, first_norm2);
            $display("  beats accepted %0d, results transferred %0d", n_in_fire, n_out_fire);
        end
        endcase

        if (n_fail == 0)
            $display("WAVE_%0s PASS (%0d checks, %0d cycles)", sname, n_checks, n_cyc);
        else
            $display("WAVE_%0s FAIL (%0d of %0d checks failed)", sname, n_fail, n_checks);
        $finish;
    end

    initial begin
        #100000;
        $display("WAVE FAIL: watchdog");
        $finish;
    end

endmodule

`default_nettype wire
