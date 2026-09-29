// Post-route gate-level simulation of orbit_demo: RTL vs routed netlist in
// lockstep, with fault injection into every redundant storage copy.
//
//   rtl : orbit_demo     (the RTL, $(RTL))
//   gl  : orbit_demo_gl  (ORFS 6_final.v, top renamed by pd/gls/gen_gls.py;
//                         cell models generated from the timing liberty)
//
// Both get the same constrained-random stimulus (INT8 edge values, random
// first/last framing, output backpressure, a temperature profile that walks
// through NORMAL / THROTTLE / STOP, invalid sensor readings, resets and
// clear_fault). Every output is compared every cycle, just before the rising
// edge. Zero-delay simulation: this checks function, not timing (timing is
// covered by OpenSTA in the ORFS flow).
//
// Every INJ_EVERY cycles one redundant storage bit (all 518, in turn) is
// inverted in both models at the falling edge (SPEC section 7). The netlist
// must then behave exactly like the RTL, and additionally:
//   duplicated copy : out_valid = in_ready = 0 in that cycle, fault = 1 after
//                     the next edge (the stop the SPEC promises);
//   thermal copy    : therm_repair = 1 in that cycle with the voted state
//                     unchanged, therm_repair = 0 after the next edge.
// If synthesis had merged two copies into one flip-flop, the flipped cell
// would drive both "copies" and these checks (and the lockstep compare) fail.
//
// Plusargs: +cycles=N (default 25000), +seed=S (default 1).
// Prints "GLS PASS" or "GLS FAIL"; $finish either way.

`timescale 1ns / 1ps
`default_nettype none

module tb_gls;

    localparam integer LANES     = 4;
    localparam integer INJ_EVERY = 40;

    reg                clk = 1'b0;
    reg                rst_n = 1'b0;
    reg                in_valid = 1'b0, in_first = 1'b0, in_last = 1'b0;
    reg [LANES*8-1:0]  in_a = 0, in_b = 0;
    reg                out_ready = 1'b0;
    reg                temp_valid = 1'b0;
    reg [7:0]          temp_c = 8'd25;
    reg                clear_fault = 1'b0;

    wire               r_in_ready, g_in_ready, r_out_valid, g_out_valid;
    wire [LANES*32-1:0] r_out_data, g_out_data;
    wire               r_fault, g_fault, r_repair, g_repair, r_shutdown, g_shutdown;
    wire [1:0]         r_state, g_state;

    orbit_demo rtl (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_ready(r_in_ready),
        .in_first(in_first), .in_last(in_last), .in_a(in_a), .in_b(in_b),
        .out_valid(r_out_valid), .out_ready(out_ready), .out_data(r_out_data),
        .temp_valid(temp_valid), .temp_c(temp_c), .clear_fault(clear_fault),
        .fault(r_fault), .therm_state(r_state), .therm_repair(r_repair),
        .shutdown_req(r_shutdown)
    );

    orbit_demo_gl gl (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_ready(g_in_ready),
        .in_first(in_first), .in_last(in_last), .in_a(in_a), .in_b(in_b),
        .out_valid(g_out_valid), .out_ready(out_ready), .out_data(g_out_data),
        .temp_valid(temp_valid), .temp_c(temp_c), .clear_fault(clear_fault),
        .fault(g_fault), .therm_state(g_state), .therm_repair(g_repair),
        .shutdown_req(g_shutdown)
    );

    `include "gl_inject.vh"

    // ------------------------------------------------------------------
    // Stimulus helpers
    // ------------------------------------------------------------------
    integer seed;
    integer cycles;

    function [7:0] rand_int8(input integer dummy);
        integer r;
        begin
            r = $random(seed);
            case ((r >>> 8) & 15)
                0: rand_int8 = 8'h80;       // -128
                1: rand_int8 = 8'h7f;       //  127
                2: rand_int8 = 8'h00;
                3: rand_int8 = 8'hff;       //   -1
                default: rand_int8 = r[7:0];
            endcase
        end
    endfunction

    // Temperature profile: a new band every 300..800 cycles, jitter inside it.
    integer band = 0, band_left = 0;
    reg signed [8:0] t;
    task next_temperature;
        integer r;
        begin
            if (band_left == 0) begin
                r = $random(seed) & 15;
                band = (r < 10) ? 0 : (r < 14) ? 1 : 2;   // normal, throttle, stop
                band_left = 300 + ($random(seed) & 511);
            end
            band_left = band_left - 1;
            case (band)
                0: t = 40 + ($random(seed) & 31);          // 40..71
                1: t = 71 + ($random(seed) & 15);          // 71..86: crosses 80 and 70
                default: t = 92 + ($random(seed) & 7);     // 92..99: crosses 95
            endcase
            temp_c     = t[7:0];
            temp_valid = (($random(seed) & 255) != 0);     // ~0.4 % invalid readings
        end
    endtask

    // ------------------------------------------------------------------
    // Checking
    // ------------------------------------------------------------------
    integer errors = 0;
    integer cyc = 0;
    integer n_in_fire = 0, n_out_fire = 0, n_results_nonzero = 0;
    integer n_state [0:3];
    integer n_throttle_block = 0, n_resets = 0, n_clears = 0;
    integer n_inj_dup = 0, n_inj_tmr = 0, n_dup_stop_ok = 0, n_tmr_repair_ok = 0;
    integer i;

    task compare;
        begin
            if ({r_in_ready, r_out_valid, r_out_data, r_fault, r_state, r_repair, r_shutdown} !==
                {g_in_ready, g_out_valid, g_out_data, g_fault, g_state, g_repair, g_shutdown}) begin
                errors = errors + 1;
                if (errors <= 10) begin
                    $display("MISMATCH cycle %0d: rtl ir=%b ov=%b f=%b st=%0d rep=%b sd=%b data=%h",
                             cyc, r_in_ready, r_out_valid, r_fault, r_state, r_repair, r_shutdown, r_out_data);
                    $display("                    gl  ir=%b ov=%b f=%b st=%0d rep=%b sd=%b data=%h",
                             g_in_ready, g_out_valid, g_fault, g_state, g_repair, g_shutdown, g_out_data);
                end
            end
        end
    endtask

    task check_that(input ok, input [8*48-1:0] what);
        begin
            if (!ok) begin
                errors = errors + 1;
                if (errors <= 10) $display("CHECK FAILED cycle %0d: %0s", cyc, what);
            end
        end
    endtask

    // ------------------------------------------------------------------
    // Main loop: drive after the falling edge, check before the rising edge.
    // ------------------------------------------------------------------
    integer inj_k = 0;
    integer pending = 0;        // 0 none, 1 dup injected this cycle, 2 tmr injected this cycle
    integer after = 0;          // 1 in the cycle following an injection
    integer after_kind = 0;
    integer clear_in = -1;      // cycles until the TB host asserts clear_fault
    reg [1:0] state_before;

    always #5 clk = ~clk;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("cycles=%d", cycles)) cycles = 25000;
        for (i = 0; i < 4; i = i + 1) n_state[i] = 0;
        $display("GLS: %0d cycles, seed %0d, %0d redundant bits, injection every %0d cycles",
                 cycles, seed, N_REDUNDANT_BITS, INJ_EVERY);

        while (cyc < cycles) begin
            @(negedge clk);
            cyc = cyc + 1;

            // --- inputs for this cycle ---------------------------------
            rst_n = !(cyc <= 3 || (cyc % 9973) == 0);
            if (!rst_n) n_resets = n_resets + 1;
            next_temperature;
            in_valid  = (($random(seed) & 3) != 0);
            in_first  = (($random(seed) & 7) == 0);
            in_last   = (($random(seed) & 7) == 0);
            for (i = 0; i < LANES; i = i + 1) begin
                in_a[8*i +: 8] = rand_int8(0);
                in_b[8*i +: 8] = rand_int8(0);
            end
            out_ready = (($random(seed) % 5) != 0);

            // Host behaviour: clear a latched fault a few cycles after it is seen,
            // plus rare spontaneous clears. Never in an injection cycle.
            clear_fault = 1'b0;
            if (clear_in > 0) clear_in = clear_in - 1;
            if (clear_in == 0) begin clear_fault = 1'b1; clear_in = -1; end
            else if (clear_in < 0 && (($random(seed) & 1023) == 0)) clear_fault = 1'b1;
            if (clear_fault) n_clears = n_clears + 1;

            // --- fault injection (after the rising edge, before the next) --
            pending = 0;
            if (rst_n && !clear_fault && cyc > 20 && (cyc % INJ_EVERY) == 0 && !r_fault) begin
                state_before = r_state;
                flip_copy(inj_k);
                pending = flip_kind(inj_k) ? 2 : 1;
                if (pending == 1) n_inj_dup = n_inj_dup + 1; else n_inj_tmr = n_inj_tmr + 1;
                inj_k = (inj_k + 1) % N_REDUNDANT_BITS;
            end

            // --- check just before the rising edge -----------------------
            #4;
            if (cyc > 3) compare;
            if (pending == 1) begin
                check_that(!g_out_valid && !g_in_ready, "dup flip: out_valid/in_ready not forced low");
                if (!g_out_valid && !g_in_ready) n_dup_stop_ok = n_dup_stop_ok + 1;
            end else if (pending == 2) begin
                check_that(g_repair === 1'b1 && g_state === state_before, "tmr flip: no repair or state changed");
                if (g_repair === 1'b1 && g_state === state_before) n_tmr_repair_ok = n_tmr_repair_ok + 1;
            end
            if (after == 1 && after_kind == 1) begin
                check_that(g_fault === 1'b1, "dup flip: fault not latched");
                clear_in = 3 + ($random(seed) & 7);
            end
            if (after == 1 && after_kind == 2)
                check_that(g_repair === 1'b0, "tmr flip: copy not repaired at the edge");
            after = (pending != 0);
            after_kind = pending;

            // --- coverage ------------------------------------------------
            if (rst_n) begin
                n_state[r_state] = n_state[r_state] + 1;
                if (in_valid && r_in_ready) n_in_fire = n_in_fire + 1;
                if (r_out_valid && out_ready) begin
                    n_out_fire = n_out_fire + 1;
                    if (r_out_data != 0) n_results_nonzero = n_results_nonzero + 1;
                end
                if (r_state == 1 && in_valid && !r_in_ready && !r_out_valid && !r_fault)
                    n_throttle_block = n_throttle_block + 1;
            end
        end

        $display("coverage: beats accepted %0d, results taken %0d (%0d non-zero), resets %0d, clears %0d",
                 n_in_fire, n_out_fire, n_results_nonzero, n_resets, n_clears);
        $display("coverage: cycles NORMAL %0d, THROTTLE %0d, STOP %0d, code3 %0d; throttle-blocked beats %0d",
                 n_state[0], n_state[1], n_state[2], n_state[3], n_throttle_block);
        $display("injections: %0d duplicated-copy flips (%0d stopped), %0d thermal-copy flips (%0d repaired), %0d of %0d bits",
                 n_inj_dup, n_dup_stop_ok, n_inj_tmr, n_tmr_repair_ok,
                 (n_inj_dup + n_inj_tmr < N_REDUNDANT_BITS) ? n_inj_dup + n_inj_tmr : N_REDUNDANT_BITS,
                 N_REDUNDANT_BITS);

        // The run must actually have exercised the design.
        check_that(n_out_fire > 500 && n_results_nonzero > 400, "too few results transferred");
        check_that(n_state[0] > 1000 && n_state[1] > 500 && n_state[2] > 500, "thermal states not all visited");
        check_that(n_throttle_block > 50, "throttling never blocked a beat");
        check_that(n_inj_dup + n_inj_tmr >= N_REDUNDANT_BITS, "not every redundant bit was injected");

        if (errors == 0) $display("GLS PASS: %0d cycles, 0 mismatches", cycles);
        else             $display("GLS FAIL: %0d errors", errors);
        $finish;
    end

endmodule

`default_nettype wire
