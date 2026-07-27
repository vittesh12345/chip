// Bounded end-to-end formal harness for the SECDED bank with the REAL
// decoder (rtl/ecc/orbit_ecc_bank.v + rtl/ecc/orbit_secded72.v).
//
// Complements orbit_ecc_bank_fv.sv, whose unbounded proofs replace the
// decoder by its separately proven contract: here nothing is abstracted, the
// read data is compared with the written data directly, and the check is a
// BMC from reset (tasks e2e_clean / e2e_upset in orbit_ecc_bank.sby, run at
// DEPTH 2 for 5 and 4 steps, because the parity arithmetic of two chained
// 64-bit codecs makes the SAT problem grow fast with the number of steps: at
// DEPTH 4 step 4 of the clean run took about a minute and step 5 did not
// finish in two; at DEPTH 2 step 4 of the upset run did not finish in 9).
// U4 (scrub bound) is therefore not reached here; it is proven, with the
// decoder abstracted, by orbit_ecc_bank_fv.sv.
// k-induction with the helper invariants below was tried (yices, DEPTH 16
// and DEPTH 4) and had not finished after about 2 minutes, where the
// abstracted proofs take well under a minute; it was not pursued further.
//
// The bank is read with -DORBIT_ECC_UPSET, which gives it an undriven upset
// mask `upset` XORed into the array at every clock edge; this harness drives
// it through a (* hierconn *) wire.
//
// Environment: every port input is free. Reset is forced in the first cycle
// only and is free afterwards. One arbitrary word address addr0 (anyconst)
// is tracked by a shadow register holding its last written data (0 after
// reset, because reset stores all-zero rows, i.e. data 0).
//
// Property groups (-D<group>):
//   FV_CLEAN  fault-free: upset is always 0.
//     C1  a read of addr0 returns the last data written there (read-first:
//         a same-cycle write is not yet visible), rd_ce = rd_ue = 0
//     C2  rd_valid is rd_en delayed by one cycle
//     C3  no read ever reports CE/UE; counters stay 0; no error is logged
//   FV_UPSET  one upset event, at an arbitrary time, of one bit or two
//     physically adjacent bits of one arbitrary row (a multi-cell upset);
//     no other fault. Reads, writes, scrub_en and log_clear stay free.
//     U1  a read of addr0 returns the last data written there, rd_ue = 0,
//         and rd_ce = 1 exactly when the stored codeword was in error
//     U2  nothing is ever uncorrectable: ue_count = 0, no UE logged or read
//     U3  a CE read is logged: last_err = {valid, CE, addr0}, ce_count != 0
//     U4  scrub bound: once the scrubber has had DEPTH idle cycles
//         (scrub_en & ~wr_en & ~rd_en) after the upset, every codeword of
//         the array is error-free again
//   FV_COVER  reachability covers (not used by the default tasks).
//
// Helper invariants (labels h_*, disabled with -DFV_NO_HELPERS, as the BMC
// tasks do) were written for k-induction attempts.

`default_nettype none

module orbit_ecc_bank_e2e_fv #(
    parameter integer DEPTH      = 16,
    parameter integer INTERLEAVE = 2
) (
    input wire                                clk,
    input wire                                rst_n,
    input wire                                wr_en,
    input wire [$clog2(DEPTH*INTERLEAVE)-1:0] wr_addr,
    input wire [63:0]                         wr_data,
    input wire                                rd_en,
    input wire [$clog2(DEPTH*INTERLEAVE)-1:0] rd_addr,
    input wire                                scrub_en,
    input wire                                log_clear,
    // Upset model inputs
    input wire                                up_ev,    // the upset happens at this edge
    input wire [$clog2(DEPTH)-1:0]            up_row,   // physical row hit
    input wire [$clog2(INTERLEAVE*72)-1:0]    up_pos,   // lowest physical column hit
    input wire                                up_two    // two adjacent columns (up_pos, up_pos+1)
);

    localparam integer CW    = 72;
    localparam integer ROW_W = INTERLEAVE * CW;
    localparam integer RB    = $clog2(DEPTH);
    localparam integer AW    = $clog2(DEPTH*INTERLEAVE);
    localparam integer CB    = $clog2(DEPTH + 1);    // idle counter width (counts to DEPTH)

    // ------------------------------------------------------------------
    // DUT
    // ------------------------------------------------------------------
    wire          rd_valid, rd_ce, rd_ue;
    wire [63:0]   rd_data;
    wire [RB-1:0] scrub_row;
    wire [15:0]   ce_count, ue_count;
    wire          last_err_valid, last_err_ue;
    wire [AW-1:0] last_err_addr;

    orbit_ecc_bank #(.DEPTH(DEPTH), .INTERLEAVE(INTERLEAVE), .CNT_W(16)) dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_valid(rd_valid), .rd_data(rd_data),
        .rd_ce(rd_ce), .rd_ue(rd_ue),
        .scrub_en(scrub_en), .log_clear(log_clear), .scrub_row(scrub_row),
        .ce_count(ce_count), .ue_count(ue_count),
        .last_err_valid(last_err_valid), .last_err_ue(last_err_ue), .last_err_addr(last_err_addr)
    );

    // DUT internals through hierconn wires (connected by `flatten`).
    (* hierconn *) wire [DEPTH*ROW_W-1:0] \dut.cells ;
    (* hierconn *) wire [DEPTH*ROW_W-1:0] \dut.upset ;
    (* hierconn *) wire [RB-1:0]          \dut.scrub_ptr ;

    // ------------------------------------------------------------------
    // Reset in the first cycle
    // ------------------------------------------------------------------
    reg init = 1'b1;
    always @(posedge clk) init <= 1'b0;
    always @* if (init) assume (!rst_n);

    // ------------------------------------------------------------------
    // Upset model: at most one event in the whole trace
    // ------------------------------------------------------------------
    reg up_used = 1'b0;
    always @(posedge clk) up_used <= up_used | up_ev;

    wire [ROW_W-1:0] up_bits = ({{(ROW_W-1){1'b0}}, 1'b1} << up_pos) |
                               ({{(ROW_W-1){1'b0}}, up_two} << (up_pos + 1'b1));

    always @* begin
        assume (!(up_ev && up_used));
        assume ({1'b0, up_pos} + up_two < ROW_W);
`ifdef FV_CLEAN
        assume (!up_ev);
`endif
    end

    assign \dut.upset = up_ev ? ({{((DEPTH-1)*ROW_W){1'b0}}, up_bits} << (up_row * ROW_W))
                              : {DEPTH*ROW_W{1'b0}};

    // ------------------------------------------------------------------
    // Reference: shadow of addr0, stored codewords, syndromes
    // ------------------------------------------------------------------
    (* anyconst *) wire [AW-1:0] addr0;
    wire [RB-1:0] row0 = addr0 / INTERLEAVE;
    wire [AW-1:0] way0 = addr0 % INTERLEAVE;

    reg [63:0] shadow;
    always @(posedge clk)
        if (!rst_n)                          shadow <= 64'd0;
        else if (wr_en && wr_addr == addr0)  shadow <= wr_data;

    wire [7:0]    shadow_chk;
    orbit_secded72_enc u_ref_enc (.data(shadow), .check(shadow_chk));
    wire [CW-1:0] ref_cw = {shadow_chk, shadow};

    // Codeword of every (row, way), de-interleaved, and its syndrome.
    wire [DEPTH*INTERLEAVE*CW-1:0] st_cw;
    wire [DEPTH*INTERLEAVE*8-1:0]  st_syn;
    genvar r, w, k;
    generate
        for (r = 0; r < DEPTH; r = r + 1) begin : g_row
            for (w = 0; w < INTERLEAVE; w = w + 1) begin : g_way
                wire [CW-1:0] cw;
                wire [7:0]    chk;
                for (k = 0; k < CW; k = k + 1) begin : g_bit
                    assign cw[k] = \dut.cells [r*ROW_W + k*INTERLEAVE + w];
                end
                orbit_secded72_enc u_enc (.data(cw[63:0]), .check(chk));
                assign st_cw [(r*INTERLEAVE + w)*CW +: CW] = cw;
                assign st_syn[(r*INTERLEAVE + w)*8  +: 8]  = chk ^ cw[71:64];
            end
        end
    endgenerate

    wire [CW-1:0] cw0 = st_cw[addr0*CW +: CW];

    // ------------------------------------------------------------------
    // Upset bookkeeping: where it landed and how many idle cycles followed
    // ------------------------------------------------------------------
    wire          idle = scrub_en && !wr_en && !rd_en;   // the scrubber's condition
    reg           landed = 1'b0;   // the upset is (or was) in the array since the last reset
    reg [RB-1:0]  l_row;           // row it hit
    reg [ROW_W-1:0] l_bits;        // columns it hit
    reg [RB-1:0]  l_ptr;           // scrub pointer right after it landed
    reg [CB-1:0]  idle_cnt;        // idle cycles since it landed, saturating at DEPTH

    always @(posedge clk) begin
        if (!rst_n) begin
            landed   <= 1'b0;      // reset clears the array; an upset at this edge is lost
            idle_cnt <= {CB{1'b0}};
        end else if (up_ev) begin
            landed   <= 1'b1;
            l_row    <= up_row;
            l_bits   <= up_bits;
            l_ptr    <= \dut.scrub_ptr + idle;
            idle_cnt <= {CB{1'b0}};
        end else if (landed && idle && idle_cnt < DEPTH) begin
            idle_cnt <= idle_cnt + 1'b1;
        end
    end

    // Error pattern of each way of the upset row, and its syndrome.
    wire [INTERLEAVE*CW-1:0] l_err;
    wire [INTERLEAVE*8-1:0]  l_err_syn;
    generate
        for (w = 0; w < INTERLEAVE; w = w + 1) begin : g_lerr
            wire [CW-1:0] e;
            wire [7:0]    chk;
            for (k = 0; k < CW; k = k + 1) begin : g_bit
                assign e[k] = l_bits[k*INTERLEAVE + w];
            end
            orbit_secded72_enc u_enc (.data(e[63:0]), .check(chk));
            assign l_err    [w*CW +: CW] = e;
            assign l_err_syn[w*8 +: 8]   = chk ^ e[71:64];
        end
    endgenerate

    // Any codeword of the array with a non-zero syndrome.
    wire any_err = |st_syn;
    // Any codeword of the upset row with a non-zero syndrome.
    wire row_err = |st_syn[l_row*INTERLEAVE*8 +: INTERLEAVE*8];

    // ------------------------------------------------------------------
    // Read scoreboard for addr0
    // ------------------------------------------------------------------
    reg        prev_rd = 1'b0;
    reg        exp_v   = 1'b0;
    reg [63:0] exp_d;
    reg        exp_ce;
    always @(posedge clk) begin
        prev_rd <= rst_n && rd_en;
        exp_v   <= rst_n && rd_en && rd_addr == addr0;
        exp_d   <= shadow;              // before this edge's write: read-first
        exp_ce  <= (cw0 != ref_cw);
    end

    always @* if (!init) begin
        a_rd_valid: assert (rd_valid == prev_rd);                      // C2
        if (exp_v) begin
            a_rd_data: assert (rd_data == exp_d);                      // C1, U1
            a_rd_ue:   assert (!rd_ue);
            a_rd_ce:   assert (rd_ce == exp_ce);
        end
`ifdef FV_CLEAN
        a_clean_rd:  assert (!(rd_valid && (rd_ce || rd_ue)));         // C3
        a_clean_log: assert (ce_count == 16'd0 && ue_count == 16'd0 && !last_err_valid);
`endif
`ifdef FV_UPSET
        a_no_ue:     assert (ue_count == 16'd0 && !(last_err_valid && last_err_ue) &&
                             !(rd_valid && rd_ue));                    // U2
        if (exp_v && rd_ce)
            a_ce_log: assert (last_err_valid && !last_err_ue &&
                              last_err_addr == addr0 && ce_count != 16'd0);   // U3
        if (landed && idle_cnt == DEPTH)
            a_scrub_bound: assert (!any_err);                          // U4
`endif
    end

    // ------------------------------------------------------------------
    // Helper invariants for k-induction
    // ------------------------------------------------------------------
`ifndef FV_NO_HELPERS
    integer hr, hw;
    always @* if (!init) begin
        h_used: assert (up_used || !landed);
`ifdef FV_CLEAN
        h_clean: assert (!up_used && !landed);
`endif
        h_cnt:  assert (idle_cnt <= DEPTH);
        // Rows other than the upset row hold valid codewords.
        for (hr = 0; hr < DEPTH; hr = hr + 1)
            for (hw = 0; hw < INTERLEAVE; hw = hw + 1)
                if (!(landed && hr == l_row))
                    assert (st_syn[(hr*INTERLEAVE + hw)*8 +: 8] == 8'd0);
        // Each way of the upset row is either repaired or still carries
        // exactly the error the upset put there.
        if (landed)
            for (hw = 0; hw < INTERLEAVE; hw = hw + 1)
                assert (st_syn[(l_row*INTERLEAVE + hw)*8 +: 8] == 8'd0 ||
                               st_syn[(l_row*INTERLEAVE + hw)*8 +: 8] == l_err_syn[hw*8 +: 8]);
        // addr0 holds the shadow, possibly with its way's share of the upset.
        h_addr0: assert (cw0 == ref_cw ||
                         (landed && row0 == l_row && cw0 == (ref_cw ^ l_err[way0*CW +: CW])));
        // The scrub pointer has advanced once per idle cycle since the upset,
        // and the upset row is still in error only if it has not been visited.
        if (landed && idle_cnt < DEPTH)
            h_ptr: assert (\dut.scrub_ptr == l_ptr + idle_cnt[RB-1:0]);
        if (landed && row_err)
            h_pending: assert (idle_cnt <= {1'b0, l_row - l_ptr});
    end
`endif

    // ------------------------------------------------------------------
    // Covers
    // ------------------------------------------------------------------
`ifdef FV_COVER
    always @* if (!init) begin
        // A read that corrects its share of a 2-bit upset.
        c_ce_read:    cover (exp_v && rd_ce && landed && up_used && l_bits != 0 &&
                             (l_bits & (l_bits - 1'b1)) != 0);
        // The upset row still in error after DEPTH-1 idle cycles: U4's bound is tight.
        c_bound_tight: cover (landed && idle_cnt == DEPTH - 1 && row_err);
        // Both ways of the upset row in error, then repaired by the scrubber.
        c_scrub_two:  cover (landed && idle_cnt == DEPTH && ce_count >= 2 && !any_err);
    end
`endif

endmodule

`default_nettype wire
