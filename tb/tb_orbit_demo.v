// Directed, self-checking testbench for orbit_demo (behaviour: docs/SPEC.md).
//
// Only the top-level ports of orbit_demo are used (no hierarchical references,
// no parameter overrides), so the same bench runs on the RTL and on a
// gate-level netlist whose top module is orbit_demo with the same ports
// (make sim-gls SIM_GLS_SRCS="<netlist> <cell models>").
//
// Three layers of checking:
//   1. A cycle-accurate reference model written from docs/SPEC.md sections 3, 4
//      and 6 predicts in_ready, out_valid, out_data, therm_state, shutdown_req,
//      fault (always 0 here) and therm_repair (always 0 here) in every cycle.
//   2. A transaction scoreboard: every accepted in_last beat queues the result
//      computed from the beats the DUT actually accepted; every out_fire must
//      pop exactly that result (nothing lost, duplicated or reordered).
//      clear_fault / reset drop queued results, as the SPEC requires.
//   3. Scenario checks: hand-computed literal results (attached to a result
//      with expect_lit) and cycle-exact expectations (admission patterns,
//      state sequences, data stability under backpressure).
//
// Timing: inputs change at the falling edge, outputs are sampled SAMPLE_SKEW
// before the rising edge, and the model advances at the rising edge.
//
// Pseudo-random operands come from a xorshift32 generator in this file, not
// from $random (its seeded sequence differs between simulators), so both
// simulators get identical stimulus and must print identical summaries.
//
// Plusargs: +seed=<n> seeds the pseudo-random operands (default 1);
//           +maxerr=<n> stops with FAIL after n errors (default: run to the end).
// Ends with "TB_ORBIT_DEMO PASS" or "TB_ORBIT_DEMO FAIL" and $fatal on failure.

`timescale 1ns/1ps
`default_nettype none

module tb_orbit_demo;

    parameter integer HALF        = 5;     // half clock period in ns
    parameter integer SAMPLE_SKEW = 1;     // sample outputs this long before the rising edge

    localparam integer LANES   = 4;
    localparam integer W       = 32 * LANES;
    localparam integer TIMEOUT = 1000;     // cycles to wait for one handshake
    localparam integer SBN     = 64;       // scoreboard depth (power of two)
    localparam integer LOGN    = 128;      // per-cycle log depth used by stream()

    localparam [1:0] NORMAL   = 2'd0;
    localparam [1:0] THROTTLE = 2'd1;
    localparam [1:0] STOP     = 2'd2;

    // ------------------------------------------------------------------
    // DUT
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
    // Bookkeeping
    // ------------------------------------------------------------------
    integer seed, maxerr;
    reg [31:0] prng;                  // xorshift32 state, never zero
    reg [31:0] ra, rb, rf, rl;        // drawn before use (argument order is unspecified)

    function [31:0] rnd32(input dummy);
        begin
            prng  = prng ^ (prng << 13);
            prng  = prng ^ (prng >> 17);
            prng  = prng ^ (prng << 5);
            rnd32 = prng;
        end
    endfunction

    reg [8*24-1:0] scen;              // current scenario name
    integer n_cycles, n_model_checks, n_model_err;
    integer n_scen_checks, n_scen_err, n_errors;
    integer n_in_fire, n_out_fire, n_lit_checks, n_dropped, n_b2b;
    integer n_scenarios;

    task err(input [8*96-1:0] msg);
        begin
            n_errors = n_errors + 1;
            if (n_errors <= 40)
                $display("ERROR t=%0t [%0s] %0s", $time, scen, msg);
            if (maxerr > 0 && n_errors >= maxerr) begin
                $display("TB_ORBIT_DEMO FAIL: stopped after %0d errors", n_errors);
                $fatal(1, "tb_orbit_demo: %0d errors", n_errors);
            end
        end
    endtask

    // Scenario-level assertion.
    task chk(input cond, input [8*96-1:0] msg);
        begin
            n_scen_checks = n_scen_checks + 1;
            if (cond !== 1'b1) begin
                n_scen_err = n_scen_err + 1;
                err(msg);
            end
        end
    endtask

    task start(input [8*24-1:0] name);
        begin
            scen = name;
            n_scenarios = n_scenarios + 1;
            $display("[%0t] scenario %0d: %0s", $time, n_scenarios, name);
        end
    endtask

    // Exact signed INT8 x INT8 product, sign-extended to 32 bits.
    function [31:0] prod8(input [7:0] a, input [7:0] b);
        integer ia, ib;
        begin
            ia = {{24{a[7]}}, a};          // explicit sign extension
            ib = {{24{b[7]}}, b};
            prod8 = ia * ib;
        end
    endfunction

    // Pack four signed lane values (lane 0 in the low bits).
    function [8*LANES-1:0] pk8(input integer v0, input integer v1, input integer v2, input integer v3);
        begin
            pk8 = {v3[7:0], v2[7:0], v1[7:0], v0[7:0]};
        end
    endfunction

    function [W-1:0] pk32(input [31:0] v0, input [31:0] v1, input [31:0] v2, input [31:0] v3);
        begin
            pk32 = {v3, v2, v1, v0};
        end
    endfunction

    // ------------------------------------------------------------------
    // Reference model (docs/SPEC.md), advanced at every rising edge.
    // ------------------------------------------------------------------
    reg [31:0]   m_acc [0:LANES-1];
    reg [W-1:0]  m_res;
    reg          m_ovq, m_phase, m_live;
    reg [1:0]    m_state;
    reg          m_rdy;                // predicted in_ready of the current cycle

    function [1:0] therm_next(input [1:0] st, input tv, input [7:0] tc);
        integer t;
        begin
            t = {{24{tc[7]}}, tc};         // signed degrees C
            if (!tv || t >= 95)       therm_next = STOP;
            else if (st == NORMAL)    therm_next = (t >= 80) ? THROTTLE : NORMAL;
            else if (st == THROTTLE)  therm_next = (t <= 70) ? NORMAL : THROTTLE;
            else                      therm_next = (t <= 70) ? NORMAL : STOP;
        end
    endfunction

    task model_step;
        integer ml;
        reg [1:0] nst;
        reg nph, mfire;
        begin
            if (!rst_n) begin
                for (ml = 0; ml < LANES; ml = ml + 1) m_acc[ml] = 32'd0;
                m_res   = {W{1'b0}};
                m_ovq   = 1'b0;
                m_phase = 1'b0;
                m_state = STOP;
                m_live  = 1'b1;
            end else if (m_live) begin
                mfire = in_valid & m_rdy;
                nst   = therm_next(m_state, temp_valid, temp_c);
                nph   = (m_state == THROTTLE) ? ~m_phase : 1'b0;
                if (clear_fault) begin
                    for (ml = 0; ml < LANES; ml = ml + 1) m_acc[ml] = 32'd0;
                    m_res = {W{1'b0}};
                    m_ovq = 1'b0;
                end else begin
                    if (mfire) begin
                        for (ml = 0; ml < LANES; ml = ml + 1)
                            m_acc[ml] = (in_first ? 32'd0 : m_acc[ml]) +
                                        prod8(in_a[8*ml +: 8], in_b[8*ml +: 8]);
                        if (in_last)
                            m_res = pk32(m_acc[0], m_acc[1], m_acc[2], m_acc[3]);
                    end
                    if (mfire && in_last)
                        m_ovq = 1'b1;
                    else if (m_ovq && out_ready)
                        m_ovq = 1'b0;
                end
                m_state = nst;
                m_phase = nph;
            end
        end
    endtask

    // ------------------------------------------------------------------
    // Transaction scoreboard
    // ------------------------------------------------------------------
    reg [31:0]   t_acc [0:LANES-1];    // sums of the beats the DUT accepted
    reg [W-1:0]  sb_q     [0:SBN-1];
    reg [W-1:0]  sb_lit   [0:SBN-1];
    reg [LANES-1:0] sb_litm [0:SBN-1];
    integer      sb_wr, sb_rd;
    reg [W-1:0]  lit_value;            // literal for the next accepted in_last beat
    reg [LANES-1:0] lit_mask;
    reg [W-1:0]  last_out;             // out_data of the most recent out_fire

    // Attach hand-computed lane values (lanes selected by mask) to the result
    // of the next in_last beat the DUT accepts.
    task expect_lit(input [LANES-1:0] mask, input [W-1:0] v);
        begin
            lit_mask  = mask;
            lit_value = v;
        end
    endtask

    // ------------------------------------------------------------------
    // One clock cycle: sample and check, then let the edge happen.
    // ------------------------------------------------------------------
    reg          s_in_ready, s_out_valid, s_shutdown, s_in_fire, s_out_fire;
    reg          rnd_ready;            // tick() randomizes out_ready while set
    reg [1:0]    s_state;
    reg [W-1:0]  s_out_data;

    task sample_and_check;
        integer sl, idx;
        reg [W-1:0] res_now;
        begin
            s_in_ready  = in_ready;
            s_out_valid = out_valid;
            s_out_data  = out_data;
            s_state     = therm_state;
            s_shutdown  = shutdown_req;
            s_in_fire   = in_valid & in_ready;
            s_out_fire  = out_valid & out_ready;

            if (m_live) begin
                // 1. cycle model
                m_rdy = ((m_state == NORMAL) | ((m_state == THROTTLE) & ~m_phase)) &
                        ~clear_fault & (~m_ovq | out_ready);
                n_model_checks = n_model_checks + 1;
                if (in_ready !== m_rdy || out_valid !== m_ovq || out_data !== m_res ||
                    therm_state !== m_state || shutdown_req !== m_state[1] ||
                    fault !== 1'b0 || therm_repair !== 1'b0) begin
                    n_model_err = n_model_err + 1;
                    err("DUT outputs differ from the reference model");
                    if (n_errors <= 40)
                        $display("      got  in_ready=%b out_valid=%b therm_state=%0d shutdown_req=%b fault=%b therm_repair=%b out_data=%h",
                                 in_ready, out_valid, therm_state, shutdown_req, fault, therm_repair, out_data);
                    if (n_errors <= 40)
                        $display("      want in_ready=%b out_valid=%b therm_state=%0d shutdown_req=%b fault=0 therm_repair=0 out_data=%h",
                                 m_rdy, m_ovq, m_state, m_state[1], m_res);
                end

                // 2. scoreboard: a transfer pops first, then clear/reset drops,
                //    then an accepted beat accumulates.
                if (s_out_fire === 1'b1) begin
                    n_out_fire = n_out_fire + 1;
                    last_out   = out_data;
                    if (sb_rd == sb_wr) begin
                        err("out_fire with no expected result queued");
                    end else begin
                        idx = sb_rd % SBN;
                        if (out_data !== sb_q[idx]) begin
                            err("transferred result differs from the scoreboard");
                            if (n_errors <= 40)
                                $display("      got %h want %h", out_data, sb_q[idx]);
                        end
                        for (sl = 0; sl < LANES; sl = sl + 1)
                            if (sb_litm[idx][sl]) begin
                                n_lit_checks = n_lit_checks + 1;
                                if (out_data[32*sl +: 32] !== sb_lit[idx][32*sl +: 32]) begin
                                    err("transferred lane differs from the hand-computed literal");
                                    if (n_errors <= 40)
                                        $display("      lane %0d got %h want %h", sl,
                                                 out_data[32*sl +: 32], sb_lit[idx][32*sl +: 32]);
                                end
                            end
                        sb_rd = sb_rd + 1;
                    end
                end
                if (!rst_n || clear_fault) begin
                    n_dropped = n_dropped + (sb_wr - sb_rd);
                    sb_rd = sb_wr;
                    for (sl = 0; sl < LANES; sl = sl + 1) t_acc[sl] = 32'd0;
                end else if (s_in_fire === 1'b1) begin
                    n_in_fire = n_in_fire + 1;
                    for (sl = 0; sl < LANES; sl = sl + 1)
                        t_acc[sl] = (in_first ? 32'd0 : t_acc[sl]) +
                                    prod8(in_a[8*sl +: 8], in_b[8*sl +: 8]);
                    if (in_last) begin
                        if (sb_wr - sb_rd >= SBN) err("scoreboard overflow (testbench)");
                        idx = sb_wr % SBN;
                        res_now      = pk32(t_acc[0], t_acc[1], t_acc[2], t_acc[3]);
                        sb_q[idx]    = res_now;
                        sb_lit[idx]  = lit_value;
                        sb_litm[idx] = lit_mask;
                        lit_mask     = {LANES{1'b0}};
                        sb_wr = sb_wr + 1;
                        if (s_out_fire === 1'b1) n_b2b = n_b2b + 1;
                    end
                end
            end
        end
    endtask

    task tick;
        begin
            #(HALF - SAMPLE_SKEW);
            sample_and_check;
            @(posedge clk);
            model_step;
            n_cycles = n_cycles + 1;
            @(negedge clk);
            if (rnd_ready) out_ready = (rnd32(1'b0) & 32'd3) != 32'd0;   // ready 3 cycles in 4
        end
    endtask

    // ------------------------------------------------------------------
    // Stimulus helpers
    // ------------------------------------------------------------------
    task set_temp(input v, input integer t);
        begin
            temp_valid = v;
            temp_c     = t[7:0];
        end
    endtask

    task idle(input integer n);
        begin
            in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
            repeat (n) tick;
        end
    endtask

    // Offer one beat and hold it until the DUT accepts it. Consecutive calls
    // present beats back to back (no idle cycle in between).
    task beat(input f, input l, input [8*LANES-1:0] a, input [8*LANES-1:0] b);
        integer w;
        begin
            in_valid = 1'b1; in_first = f; in_last = l; in_a = a; in_b = b;
            w = 0;
            tick;
            while (s_in_fire !== 1'b1 && w < TIMEOUT) begin
                w = w + 1;
                tick;
            end
            if (s_in_fire !== 1'b1) err("beat was never accepted");
            in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        end
    endtask

    // Run until every queued result has been transferred (out_ready forced high).
    task drain;
        integer w;
        begin
            in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
            rnd_ready = 1'b0;
            out_ready = 1'b1;
            w = 0;
            tick;
            while (sb_rd != sb_wr && w < TIMEOUT) begin
                w = w + 1;
                tick;
            end
            if (sb_rd != sb_wr) err("results still queued after drain");
        end
    endtask

    // Offer single-beat sums (in_first && in_last) in every cycle for n cycles
    // with out_ready high. Fresh random operands after each accepted beat.
    // Per cycle c (< LOGN): lg_adm[c] = beat accepted, lg_st[c] = voted state.
    reg          lg_adm [0:LOGN-1];
    reg [1:0]    lg_st  [0:LOGN-1];
    integer      st_cnt [0:3];
    integer      adm_cnt;

    task stream(input integer n);
        integer c;
        begin
            adm_cnt = 0;
            for (c = 0; c < 4; c = c + 1) st_cnt[c] = 0;
            out_ready = 1'b1;
            in_valid  = 1'b1; in_first = 1'b1; in_last = 1'b1;
            in_a = rnd32(1'b0); in_b = rnd32(1'b0);
            for (c = 0; c < n; c = c + 1) begin
                tick;
                if (s_in_fire === 1'b1) begin
                    adm_cnt = adm_cnt + 1;
                    in_a = rnd32(1'b0);
                    in_b = rnd32(1'b0);
                end
                st_cnt[s_state] = st_cnt[s_state] + 1;
                if (c < LOGN) begin
                    lg_adm[c] = s_in_fire;
                    lg_st[c]  = s_state;
                end
            end
            in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        end
    endtask

    // Apply a sensor reading for one cycle and check the state after the edge.
    task temp_step(input v, input integer t, input [1:0] want);
        begin
            set_temp(v, t);
            tick;
            chk(therm_state === want, "thermal state after one reading");
            if (therm_state !== want && n_errors <= 40)
                $display("      reading valid=%0d t=%0d: state %0d, want %0d", v, t, therm_state, want);
        end
    endtask

    // ------------------------------------------------------------------
    // Signed edge cases (SPEC section 9, claim 1)
    // ------------------------------------------------------------------
    integer case_a [0:7];
    integer case_b [0:7];
    reg [31:0] case_p [0:7];           // hand-computed products

    initial begin
        case_a[0] = -128; case_b[0] = -128; case_p[0] = 32'h0000_4000;  //  16384
        case_a[1] =  127; case_b[1] = -128; case_p[1] = 32'hFFFF_C080;  // -16256
        case_a[2] = -128; case_b[2] =  127; case_p[2] = 32'hFFFF_C080;  // -16256
        case_a[3] =  127; case_b[3] =  127; case_p[3] = 32'h0000_3F01;  //  16129
        case_a[4] =   -1; case_b[4] =   -1; case_p[4] = 32'h0000_0001;  //      1
        case_a[5] =    0; case_b[5] = -128; case_p[5] = 32'h0000_0000;  //      0
        case_a[6] =   -1; case_b[6] =  127; case_p[6] = 32'hFFFF_FF81;  //   -127
        case_a[7] =  100; case_b[7] =   -3; case_p[7] = 32'hFFFF_FED4;  //   -300
    end

    // ------------------------------------------------------------------
    // Test sequence
    // ------------------------------------------------------------------
    integer i, k, r, n, cnt;
    reg     good;
    reg [W-1:0] held;
    integer a0, b0, a1, b1;
    reg wl;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("maxerr=%d", maxerr)) maxerr = 0;
        prng = seed ^ 32'h9E37_79B9;
        if (prng == 32'd0) prng = 32'h1;
        scen = "init";
        n_cycles = 0; n_model_checks = 0; n_model_err = 0;
        n_scen_checks = 0; n_scen_err = 0; n_errors = 0;
        n_in_fire = 0; n_out_fire = 0; n_lit_checks = 0; n_dropped = 0; n_b2b = 0;
        n_scenarios = 0;
        sb_wr = 0; sb_rd = 0;
        lit_mask = {LANES{1'b0}}; lit_value = {W{1'b0}};
        last_out = {W{1'b0}};
        m_live = 1'b0; m_rdy = 1'b0; rnd_ready = 1'b0;
        m_ovq = 1'b0; m_phase = 1'b0; m_state = STOP; m_res = {W{1'b0}};
        for (i = 0; i < LANES; i = i + 1) begin
            t_acc[i] = 32'd0;
            m_acc[i] = 32'd0;
        end

        // Inputs are only ever changed at the falling edge.
        rst_n = 1'b0; in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        in_a = 0; in_b = 0; out_ready = 1'b1; temp_valid = 1'b1; temp_c = 8'd25;
        clear_fault = 1'b0;
        @(negedge clk);

        // ---- 1. Reset lands in STOP; nothing admitted until a valid reading <= 70 C
        start("reset_stop");
        in_valid = 1'b1; in_first = 1'b1; in_last = 1'b1;   // a beat waiting all along
        in_a = pk8(3, -4, 5, -6); in_b = pk8(7, 8, -9, -10);
        expect_lit(4'hF, pk32(32'd21, 32'hFFFF_FFE0, 32'hFFFF_FFD3, 32'd60));
        cnt = 0;
        repeat (4) tick;                                     // reset asserted, cool reading
        chk(s_state === STOP && s_shutdown === 1'b1 && s_in_ready === 1'b0 &&
            s_out_valid === 1'b0 && fault === 1'b0, "in reset: STOP, in_ready=0, out_valid=0, fault=0");
        rst_n = 1'b1;
        set_temp(1'b0, 20);                                  // invalid sensor (value would be cool)
        repeat (6) begin tick; chk(s_state === STOP && s_in_ready === 1'b0, "invalid sensor after reset: STOP, in_ready=0"); if (s_in_fire === 1'b1) cnt = cnt + 1; end
        set_temp(1'b1, 90);
        repeat (6) begin tick; chk(s_state === STOP && s_in_ready === 1'b0, "90 C after reset: STOP (no STOP->THROTTLE)"); if (s_in_fire === 1'b1) cnt = cnt + 1; end
        set_temp(1'b1, 71);
        repeat (6) begin tick; chk(s_state === STOP && s_in_ready === 1'b0, "71 C after reset: STOP (hysteresis)"); if (s_in_fire === 1'b1) cnt = cnt + 1; end
        set_temp(1'b1, 70);
        tick;                                                // reading is registered at this edge
        chk(s_state === STOP && s_in_ready === 1'b0, "cycle with the first 70 C reading still STOP");
        if (s_in_fire === 1'b1) cnt = cnt + 1;
        chk(cnt == 0, "no beat accepted before the first valid reading <= 70 C");
        tick;
        chk(s_state === NORMAL && s_shutdown === 1'b0 && s_in_ready === 1'b1 && s_in_fire === 1'b1,
            "first NORMAL cycle admits the waiting beat");
        in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        set_temp(1'b1, 25);
        drain;
        chk(n_out_fire == 1, "exactly one result after reset scenario");

        // ---- 2. Signed edge cases, a different case in each lane, all rotations
        start("signed_edges");
        for (r = 0; r < 8; r = r + 1) begin
            expect_lit(4'hF, pk32(case_p[(0 + r) % 8], case_p[(1 + r) % 8],
                                  case_p[(2 + r) % 8], case_p[(3 + r) % 8]));
            beat(1'b1, 1'b1,
                 pk8(case_a[(0 + r) % 8], case_a[(1 + r) % 8], case_a[(2 + r) % 8], case_a[(3 + r) % 8]),
                 pk8(case_b[(0 + r) % 8], case_b[(1 + r) % 8], case_b[(2 + r) % 8], case_b[(3 + r) % 8]));
        end
        drain;
        // Swapped operand order gives the same products.
        for (r = 0; r < 8; r = r + 1) begin
            expect_lit(4'hF, pk32(case_p[(0 + r) % 8], case_p[(1 + r) % 8],
                                  case_p[(2 + r) % 8], case_p[(3 + r) % 8]));
            beat(1'b1, 1'b1,
                 pk8(case_b[(0 + r) % 8], case_b[(1 + r) % 8], case_b[(2 + r) % 8], case_b[(3 + r) % 8]),
                 pk8(case_a[(0 + r) % 8], case_a[(1 + r) % 8], case_a[(2 + r) % 8], case_a[(3 + r) % 8]));
        end
        drain;

        // ---- 3. Multi-beat sums
        start("multi_beat");
        // 3 x (-128*-128), 3 x (127*-128), 3 x (-128*127), 3 x (-1*-1)
        beat(1'b1, 1'b0, pk8(-128, 127, -128, -1), pk8(-128, -128, 127, -1));
        beat(1'b0, 1'b0, pk8(-128, 127, -128, -1), pk8(-128, -128, 127, -1));
        expect_lit(4'hF, pk32(32'h0000_C000, 32'hFFFF_4180, 32'hFFFF_4180, 32'd3));
        beat(1'b0, 1'b1, pk8(-128, 127, -128, -1), pk8(-128, -128, 127, -1));
        drain;
        // Mixed signs with idle gaps inside the sum: 10*3 - 7*9 + (-2)*(-8) = -17, ...
        beat(1'b1, 1'b0, pk8(10, -1, 0, 127), pk8(3, 1, 55, 1));
        idle(3);
        beat(1'b0, 1'b0, pk8(-7, -1, 0, 127), pk8(9, 1, -55, 1));
        idle(1);
        expect_lit(4'hF, pk32(32'hFFFF_FFEF, 32'hFFFF_FFFD, 32'd0, 32'd381));
        beat(1'b0, 1'b1, pk8(-2, -1, 0, 127), pk8(-8, 1, 99, 1));
        drain;
        // Pseudo-random sums of several lengths, back to back (scoreboard-checked).
        for (n = 2; n <= 128; n = n * 2) begin
            for (k = 0; k < n; k = k + 1) begin
                ra = rnd32(1'b0); rb = rnd32(1'b0);
                beat(k == 0, k == n - 1, ra, rb);
            end
        end
        drain;
        // Same, with random out_ready and idle gaps.
        rnd_ready = 1'b1;
        for (n = 1; n <= 40; n = n + 3) begin
            for (k = 0; k < n; k = k + 1) begin
                ra = rnd32(1'b0); rb = rnd32(1'b0);
                beat(k == 0, k == n - 1, ra, rb);
                rf = rnd32(1'b0);
                if (rf[1:0] == 2'd0) idle(1);
            end
        end
        drain;

        // ---- 4. in_first && in_last in one beat discards a sum in progress
        start("first_and_last");
        beat(1'b1, 1'b0, pk8(100, 100, 100, 100), pk8(100, 100, 100, 100));
        beat(1'b0, 1'b0, pk8(100, 100, 100, 100), pk8(100, 100, 100, 100));
        expect_lit(4'hF, pk32(32'hFFFF_FFE7, 32'd25, 32'd0, 32'hFFFF_C080));
        beat(1'b1, 1'b1, pk8(5, -5, 0, 127), pk8(-5, -5, 77, -128));
        drain;
        expect_lit(4'hF, pk32(32'd1, 32'd1, 32'd1, 32'd1));
        beat(1'b1, 1'b1, pk8(1, 1, 1, 1), pk8(1, 1, 1, 1));
        drain;

        // ---- 5. A sum continues across an earlier in_last when in_first is low
        start("continue_after_last");
        expect_lit(4'hF, pk32(32'd10, 32'hFFFF_FFF6, 32'd16384, 32'd0));
        beat(1'b1, 1'b1, pk8(5, -5, -128, 0), pk8(2, 2, -128, 9));
        expect_lit(4'hF, pk32(32'd15, 32'hFFFF_FFF1, 32'd32768, 32'd1));
        beat(1'b0, 1'b1, pk8(5, -5, -128, 1), pk8(1, 1, -128, 1));
        beat(1'b0, 1'b0, pk8(1, 1, 1, 1), pk8(7, 7, 7, 7));
        expect_lit(4'hF, pk32(32'hFFFF_FFF8, 32'hFFFF_FFE9, 32'd32745, 32'hFFFF_FFE8));
        beat(1'b0, 1'b1, pk8(-6, -3, -2, 16), pk8(5, 5, 15, -2));
        drain;
        // The same result is presented again only by a new in_last.
        expect_lit(4'hF, pk32(32'hFFFF_FFF8, 32'hFFFF_FFE9, 32'd32745, 32'hFFFF_FFE8));
        beat(1'b0, 1'b1, 32'd0, 32'd0);
        drain;

        // ---- 6. Output backpressure
        start("backpressure");
        out_ready = 1'b0;
        expect_lit(4'hF, pk32(32'd6, 32'd12, 32'd20, 32'd30));
        beat(1'b1, 1'b1, pk8(2, 3, 4, 5), pk8(3, 4, 5, 6));       // result X, not taken
        // Offer a NON-last beat: blocked while the buffer is full.
        in_valid = 1'b1; in_first = 1'b1; in_last = 1'b0;
        in_a = pk8(1, 2, 3, 4); in_b = pk8(10, 10, 10, 10);
        tick;
        held = s_out_data;
        good = (s_out_valid === 1'b1 && s_in_ready === 1'b0 && s_in_fire === 1'b0);
        for (k = 0; k < 30; k = k + 1) begin
            tick;
            if (!(s_out_valid === 1'b1 && s_out_data === held && s_in_ready === 1'b0 && s_in_fire === 1'b0))
                good = 1'b0;
        end
        chk(good === 1'b1, "31 stalled cycles: out_valid held, out_data stable, non-last beat blocked");
        chk(held === pk32(32'd6, 32'd12, 32'd20, 32'd30), "held result is X");
        cnt = n_out_fire;
        out_ready = 1'b1;
        tick;
        chk(s_out_fire === 1'b1 && s_in_fire === 1'b1, "draining cycle also accepts the waiting beat");
        // Last beat of that sum with out_ready low again: buffer is empty, so accepted.
        out_ready = 1'b0;
        expect_lit(4'hF, pk32(32'd11, 32'd22, 32'd33, 32'd44));
        in_first = 1'b0; in_last = 1'b1; in_a = pk8(1, 2, 3, 4); in_b = pk8(1, 1, 1, 1);
        tick;
        chk(s_in_fire === 1'b1, "last beat accepted into the empty buffer");
        // Offer a single-beat sum Z (last): blocked for 50 cycles while Y is held.
        in_first = 1'b1; in_last = 1'b1; in_a = pk8(-1, -1, -1, -1); in_b = pk8(9, 8, 7, 6);
        good = 1'b1;
        tick;
        held = s_out_data;
        for (k = 0; k < 50; k = k + 1) begin
            tick;
            if (!(s_out_valid === 1'b1 && s_out_data === held && s_in_ready === 1'b0 && s_in_fire === 1'b0))
                good = 1'b0;
        end
        chk(good === 1'b1, "51 stalled cycles: out_valid held, out_data stable, last beat blocked");
        chk(held === pk32(32'd11, 32'd22, 32'd33, 32'd44), "held result is Y");
        expect_lit(4'hF, pk32(32'hFFFF_FFF7, 32'hFFFF_FFF8, 32'hFFFF_FFF9, 32'hFFFF_FFFA));
        out_ready = 1'b1;
        tick;
        chk(s_out_fire === 1'b1 && s_in_fire === 1'b1, "Y drains and Z is accepted in the same cycle");
        in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        tick;
        chk(s_out_fire === 1'b1 && s_out_data === pk32(32'hFFFF_FFF7, 32'hFFFF_FFF8, 32'hFFFF_FFF9, 32'hFFFF_FFFA),
            "Z transferred right after");
        chk(n_out_fire - cnt == 3, "exactly three results X, Y, Z: none lost or repeated");
        // Random out_ready with a continuous stream of random first/last beats.
        rnd_ready = 1'b1;
        for (k = 0; k < 300; k = k + 1) begin
            rf = rnd32(1'b0); rl = rnd32(1'b0); ra = rnd32(1'b0); rb = rnd32(1'b0);
            beat((rf % 32'd3) == 32'd0, rl[0], ra, rb);
        end
        drain;

        // ---- 7. Back-to-back results, no bubble
        start("back_to_back");
        out_ready = 1'b1;
        cnt = n_b2b; k = n_cycles; i = n_out_fire;
        for (r = 0; r < 32; r = r + 1) begin
            ra = rnd32(1'b0); rb = rnd32(1'b0);
            beat(1'b1, 1'b1, ra, rb);
        end
        chk(n_cycles - k == 32, "32 single-beat sums accepted in 32 consecutive cycles");
        chk(n_b2b - cnt == 31, "31 cycles with in_last accepted together with out_fire");
        tick;
        chk(n_out_fire - i == 32 && n_cycles - k == 33, "32 results transferred in 32 consecutive cycles");
        // Two-beat sums back to back: a result every other cycle, no stall.
        k = n_cycles;
        for (r = 0; r < 16; r = r + 1) begin
            ra = rnd32(1'b0); rb = rnd32(1'b0);
            beat(1'b1, 1'b0, ra, rb);
            ra = rnd32(1'b0); rb = rnd32(1'b0);
            beat(1'b0, 1'b1, ra, rb);
        end
        chk(n_cycles - k == 32, "16 two-beat sums accepted in 32 consecutive cycles");
        drain;

        // ---- 8. Thermal: 79 C NORMAL, 80 C THROTTLE with alternate-cycle admission
        start("throttle");
        set_temp(1'b1, 25);
        stream(10);
        chk(adm_cnt == 10 && st_cnt[NORMAL] == 10, "25 C: NORMAL, a beat every cycle");
        set_temp(1'b1, 79);
        stream(40);
        chk(adm_cnt == 40 && st_cnt[NORMAL] == 40, "79 C for 40 cycles: stays NORMAL, 40 beats admitted");
        set_temp(1'b1, 80);
        stream(41);                        // cycle 0 still NORMAL, cycles 1..40 THROTTLE
        good = (lg_st[0] === NORMAL && lg_adm[0] === 1'b1);
        for (k = 1; k <= 40; k = k + 1)
            if (lg_st[k] !== THROTTLE || lg_adm[k] !== (((k - 1) % 2) == 0)) good = 1'b0;
        chk(good === 1'b1, "80 C: THROTTLE from the next cycle, admits exactly alternate cycles");
        chk(lg_st[1] === THROTTLE && lg_adm[1] === 1'b1, "the first THROTTLE cycle admits");
        chk(adm_cnt == 21 && st_cnt[THROTTLE] == 40, "40 THROTTLE cycles admit exactly 20 beats");
        set_temp(1'b1, 94);
        stream(20);
        chk(st_cnt[THROTTLE] == 20 && adm_cnt == 10, "94 C: stays THROTTLE, 10 of 20 admitted");
        set_temp(1'b1, 71);
        stream(20);
        chk(st_cnt[THROTTLE] == 20 && adm_cnt == 10, "71 C: stays THROTTLE (hysteresis), 10 of 20 admitted");
        set_temp(1'b1, 70);
        stream(21);                        // cycle 0 THROTTLE, then NORMAL
        chk(lg_st[0] === THROTTLE && lg_st[1] === NORMAL && st_cnt[NORMAL] == 20,
            "70 C: THROTTLE -> NORMAL after one cycle");
        good = 1'b1;
        for (k = 1; k <= 20; k = k + 1) if (lg_adm[k] !== 1'b1) good = 1'b0;
        chk(good === 1'b1, "after recovery every cycle admits again");
        // One admitting THROTTLE cycle, one NORMAL cycle (the phase flip-flop
        // toggled to 1 in it), THROTTLE again: the phase must have been forced
        // to 0, so the first cycle of the new THROTTLE admits.
        set_temp(1'b1, 85);
        stream(1);                         // NORMAL, 85 C registered
        chk(lg_st[0] === NORMAL, "85 C applied in NORMAL");
        set_temp(1'b1, 60);
        stream(1);                         // THROTTLE (admits), 60 C registered
        chk(lg_st[0] === THROTTLE && lg_adm[0] === 1'b1, "single THROTTLE cycle admits");
        set_temp(1'b1, 81);
        stream(5);                         // NORMAL, THROTTLE: admit, block, admit, block
        chk(lg_st[0] === NORMAL && lg_st[1] === THROTTLE && lg_adm[1] === 1'b1 && lg_adm[2] === 1'b0 &&
            lg_adm[3] === 1'b1 && lg_adm[4] === 1'b0,
            "THROTTLE after one NORMAL cycle: first cycle admits (phase forced to 0)");
        set_temp(1'b1, 95);
        stream(2);                         // THROTTLE (admits), then STOP
        chk(lg_st[0] === THROTTLE && lg_adm[0] === 1'b1 && lg_st[1] === STOP && lg_adm[1] === 1'b0,
            "95 C from THROTTLE: STOP next cycle");
        set_temp(1'b1, 70);
        stream(2);                         // STOP, then NORMAL
        chk(lg_st[0] === STOP && lg_st[1] === NORMAL, "70 C: STOP -> NORMAL");
        set_temp(1'b1, 80);
        stream(4);
        chk(lg_st[1] === THROTTLE && lg_adm[1] === 1'b1 && lg_adm[2] === 1'b0 && lg_adm[3] === 1'b1,
            "THROTTLE after STOP: first cycle admits");
        set_temp(1'b1, 25);
        stream(2);
        drain;

        // ---- 9. STOP at 95 C and on an invalid sensor; hysteresis; state sequences
        start("stop_and_recover");
        temp_step(1'b1,  25, NORMAL);
        temp_step(1'b1,  94, THROTTLE);    // 94 from NORMAL throttles, does not stop
        temp_step(1'b1,  95, STOP);        // THROTTLE -> STOP at 95
        temp_step(1'b1,  94, STOP);        // STOP holds above 70 ...
        temp_step(1'b1,  80, STOP);        // ... never STOP -> THROTTLE
        temp_step(1'b1,  71, STOP);
        temp_step(1'b1,  70, NORMAL);      // recovery at exactly 70
        temp_step(1'b1,  95, STOP);        // NORMAL -> STOP at 95
        temp_step(1'b1,  50, NORMAL);
        temp_step(1'b1, 127, STOP);        // hottest reading
        temp_step(1'b1,  69, NORMAL);
        temp_step(1'b0,  25, STOP);        // invalid sensor from NORMAL (value is cool)
        temp_step(1'b0,  25, STOP);
        temp_step(1'b1,  25, NORMAL);
        temp_step(1'b1,  88, THROTTLE);
        temp_step(1'b0,  60, STOP);        // invalid sensor from THROTTLE
        temp_step(1'b0, -20, STOP);
        temp_step(1'b1,  96, STOP);
        temp_step(1'b1,  60, NORMAL);
        temp_step(1'b1,  79, NORMAL);
        temp_step(1'b1,  80, THROTTLE);
        temp_step(1'b1,  71, THROTTLE);
        temp_step(1'b1,  70, NORMAL);
        // Nothing is admitted in STOP.
        set_temp(1'b1, 100);
        stream(12);
        chk(lg_st[0] === NORMAL && st_cnt[STOP] == 11 && adm_cnt == 1, "100 C: STOP admits nothing");
        good = 1'b1;
        for (k = 1; k < 12; k = k + 1) if (lg_adm[k] !== 1'b0) good = 1'b0;
        chk(good === 1'b1 && shutdown_req === 1'b1, "STOP: in_ready low every cycle, shutdown_req high");
        set_temp(1'b0, 0);
        stream(5);
        chk(st_cnt[STOP] == 5 && adm_cnt == 0, "invalid sensor: STOP admits nothing");
        set_temp(1'b1, 25);
        idle(2);
        drain;

        // ---- 10. The output buffer drains while STOP
        start("drain_in_stop");
        out_ready = 1'b0;
        expect_lit(4'hF, pk32(32'd42, 32'hFFFF_FFD6, 32'd0, 32'd1));
        beat(1'b1, 1'b1, pk8(6, -6, 0, 1), pk8(7, 7, 7, 1));
        set_temp(1'b1, 110);
        in_valid = 1'b1; in_first = 1'b1; in_last = 1'b1; in_a = 32'h01010101; in_b = 32'h01010101;
        tick;                              // reading registered
        good = 1'b1;
        for (k = 0; k < 10; k = k + 1) begin
            tick;
            if (!(s_state === STOP && s_out_valid === 1'b1 && s_in_ready === 1'b0)) good = 1'b0;
        end
        chk(good === 1'b1, "STOP with a full buffer: result held, input blocked");
        cnt = n_out_fire;
        out_ready = 1'b1;
        tick;
        chk(s_state === STOP && s_out_fire === 1'b1 && s_in_fire === 1'b0,
            "result transferred while STOP, no beat admitted");
        tick;
        chk(s_out_valid === 1'b0 && n_out_fire - cnt == 1, "buffer empty after the drain");
        in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        set_temp(1'b1, 30);
        idle(2);
        drain;

        // ---- 11. Negative temperatures are cold (signed comparison)
        start("negative_temps");
        set_temp(1'b1, 100);
        idle(2);
        chk(therm_state === STOP, "hot reading: STOP");
        set_temp(1'b1, -40);
        stream(10);
        chk(lg_st[0] === STOP && st_cnt[NORMAL] == 9 && adm_cnt == 9, "-40 C: STOP -> NORMAL");
        set_temp(1'b1, -1);
        stream(10);
        chk(st_cnt[NORMAL] == 10 && adm_cnt == 10, "-1 C (0xFF): NORMAL");
        set_temp(1'b1, -128);
        stream(10);
        chk(st_cnt[NORMAL] == 10 && adm_cnt == 10, "-128 C (0x80): NORMAL");
        temp_step(1'b1, 90, THROTTLE);
        temp_step(1'b1, -1, NORMAL);       // THROTTLE -> NORMAL on a negative reading
        temp_step(1'b1, 99, STOP);
        temp_step(1'b1, -128, NORMAL);     // STOP -> NORMAL on the most negative reading
        set_temp(1'b1, 25);
        drain;

        // ---- 12. INT32 wraparound in both directions, no fault
        start("int32_wrap");
        out_ready = 1'b1;
        for (k = 1; k <= 132106; k = k + 1) begin
            // lane 0: 131071 x 16384 = 0x7FFFC000, +16129 +254 = INT_MAX, +1 wraps to INT_MIN,
            //         zeros, then -1 wraps back to INT_MAX
            if (k <= 131071)      begin a0 = -128; b0 = -128; end
            else if (k == 131072) begin a0 =  127; b0 =  127; end
            else if (k == 131073) begin a0 =  127; b0 =    2; end
            else if (k == 131074) begin a0 =    1; b0 =    1; end
            else if (k <  132106) begin a0 =    0; b0 =    0; end
            else                  begin a0 =   -1; b0 =    1; end
            // lane 1: 132104 x -16256 = INT_MIN + 1024, -1024 = INT_MIN, -1 wraps to INT_MAX
            if (k <= 132104)      begin a1 = -128; b1 =  127; end
            else if (k == 132105) begin a1 =  -32; b1 =   32; end
            else                  begin a1 =   -1; b1 =    1; end
            // lane 2: +16384 every beat (wraps upward); lane 3: -16256 every beat (wraps downward)
            wl = 1'b1;
            case (k)
                131071: expect_lit(4'hF, pk32(32'h7FFF_C000, 32'h8100_3F80, 32'h7FFF_C000, 32'h8100_3F80));
                131073: expect_lit(4'hF, pk32(32'h7FFF_FFFF, 32'h80FF_C080, 32'h8000_4000, 32'h80FF_C080));
                131074: expect_lit(4'hF, pk32(32'h8000_0000, 32'h80FF_8100, 32'h8000_8000, 32'h80FF_8100));
                132104: expect_lit(4'hF, pk32(32'h8000_0000, 32'h8000_0400, 32'h8102_0000, 32'h8000_0400));
                132105: expect_lit(4'hF, pk32(32'h8000_0000, 32'h8000_0000, 32'h8102_4000, 32'h7FFF_C480));
                132106: expect_lit(4'hF, pk32(32'h7FFF_FFFF, 32'h7FFF_FFFF, 32'h8102_8000, 32'h7FFF_8500));
                default: wl = 1'b0;
            endcase
            beat(k == 1, wl, pk8(a0, a1, -128, 127), pk8(b0, b1, -128, -128));
        end
        drain;
        chk(fault === 1'b0 && n_model_err == 0, "no fault and no model mismatch across both wraps");
        chk(last_out === pk32(32'h7FFF_FFFF, 32'h7FFF_FFFF, 32'h8102_8000, 32'h7FFF_8500),
            "final wrapped sums (no saturation)");

        // ---- 13. clear_fault zeroes the sums, empties the buffer, holds in_ready low
        start("clear_fault");
        out_ready = 1'b1;
        beat(1'b1, 1'b0, pk8(100, -100, 50, 7), pk8(100, 100, 50, 7));   // sum in progress
        out_ready = 1'b0;
        beat(1'b0, 1'b1, pk8(1, 1, 1, 1), pk8(1, 1, 1, 1));               // result pending
        in_valid = 1'b1; in_first = 1'b0; in_last = 1'b1;                 // beat offered throughout
        in_a = pk8(3, -3, 127, -128); in_b = pk8(3, 3, -128, -128);
        clear_fault = 1'b1;
        cnt = n_dropped;
        tick;
        chk(s_in_ready === 1'b0 && s_in_fire === 1'b0, "in_ready low in the first clear_fault cycle");
        good = 1'b1;
        for (k = 0; k < 5; k = k + 1) begin
            out_ready = k[0];              // draining is irrelevant: the buffer is empty
            tick;
            if (!(s_in_ready === 1'b0 && s_in_fire === 1'b0 && s_out_valid === 1'b0 &&
                  s_out_data === {W{1'b0}} && fault === 1'b0)) good = 1'b0;
        end
        chk(good === 1'b1, "while clear_fault: in_ready low, buffer empty, out_data zero, no fault");
        chk(n_dropped - cnt == 1, "the pending result was discarded by clear_fault");
        clear_fault = 1'b0;
        out_ready = 1'b1;
        // Next sum without in_first starts from 0.
        expect_lit(4'hF, pk32(32'd9, 32'hFFFF_FFF7, 32'hFFFF_C080, 32'h0000_4000));
        tick;
        chk(s_in_fire === 1'b1, "beat accepted once clear_fault is released");
        in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        drain;
        chk(last_out === pk32(32'd9, 32'hFFFF_FFF7, 32'hFFFF_C080, 32'h0000_4000),
            "sum after clear_fault started from zero");
        // clear_fault does not touch the thermal state (THROTTLE survives it).
        set_temp(1'b1, 85);
        idle(2);
        clear_fault = 1'b1;
        idle(4);
        chk(therm_state === THROTTLE, "clear_fault leaves THROTTLE alone");
        clear_fault = 1'b0;
        set_temp(1'b1, 25);
        idle(2);
        chk(therm_state === NORMAL, "recovered");
        // A one-cycle clear with an empty buffer, then a continuing (no in_first) beat.
        beat(1'b1, 1'b0, pk8(9, 9, 9, 9), pk8(9, 9, 9, 9));
        clear_fault = 1'b1;
        in_valid = 1'b1; in_first = 1'b0; in_last = 1'b1; in_a = pk8(2, 2, 2, 2); in_b = pk8(-3, 3, -3, 3);
        tick;
        chk(s_in_fire === 1'b0, "in_ready low during a single-cycle clear_fault");
        clear_fault = 1'b0;
        expect_lit(4'hF, pk32(32'hFFFF_FFFA, 32'd6, 32'hFFFF_FFFA, 32'd6));
        tick;
        chk(s_in_fire === 1'b1, "accepted after the clear");
        in_valid = 1'b0; in_first = 1'b0; in_last = 1'b0;
        drain;

        // ---- End
        idle(3);
        scen = "end";
        chk(sb_rd == sb_wr, "scoreboard empty: every result accounted for");
        chk(fault === 1'b0, "fault never raised in fault-free operation");

        $display("");
        $display("tb_orbit_demo summary (seed %0d)", seed);
        $display("  scenarios            %0d", n_scenarios);
        $display("  cycles               %0d", n_cycles);
        $display("  model cycle checks   %0d (mismatches %0d)", n_model_checks, n_model_err);
        $display("  scenario checks      %0d (failed %0d)", n_scen_checks, n_scen_err);
        $display("  beats accepted       %0d", n_in_fire);
        $display("  results transferred  %0d (all compared with the scoreboard)", n_out_fire);
        $display("  literal lane checks  %0d", n_lit_checks);
        $display("  back-to-back results %0d", n_b2b);
        $display("  results dropped by clear_fault/reset %0d", n_dropped);
        $display("  errors               %0d", n_errors);
        if (n_errors == 0 && n_model_checks > 0 && n_out_fire > 0) begin
            $display("TB_ORBIT_DEMO PASS");
            $finish;
        end else begin
            $display("TB_ORBIT_DEMO FAIL");
            $fatal(1, "tb_orbit_demo: %0d errors", n_errors);
        end
    end

    // Global watchdog.
    initial begin
        #(64'd2 * HALF * 64'd400000);
        $display("TB_ORBIT_DEMO FAIL: watchdog timeout");
        $fatal(1, "tb_orbit_demo: watchdog");
    end

endmodule

`default_nettype wire
