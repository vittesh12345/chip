// Self-checking random testbench for the SECDED bank (rtl/ecc/orbit_ecc_bank.v).
//
// Stimulus: random writes, reads (including same-cycle read/write of one
// address), idle stretches with and without scrub_en, log_clear pulses, a
// mid-run reset, and random error injection into the array between clock
// edges (hierarchical writes to dut.cells, i.e. upsets of stored bits):
//   * single-bit upsets of a random physical bit,
//   * physically adjacent 2-bit upsets (one bit in each of two ways),
//   * a second upset in an already-hit codeword (a double error -> UE).
// No codeword is ever given a third error (outside the SECDED guarantee).
//
// Reference model (independent of the RTL internals): per word address the
// last written data and the injected error pattern `err`; the expected array
// contents are encode(data) ^ err in the documented interleaved layout
// (codeword bit k of way w at physical column k*INTERLEAVE + w). The model
// has its own Hsiao encoder (construction rule, not the RTL table), its own
// scrub pointer, CE/UE event counters and last-error record.
//
// Checks every cycle: read data/flags/rd_valid, scrub_row, counters,
// last_err_*, and the array rows written at this edge against the model (so
// every scrub write-back is checked bit for bit), plus the whole array every
// 16 cycles. A second DUT with CNT_W = 3 gets the
// same stimulus and injections and checks counter saturation.
// Plusargs: +seed=<n> +cycles=<n>. Prints TB_ORBIT_ECC_BANK PASS/FAIL.

`default_nettype none

module tb_orbit_ecc_bank;

    localparam integer DEPTH = 16;
    localparam integer IL    = 2;
    localparam integer NW    = DEPTH * IL;
    localparam integer AW    = 5;
    localparam integer RB    = 4;
    localparam integer ROW_W = IL * 72;

    reg           clk = 1'b0;
    reg           rst_n = 1'b0;
    reg           wr_en = 1'b0, rd_en = 1'b0, scrub_en = 1'b0, log_clear = 1'b0;
    reg  [AW-1:0] wr_addr = 0, rd_addr = 0;
    reg  [63:0]   wr_data = 0;

    wire          rd_valid, rd_ce, rd_ue, lev, leu;
    wire [63:0]   rd_data;
    wire [RB-1:0] scrub_row;
    wire [15:0]   ce_count, ue_count;
    wire [AW-1:0] lea;

    orbit_ecc_bank #(.DEPTH(DEPTH), .INTERLEAVE(IL), .CNT_W(16)) dut (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_valid(rd_valid), .rd_data(rd_data),
        .rd_ce(rd_ce), .rd_ue(rd_ue), .scrub_en(scrub_en), .log_clear(log_clear),
        .scrub_row(scrub_row), .ce_count(ce_count), .ue_count(ue_count),
        .last_err_valid(lev), .last_err_ue(leu), .last_err_addr(lea)
    );

    // Same stimulus, 3-bit saturating counters.
    wire [2:0] ce_count3, ue_count3;
    /* verilator lint_off PINCONNECTEMPTY */
    orbit_ecc_bank #(.DEPTH(DEPTH), .INTERLEAVE(IL), .CNT_W(3)) dut3 (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_valid(), .rd_data(),
        .rd_ce(), .rd_ue(), .scrub_en(scrub_en), .log_clear(log_clear),
        .scrub_row(), .ce_count(ce_count3), .ue_count(ue_count3),
        .last_err_valid(), .last_err_ue(), .last_err_addr()
    );
    /* verilator lint_on PINCONNECTEMPTY */

    always #5 clk = ~clk;

    // ------------------------------------------------------------------
    // Reference model state
    // ------------------------------------------------------------------
    reg [7:0]  ref_col [0:63];
    reg [63:0] m_data  [0:NW-1];
    reg [71:0] m_err   [0:NW-1];
    reg [7:0]  m_chk   [0:NW-1];      // ref_check(m_data), cached
    reg [RB-1:0] m_touch_row;          // row written this edge (checked every cycle)
    reg        m_touch;
    reg [RB-1:0] m_sp;
    integer    m_ce, m_ue;             // unbounded event counts since the last clear
    reg        m_lev, m_leu;
    reg [AW-1:0] m_lea;
    reg        m_rv, m_rce, m_rue;
    reg [63:0] m_rd;

    integer seed, seed0, cycles, errors, cyc, i, w, k, t;
    integer n_rd, n_rd_ce, n_rd_ue, n_wr, n_coll, n_inj1, n_inj_adj, n_inj_dbl, n_scrub_fix, n_clear;
    integer n_sat;

    function [7:0] ref_check(input [63:0] x);
        integer q;
        begin
            ref_check = 8'd0;
            for (q = 0; q < 64; q = q + 1)
                if (x[q]) ref_check = ref_check ^ ref_col[q];
        end
    endfunction

    function integer pop72(input [71:0] x);
        integer q;
        begin
            pop72 = 0;
            for (q = 0; q < 72; q = q + 1) pop72 = pop72 + x[q];
        end
    endfunction

    function [63:0] rand64(input integer dummy);
        begin
            rand64 = {$random(seed), $random(seed)};
        end
    endfunction

    function integer urand(input integer n);   // 0 .. n-1
        begin
            urand = {$random(seed)} % n;
        end
    endfunction

    task err_msg(input [8*40-1:0] what);
        begin
            errors = errors + 1;
            if (errors <= 25)
                $display("ERROR cycle %0d: %0s", cyc, what);
        end
    endtask

    // Expected physical bit of the array.
    function exp_bit(input integer row, input integer col);
        reg [71:0] cw;
        integer a;
        begin
            a  = row * IL + (col % IL);
            cw = {m_chk[a], m_data[a]} ^ m_err[a];
            exp_bit = cw[col / IL];
        end
    endfunction

    // ------------------------------------------------------------------
    // Model update for one rising edge (inputs as driven for this cycle)
    // ------------------------------------------------------------------
    task model_edge;
        integer a, pe, nce, nue, ev_a;
        reg     ev, ev_ue;
        begin
            if (!rst_n) begin
                for (a = 0; a < NW; a = a + 1) begin m_data[a] = 0; m_err[a] = 0; m_chk[a] = 0; end
                m_sp = 0; m_ce = 0; m_ue = 0; m_lev = 0; m_leu = 0; m_lea = 0;
                m_rv = 0; m_rce = 0; m_rue = 0; m_rd = 0;
            end else begin
                nce = 0; nue = 0; ev = 0; ev_ue = 0; ev_a = 0;
                m_touch = wr_en; m_touch_row = wr_addr / IL;
                // Read (sees the contents before this edge).
                m_rv = rd_en;
                if (rd_en) begin
                    pe    = pop72(m_err[rd_addr]);
                    // UE: the uncorrected received data is returned.
                    m_rd  = m_data[rd_addr] ^ ((pe == 2) ? m_err[rd_addr][63:0] : 64'd0);
                    m_rce = (pe == 1);
                    m_rue = (pe == 2);
                    if (pe == 1) nce = 1;
                    if (pe == 2) nue = 1;
                    if (pe != 0) begin ev = 1; ev_ue = (pe == 2); ev_a = rd_addr; end
                end else if (scrub_en && !wr_en) begin
                    // Scrubber visits row m_sp: events for every way, UE first, lowest way.
                    for (w = IL - 1; w >= 0; w = w - 1) begin
                        a  = m_sp * IL + w;
                        pe = pop72(m_err[a]);
                        if (pe == 1) begin
                            nce = nce + 1;
                            if (!(ev && ev_ue)) begin ev = 1; ev_a = a; end
                        end
                        if (pe == 2) begin
                            nue = nue + 1;
                            ev = 1; ev_ue = 1; ev_a = a;
                        end
                    end
                    // UE-first: if any UE, record the lowest UE way.
                    if (ev_ue)
                        for (w = IL - 1; w >= 0; w = w - 1)
                            if (pop72(m_err[m_sp * IL + w]) == 2) ev_a = m_sp * IL + w;
                    for (w = 0; w < IL; w = w + 1) begin
                        a = m_sp * IL + w;
                        if (pop72(m_err[a]) == 1) begin
                            m_err[a] = 72'd0;            // corrected and written back
                            n_scrub_fix = n_scrub_fix + 1;
                        end
                    end
                    m_sp = m_sp + 1'b1;
                end
                // Error log: clear first, keep this cycle's events.
                if (log_clear) begin m_ce = 0; m_ue = 0; end
                m_ce = m_ce + nce;
                m_ue = m_ue + nue;
                if (ev) begin
                    m_lev = 1; m_leu = ev_ue; m_lea = ev_a;
                end else if (log_clear) begin
                    m_lev = 0; m_leu = 0; m_lea = 0;
                end
                // Write (after the read: read-first).
                if (wr_en) begin
                    m_data[wr_addr] = wr_data;
                    m_err[wr_addr]  = 72'd0;
                    m_chk[wr_addr]  = ref_check(wr_data);
                end
            end
        end
    endtask

    // ------------------------------------------------------------------
    // Checks after an edge
    // ------------------------------------------------------------------
    task check_outputs;
        integer r, c, bad;
        begin
            if (rd_valid !== m_rv) err_msg("rd_valid");
            if (m_rv) begin
                if (rd_ce !== m_rce || rd_ue !== m_rue) err_msg("read CE/UE flags");
                if (rd_data !== m_rd) err_msg("read data");
            end
            if (scrub_row !== m_sp) err_msg("scrub_row");
            if (ce_count !== ((m_ce > 65535) ? 65535 : m_ce)) err_msg("ce_count");
            if (ue_count !== ((m_ue > 65535) ? 65535 : m_ue)) err_msg("ue_count");
            if (ce_count3 !== ((m_ce > 7) ? 7 : m_ce)) err_msg("ce_count (CNT_W=3)");
            if (ue_count3 !== ((m_ue > 7) ? 7 : m_ue)) err_msg("ue_count (CNT_W=3)");
            if (m_ce > 7) n_sat = n_sat + 1;
            if (lev !== m_lev || (m_lev && (leu !== m_leu || lea !== m_lea))) err_msg("last_err");
            // Array against the model: every row every 16 cycles, otherwise
            // the rows this edge could have written (write row, scrubbed row).
            bad = 0;
            for (r = 0; r < DEPTH; r = r + 1)
                if (cyc % 16 == 0 || (m_touch && r == m_touch_row) || r == ((m_sp - 1) % DEPTH))
                    for (c = 0; c < ROW_W; c = c + 1)
                        if (dut.cells[r*ROW_W + c] !== exp_bit(r, c)) bad = bad + 1;
            if (bad != 0) err_msg("array contents differ from model");
        end
    endtask

    // Flip physical bit (row, col) in both DUTs and record it in the model.
    task flip(input integer row, input integer col);
        integer a;
        begin
            dut.cells[row*ROW_W + col]  = ~dut.cells[row*ROW_W + col];
            dut3.cells[row*ROW_W + col] = ~dut3.cells[row*ROW_W + col];
            a = row * IL + (col % IL);
            m_err[a][col / IL] = ~m_err[a][col / IL];
        end
    endtask

    // Random upset between edges, never a third error in one codeword.
    task inject;
        integer row, col, kind, a0, a1;
        begin
            kind = urand(10);
            row  = urand(DEPTH);
            if (kind < 5) begin                      // single bit, clean codeword
                col = urand(ROW_W);
                a0  = row * IL + (col % IL);
                if (pop72(m_err[a0]) == 0) begin flip(row, col); n_inj1 = n_inj1 + 1; end
            end else if (kind < 8) begin             // adjacent pair, both codewords clean
                col = urand(ROW_W - 1);
                a0  = row * IL + (col % IL);
                a1  = row * IL + ((col + 1) % IL);
                if (pop72(m_err[a0]) == 0 && pop72(m_err[a1]) == 0) begin
                    flip(row, col); flip(row, col + 1); n_inj_adj = n_inj_adj + 1;
                end
            end else begin                           // second error in a codeword -> UE
                col = urand(ROW_W);
                a0  = row * IL + (col % IL);
                if (pop72(m_err[a0]) == 1 && !m_err[a0][col / IL]) begin
                    flip(row, col); n_inj_dbl = n_inj_dbl + 1;
                end
            end
        end
    endtask

    // Drive random inputs for the next cycle.
    task drive_random(input integer mode);
        integer x;
        begin
            x = urand(100);
            wr_en     = (mode == 1) ? 1'b0 : (x < 25);
            rd_en     = (mode == 1) ? 1'b0 : (urand(100) < 35);
            scrub_en  = (mode == 2) ? 1'b0 : (urand(100) < 90);
            log_clear = (urand(1000) < 5);
            wr_addr   = urand(NW);
            rd_addr   = (urand(4) == 0) ? wr_addr : urand(NW);
            wr_data   = (urand(8) == 0) ? {64{x[0]}} : rand64(0);
        end
    endtask

    // One clock cycle: model, edge, checks, then maybe an upset.
    task step(input integer inj_pct);
        begin
            if (rst_n) begin
                if (rd_en) begin
                    n_rd = n_rd + 1;
                    if (pop72(m_err[rd_addr]) == 1) n_rd_ce = n_rd_ce + 1;
                    if (pop72(m_err[rd_addr]) == 2) n_rd_ue = n_rd_ue + 1;
                    if (wr_en && wr_addr == rd_addr) n_coll = n_coll + 1;
                end
                if (wr_en) n_wr = n_wr + 1;
                if (log_clear) n_clear = n_clear + 1;
            end
            model_edge;
            @(posedge clk);
            #1;
            check_outputs;
            cyc = cyc + 1;
            if (rst_n && urand(100) < inj_pct) inject;
        end
    endtask

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("cycles=%d", cycles)) cycles = 40000;
        seed0 = seed;
        errors = 0; cyc = 0;
        n_rd = 0; n_rd_ce = 0; n_rd_ue = 0; n_wr = 0; n_coll = 0; n_inj1 = 0; n_inj_adj = 0;
        n_inj_dbl = 0; n_scrub_fix = 0; n_clear = 0; n_sat = 0;

        // Reference Hsiao columns from the construction rule.
        k = 0;
        for (i = 0; i < 8; i = i + 1)
            for (w = i + 1; w < 8; w = w + 1)
                for (t = w + 1; t < 8; t = t + 1) begin
                    ref_col[k] = (8'd1 << i) | (8'd1 << w) | (8'd1 << t);
                    k = k + 1;
                end
        for (i = 0; i < 8; i = i + 1) begin
            ref_col[k] = (8'h1F << i) | (8'h1F >> (8 - i));
            k = k + 1;
        end

        @(negedge clk);
        rst_n = 1'b0;
        step(0); step(0);
        rst_n = 1'b1;

        // Directed: write every word, read every word back (no scrub).
        for (i = 0; i < NW; i = i + 1) begin
            wr_en = 1; rd_en = 0; scrub_en = 0; log_clear = 0;
            wr_addr = i; wr_data = rand64(0);
            step(0);
        end
        for (i = 0; i < NW; i = i + 1) begin
            wr_en = 0; rd_en = 1; rd_addr = i;
            step(0);
        end

        // Directed scrub bound: one single-bit error in every codeword, then
        // DEPTH idle cycles must repair all of them.
        rd_en = 0; wr_en = 0; scrub_en = 1;
        for (i = 0; i < NW; i = i + 1)
            flip(i / IL, urand(72) * IL + (i % IL));
        n_inj1 = n_inj1 + NW;
        for (i = 0; i < DEPTH; i = i + 1) step(0);
        for (i = 0; i < NW; i = i + 1)
            if (m_err[i] !== 72'd0) err_msg("scrub bound: error left after DEPTH idle cycles");

        // Random phase: mostly mixed traffic, with idle and no-scrub stretches.
        for (t = 0; t < cycles; t = t + 1) begin
            drive_random((t % 2000 < 1700) ? 0 : (t % 2000 < 1850) ? 1 : 2);
            if (t == cycles / 2) rst_n = 1'b0;        // one mid-run reset
            else rst_n = 1'b1;
            step(8);
        end

        // Drain: idle with scrub, then no single-bit error may remain.
        wr_en = 0; rd_en = 0; scrub_en = 1; log_clear = 0; rst_n = 1;
        for (i = 0; i < DEPTH; i = i + 1) step(0);
        for (i = 0; i < NW; i = i + 1)
            if (pop72(m_err[i]) == 1) err_msg("drain: single-bit error not scrubbed");

        // Coverage: every interesting case must have happened.
        if (n_rd_ce == 0 || n_rd_ue == 0 || n_coll == 0 || n_inj_adj == 0 || n_inj_dbl == 0 ||
            n_scrub_fix == 0 || n_clear == 0 || n_sat == 0)
            err_msg("coverage hole");

        $display("tb_orbit_ecc_bank summary");
        $display("  seed / cycles                %0d / %0d", seed0, cyc);
        $display("  writes / reads               %0d / %0d", n_wr, n_rd);
        $display("  reads with CE / UE           %0d / %0d", n_rd_ce, n_rd_ue);
        $display("  same-cycle read+write        %0d", n_coll);
        $display("  upsets: single / adjacent 2-bit / second-in-codeword  %0d / %0d / %0d",
                 n_inj1, n_inj_adj, n_inj_dbl);
        $display("  scrubber repairs             %0d", n_scrub_fix);
        $display("  log_clear pulses             %0d", n_clear);
        $display("  cycles with CNT_W=3 counter saturated  %0d", n_sat);
        $display("  errors                       %0d", errors);
        if (errors == 0) $display("TB_ORBIT_ECC_BANK PASS");
        else             $display("TB_ORBIT_ECC_BANK FAIL");
        $finish;
    end

endmodule

`default_nettype wire
