// Simulation single-event-upset (SEU) campaign for orbit_demo (Icarus Verilog).
//
// Two copies of the production design run side by side, each behind its own
// host (seu_host: stimulus driver, scoreboard, fault reaction):
//   u_dut   the copy that receives the upset
//   u_gold  an identical, never-upset copy (fault-free reference run)
// Both hosts see the same per-cycle environment (reset, temperature,
// out_ready, beat offers, scheduled clear_fault) and send the same beat
// sequence, each at the pace its own design accepts it.
//
// One trial: reset, a random prefix, then exactly one stored bit of u_dut is
// flipped by hierarchical assignment at the falling clock edge (SPEC section
// 7; bit id 0..520 in the order of the storage map below), then the run
// continues POST cycles, and a drain (favourable conditions, then no new
// beats) lets every accepted result come out. Trials with id -1 inject
// nothing (controls; they must come out MASKED).
//
// Bit ids (the state vector of seu_host):
//   0..127   accumulator copy A, lane i at 32*i      256..383 result copy A
//   128..255 accumulator copy B                      384..511 result copy B
//   512..517 thermal copies 0,1,2 (2 bits each)      518 phase, 519 out_valid_q, 520 fault_q
//
// Outcome of a trial (first match wins; see fault/campaign_report.py):
//   SDC       a transferred result differs from the scoreboard's expectation
//   LOST      an accepted result was dropped without a fault (overwritten or
//             never delivered)
//   EXTRA     a result was transferred when none was pending (duplicate or
//             stale re-presentation)
//   HANG      no fault, but no beat accepted under favourable conditions
//   OTHER     a stop that did not block the handshakes (structural check)
//   DETECTED  fault rose (the host then clears it); no wrong data transferred
//   TIMING    no fault, all data correct, but the port trace differs from the
//             fault-free run (e.g. a shifted throttled admission)
//   REPAIRED  only therm_repair differed from the fault-free run
//   MASKED    port trace identical to the fault-free run
//
// Plusargs: +seed=<n> +tpb=<trials per protected bit> +tpb_unprot=<trials
// per unprotected flip-flop> +controls=<n> +out=<trial log> +first=<id>
// +last=<id>

`timescale 1ns/1ps
`default_nettype none

module seu_host (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         temp_valid,
    input  wire [7:0]   temp_c,
    input  wire         out_ready,
    input  wire         offer,          // offer the pending beat this cycle
    input  wire         sched_clear,    // host-scheduled clear_fault
    input  wire         trial_start,    // load beat_seed, clear the counters
    input  wire [31:0]  beat_seed
);

    // ------------------------------------------------------------------
    // Design and its ports
    // ------------------------------------------------------------------
    reg          in_first, in_last;
    reg  [31:0]  in_a, in_b;
    reg          auto_clear;
    wire         in_valid    = offer;
    wire         clear_fault = sched_clear | auto_clear;
    wire         in_ready, out_valid, fault, therm_repair, shutdown_req;
    wire [127:0] out_data;
    wire [1:0]   therm_state;

    orbit_demo dut (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_ready(in_ready),
        .in_first(in_first), .in_last(in_last), .in_a(in_a), .in_b(in_b),
        .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data),
        .temp_valid(temp_valid), .temp_c(temp_c), .clear_fault(clear_fault),
        .fault(fault), .therm_state(therm_state), .therm_repair(therm_repair),
        .shutdown_req(shutdown_req)
    );

    wire in_fire  = in_valid & in_ready;
    wire out_fire = out_valid & out_ready;

    // Complete storage (SPEC section 7) as one vector; index = bit id.
    wire [520:0] state = {
        dut.fault_q, dut.out_valid_q, dut.u_thermal.phase,
        dut.u_thermal.u_copy2.q, dut.u_thermal.u_copy1.q, dut.u_thermal.u_copy0.q,
        dut.g_lane[3].u_lane.u_res_b.q, dut.g_lane[2].u_lane.u_res_b.q,
        dut.g_lane[1].u_lane.u_res_b.q, dut.g_lane[0].u_lane.u_res_b.q,
        dut.g_lane[3].u_lane.u_res_a.q, dut.g_lane[2].u_lane.u_res_a.q,
        dut.g_lane[1].u_lane.u_res_a.q, dut.g_lane[0].u_lane.u_res_a.q,
        dut.g_lane[3].u_lane.u_acc_b.q, dut.g_lane[2].u_lane.u_acc_b.q,
        dut.g_lane[1].u_lane.u_acc_b.q, dut.g_lane[0].u_lane.u_acc_b.q,
        dut.g_lane[3].u_lane.u_acc_a.q, dut.g_lane[2].u_lane.u_acc_a.q,
        dut.g_lane[1].u_lane.u_acc_a.q, dut.g_lane[0].u_lane.u_acc_a.q};

    // Flip one stored bit (call at the falling edge only).
    task flip_bit(input integer id);
        integer b;
        begin
            b = id % 32;
            case (id / 32)
                0:  dut.g_lane[0].u_lane.u_acc_a.q[b] = ~dut.g_lane[0].u_lane.u_acc_a.q[b];
                1:  dut.g_lane[1].u_lane.u_acc_a.q[b] = ~dut.g_lane[1].u_lane.u_acc_a.q[b];
                2:  dut.g_lane[2].u_lane.u_acc_a.q[b] = ~dut.g_lane[2].u_lane.u_acc_a.q[b];
                3:  dut.g_lane[3].u_lane.u_acc_a.q[b] = ~dut.g_lane[3].u_lane.u_acc_a.q[b];
                4:  dut.g_lane[0].u_lane.u_acc_b.q[b] = ~dut.g_lane[0].u_lane.u_acc_b.q[b];
                5:  dut.g_lane[1].u_lane.u_acc_b.q[b] = ~dut.g_lane[1].u_lane.u_acc_b.q[b];
                6:  dut.g_lane[2].u_lane.u_acc_b.q[b] = ~dut.g_lane[2].u_lane.u_acc_b.q[b];
                7:  dut.g_lane[3].u_lane.u_acc_b.q[b] = ~dut.g_lane[3].u_lane.u_acc_b.q[b];
                8:  dut.g_lane[0].u_lane.u_res_a.q[b] = ~dut.g_lane[0].u_lane.u_res_a.q[b];
                9:  dut.g_lane[1].u_lane.u_res_a.q[b] = ~dut.g_lane[1].u_lane.u_res_a.q[b];
                10: dut.g_lane[2].u_lane.u_res_a.q[b] = ~dut.g_lane[2].u_lane.u_res_a.q[b];
                11: dut.g_lane[3].u_lane.u_res_a.q[b] = ~dut.g_lane[3].u_lane.u_res_a.q[b];
                12: dut.g_lane[0].u_lane.u_res_b.q[b] = ~dut.g_lane[0].u_lane.u_res_b.q[b];
                13: dut.g_lane[1].u_lane.u_res_b.q[b] = ~dut.g_lane[1].u_lane.u_res_b.q[b];
                14: dut.g_lane[2].u_lane.u_res_b.q[b] = ~dut.g_lane[2].u_lane.u_res_b.q[b];
                15: dut.g_lane[3].u_lane.u_res_b.q[b] = ~dut.g_lane[3].u_lane.u_res_b.q[b];
                16: case (id)
                        512: dut.u_thermal.u_copy0.q[0] = ~dut.u_thermal.u_copy0.q[0];
                        513: dut.u_thermal.u_copy0.q[1] = ~dut.u_thermal.u_copy0.q[1];
                        514: dut.u_thermal.u_copy1.q[0] = ~dut.u_thermal.u_copy1.q[0];
                        515: dut.u_thermal.u_copy1.q[1] = ~dut.u_thermal.u_copy1.q[1];
                        516: dut.u_thermal.u_copy2.q[0] = ~dut.u_thermal.u_copy2.q[0];
                        517: dut.u_thermal.u_copy2.q[1] = ~dut.u_thermal.u_copy2.q[1];
                        518: dut.u_thermal.phase        = ~dut.u_thermal.phase;
                        519: dut.out_valid_q            = ~dut.out_valid_q;
                        520: dut.fault_q                = ~dut.fault_q;
                        default: $display("ERROR: flip_bit: bad id %0d", id);
                    endcase
                default: $display("ERROR: flip_bit: bad id %0d", id);
            endcase
        end
    endtask

    // ------------------------------------------------------------------
    // Beat generator: the next beat is drawn only when the current one is
    // accepted, so both hosts send the same sequence at their own pace.
    // ------------------------------------------------------------------
    integer bseed;

    function [7:0] rand_operand;
        input integer r;
        input integer e;
        begin
            case (e % 8)
                0: rand_operand = 8'h80;   // -128
                1: rand_operand = 8'h7f;   //  127
                2: rand_operand = 8'hff;   //   -1
                3: rand_operand = 8'h00;
                4: rand_operand = 8'h01;
                5: rand_operand = 8'h81;   // -127
                default: rand_operand = r[7:0];
            endcase
        end
    endfunction

    task next_beat;
        integer k;
        integer r;
        begin
            r = $random(bseed);
            in_first <= (r[6:0] < 7'd32);           // 25 %
            in_last  <= (r[14:8] < 7'd40);          // 31 %
            for (k = 0; k < 4; k = k + 1) begin
                r = $random(bseed);
                in_a[8*k +: 8] <= rand_operand(r, (r[20:16] < 5'd10) ? r[26:24] : 7);
                in_b[8*k +: 8] <= rand_operand(r >>> 8, (r[31:27] < 5'd10) ? r[23:21] : 7);
            end
        end
    endtask

    // ------------------------------------------------------------------
    // Scoreboard (SPEC sections 3-5), following this design's handshakes
    // ------------------------------------------------------------------
    function [31:0] prod;
        input [7:0] a;
        input [7:0] b;
        reg signed [15:0] p;
        begin
            p    = $signed(a) * $signed(b);
            prod = {{16{p[15]}}, p};
        end
    endfunction

    reg  [127:0] m_acc;          // expected running sums
    reg          m_pend;         // an accepted result is waiting for out_fire
    reg  [127:0] m_pend_data;
    reg  [127:0] nxt;
    integer      j;

    // Per-trial counters (read by the top level).
    integer n_ok;          // results delivered and correct
    integer n_sdc;         // results delivered with wrong data
    integer n_extra;       // out_fire with nothing pending
    integer n_lost;        // pending result overwritten by a new one
    integer n_discard;     // pending result discarded by clear_fault / reset
    integer n_fault_cyc;   // cycles with fault = 1
    integer n_stop_viol;   // fault = 1 but a handshake was not blocked
    integer n_in_fire;     // accepted beats
    integer n_clears;      // clear_fault pulses issued by the fault reaction
    reg     saw_fault;

    reg [1:0] clr_wait;    // fault reaction: clear 2 cycles after fault is seen

    always @(posedge clk) begin
        if (trial_start) begin
            bseed = beat_seed;
            next_beat;
            m_acc       <= 128'd0;
            m_pend      <= 1'b0;
            auto_clear  <= 1'b0;
            clr_wait    <= 2'd0;
            n_ok = 0; n_sdc = 0; n_extra = 0; n_lost = 0; n_discard = 0;
            n_fault_cyc = 0; n_stop_viol = 0; n_in_fire = 0; n_clears = 0;
            saw_fault   <= 1'b0;
        end else begin
            // Values sampled here are those of the cycle ending at this edge.
            if (fault) begin
                n_fault_cyc = n_fault_cyc + 1;
                saw_fault  <= 1'b1;
                if (in_ready || out_valid)
                    n_stop_viol = n_stop_viol + 1;
            end

            if (!rst_n) begin
                m_acc  <= 128'd0;
                m_pend <= 1'b0;
            end else if (clear_fault) begin
                // clear_fault zeroes the sums and discards a waiting result.
                m_acc <= 128'd0;
                if (m_pend)
                    n_discard = n_discard + 1;
                m_pend <= 1'b0;
            end else begin
                if (out_fire) begin
                    if (!m_pend)
                        n_extra = n_extra + 1;
                    else if (out_data !== m_pend_data)
                        n_sdc = n_sdc + 1;
                    else
                        n_ok = n_ok + 1;
                end
                if (in_fire) begin
                    n_in_fire = n_in_fire + 1;
                    for (j = 0; j < 4; j = j + 1)
                        nxt[32*j +: 32] = (in_first ? 32'd0 : m_acc[32*j +: 32]) +
                                          prod(in_a[8*j +: 8], in_b[8*j +: 8]);
                    m_acc <= nxt;
                    if (in_last) begin
                        // A result still pending here was not delivered in
                        // this cycle and is now overwritten: lost.
                        if (m_pend && !out_fire)
                            n_lost = n_lost + 1;
                        m_pend      <= 1'b1;
                        m_pend_data <= nxt;
                    end else if (out_fire) begin
                        m_pend <= 1'b0;
                    end
                end else if (out_fire) begin
                    m_pend <= 1'b0;
                end
            end

            if (in_fire)
                next_beat;

            // Fault reaction of the host: clear_fault two cycles after fault
            // is seen, for one cycle (SPEC section 5: the host re-sends work).
            auto_clear <= 1'b0;
            if (rst_n && fault && !auto_clear) begin
                if (clr_wait == 2'd1) begin
                    auto_clear <= 1'b1;
                    n_clears    = n_clears + 1;
                    clr_wait   <= 2'd0;
                end else begin
                    clr_wait <= clr_wait + 2'd1;
                end
            end else begin
                clr_wait <= 2'd0;
            end
        end
    end

endmodule


module tb_seu_campaign;

    localparam integer NBITS   = 521;
    localparam integer PREFIX0 = 8;     // earliest injection cycle after reset
    localparam integer SPAN    = 120;   // injection cycles PREFIX0 .. PREFIX0+SPAN-1
    localparam integer POST    = 64;    // cycles after the upset
    localparam integer DRAIN_A = 24;    // favourable conditions, beats offered
    localparam integer DRAIN_B = 8;     // favourable conditions, no new beats

    reg clk = 1'b0;
    always #5 clk = ~clk;

    // Shared environment, changed only right after a rising edge (NBA).
    reg        rst_n       = 1'b0;
    reg        temp_valid  = 1'b1;
    reg [7:0]  temp_c      = 8'd25;
    reg        out_ready   = 1'b0;
    reg        offer       = 1'b0;
    reg        sched_clear = 1'b0;
    reg        trial_start = 1'b0;
    reg [31:0] beat_seed   = 32'd0;

    seu_host u_dut (
        .clk(clk), .rst_n(rst_n), .temp_valid(temp_valid), .temp_c(temp_c),
        .out_ready(out_ready), .offer(offer), .sched_clear(sched_clear),
        .trial_start(trial_start), .beat_seed(beat_seed)
    );
    seu_host u_gold (
        .clk(clk), .rst_n(rst_n), .temp_valid(temp_valid), .temp_c(temp_c),
        .out_ready(out_ready), .offer(offer), .sched_clear(sched_clear),
        .trial_start(trial_start), .beat_seed(beat_seed)
    );

    // ------------------------------------------------------------------
    // Per-cycle comparison of the two port traces
    // ------------------------------------------------------------------
    reg     cmp_on = 1'b0;
    reg     diff_ports, diff_repair;
    integer cyc;                 // cycle index within the run phase
    integer inj_at;              // injection cycle (-1: none)
    integer fault_at;            // first cycle whose sample shows fault = 1
    reg     stop_same_cycle;     // in the upset cycle: in_ready = out_valid = 0
    integer drain_fire;          // u_dut beats accepted in the late part of drain A
    reg     in_drain_a_late;

    wire [127:0] od_dut  = u_dut.out_valid  ? u_dut.out_data  : 128'd0;
    wire [127:0] od_gold = u_gold.out_valid ? u_gold.out_data : 128'd0;

    always @(posedge clk) begin
        if (cmp_on) begin
            if (u_dut.in_ready !== u_gold.in_ready || u_dut.out_valid !== u_gold.out_valid ||
                od_dut !== od_gold || u_dut.fault !== u_gold.fault ||
                u_dut.therm_state !== u_gold.therm_state || u_dut.shutdown_req !== u_gold.shutdown_req)
                diff_ports <= 1'b1;
            if (u_dut.therm_repair !== u_gold.therm_repair)
                diff_repair <= 1'b1;
            if (u_dut.fault && fault_at < 0)
                fault_at <= cyc;
            if (inj_at >= 0 && cyc == inj_at)
                stop_same_cycle <= !u_dut.in_ready && !u_dut.out_valid;
            if (in_drain_a_late && u_dut.in_fire)
                drain_fire <= drain_fire + 1;
        end
    end

    // ------------------------------------------------------------------
    // Environment generator (shared by both hosts)
    // ------------------------------------------------------------------
    integer eseed;
    integer seg_left;
    integer seg_kind;
    integer clear_rate;          // per-mille rate of scheduled clear_fault in this trial

    task env_step;               // drive the environment of the next cycle
        integer r;
        begin
            if (seg_left <= 0) begin
                r = $random(eseed);
                r = (r < 0) ? -r : r;
                seg_left = 4 + (r % 37);
                r = $random(eseed);
                r = (r < 0) ? -r : r;
                seg_kind = r % 100;
            end
            seg_left = seg_left - 1;
            r = $random(eseed);
            r = (r < 0) ? -r : r;
            temp_valid <= 1'b1;
            if (seg_kind < 45)       temp_c <= 20 + (r % 50);          // 20..69  NORMAL / recover
            else if (seg_kind < 58)  temp_c <= 71 + (r % 9);           // 71..79  hysteresis band
            else if (seg_kind < 85)  temp_c <= 80 + (r % 15);          // 80..94  THROTTLE
            else if (seg_kind < 92)  temp_c <= 95 + (r % 30);          // 95..124 STOP
            else if (seg_kind < 96) begin temp_valid <= 1'b0; temp_c <= r[7:0]; end   // invalid sensor
            else                     temp_c <= -8'sd40 + (r % 60);    // -40..19 cold
            r = $random(eseed);
            out_ready   <= (r[9:0] % 100) < 75;
            offer       <= (r[19:10] % 100) < 85;
            sched_clear <= (r[29:20] % 1000) < clear_rate;
        end
    endtask

    task env_favourable;         // drain: cool, valid sensor, consumer ready
        input beats;
        begin
            temp_valid  <= 1'b1;
            temp_c      <= 8'd25;
            out_ready   <= 1'b1;
            offer       <= beats;
            sched_clear <= 1'b0;
        end
    endtask

    // ------------------------------------------------------------------
    // One trial
    // ------------------------------------------------------------------
    integer fd;
    integer errors;
    integer n_trials;
    reg [8*16-1:0] outcome;
    reg [520:0]    sdiff;
    reg [520:0]    expect_diff;
    reg            old_bit;
    reg [1:0]      therm_at_inj;
    reg            ovq_at_inj;
    integer        latency;
    integer        k;

    task run_trial;
        input integer tr;          // trial number
        input integer fid;         // bit id, -1: no injection (control)
        input integer finj;        // injection cycle
        input integer tseed;       // trial seed
        begin
            eseed      = tseed;
            seg_left   = 0;
            clear_rate = ((tseed & 32'h7) == 0) ? 5 : 0;   // 1 trial in 8 has rare clear_fault

            // Reset (3 cycles); load the beat generators.
            @(posedge clk);
            rst_n       <= 1'b0;
            trial_start <= 1'b1;
            beat_seed   <= tseed ^ 32'h5eed_1234;
            env_favourable(1'b0);
            @(posedge clk);
            trial_start <= 1'b0;
            @(posedge clk);
            @(posedge clk);
            rst_n <= 1'b1;
            env_step;

            diff_ports      <= 1'b0;
            diff_repair     <= 1'b0;
            fault_at        <= -1;
            stop_same_cycle <= 1'b0;
            drain_fire      <= 0;
            in_drain_a_late <= 1'b0;
            inj_at           = (fid >= 0) ? finj : -1;
            cmp_on          <= 1'b1;
            old_bit          = 1'b0;
            therm_at_inj     = 2'd0;
            ovq_at_inj       = 1'b0;

            // Run phase. Cycle `cyc` lasts from one rising edge to the next;
            // the upset lands at its falling edge. cyc only changes at falling
            // edges, so the comparison block reads a stable value.
            cyc = -1;
            for (k = 0; k < finj + POST; k = k + 1) begin
                @(negedge clk);
                cyc = cyc + 1;
                if (fid >= 0 && cyc == finj) begin
                    sdiff = u_dut.state ^ u_gold.state;
                    if (sdiff !== {NBITS{1'b0}}) begin
                        $display("ERROR: trial %0d: designs differ before the upset", tr);
                        errors = errors + 1;
                    end
                    old_bit      = u_dut.state[fid];
                    therm_at_inj = u_gold.therm_state;
                    ovq_at_inj   = u_gold.dut.out_valid_q;
                    u_dut.flip_bit(fid);
                    #0;
                    sdiff       = u_dut.state ^ u_gold.state;
                    expect_diff = {{(NBITS-1){1'b0}}, 1'b1} << fid;
                    if (sdiff !== expect_diff) begin
                        $display("ERROR: trial %0d: flip of bit %0d changed %0d bits / the wrong bit",
                                 tr, fid, count_ones(sdiff));
                        errors = errors + 1;
                    end
                end
                @(posedge clk);
                env_step;
            end

            // Drain A: favourable conditions, beats offered (liveness check
            // in its second half); drain B: no new beats, results come out.
            for (k = 0; k < DRAIN_A + DRAIN_B; k = k + 1) begin
                in_drain_a_late <= (k >= DRAIN_A / 2) && (k < DRAIN_A);
                env_favourable(k < DRAIN_A);
                @(negedge clk);
                cyc = cyc + 1;
                @(posedge clk);
            end
            cmp_on          <= 1'b0;
            in_drain_a_late <= 1'b0;
            @(negedge clk);

            // A result still pending after the drain was never delivered.
            if (u_dut.m_pend && !u_dut.fault)
                u_dut.n_lost = u_dut.n_lost + 1;

            // Fault-free reference run: must be perfect.
            if (u_gold.n_sdc || u_gold.n_extra || u_gold.n_lost || u_gold.saw_fault ||
                u_gold.m_pend || u_gold.n_stop_viol) begin
                $display("ERROR: trial %0d: fault-free run failed (sdc %0d extra %0d lost %0d fault %0d pend %0d)",
                         tr, u_gold.n_sdc, u_gold.n_extra, u_gold.n_lost, u_gold.saw_fault, u_gold.m_pend);
                errors = errors + 1;
            end

            if (u_dut.n_sdc)                                   outcome = "SDC";
            else if (u_dut.n_lost)                             outcome = "LOST";
            else if (u_dut.n_extra)                            outcome = "EXTRA";
            else if (!u_dut.saw_fault && drain_fire == 0)      outcome = "HANG";
            else if (u_dut.n_stop_viol)                        outcome = "OTHER";
            else if (u_dut.saw_fault)                          outcome = "DETECTED";
            else if (diff_ports)                               outcome = "TIMING";
            else if (diff_repair)                              outcome = "REPAIRED";
            else                                               outcome = "MASKED";

            latency = (fid >= 0 && fault_at >= 0) ? fault_at - finj : -1;
            $fdisplay(fd, "%0d\t%0d\t%0d\t%0d\t%0d\t%0d\t%0s\t%0d\t%0d\t%0d\t%0d\t%0d",
                      tr, fid, finj, old_bit, therm_at_inj, ovq_at_inj, outcome, latency,
                      stop_same_cycle, u_dut.n_ok, u_dut.n_discard, u_dut.n_clears);
            n_trials = n_trials + 1;
        end
    endtask

    function integer count_ones;
        input [520:0] v;
        integer i;
        begin
            count_ones = 0;
            for (i = 0; i < NBITS; i = i + 1)
                count_ones = count_ones + v[i];
        end
    endfunction

    // ------------------------------------------------------------------
    // Campaign
    // ------------------------------------------------------------------
    integer seed, tpb, tpb_unprot, controls, first_id, last_id;
    integer id, t, n, stratum, trial, inj, r, iseed;
    reg [8*512-1:0] out_path;

    initial begin
        if (!$value$plusargs("seed=%d", seed))             seed = 1;
        if (!$value$plusargs("tpb=%d", tpb))               tpb = 12;
        if (!$value$plusargs("tpb_unprot=%d", tpb_unprot)) tpb_unprot = 200;
        if (!$value$plusargs("controls=%d", controls))     controls = 20;
        if (!$value$plusargs("first=%d", first_id))        first_id = 0;
        if (!$value$plusargs("last=%d", last_id))          last_id = NBITS - 1;
        if (!$value$plusargs("out=%s", out_path))          out_path = "seu_trials.tsv";
        fd = $fopen(out_path, "w");
        if (fd == 0) begin
            $display("ERROR: cannot open %0s", out_path);
            $finish;
        end
        $fdisplay(fd, "# seed=%0d tpb=%0d tpb_unprot=%0d controls=%0d prefix=%0d..%0d post=%0d drain=%0d+%0d",
                  seed, tpb, tpb_unprot, controls, PREFIX0, PREFIX0 + SPAN - 1, POST, DRAIN_A, DRAIN_B);
        $fdisplay(fd, "trial\tid\tinj_cycle\told_bit\ttherm_at_inj\tovq_at_inj\toutcome\tlatency\tstop_same_cycle\tn_ok\tn_discard\tn_clears");
        errors   = 0;
        n_trials = 0;
        trial    = 0;
        iseed    = seed;

        // Fault-free controls: the classifier must report MASKED.
        for (t = 0; t < controls; t = t + 1) begin
            run_trial(trial, -1, PREFIX0 + SPAN / 2, seed * 1000003 + trial * 7919 + 17);
            trial = trial + 1;
        end

        // Every bit at several injection times, stratified over the prefix
        // window (one stratum per trial of that bit, random within it).
        for (id = first_id; id <= last_id; id = id + 1) begin
            n = (id >= 518) ? tpb_unprot : tpb;
            for (t = 0; t < n; t = t + 1) begin
                stratum = (SPAN + n - 1) / n;
                r   = $random(iseed);
                r   = (r < 0) ? -r : r;
                inj = PREFIX0 + (t * SPAN) / n + (r % stratum);
                if (inj >= PREFIX0 + SPAN)
                    inj = PREFIX0 + SPAN - 1;
                run_trial(trial, id, inj, seed * 1000003 + trial * 7919 + 17);
                trial = trial + 1;
            end
        end

        $fdisplay(fd, "# done trials=%0d errors=%0d", n_trials, errors);
        $fclose(fd);
        $display("SEU_CAMPAIGN %0s trials=%0d errors=%0d", (errors == 0) ? "DONE" : "ERRORS", n_trials, errors);
        $finish;
    end

endmodule

`default_nettype wire
