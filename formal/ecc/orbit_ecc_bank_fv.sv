// Formal harness for the SECDED-protected bank (rtl/ecc/orbit_ecc_bank.v):
// unbounded proofs by k-induction with a decoder abstraction.
//
// Run through formal/ecc/orbit_ecc_bank.sby. The bank is read with
// -DORBIT_ECC_UPSET, which gives it an undriven upset mask `upset` that is
// XORed into the array at every clock edge; this harness drives it through
// a (* hierconn *) wire. The decoder inside the bank is replaced by
// formal/ecc/orbit_secded72_dec_abs.v (free outputs), and this harness
// constrains those outputs to the decoder contract that
// formal/ecc/orbit_secded72.sby proves for the real decoder (see that file
// and rtl/ecc/README.md, "Formal"). The encoder is the real one.
//
// Reference model, per word address a (DEPTH*INTERLEAVE words):
//   G[a]       golden codeword: 0 after reset, the bank's encoded write word
//              (dut.wr_cw, whose data half is asserted equal to wr_data) after
//              a write to a
//   E[a], n[a] its error pattern (the codeword bits flipped by upsets and
//              not yet repaired) and the number of its set bits (0, 1, 2)
//   age[a]     idle cycles since a single error appeared in a and was not
//              repaired (idle = scrub_en & ~wr_en & ~rd_en, the scrubber's
//              condition)
//   m_ptr      the scrub row; m_ce/m_ue/m_le*: the error log
// Expected array: word a's codeword G ^ E in the documented interleaved
// layout (codeword bit k of way w at physical column k*INTERLEAVE + w).
//
// Upset model: at most one upset event per clock edge: one bit, or two
// physically adjacent bits (columns up_pos, up_pos+1), of one row up_row,
// at arbitrary times, any number of events. The groups restrict it:
//   FV_CLEAN  no upsets
//   FV_SEC    an upset never lands on a codeword that already holds an error
//             (errors are repaired or overwritten before the same word is hit
//             again - the SECDED operating assumption). Whether a 2-bit event
//             is one error in each of two codewords or two errors in one is
//             decided by the bank's interleaving, not assumed.
//   FV_DED    as FV_SEC, but a second upset may hit a codeword with one error
//             (never a third error, never the same bit twice)
//
// Properties (all groups unless noted):
//   A1  the array always equals the expected array (write path, interleaving,
//       scrub write-back of exactly the corrected words, nothing else changes)
//   A2  rd_valid is rd_en delayed by one cycle; a read returns G's data, i.e.
//       the data last written to that address (read-first: a same-cycle write
//       is not yet visible), with rd_ce = (1 error), rd_ue = (2 errors); a UE
//       read returns the uncorrected received data
//   A3  the encoded write word is {enc(wr_data), wr_data} with the real
//       encoder, so every golden word G is a codeword of the proven code;
//       scrub_row advances by one per idle cycle only
//   A5  each (abstracted) decoder instance is fed exactly the stored codeword
//       of its way of the decoded row (documented de-interleaving), so the
//       decoder contract is applied to the decoder's real input
//   A4  ce_count, ue_count (CNT_W = 3, saturating), last_err_* equal the model
//   U2  (FV_SEC, FV_CLEAN) no read and no scrub ever sees a UE: ue_count = 0
//   U4  (FV_SEC, FV_DED) scrub bound: a single error is repaired within DEPTH
//       idle cycles (age < DEPTH for every word with one error), whatever the
//       read/write traffic in between
//   C3  (FV_CLEAN) no CE or UE is ever reported or logged
//   Covers (FV_COVER): the bound of U4 is reached (age = DEPTH-1), a CE read
//   of one half of an adjacent 2-bit upset, a scrub visit repairing both
//   halves of an adjacent upset in one cycle, counter saturation; with FV_DED
//   only a UE read (task cover_ded).

`default_nettype none

module orbit_ecc_bank_fv #(
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
    input wire                                up_ev,    // an upset lands at this edge
    input wire [$clog2(DEPTH)-1:0]            up_row,   // physical row hit
    input wire [$clog2(INTERLEAVE*72)-1:0]    up_pos,   // lowest physical column hit
    input wire                                up_two    // also column up_pos + 1
);

    localparam integer CW    = 72;
    localparam integer IL    = INTERLEAVE;
    localparam integer NW    = DEPTH * IL;
    localparam integer ROW_W = IL * CW;
    localparam integer RB    = $clog2(DEPTH);
    localparam integer AW    = $clog2(NW);
    localparam integer PB    = $clog2(ROW_W);
    localparam integer CB    = $clog2(DEPTH + 1);   // age counter, counts to DEPTH
    localparam integer CNT_W = 3;                    // small, so saturation is reachable
    localparam [CNT_W-1:0] CNT_MAX = {CNT_W{1'b1}};

    // ------------------------------------------------------------------
    // DUT
    // ------------------------------------------------------------------
    wire             rd_valid, rd_ce, rd_ue;
    wire [63:0]      rd_data;
    wire [RB-1:0]    scrub_row;
    wire [CNT_W-1:0] ce_count, ue_count;
    wire             last_err_valid, last_err_ue;
    wire [AW-1:0]    last_err_addr;

    orbit_ecc_bank #(.DEPTH(DEPTH), .INTERLEAVE(IL), .CNT_W(CNT_W)) dut (
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
    (* hierconn *) wire [CW-1:0]          \dut.wr_cw ;       // encoded write word
    (* hierconn *) wire [RB-1:0]          \dut.dec_row ;     // row at the shared decoders
    (* hierconn *) wire [IL*CW-1:0]       \dut.way_cw ;      // decoder outputs (abstracted)
    (* hierconn *) wire [IL-1:0]          \dut.way_ce ;
    (* hierconn *) wire [IL-1:0]          \dut.way_ue ;
    // Inputs of the (abstracted) decoder instances. The contract below is
    // stated for the harness's own de-interleaving of the array (rx); A5
    // asserts that the bank really feeds that word to its decoder, otherwise a
    // wrong read-side bit mapping would be hidden by the free decoder outputs.
    // Way 1 is read only when INTERLEAVE > 1 (it does not exist otherwise).
    (* hierconn *) wire [63:0]            \dut.g_dec[0].u_dec.data_in ;
    (* hierconn *) wire [7:0]             \dut.g_dec[0].u_dec.check_in ;
    (* hierconn *) wire [63:0]            \dut.g_dec[1].u_dec.data_in ;
    (* hierconn *) wire [7:0]             \dut.g_dec[1].u_dec.check_in ;

    // The real encoder, applied to wr_data: A3 asserts that the bank stores
    // exactly this codeword, so every golden word G is a codeword of the code
    // that orbit_secded72.sby proves (the premise of the decoder contract).
    wire [7:0] f_wr_check;
    orbit_secded72_enc u_f_enc (.data(wr_data), .check(f_wr_check));

    // ------------------------------------------------------------------
    // Reset in the first cycle
    // ------------------------------------------------------------------
    reg init = 1'b1;
    always @(posedge clk) init <= 1'b0;
    always @* if (init) assume (!rst_n);

    wire idle = rst_n && scrub_en && !wr_en && !rd_en;   // the scrubber works this cycle

    // ------------------------------------------------------------------
    // Upset event
    // ------------------------------------------------------------------
    always @* begin
        assume ({1'b0, up_pos} + up_two < ROW_W);
`ifdef FV_CLEAN
        assume (!up_ev);
`endif
    end

    // Physical columns hit by the event, and the resulting upset mask.
    wire [ROW_W-1:0] up_bits;
    genvar r, c;
    generate
        for (c = 0; c < ROW_W; c = c + 1) begin : g_upcol
            assign up_bits[c] = (up_pos == c) || (up_two && {1'b0, up_pos} + 1'b1 == c);
        end
        for (r = 0; r < DEPTH; r = r + 1) begin : g_uprow
            assign \dut.upset [r*ROW_W +: ROW_W] =
                (up_ev && up_row == r) ? up_bits : {ROW_W{1'b0}};
        end
    endgenerate

    // ------------------------------------------------------------------
    // Reference model, one generate block per word
    // ------------------------------------------------------------------
    reg  [RB-1:0] m_ptr;
    always @(posedge clk)
        if (!rst_n)    m_ptr <= {RB{1'b0}};
        else if (idle) m_ptr <= m_ptr + 1'b1;

    wire [NW*CW-1:0] g_flat;    // G[a]
    wire [NW*CW-1:0] x_flat;    // G[a] ^ E[a], the expected stored codeword
    wire [NW*2-1:0]  n_flat;    // number of errors in word a
    wire [NW*CW-1:0] cells_cw;  // actual stored codeword of word a (de-interleaved)
    wire [NW*CB-1:0] age_flat;  // age[a]

    genvar a, k;
    generate
        for (a = 0; a < NW; a = a + 1) begin : g_w
            localparam integer RA = a / IL;     // row of word a
            localparam integer WA = a % IL;     // way of word a
            localparam [RB-1:0] RAB = a / IL;

            reg [CW-1:0] G;
            reg [CW-1:0] E;         // error pattern (flipped codeword bits)
            reg [1:0]    n;         // number of set bits of E (0, 1 or 2)
            reg [CB-1:0] age;

            // State after this edge's write or scrub, before the upset.
            wire          wr_hit   = wr_en && wr_addr == a;
            wire          scrubbed = idle && m_ptr == RA && n == 2'd1;
            wire [CW-1:0] e_c      = (wr_hit || scrubbed) ? {CW{1'b0}} : E;
            wire [1:0]    n_c      = (wr_hit || scrubbed) ? 2'd0 : n;
            // Upset bits landing in this word: codeword bit k is column k*IL + WA.
            wire [CW-1:0] hitv;
            for (k = 0; k < CW; k = k + 1) begin : g_hit
                assign hitv[k] = up_ev && up_row == RA && up_bits[k*IL + WA];
            end
            // How many (0, 1, 2 - two only without interleaving).
            wire          hit0 = up_ev && up_row == RA && (up_pos % IL) == WA;
            wire          hit1 = up_ev && up_two && up_row == RA && ((up_pos + 1'b1) % IL) == WA;

            always @* if (rst_n) begin
`ifdef FV_SEC
                if (hit0 || hit1) assume (n_c == 2'd0);
`endif
`ifdef FV_DED
                assume ({1'b0, n_c} + hit0 + hit1 <= 3'd2);
                assume ((e_c & hitv) == {CW{1'b0}});   // never the same bit twice
`endif
            end

            always @(posedge clk) begin
                if (!rst_n) begin
                    G   <= {CW{1'b0}};
                    E   <= {CW{1'b0}};
                    n   <= 2'd0;
                    age <= {CB{1'b0}};
                end else begin
                    if (wr_hit)
                        G <= \dut.wr_cw ;
                    E <= e_c ^ hitv;
                    n <= n_c + hit0 + hit1;
                    if (wr_hit || scrubbed || (n_c == 2'd0 && (hit0 || hit1)))
                        age <= {CB{1'b0}};
                    else if (idle && n == 2'd1 && age < DEPTH)
                        age <= age + 1'b1;
                end
            end

            assign g_flat[a*CW +: CW] = G;
            assign x_flat[a*CW +: CW] = G ^ E;
            assign n_flat[a*2 +: 2]   = n;
            assign age_flat[a*CB +: CB] = age;
            for (k = 0; k < CW; k = k + 1) begin : g_bit
                assign cells_cw[a*CW + k] = \dut.cells [RA*ROW_W + k*IL + WA];
            end

            // Model consistency (helpers for induction) and the scrub bound.
            always @* if (!init) begin
                assert (n != 2'd3);
                assert (age <= DEPTH);
                // Each idle cycle either repairs the word or moves the scrub
                // pointer one row closer to it: distance + age is constant.
                if (n == 2'd1)
                    assert ({1'b0, RAB - m_ptr} + age <= DEPTH - 1);
`ifndef FV_CLEAN
                if (n == 2'd1) assert (age < DEPTH);                 // U4
`endif
`ifdef FV_CLEAN
                assert (n == 2'd0);
`endif
`ifdef FV_SEC
                assert (n != 2'd2);
`endif
            end
        end
    endgenerate

    // ------------------------------------------------------------------
    // Decoder contract (proven for the real decoder: orbit_secded72.sby)
    // ------------------------------------------------------------------
    generate
        for (a = 0; a < IL; a = a + 1) begin : g_dec
            wire [AW-1:0] wa  = \dut.dec_row * IL + a;
            wire [CW-1:0] rx  = cells_cw[wa*CW +: CW];
            wire [CW-1:0] gw  = g_flat  [wa*CW +: CW];
            wire [CW-1:0] xw  = x_flat  [wa*CW +: CW];
            wire [1:0]    nw  = n_flat  [wa*2  +: 2];
            wire [CW-1:0] out = \dut.way_cw [a*CW +: CW];
            always @* if (rx == xw) begin
                if (nw == 2'd0) assume (out == gw && !\dut.way_ce [a] && !\dut.way_ue [a]);
                if (nw == 2'd1) assume (out == gw &&  \dut.way_ce [a] && !\dut.way_ue [a]);
                if (nw == 2'd2) assume (out == rx && !\dut.way_ce [a] &&  \dut.way_ue [a]);
            end
        end
    endgenerate

    // ------------------------------------------------------------------
    // Error log model
    // ------------------------------------------------------------------
    reg [1:0]    ev_nce, ev_nue;     // events this cycle
    reg          ev_any, ev_ue;
    reg [AW-1:0] ev_addr;
    integer      i;
    always @* begin
        ev_nce = 2'd0; ev_nue = 2'd0; ev_any = 1'b0; ev_ue = 1'b0; ev_addr = {AW{1'b0}}; i = 0;
        if (rst_n && rd_en) begin
            ev_nce  = (n_flat[rd_addr*2 +: 2] == 2'd1);
            ev_nue  = (n_flat[rd_addr*2 +: 2] == 2'd2);
            ev_any  = (n_flat[rd_addr*2 +: 2] != 2'd0);
            ev_ue   = (n_flat[rd_addr*2 +: 2] == 2'd2);
            ev_addr = rd_addr;
        end else if (idle) begin
            // UE events take precedence, then the lowest way.
            for (i = IL - 1; i >= 0; i = i - 1)
                if (n_flat[(m_ptr*IL + i)*2 +: 2] == 2'd1) begin
                    ev_nce = ev_nce + 1'b1;
                    ev_any = 1'b1;
                    if (!ev_ue) ev_addr = m_ptr * IL + i;
                end
            for (i = IL - 1; i >= 0; i = i - 1)
                if (n_flat[(m_ptr*IL + i)*2 +: 2] == 2'd2) begin
                    ev_nue  = ev_nue + 1'b1;
                    ev_any  = 1'b1;
                    ev_ue   = 1'b1;
                    ev_addr = m_ptr * IL + i;
                end
        end
    end

    wire [CNT_W:0] ce_sum = (log_clear ? {(CNT_W+1){1'b0}} : {1'b0, m_ce}) + ev_nce;
    wire [CNT_W:0] ue_sum = (log_clear ? {(CNT_W+1){1'b0}} : {1'b0, m_ue}) + ev_nue;

    reg [CNT_W-1:0] m_ce, m_ue;
    reg             m_lev, m_leu;
    reg [AW-1:0]    m_lea;
    always @(posedge clk) begin
        if (!rst_n) begin
            m_ce <= 0; m_ue <= 0; m_lev <= 1'b0; m_leu <= 1'b0; m_lea <= 0;
        end else begin
            m_ce <= ce_sum[CNT_W] ? CNT_MAX : ce_sum[CNT_W-1:0];
            m_ue <= ue_sum[CNT_W] ? CNT_MAX : ue_sum[CNT_W-1:0];
            if (ev_any) begin
                m_lev <= 1'b1; m_leu <= ev_ue; m_lea <= ev_addr;
            end else if (log_clear) begin
                m_lev <= 1'b0; m_leu <= 1'b0; m_lea <= 0;
            end
        end
    end

    // ------------------------------------------------------------------
    // Read scoreboard (any address)
    // ------------------------------------------------------------------
    reg        prev_rd = 1'b0;
    reg [63:0] exp_d;
    reg        exp_ce, exp_ue;
    always @(posedge clk) begin
        prev_rd <= rst_n && rd_en;
        exp_ue  <= n_flat[rd_addr*2 +: 2] == 2'd2;
        exp_ce  <= n_flat[rd_addr*2 +: 2] == 2'd1;
        exp_d   <= (n_flat[rd_addr*2 +: 2] == 2'd2) ? x_flat[rd_addr*CW +: 64]
                                                     : g_flat[rd_addr*CW +: 64];
    end

    // Expected physical array.
    wire [DEPTH*ROW_W-1:0] exp_cells;
    generate
        for (a = 0; a < NW; a = a + 1) begin : g_exp
            for (k = 0; k < CW; k = k + 1) begin : g_bit
                assign exp_cells[(a/IL)*ROW_W + k*IL + (a%IL)] = x_flat[a*CW + k];
            end
        end
    endgenerate

    // ------------------------------------------------------------------
    // Properties
    // ------------------------------------------------------------------
    always @* if (!init) begin
        a_array:     assert (\dut.cells == exp_cells);                          // A1
        a_rd_valid:  assert (rd_valid == prev_rd);                              // A2
        if (prev_rd) begin
            a_rd_data:  assert (rd_data == exp_d);
            a_rd_flags: assert (rd_ce == exp_ce && rd_ue == exp_ue);
        end
        a_wr_cw:     assert (\dut.wr_cw == {f_wr_check, wr_data});              // A3
        a_dec_in0:   assert ({\dut.g_dec[0].u_dec.check_in , \dut.g_dec[0].u_dec.data_in } ==
                             g_dec[0].rx);                                       // A5
        if (IL > 1)
            a_dec_in1: assert ({\dut.g_dec[1].u_dec.check_in , \dut.g_dec[1].u_dec.data_in } ==
                               g_dec[IL > 1 ? 1 : 0].rx);                        // A5
        a_ptr:       assert (\dut.scrub_ptr == m_ptr && scrub_row == m_ptr);
        a_log:       assert (ce_count == m_ce && ue_count == m_ue &&            // A4
                             last_err_valid == m_lev && last_err_ue == m_leu &&
                             last_err_addr == m_lea);
`ifndef FV_DED
        a_no_ue:     assert (ue_count == 0 && !(rd_valid && rd_ue));            // U2
`endif
`ifdef FV_CLEAN
        a_clean:     assert (ce_count == 0 && !last_err_valid && !(rd_valid && rd_ce));  // C3
`endif
    end

    // ------------------------------------------------------------------
    // Covers
    // ------------------------------------------------------------------
`ifdef FV_COVER
    reg saw_adj = 1'b0;   // an adjacent 2-bit event landed since reset
    always @(posedge clk)
        if (!rst_n) saw_adj <= 1'b0;
        else if (up_ev && up_two) saw_adj <= 1'b1;

    always @* if (!init) begin
`ifndef FV_DED
        // (cover_ded only adds the UE read; the others are the same as in
        // `cover` and take several minutes more under the DED model.)
        c_bound_tight: cover (n_flat[1:0] == 2'd1 && age_flat[CB-1:0] == DEPTH - 1);
        c_ce_read_adj: cover (saw_adj && rd_valid && rd_ce && n_flat[1:0] == 2'd0 &&
                              n_flat[3:2] == 2'd1);
        // The scrubber visits a row with a single error in two ways (an
        // adjacent 2-bit upset) and repairs both in one cycle.
        c_scrub_two:   cover (idle && saw_adj && n_flat[(m_ptr*IL)*2 +: 2] == 2'd1 &&
                              n_flat[(m_ptr*IL + IL - 1)*2 +: 2] == 2'd1 && IL > 1);
        c_saturate:    cover (ce_count == CNT_MAX);
`else
        c_ue_read:     cover (rd_valid && rd_ue);
`endif
    end
`endif

endmodule

`default_nettype wire
