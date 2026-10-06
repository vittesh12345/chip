// ORBIT-AI ECC extension: small SECDED-protected storage bank with
// bit interleaving and a background scrubber.
//
// Target-architecture items "Protected SRAM / SECDED ECC + interleaving" and
// "ECC / scrub: Correct, Report, Refresh" (docs/orbit-ai-design-brief.pdf,
// page 1). Not part of the built demonstrator (orbit_demo). The flip-flop
// array stands in for an SRAM macro. Interface and protocol: rtl/ecc/README.md.
//
// Organisation
//   DEPTH physical rows of INTERLEAVE x 72 bits. Each row holds INTERLEAVE
//   (72,64) codewords, bit-interleaved: codeword bit k of way w sits at
//   physical column k*INTERLEAVE + w. Physically adjacent bits therefore
//   belong to different codewords, and an upset of up to INTERLEAVE adjacent
//   bits of one row is at most one bit error per codeword.
//   Word address = {row, way}: row = addr[AW-1:WB], way = addr[WB-1:0].
//
// Ports (all synchronous to clk; rst_n is synchronous, active low)
//   Write: wr_en/wr_addr/wr_data. The encoded word is stored at the rising
//     edge; only the addressed codeword of the row is written.
//   Read:  rd_en/rd_addr. At the next edge rd_valid pulses and rd_data,
//     rd_ce, rd_ue hold the decoded word (they keep their value until the next
//     read). A read and a write in the same cycle are both performed; the read
//     returns the contents from before the write (read-first).
//   Scrubber: in every cycle with scrub_en & ~wr_en & ~rd_en ("idle") it
//     decodes all codewords of row scrub_row, writes back the corrected
//     codeword of every way that had a single-bit error, and advances
//     scrub_row by one (wrapping). Ways with an uncorrectable error are left
//     unchanged. Any single-bit error is therefore repaired within DEPTH idle
//     cycles.
//   Error log: every error the decoders see - the addressed codeword of a
//     read, every codeword of a scrubbed row - is an event. ce_count/ue_count
//     add the number of CE/UE events per cycle and saturate at all ones.
//     last_err_* records the most recent event (UE before CE, then the lowest
//     way). log_clear zeroes the log first; events in the same cycle are kept.
//
// Reset writes all-zero rows, which are valid codewords (data 0), so every
// word reads 0 after reset. A real SRAM macro would need an init sweep.

`default_nettype none

module orbit_ecc_bank #(
    parameter integer DEPTH      = 16,  // physical rows, power of 2, >= 2
    parameter integer INTERLEAVE = 2,   // codewords per row, power of 2, >= 1
    parameter integer CNT_W      = 16   // saturating error counter width, >= 1
) (
    input  wire                                clk,
    input  wire                                rst_n,
    // Write port
    input  wire                                wr_en,
    input  wire [$clog2(DEPTH*INTERLEAVE)-1:0] wr_addr,
    input  wire [63:0]                         wr_data,
    // Read port, latency 1
    input  wire                                rd_en,
    input  wire [$clog2(DEPTH*INTERLEAVE)-1:0] rd_addr,
    output reg                                 rd_valid,
    output reg  [63:0]                         rd_data,
    output reg                                 rd_ce,
    output reg                                 rd_ue,
    // Scrubber and error log
    input  wire                                scrub_en,
    input  wire                                log_clear,
    output wire [$clog2(DEPTH)-1:0]            scrub_row,
    output reg  [CNT_W-1:0]                    ce_count,
    output reg  [CNT_W-1:0]                    ue_count,
    output reg                                 last_err_valid,
    output reg                                 last_err_ue,
    output reg  [$clog2(DEPTH*INTERLEAVE)-1:0] last_err_addr
);

    localparam integer CW    = 72;                          // codeword bits
    localparam integer ROW_W = INTERLEAVE * CW;             // physical bits per row
    localparam integer RB    = $clog2(DEPTH);               // row address bits
    localparam integer WB    = $clog2(INTERLEAVE);          // way address bits (0 if INTERLEAVE = 1)
    localparam integer AW    = RB + WB;                     // word address bits
    localparam integer WX    = (WB > 0) ? WB : 1;           // width of way-index signals
    localparam integer SW    = ((CNT_W > WB + 1) ? CNT_W : WB + 1) + 1;  // counter adder width

    localparam [INTERLEAVE-1:0] WAY_ONE = 1;
    localparam [DEPTH-1:0]      ROW_ONE = 1;
    localparam [SW-1:0]         CNT_MAX = {{(SW-CNT_W){1'b0}}, {CNT_W{1'b1}}};

    // Elaboration-time parameter check: an illegal value instantiates a module
    // that does not exist, which every tool reports as an error.
    generate
        if (DEPTH < 2 || (DEPTH & (DEPTH - 1)) != 0) begin : g_bad_depth
            orbit_ecc_bank_DEPTH_must_be_a_power_of_2_and_at_least_2 u_bad ();
        end
        if (INTERLEAVE < 1 || (INTERLEAVE & (INTERLEAVE - 1)) != 0) begin : g_bad_interleave
            orbit_ecc_bank_INTERLEAVE_must_be_a_power_of_2 u_bad ();
        end
        if (CNT_W < 1) begin : g_bad_cnt_w
            orbit_ecc_bank_CNT_W_must_be_at_least_1 u_bad ();
        end
    endgenerate

    // ------------------------------------------------------------------
    // Address split
    // ------------------------------------------------------------------
    wire [RB-1:0] wr_row = wr_addr[AW-1:WB];
    wire [RB-1:0] rd_row = rd_addr[AW-1:WB];
    wire [WX-1:0] wr_way;
    wire [WX-1:0] rd_way;

    generate
        if (WB > 0) begin : g_way
            assign wr_way = wr_addr[WX-1:0];
            assign rd_way = rd_addr[WX-1:0];
        end else begin : g_no_way
            assign wr_way = 1'b0;
            assign rd_way = 1'b0;
        end
    endgenerate

    wire [INTERLEAVE-1:0] wr_way_oh = WAY_ONE << wr_way;
    wire [INTERLEAVE-1:0] rd_way_oh = WAY_ONE << rd_way;

    // ------------------------------------------------------------------
    // Storage: row r at cells[r*ROW_W +: ROW_W]
    // ------------------------------------------------------------------
    reg  [DEPTH*ROW_W-1:0] cells;
    wire [DEPTH*ROW_W-1:0] cells_nxt;
    reg  [RB-1:0]          scrub_ptr;

    // ------------------------------------------------------------------
    // Shared row decoders: the read port uses them when rd_en is high, the
    // scrubber otherwise (it only acts when both ports are idle).
    // ------------------------------------------------------------------
    wire [RB-1:0]          dec_row  = rd_en ? rd_row : scrub_ptr;
    wire [ROW_W-1:0]       dec_bits = cells[dec_row*ROW_W +: ROW_W];

    wire [INTERLEAVE*64-1:0] way_data;   // corrected data per way
    wire [INTERLEAVE*CW-1:0] way_cw;     // corrected codeword per way
    wire [INTERLEAVE-1:0]    way_ce;
    wire [INTERLEAVE-1:0]    way_ue;

    genvar w, k, r;
    generate
        for (w = 0; w < INTERLEAVE; w = w + 1) begin : g_dec
            wire [CW-1:0] cw_raw;           // de-interleaved codeword of way w
            /* verilator lint_off UNUSEDSIGNAL */
            wire [7:0]    syndrome;         // not needed by the bank
            /* verilator lint_on UNUSEDSIGNAL */
            for (k = 0; k < CW; k = k + 1) begin : g_bit
                assign cw_raw[k] = dec_bits[k*INTERLEAVE + w];
            end
            orbit_secded72_dec u_dec (
                .data_in   (cw_raw[63:0]),
                .check_in  (cw_raw[71:64]),
                .data_out  (way_cw[w*CW +: 64]),
                .check_out (way_cw[w*CW + 64 +: 8]),
                .ce        (way_ce[w]),
                .ue        (way_ue[w]),
                .syndrome  (syndrome)
            );
            assign way_data[w*64 +: 64] = way_cw[w*CW +: 64];
        end
    endgenerate

    // ------------------------------------------------------------------
    // Array write port: the write port has priority; otherwise the scrubber
    // writes back the corrected codeword of every way with a CE.
    // ------------------------------------------------------------------
    wire [7:0]            wr_check;
    wire [CW-1:0]         wr_cw = {wr_check, wr_data};

    orbit_secded72_enc u_wr_enc (.data(wr_data), .check(wr_check));

    wire                  scrub_go  = scrub_en & ~wr_en & ~rd_en;
    wire [INTERLEAVE-1:0] scrub_fix = way_ce & {INTERLEAVE{scrub_go}};

    wire                  arr_we     = wr_en | (|scrub_fix);
    wire [RB-1:0]         arr_row    = wr_en ? wr_row : scrub_ptr;
    wire [DEPTH-1:0]      arr_row_oh = arr_we ? (ROW_ONE << arr_row) : {DEPTH{1'b0}};
    wire [INTERLEAVE-1:0] arr_ways   = wr_en ? wr_way_oh : scrub_fix;
    wire [ROW_W-1:0]      arr_mask;
    wire [ROW_W-1:0]      arr_data;

    generate
        for (w = 0; w < INTERLEAVE; w = w + 1) begin : g_wr_way
            for (k = 0; k < CW; k = k + 1) begin : g_bit
                assign arr_mask[k*INTERLEAVE + w] = arr_ways[w];
                assign arr_data[k*INTERLEAVE + w] = wr_en ? wr_cw[k] : way_cw[w*CW + k];
            end
        end
        for (r = 0; r < DEPTH; r = r + 1) begin : g_row
            wire [ROW_W-1:0] q = cells[r*ROW_W +: ROW_W];
            assign cells_nxt[r*ROW_W +: ROW_W] =
                arr_row_oh[r] ? ((q & ~arr_mask) | (arr_data & arr_mask)) : q;
        end
    endgenerate

`ifdef ORBIT_ECC_UPSET
    // Verification only (never defined for synthesis): an upset mask that is
    // XORed into the array at every clock edge. It is deliberately undriven
    // here; the formal harness (formal/ecc/orbit_ecc_bank_fv.sv) reads it
    // through a hierconn wire, SymbiYosys makes it a free input, and the
    // harness constrains it to the upset model it wants.
    wire [DEPTH*ROW_W-1:0] upset;
`else
    wire [DEPTH*ROW_W-1:0] upset = {DEPTH*ROW_W{1'b0}};
`endif

    always @(posedge clk) begin
        if (!rst_n)
            cells <= {DEPTH*ROW_W{1'b0}};   // all-zero rows are valid codewords
        else
            cells <= cells_nxt ^ upset;     // upset is constant 0 outside verification
    end

    always @(posedge clk) begin
        if (!rst_n)
            scrub_ptr <= {RB{1'b0}};
        else if (scrub_go)
            scrub_ptr <= scrub_ptr + 1'b1;
    end

    assign scrub_row = scrub_ptr;

    // ------------------------------------------------------------------
    // Read port
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            rd_valid <= 1'b0;
            rd_data  <= 64'd0;
            rd_ce    <= 1'b0;
            rd_ue    <= 1'b0;
        end else begin
            rd_valid <= rd_en;
            if (rd_en) begin
                rd_data <= way_data[rd_way*64 +: 64];
                rd_ce   <= way_ce[rd_way];
                rd_ue   <= way_ue[rd_way];
            end
        end
    end

    // ------------------------------------------------------------------
    // Error log
    // ------------------------------------------------------------------
    // Events this cycle: the addressed codeword of a read, or every codeword
    // of the row the scrubber visits.
    wire [INTERLEAVE-1:0] ev_ce = rd_en ? (way_ce & rd_way_oh) : (way_ce & {INTERLEAVE{scrub_go}});
    wire [INTERLEAVE-1:0] ev_ue = rd_en ? (way_ue & rd_way_oh) : (way_ue & {INTERLEAVE{scrub_go}});
    wire                  ev_any = |{ev_ce, ev_ue};
    wire                  ev_is_ue = |ev_ue;
    wire [RB-1:0]         ev_row = dec_row;

    reg  [SW-1:0] n_ce;       // number of CE events this cycle
    reg  [SW-1:0] n_ue;       // number of UE events this cycle
    /* verilator lint_off UNUSEDSIGNAL */
    reg  [WX-1:0] ev_way;     // way of the event to record (UE first, lowest way);
                              // unused when INTERLEAVE = 1
    /* verilator lint_on UNUSEDSIGNAL */
    integer       i;

    always @* begin
        n_ce   = {SW{1'b0}};
        n_ue   = {SW{1'b0}};
        ev_way = {WX{1'b0}};
        for (i = 0; i < INTERLEAVE; i = i + 1) begin
            n_ce = n_ce + {{(SW-1){1'b0}}, ev_ce[i]};
            n_ue = n_ue + {{(SW-1){1'b0}}, ev_ue[i]};
        end
        for (i = INTERLEAVE - 1; i >= 0; i = i - 1) begin
            if (ev_is_ue ? ev_ue[i] : ev_ce[i])
                ev_way = i[WX-1:0];
        end
    end

    wire [AW-1:0] ev_addr;

    generate
        if (WB > 0) begin : g_ev_addr
            assign ev_addr = {ev_row, ev_way};
        end else begin : g_ev_addr_row
            assign ev_addr = ev_row;
        end
    endgenerate

    // Saturating counters: clear first, then add this cycle's events.
    wire [SW-1:0] ce_sum = (log_clear ? {SW{1'b0}} : {{(SW-CNT_W){1'b0}}, ce_count}) + n_ce;
    wire [SW-1:0] ue_sum = (log_clear ? {SW{1'b0}} : {{(SW-CNT_W){1'b0}}, ue_count}) + n_ue;

    always @(posedge clk) begin
        if (!rst_n) begin
            ce_count       <= {CNT_W{1'b0}};
            ue_count       <= {CNT_W{1'b0}};
            last_err_valid <= 1'b0;
            last_err_ue    <= 1'b0;
            last_err_addr  <= {AW{1'b0}};
        end else begin
            ce_count <= (ce_sum > CNT_MAX) ? {CNT_W{1'b1}} : ce_sum[CNT_W-1:0];
            ue_count <= (ue_sum > CNT_MAX) ? {CNT_W{1'b1}} : ue_sum[CNT_W-1:0];
            if (ev_any) begin
                last_err_valid <= 1'b1;
                last_err_ue    <= ev_is_ue;
                last_err_addr  <= ev_addr;
            end else if (log_clear) begin
                last_err_valid <= 1'b0;
                last_err_ue    <= 1'b0;
                last_err_addr  <= {AW{1'b0}};
            end
        end
    end

endmodule

`default_nettype wire
