// Formal harness for the fault-free ORBIT-AI demonstrator (orbit_demo).
//
// Contract: docs/SPEC.md. Run through formal/orbit_demo.sby (SymbiYosys).
//
// Environment: every DUT input is a free primary input of this harness. The
// only constraint is a reset in the first cycle (FV_FREE_START replaces that
// by an arbitrary state in which DUT and reference model agree; used for the
// INT32 wraparound job, see below). Reset and clear_fault stay free later on.
//
// Reference model: written from SPEC sections 3, 4 and 6, not from the RTL.
// Where a different formulation is available it is used on purpose: the
// product is formed as sign * (|a| * |b|) instead of a signed multiply, and
// the thresholds are the SPEC constants, not the DUT parameters. The model
// follows the DUT's port handshakes (in_fire / out_fire), like a scoreboard,
// and separately predicts in_ready and out_valid, which are asserted equal.
//
// DUT internals (for the P7 invariants and induction helpers) are reached
// through Yosys `hierconn` wires: an escaped wire named `\dut.<path>` with the
// (* hierconn *) attribute is connected to that internal signal by `flatten`.
// This requires `hierarchy; proc; flatten` before any opt pass, with the
// keep_hierarchy attribute removed from orbit_keep_reg (see the .sby
// script). `check -assert` in the script fails the run if one of these paths
// does not exist, so a typo cannot silently turn into a free input.
//
// Property groups, enabled per SymbiYosys task with -D<group>:
//   FV_THERMAL    P5 thermal FSM vs SPEC table, reset -> STOP; P6 throttle
//   FV_DUP        P7 fault-free invariants (no fault, no repair, copies equal)
//   FV_HANDSHAKE  P2 no loss / duplication, P3 backpressure, P4 in_ready
//   FV_DATAPATH   P1 exact results, P8 clear_fault
//   FV_COVER      reachability covers from reset
//   FV_WRAP       INT32 wraparound covers (use with FV_FREE_START)
// Groups also contain the helper invariants that make their induction close.

`default_nettype none

module orbit_demo_fv (
    input wire         clk,
    input wire         rst_n,
    input wire         in_valid,
    input wire         in_first,
    input wire         in_last,
    input wire [31:0]  in_a,
    input wire [31:0]  in_b,
    input wire         out_ready,
    input wire         temp_valid,
    input wire [7:0]   temp_c,
    input wire         clear_fault
);

    localparam integer LANES = 4;

    localparam [1:0] S_NORMAL   = 2'd0;
    localparam [1:0] S_THROTTLE = 2'd1;
    localparam [1:0] S_STOP     = 2'd2;

    // SPEC section 1 thresholds, signed whole degrees C.
    localparam integer TH_THROTTLE = 80;
    localparam integer TH_STOP     = 95;
    localparam integer TH_RECOVER  = 70;

    // ------------------------------------------------------------------
    // Device under test
    // ------------------------------------------------------------------
    wire                in_ready;
    wire                out_valid;
    wire [32*LANES-1:0] out_data;
    wire                fault;
    wire [1:0]          therm_state;
    wire                therm_repair;
    wire                shutdown_req;

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

    wire in_fire  = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;

    // ------------------------------------------------------------------
    // DUT internals (SPEC section 7 storage map), via hierconn wires
    // ------------------------------------------------------------------
    (* hierconn *) wire [31:0] \dut.g_lane[0].u_lane.u_acc_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[1].u_lane.u_acc_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[2].u_lane.u_acc_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[3].u_lane.u_acc_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[0].u_lane.u_acc_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[1].u_lane.u_acc_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[2].u_lane.u_acc_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[3].u_lane.u_acc_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[0].u_lane.u_res_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[1].u_lane.u_res_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[2].u_lane.u_res_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[3].u_lane.u_res_a.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[0].u_lane.u_res_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[1].u_lane.u_res_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[2].u_lane.u_res_b.q ;
    (* hierconn *) wire [31:0] \dut.g_lane[3].u_lane.u_res_b.q ;
    (* hierconn *) wire [1:0]  \dut.u_thermal.u_copy0.q ;
    (* hierconn *) wire [1:0]  \dut.u_thermal.u_copy1.q ;
    (* hierconn *) wire [1:0]  \dut.u_thermal.u_copy2.q ;
    (* hierconn *) wire        \dut.u_thermal.phase ;
    (* hierconn *) wire        \dut.admit ;
    (* hierconn *) wire        \dut.mismatch ;
    (* hierconn *) wire        \dut.fault_q ;
    (* hierconn *) wire        \dut.out_valid_q ;

    wire [32*LANES-1:0] h_acc_a = {\dut.g_lane[3].u_lane.u_acc_a.q , \dut.g_lane[2].u_lane.u_acc_a.q ,
                                   \dut.g_lane[1].u_lane.u_acc_a.q , \dut.g_lane[0].u_lane.u_acc_a.q };
    wire [32*LANES-1:0] h_acc_b = {\dut.g_lane[3].u_lane.u_acc_b.q , \dut.g_lane[2].u_lane.u_acc_b.q ,
                                   \dut.g_lane[1].u_lane.u_acc_b.q , \dut.g_lane[0].u_lane.u_acc_b.q };
    wire [32*LANES-1:0] h_res_a = {\dut.g_lane[3].u_lane.u_res_a.q , \dut.g_lane[2].u_lane.u_res_a.q ,
                                   \dut.g_lane[1].u_lane.u_res_a.q , \dut.g_lane[0].u_lane.u_res_a.q };
    wire [32*LANES-1:0] h_res_b = {\dut.g_lane[3].u_lane.u_res_b.q , \dut.g_lane[2].u_lane.u_res_b.q ,
                                   \dut.g_lane[1].u_lane.u_res_b.q , \dut.g_lane[0].u_lane.u_res_b.q };
    wire [1:0] h_c0        = \dut.u_thermal.u_copy0.q ;
    wire [1:0] h_c1        = \dut.u_thermal.u_copy1.q ;
    wire [1:0] h_c2        = \dut.u_thermal.u_copy2.q ;
    wire       h_phase     = \dut.u_thermal.phase ;
    wire       h_admit     = \dut.admit ;
    wire       h_mismatch  = \dut.mismatch ;
    wire       h_fault_q   = \dut.fault_q ;
    wire       h_out_valid_q = \dut.out_valid_q ;

    // ------------------------------------------------------------------
    // Reference model (SPEC sections 3, 4, 6)
    // ------------------------------------------------------------------

    // Thermal next state, SPEC section 6 table (first match wins).
    function [1:0] spec_next;
        input [1:0] s;
        input       tv;
        input [7:0] tc;
        integer     t;
        begin
            t = $signed(tc);
            if (!tv || t >= TH_STOP)
                spec_next = S_STOP;
            else if (s == S_NORMAL)
                spec_next = (t >= TH_THROTTLE) ? S_THROTTLE : S_NORMAL;
            else if (s == S_THROTTLE)
                spec_next = (t <= TH_RECOVER) ? S_NORMAL : S_THROTTLE;
            else // STOP, or the unused code 3 which behaves as STOP
                spec_next = (t <= TH_RECOVER) ? S_NORMAL : S_STOP;
        end
    endfunction

    // Exact signed INT8 x INT8 product, sign-extended to 32 bits, formed as
    // sign * (|a| * |b|). |-128| = 128 needs 9 bits; |a*b| <= 16384.
    function [31:0] spec_prod;
        input [7:0] a;
        input [7:0] b;
        reg   [8:0]  mag_a;
        reg   [8:0]  mag_b;
        reg   [17:0] mag_p;
        begin
            mag_a     = a[7] ? (9'd256 - {1'b0, a}) : {1'b0, a};
            mag_b     = b[7] ? (9'd256 - {1'b0, b}) : {1'b0, b};
            mag_p     = mag_a * mag_b;
            spec_prod = (a[7] ^ b[7]) ? (32'd0 - {14'd0, mag_p}) : {14'd0, mag_p};
        end
    endfunction

    reg [1:0]          m_therm;     // expected voted thermal state
    reg                m_phase;     // expected throttle phase
    reg                m_valid;     // output buffer holds an undelivered result
    reg [32*LANES-1:0] m_acc;       // expected running sum per lane
    reg [32*LANES-1:0] m_buf;       // expected output-buffer contents
    reg [2:0]          m_seq_in;    // accepted in_last beats (mod 8)
    reg [2:0]          m_seq_out;   // results delivered, or discarded by reset/clear (mod 8)
    reg                m_fresh;     // no beat accepted since the last reset / clear_fault
    reg                m_fresh_clr; // ... and that was a clear_fault, not a reset (for a cover)
    reg [LANES-1:0]    m_ovf;       // per lane: current sum has wrapped (signed overflow)
    reg [LANES-1:0]    m_buf_ovf;   // per lane: buffered result has wrapped

    // Per-lane values after an accepted beat.
    reg [32*LANES-1:0] m_acc_nxt;
    reg [LANES-1:0]    m_ovf_nxt;
    reg [31:0]         f_base;
    reg [31:0]         f_prod;
    reg [31:0]         f_sum;
    integer            k;
    always @* begin
        for (k = 0; k < LANES; k = k + 1) begin
            f_base = in_first ? 32'd0 : m_acc[32*k +: 32];
            f_prod = spec_prod(in_a[8*k +: 8], in_b[8*k +: 8]);
            f_sum  = f_base + f_prod;                      // mod 2^32
            m_acc_nxt[32*k +: 32] = f_sum;
            // Signed overflow: operands of equal sign, result of the other.
            m_ovf_nxt[k] = (in_first ? 1'b0 : m_ovf[k]) |
                           ((f_base[31] == f_prod[31]) && (f_sum[31] != f_base[31]));
        end
    end

    // Expected product of the current beat for every lane.
    reg [32*LANES-1:0] f_prod_all;
    integer            kp;
    always @* begin
        for (kp = 0; kp < LANES; kp = kp + 1)
            f_prod_all[32*kp +: 32] = spec_prod(in_a[8*kp +: 8], in_b[8*kp +: 8]);
    end

    // Expected handshake (fault-free: fault_q = 0 and mismatch = 0).
    wire m_admit    = (m_therm == S_NORMAL) || ((m_therm == S_THROTTLE) && !m_phase);
    wire m_in_ready = m_admit && !clear_fault && (!m_valid || out_ready);

    always @(posedge clk) begin
        if (!rst_n) begin
            m_therm   <= S_STOP;
            m_phase   <= 1'b0;
            m_valid   <= 1'b0;
            m_acc     <= {32*LANES{1'b0}};
            m_buf     <= {32*LANES{1'b0}};
            m_seq_out <= m_seq_in;
            m_fresh   <= 1'b1;
            m_fresh_clr <= 1'b0;
            m_ovf     <= {LANES{1'b0}};
            m_buf_ovf <= {LANES{1'b0}};
        end else begin
            m_therm <= spec_next(m_therm, temp_valid, temp_c);
            m_phase <= (m_therm == S_THROTTLE) ? !m_phase : 1'b0;
            if (clear_fault) begin
                m_valid   <= 1'b0;
                m_acc     <= {32*LANES{1'b0}};
                m_buf     <= {32*LANES{1'b0}};
                m_seq_out <= m_seq_in;
                m_fresh   <= 1'b1;
                m_fresh_clr <= 1'b1;
                m_ovf     <= {LANES{1'b0}};
                m_buf_ovf <= {LANES{1'b0}};
            end else begin
                if (in_fire) begin
                    m_acc   <= m_acc_nxt;
                    m_ovf   <= m_ovf_nxt;
                    m_fresh <= 1'b0;
                end
                if (in_fire && in_last) begin
                    m_buf     <= m_acc_nxt;
                    m_buf_ovf <= m_ovf_nxt;
                    m_valid   <= 1'b1;
                    m_seq_in  <= m_seq_in + 3'd1;
                end else if (out_fire) begin
                    m_valid <= 1'b0;
                end
                if (out_fire)
                    m_seq_out <= m_seq_out + 3'd1;
            end
        end
    end

    wire [2:0] m_pending = m_seq_in - m_seq_out;   // accepted, not yet delivered

    // P8 tracker: an accepted in_last beat without in_first that is the first
    // beat since reset / clear_fault must deliver exactly its own products.
    reg                f_fresh_chk;
    reg                f_fresh_clr;
    reg [32*LANES-1:0] f_fresh_exp;
    always @(posedge clk) begin
        f_fresh_chk <= rst_n && !clear_fault && in_fire && in_last && !in_first && m_fresh;
        f_fresh_clr <= m_fresh_clr;
        f_fresh_exp <= f_prod_all;
    end

    // ------------------------------------------------------------------
    // Environment
    // ------------------------------------------------------------------
    reg f_past_valid = 1'b0;    // not the first cycle
    reg f_past2      = 1'b0;    // neither of the first two cycles
    always @(posedge clk) begin
        f_past_valid <= 1'b1;
        f_past2      <= f_past_valid;
    end

`ifdef FV_FREE_START
    // Start in an arbitrary state in which DUT and model agree (exactly the
    // invariants the prove tasks establish), not from reset. Used to reach
    // accumulator values near +/-2^31 in a few cycles; from reset that takes
    // at least 2^31 / 16384 = 131072 beats, far beyond any BMC depth.
    always @* begin
        if (!f_past_valid) begin
            assume(rst_n);
            assume(h_acc_a == m_acc && h_acc_b == m_acc);
            assume(h_res_a == m_buf && h_res_b == m_buf);
            assume(!h_fault_q && (h_out_valid_q == m_valid));
            assume(h_c0 == m_therm && h_c1 == m_therm && h_c2 == m_therm && m_therm != 2'd3);
            assume(h_phase == m_phase);
            assume(m_pending == {2'b00, m_valid});
            assume(!m_fresh && !f_fresh_chk && m_ovf == 0 && m_buf_ovf == 0);
        end
    end
`else
    always @* begin
        if (!f_past_valid)
            assume(!rst_n);
    end
`endif

    // ------------------------------------------------------------------
    // P5 / P6: thermal state machine and throttled admission
    // ------------------------------------------------------------------
`ifdef FV_THERMAL
    always @* begin
        if (f_past_valid) begin
            // P5: the voted state is the SPEC table's state (independent FSM).
            P5_state_matches_model: assert (therm_state == m_therm);
            P5_never_code3:         assert (therm_state != 2'd3);
            P5_shutdown_req:        assert (shutdown_req == therm_state[1]);
            // Helpers: the three copies and the phase follow the model.
            P5_h_copy0: assert (h_c0 == m_therm);
            P5_h_copy1: assert (h_c1 == m_therm);
            P5_h_copy2: assert (h_c2 == m_therm);
            P5_h_phase: assert (h_phase == m_phase);
        end
    end

    always @(posedge clk) begin
        if (f_past_valid) begin
            // P5: reset gives STOP (and no throttle phase).
            if (!$past(rst_n)) begin
                P5_reset_stop:  assert (therm_state == S_STOP);
                P5_reset_phase: assert (!h_phase);
            end
            // P5: one-step transition from the DUT's own previous voted state.
            if ($past(rst_n) && f_past2) begin
                P5_next_state: assert (therm_state == spec_next($past(therm_state), $past(temp_valid), $past(temp_c)));
            end

            // P6: NORMAL admits every cycle, STOP / 3 never.
            if (therm_state == S_NORMAL) begin
                P6_normal_admits: assert (h_admit);
            end
            if (therm_state[1]) begin
                P6_stop_blocks: assert (!h_admit);
            end
            // P6: the first THROTTLE cycle admits ...
            if (therm_state == S_THROTTLE && $past(therm_state) != S_THROTTLE) begin
                P6_first_throttle_admits: assert (h_admit);
            end
            // ... and consecutive THROTTLE cycles alternate.
            if (f_past2 && therm_state == S_THROTTLE && $past(therm_state) == S_THROTTLE && $past(rst_n)) begin
                P6_throttle_alternates: assert (h_admit != $past(h_admit));
            end
            // P6 at the ports: while throttled and nothing else blocks, in_ready
            // follows the alternating admission.
            if (therm_state == S_THROTTLE && !clear_fault && !fault && (!out_valid || out_ready)) begin
                P6_port_throttle: assert (in_ready == !m_phase);
            end
        end
    end
`endif

    // ------------------------------------------------------------------
    // P7: fault-free invariants
    // ------------------------------------------------------------------
`ifdef FV_DUP
    // Yosys does not prefix assertion labels with a generate scope, so the
    // per-lane checks are expanded with a macro to get unique names.
`define FV_DUP_LANE(L) \
    always @* begin \
        if (f_past_valid) begin \
            P7_acc_copies_equal_lane``L: assert (h_acc_a[32*L +: 32] == h_acc_b[32*L +: 32]); \
            P7_res_copies_equal_lane``L: assert (h_res_a[32*L +: 32] == h_res_b[32*L +: 32]); \
        end \
    end
    `FV_DUP_LANE(0)
    `FV_DUP_LANE(1)
    `FV_DUP_LANE(2)
    `FV_DUP_LANE(3)
`undef FV_DUP_LANE

    always @* begin
        if (f_past_valid) begin
            P7_no_fault:           assert (!fault);
            P7_no_therm_repair:    assert (!therm_repair);
            P7_no_mismatch:        assert (!h_mismatch);
            P7_therm_copies_equal: assert (h_c0 == h_c1 && h_c1 == h_c2);
        end
    end
`endif

    // ------------------------------------------------------------------
    // P2 / P3 / P4: handshake, output buffer, backpressure
    // ------------------------------------------------------------------
`ifdef FV_HANDSHAKE
    // P4: in_ready is structurally blocked. Checked in every state, including
    // the unconstrained first cycle.
    always @* begin
        if (therm_state[1]) begin
            P4_blocked_stop_or_3: assert (!in_ready);
        end
        if (fault) begin
            P4_blocked_fault: assert (!in_ready);
        end
        if (clear_fault) begin
            P4_blocked_clear_fault: assert (!in_ready);
        end
        if (h_out_valid_q && !out_ready) begin
            P4_blocked_buffer_full: assert (!in_ready);
        end
        if (out_valid && !out_ready) begin
            P4_blocked_out_valid: assert (!in_ready);
        end
    end

    always @* begin
        if (f_past_valid) begin
            // Handshake outputs equal the SPEC section 4 prediction.
            P4_in_ready_matches_model:  assert (in_ready == m_in_ready);
            P2_out_valid_matches_model: assert (out_valid == m_valid);
            P2_h_out_valid_q:           assert (h_out_valid_q == m_valid);

            // P2: at most one accepted result is outstanding (a second one
            // would have overwritten the first), it is the one presented, and
            // every out_fire delivers exactly one outstanding result.
            P2_at_most_one_pending: assert (m_pending <= 3'd1);
            P2_valid_iff_pending:   assert (out_valid == (m_pending == 3'd1));
            if (out_fire) begin
                P2_fire_has_pending: assert (m_pending == 3'd1);
            end
            if (in_fire && in_last && !out_fire) begin
                P2_no_overwrite: assert (m_pending == 3'd0);
            end
        end
    end

    // P3: a presented, unconsumed result stays presented and unchanged.
    always @(posedge clk) begin
        if (f_past2 && $past(rst_n) && !$past(clear_fault) && $past(out_valid) && !$past(out_ready)) begin
            P3_valid_held:  assert (out_valid);
            P3_data_stable: assert (out_data == $past(out_data));
        end
    end
`endif

    // ------------------------------------------------------------------
    // P1 / P8: results and clear_fault
    // ------------------------------------------------------------------
`ifdef FV_DATAPATH
`define FV_DP_LANE(L) \
    always @* begin \
        if (f_past_valid) begin \
            /* P1: every transferred result is exact (mod 2^32). */ \
            if (out_fire) begin \
                P1_out_fire_data_lane``L: assert (out_data[32*L +: 32] == m_buf[32*L +: 32]); \
            end \
            /* Stronger: whatever is presented is the expected result. */ \
            if (out_valid) begin \
                P1_out_valid_data_lane``L: assert (out_data[32*L +: 32] == m_buf[32*L +: 32]); \
            end \
            /* Helpers: DUT storage equals the model. */ \
            P1_h_acc_a_lane``L: assert (h_acc_a[32*L +: 32] == m_acc[32*L +: 32]); \
            P1_h_res_a_lane``L: assert (h_res_a[32*L +: 32] == m_buf[32*L +: 32]); \
            /* P8 helper: no beat since reset / clear_fault -> sums are 0. */ \
            if (m_fresh) begin \
                P8_h_fresh_acc_a_lane``L: assert (h_acc_a[32*L +: 32] == 32'd0); \
                P8_h_fresh_acc_b_lane``L: assert (h_acc_b[32*L +: 32] == 32'd0); \
            end \
        end \
    end \
    always @(posedge clk) begin \
        /* P8: clear_fault zeroes both copies of all lane storage. */ \
        if (f_past_valid && $past(rst_n) && $past(clear_fault)) begin \
            P8_clear_zero_acc_a_lane``L: assert (h_acc_a[32*L +: 32] == 32'd0); \
            P8_clear_zero_acc_b_lane``L: assert (h_acc_b[32*L +: 32] == 32'd0); \
            P8_clear_zero_res_a_lane``L: assert (h_res_a[32*L +: 32] == 32'd0); \
            P8_clear_zero_res_b_lane``L: assert (h_res_b[32*L +: 32] == 32'd0); \
        end \
        /* P8: the first beat after clear_fault / reset without in_first sums from 0. */ \
        if (f_past_valid && f_fresh_chk) begin \
            P8_fresh_sum_from_zero_lane``L: assert (out_data[32*L +: 32] == f_fresh_exp[32*L +: 32]); \
        end \
    end
    `FV_DP_LANE(0)
    `FV_DP_LANE(1)
    `FV_DP_LANE(2)
    `FV_DP_LANE(3)
`undef FV_DP_LANE

    always @(posedge clk) begin
        if (f_past_valid && $past(rst_n) && $past(clear_fault)) begin
            // P8: after clear_fault, fault = 0 and out_valid = 0.
            P8_clear_no_fault: assert (!fault);
            P8_clear_no_valid: assert (!out_valid);
        end
        if (f_past_valid && f_fresh_chk) begin
            P8_fresh_result_valid: assert (out_valid);
        end
    end
`endif

    // ------------------------------------------------------------------
    // Covers from reset
    // ------------------------------------------------------------------
`ifdef FV_COVER
    always @(posedge clk) begin
        if (f_past2) begin
            C01_out_fire:            cover (out_fire);
            C02_back_to_back_fire:   cover (out_fire && $past(out_fire));
            C03_throttle_entered:    cover (therm_state == S_THROTTLE && $past(therm_state) == S_NORMAL);
            C04_stop_by_temperature: cover (therm_state == S_STOP && $past(therm_state) != S_STOP &&
                                            $past(rst_n) && $past(temp_valid));
            C05_stop_by_invalid:     cover (therm_state == S_STOP && $past(therm_state) != S_STOP &&
                                            $past(rst_n) && !$past(temp_valid));
            C06_recover_from_stop:   cover (therm_state == S_NORMAL && $past(therm_state) == S_STOP &&
                                            $past(rst_n) && f_past_valid);
            C07_recover_from_throttle: cover (therm_state == S_NORMAL && $past(therm_state) == S_THROTTLE);
            C08_clear_then_result:   cover (out_fire && f_fresh_chk && f_fresh_clr);
            C09_throttle_blocks:     cover (therm_state == S_THROTTLE && in_valid && !in_ready &&
                                            !clear_fault && !out_valid);
            C10_backpressure_then_fire: cover (out_fire && $past(out_valid && !out_ready) &&
                                               $past(out_valid && !out_ready, 2));
            C11_replace_no_bubble:   cover (out_fire && in_fire && in_last);
            C12_edge_min_min:        cover (out_fire && out_data[31:0] == 32'sd16384);
            C13_edge_max_min:        cover (out_fire && out_data[31:0] == -32'sd16256);
            C14_throttle_admit_run:  cover (therm_state == S_THROTTLE && $past(therm_state) == S_THROTTLE &&
                                            $past(therm_state, 2) == S_THROTTLE && in_fire && $past(in_fire, 2));
        end
    end
`endif

    // ------------------------------------------------------------------
    // INT32 wraparound covers (from a consistent arbitrary state)
    // ------------------------------------------------------------------
`ifdef FV_WRAP
    always @(posedge clk) begin
        if (f_past_valid) begin
            // A delivered lane-0 result whose sum wrapped past +2^31-1 ...
            C20_wrap_pos_to_neg: cover (out_fire && m_buf_ovf[0] && out_data[31]);
            // ... and one that wrapped past -2^31.
            C21_wrap_neg_to_pos: cover (out_fire && m_buf_ovf[0] && !out_data[31]);
            // All four lanes wrapped in the same delivered result.
            C22_wrap_all_lanes:  cover (out_fire && (&m_buf_ovf));
        end
    end
`endif

endmodule

`default_nettype wire
