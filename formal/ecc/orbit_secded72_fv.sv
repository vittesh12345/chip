// Formal harness for the (72,64) Hsiao SECDED codec (rtl/ecc/orbit_secded72.v).
//
// All inputs are free: the data word and two error positions. The codec is
// combinational, so a one-step proof (sby mode prove) covers every input
// value; there is no state to induct over, and the result is unbounded.
//
// Properties (one decoder instance each):
//   S0  no error:      data and check bits returned unchanged, ce = ue = 0,
//                      syndrome 0
//   S1  single error at any position p in 0..71: data and check bits
//                      corrected, ce = 1, ue = 0, syndrome != 0
//   S2  double error at any positions p != q: ue = 1, ce = 0, and the
//                      outputs equal the received word (nothing is flipped,
//                      so no miscorrection)
//   ENC the encoder is linear: check(d1 ^ d2) = check(d1) ^ check(d2)
//                      (sanity property relating the two encoder instances)

`default_nettype none

module orbit_secded72_fv (
    input wire [63:0] data,
    input wire [63:0] data2,
    input wire [6:0]  pos_p,
    input wire [6:0]  pos_q
);

    // Error positions: codeword bits 0..71, distinct for the double error.
    always @* begin
        assume (pos_p < 7'd72);
        assume (pos_q < 7'd72);
        assume (pos_p != pos_q);
    end

    wire [7:0]  check, check2, check12;
    orbit_secded72_enc u_enc   (.data(data),         .check(check));
    orbit_secded72_enc u_enc2  (.data(data2),        .check(check2));
    orbit_secded72_enc u_enc12 (.data(data ^ data2), .check(check12));

    wire [71:0] cw  = {check, data};
    wire [71:0] e1  = 72'd1 << pos_p;
    wire [71:0] e2  = (72'd1 << pos_p) | (72'd1 << pos_q);
    wire [71:0] rx1 = cw ^ e1;
    wire [71:0] rx2 = cw ^ e2;

    // S0: no error
    wire [63:0] d0;  wire [7:0] c0, s0;  wire ce0, ue0;
    orbit_secded72_dec u_dec0 (.data_in(cw[63:0]), .check_in(cw[71:64]), .data_out(d0),
                               .check_out(c0), .ce(ce0), .ue(ue0), .syndrome(s0));

    // S1: single error
    wire [63:0] d1;  wire [7:0] c1, s1;  wire ce1, ue1;
    orbit_secded72_dec u_dec1 (.data_in(rx1[63:0]), .check_in(rx1[71:64]), .data_out(d1),
                               .check_out(c1), .ce(ce1), .ue(ue1), .syndrome(s1));

    // S2: double error
    wire [63:0] d2;  wire [7:0] c2, s2;  wire ce2, ue2;
    orbit_secded72_dec u_dec2 (.data_in(rx2[63:0]), .check_in(rx2[71:64]), .data_out(d2),
                               .check_out(c2), .ce(ce2), .ue(ue2), .syndrome(s2));

    always @* begin
        s0_data:     assert (d0 == data && c0 == check);
        s0_flags:    assert (!ce0 && !ue0 && s0 == 8'd0);

        s1_data:     assert (d1 == data && c1 == check);
        s1_flags:    assert (ce1 && !ue1 && s1 != 8'd0);

        s2_flags:    assert (ue2 && !ce2 && s2 != 8'd0);
        s2_no_flip:  assert (d2 == rx2[63:0] && c2 == rx2[71:64]);

        enc_linear:  assert (check12 == (check ^ check2));
    end

endmodule

`default_nettype wire
