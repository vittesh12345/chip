// ORBIT-AI demonstrator: one signed INT8 multiply / INT32 accumulate lane.
//
// Storage is duplicated (accumulator A/B, result A/B) and compared every
// cycle. The multiplier is shared by both copies, so a fault in the shared
// product (or in anything upstream of it) corrupts both copies identically and
// is NOT detected. Accumulation wraps modulo 2^32; there is no saturation and
// no overflow alarm.

`default_nettype none

module orbit_mac_lane (
    input  wire        clk,
    input  wire        rst_n,     // synchronous, active low
    input  wire        clr,       // resynchronise: both copies of everything to 0
    input  wire        mac_en,    // an input beat was accepted this cycle
    input  wire        first,     // with mac_en: start a new sum (acc = a*b)
    input  wire        last,      // with mac_en: copy the updated sum to the result registers
    input  wire [7:0]  a,         // signed INT8
    input  wire [7:0]  b,         // signed INT8
    output wire [31:0] result,    // primary result copy (A)
    output wire        mismatch   // accumulator or result copies disagree
);

    // Shared signed 8x8 -> 16 bit product, sign-extended to 32 bits.
    wire signed [15:0] prod   = $signed(a) * $signed(b);
    wire        [31:0] prod32 = {{16{prod[15]}}, prod};

    wire [31:0] acc_a, acc_b;
    wire [31:0] res_a, res_b;

    // Each copy updates from its own stored value, so the two adders are
    // separate even though they share the product.
    wire [31:0] acc_a_sum = (first ? 32'd0 : acc_a) + prod32;
    wire [31:0] acc_b_sum = (first ? 32'd0 : acc_b) + prod32;

    wire acc_en = clr | mac_en;
    wire res_en = clr | (mac_en & last);

    orbit_keep_reg #(.W(32)) u_acc_a (
        .clk(clk), .rst_n(rst_n), .en(acc_en),
        .d(clr ? 32'd0 : acc_a_sum), .q(acc_a)
    );

    orbit_keep_reg #(.W(32)) u_acc_b (
        .clk(clk), .rst_n(rst_n), .en(acc_en),
        .d(clr ? 32'd0 : acc_b_sum), .q(acc_b)
    );

    orbit_keep_reg #(.W(32)) u_res_a (
        .clk(clk), .rst_n(rst_n), .en(res_en),
        .d(clr ? 32'd0 : acc_a_sum), .q(res_a)
    );

    orbit_keep_reg #(.W(32)) u_res_b (
        .clk(clk), .rst_n(rst_n), .en(res_en),
        .d(clr ? 32'd0 : acc_b_sum), .q(res_b)
    );

    assign mismatch = (acc_a != acc_b) | (res_a != res_b);
    assign result   = res_a;

endmodule

`default_nettype wire
