// Self-checking testbench for the (72,64) Hsiao SECDED codec
// (rtl/ecc/orbit_secded72.v: orbit_secded72_enc, orbit_secded72_dec).
//
// Reference: the testbench builds its own H matrix from the published Hsiao
// construction (56 weight-3 columns in lexicographic order, then 0x1F rotated
// by 0..7) and never reads the RTL table. Checks:
//   1. Encoder == reference encoder (all 64 unit vectors, random data) and
//      the code properties of the encoder's columns (odd weight, distinct,
//      no unit column, 26 ones per data row).
//   2. No error: data back unchanged, ce = ue = 0, syndrome 0.
//   3. Every single-bit error (all 72 positions) for SEC_WORDS data words:
//      data and check bits corrected, ce = 1, ue = 0, syndrome = H column.
//   4. Every double-bit error (all 2556 position pairs) for DED_WORDS words:
//      ue = 1, ce = 0, nothing flipped (outputs == received word).
//   5. Random triple errors: never silent (ce | ue); the number that are
//      miscorrected (ce = 1, wrong data) is reported, not required to be 0.
// Plusargs: +seed=<n>. Prints TB_ORBIT_SECDED72 PASS/FAIL.

`default_nettype none

module tb_orbit_secded72;

    parameter integer SEC_WORDS    = 300;
    parameter integer DED_WORDS    = 12;
    parameter integer RANDOM_WORDS = 20000;
    parameter integer TRIPLES      = 20000;

    // DUT
    reg  [63:0] enc_data;
    wire [7:0]  enc_check;
    reg  [63:0] dec_data;
    reg  [7:0]  dec_check;
    wire [63:0] dec_data_out;
    wire [7:0]  dec_check_out;
    wire        dec_ce, dec_ue;
    wire [7:0]  dec_syndrome;

    orbit_secded72_enc dut_enc (.data(enc_data), .check(enc_check));
    orbit_secded72_dec dut_dec (
        .data_in(dec_data), .check_in(dec_check), .data_out(dec_data_out),
        .check_out(dec_check_out), .ce(dec_ce), .ue(dec_ue), .syndrome(dec_syndrome)
    );

    // Reference H columns: ref_col[i] for data bit i; check bit j is 1 << j.
    reg [7:0] ref_col [0:63];

    integer seed, seed0, errors, i, j, n, a, b, c, t;
    integer n_sec, n_ded, n_clean, n_tri, n_tri_ue, n_tri_mis, n_tri_ok;
    reg [63:0] d, d_exp;
    reg [7:0]  chk, syn_exp;
    reg [71:0] cw, e, rx;
    reg [7:0]  row_w [0:7];

    function [7:0] ref_check(input [63:0] x);
        integer q;
        begin
            ref_check = 8'd0;
            for (q = 0; q < 64; q = q + 1)
                if (x[q]) ref_check = ref_check ^ ref_col[q];
        end
    endfunction

    function [7:0] colof(input integer pos);   // H column of codeword bit pos
        begin
            colof = (pos < 64) ? ref_col[pos] : (8'd1 << (pos - 64));
        end
    endfunction

    function integer pop8(input [7:0] x);
        integer q;
        begin
            pop8 = 0;
            for (q = 0; q < 8; q = q + 1) pop8 = pop8 + x[q];
        end
    endfunction

    function [63:0] rand64(input integer dummy);
        begin
            rand64 = {$random(seed), $random(seed)};
        end
    endfunction

    task fail(input [8*48-1:0] what);
        begin
            errors = errors + 1;
            if (errors <= 20)
                $display("ERROR %0s: data=%h e=%h out=%h/%h ce=%b ue=%b syn=%h", what, d, e,
                         dec_data_out, dec_check_out, dec_ce, dec_ue, dec_syndrome);
        end
    endtask

    // Encode d with the DUT, apply error pattern e, decode with the DUT.
    task apply(input [63:0] data, input [71:0] err);
        begin
            enc_data = data;
            #1;
            cw  = {enc_check, data};
            rx  = cw ^ err;
            dec_data  = rx[63:0];
            dec_check = rx[71:64];
            #1;
        end
    endtask

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        seed0  = seed;
        errors = 0;

        // Reference matrix from the construction rule.
        n = 0;
        for (a = 0; a < 8; a = a + 1)
            for (b = a + 1; b < 8; b = b + 1)
                for (c = b + 1; c < 8; c = c + 1) begin
                    ref_col[n] = (8'd1 << a) | (8'd1 << b) | (8'd1 << c);
                    n = n + 1;
                end
        for (a = 0; a < 8; a = a + 1) begin
            ref_col[n] = (8'h1F << a) | (8'h1F >> (8 - a));
            n = n + 1;
        end

        // 1. Encoder against the reference, and code properties.
        for (i = 0; i < 8; i = i + 1) row_w[i] = 0;
        for (i = 0; i < 64; i = i + 1) begin
            enc_data = 64'd1 << i;
            #1;
            if (enc_check !== ref_col[i]) begin
                errors = errors + 1;
                $display("ERROR column %0d: rtl %b ref %b", i, enc_check, ref_col[i]);
            end
            if (pop8(enc_check) % 2 != 1 || pop8(enc_check) < 3) begin
                errors = errors + 1;
                $display("ERROR column %0d has weight %0d", i, pop8(enc_check));
            end
            for (j = 0; j < 8; j = j + 1) row_w[j] = row_w[j] + enc_check[j];
        end
        for (i = 0; i < 64; i = i + 1)
            for (j = i + 1; j < 64; j = j + 1)
                if (ref_col[i] == ref_col[j]) begin
                    errors = errors + 1;
                    $display("ERROR columns %0d and %0d are equal", i, j);
                end
        for (j = 0; j < 8; j = j + 1)
            if (row_w[j] != 26) begin
                errors = errors + 1;
                $display("ERROR row %0d has %0d data ones (expected 26)", j, row_w[j]);
            end
        for (t = 0; t < RANDOM_WORDS; t = t + 1) begin
            d = rand64(0);
            enc_data = d;
            #1;
            if (enc_check !== ref_check(d)) begin
                errors = errors + 1;
                if (errors <= 20) $display("ERROR encoder: data %h rtl %h ref %h", d, enc_check, ref_check(d));
            end
        end
        $display("encoder: 64 unit vectors + %0d random words vs reference, row weights %0d %0d %0d %0d %0d %0d %0d %0d",
                 RANDOM_WORDS, row_w[0], row_w[1], row_w[2], row_w[3], row_w[4], row_w[5], row_w[6], row_w[7]);

        // 2. No error.
        n_clean = 0;
        for (t = 0; t < RANDOM_WORDS + 3; t = t + 1) begin
            d = (t == 0) ? 64'd0 : (t == 1) ? ~64'd0 : (t == 2) ? 64'haaaa_5555_aaaa_5555 : rand64(0);
            e = 72'd0;
            apply(d, e);
            if (dec_data_out !== d || dec_check_out !== cw[71:64] || dec_ce !== 1'b0 ||
                dec_ue !== 1'b0 || dec_syndrome !== 8'd0)
                fail("no-error decode");
            n_clean = n_clean + 1;
        end

        // 3. Every single-bit error.
        n_sec = 0;
        for (t = 0; t < SEC_WORDS; t = t + 1) begin
            d = (t == 0) ? 64'd0 : (t == 1) ? ~64'd0 : rand64(0);
            for (i = 0; i < 72; i = i + 1) begin
                e = 72'd1 << i;
                apply(d, e);
                if (dec_data_out !== d || dec_check_out !== cw[71:64] || dec_ce !== 1'b1 ||
                    dec_ue !== 1'b0 || dec_syndrome !== colof(i))
                    fail("single-error correction");
                n_sec = n_sec + 1;
            end
        end

        // 4. Every double-bit error.
        n_ded = 0;
        for (t = 0; t < DED_WORDS; t = t + 1) begin
            d = (t == 0) ? 64'd0 : (t == 1) ? ~64'd0 : rand64(0);
            for (i = 0; i < 72; i = i + 1)
                for (j = i + 1; j < 72; j = j + 1) begin
                    e = (72'd1 << i) | (72'd1 << j);
                    apply(d, e);
                    syn_exp = colof(i) ^ colof(j);
                    if (dec_ue !== 1'b1 || dec_ce !== 1'b0 || dec_data_out !== rx[63:0] ||
                        dec_check_out !== rx[71:64] || dec_syndrome !== syn_exp)
                        fail("double-error detection");
                    n_ded = n_ded + 1;
                end
        end

        // 5. Random triple errors (characterisation).
        n_tri = 0; n_tri_ue = 0; n_tri_mis = 0; n_tri_ok = 0;
        for (t = 0; t < TRIPLES; t = t + 1) begin
            d = rand64(0);
            a = {$random(seed)} % 72;
            b = {$random(seed)} % 72;
            c = {$random(seed)} % 72;
            if (a != b && b != c && a != c) begin
                e = (72'd1 << a) | (72'd1 << b) | (72'd1 << c);
                apply(d, e);
                n_tri = n_tri + 1;
                if (!(dec_ce | dec_ue)) fail("silent triple error");
                if (dec_ue) n_tri_ue = n_tri_ue + 1;
                if (dec_ce && dec_data_out !== d) n_tri_mis = n_tri_mis + 1;
                if (dec_ce && dec_data_out === d) n_tri_ok = n_tri_ok + 1;
            end
        end

        $display("tb_orbit_secded72 summary");
        $display("  seed                         %0d", seed0);
        $display("  no-error words               %0d", n_clean);
        $display("  single-bit errors corrected  %0d (%0d words x 72 positions)", n_sec, SEC_WORDS);
        $display("  double-bit errors detected   %0d (%0d words x 2556 pairs)", n_ded, DED_WORDS);
        $display("  triple-bit errors            %0d: %0d flagged UE, %0d miscorrected (CE, wrong data), %0d CE with right data",
                 n_tri, n_tri_ue, n_tri_mis, n_tri_ok);
        $display("  errors                       %0d", errors);
        if (errors == 0) $display("TB_ORBIT_SECDED72 PASS");
        else             $display("TB_ORBIT_SECDED72 FAIL");
        $finish;
    end

endmodule

`default_nettype wire
